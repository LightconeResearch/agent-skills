# Plugin smoke suite

Does a cheap model, given the `lightcone` plugin, still get through the core
paths? Five [Harbor](https://harborframework.com) tasks of a few minutes each,
each with a deterministic verifier that calls the real `astra` / `lc` and
scores all-or-nothing. Prompts name the CLI and never teach it; the plugin is
a run-time axis, never baked into an image.

Hook mechanics are covered deterministically elsewhere: `npm test`
(`scripts/test-hooks.mjs`, about a second) and the `e2e-hooks` workflow fail
when a hook says the wrong thing or doesn't fire. This suite asks the question
those can't: whether an agent reading the skills gets through the work.

| task | the agent must | decided by |
|---|---|---|
| `astra-author` | write `astra.yaml` for a stated two-step pipeline | `astra validate`; astra's resolver sees the declared graph |
| `astra-add-decision` | add decision `fit_model`, wire it into a recipe, add universe `quadratic` | `astra validate`, `astra universe check` |
| `astra-query` | answer five questions about a spec with conditional decisions and constraints | expected values derived with astra's resolver |
| `lc-materialize` | materialize `baseline/summary` of a ready Lightcone project | `lc status --json`, `lc materialize --check --json`, the run manifest |
| `lc-wire-recipe` | give a declared output its recipe, then materialize it | the same, plus `astra validate` |

## Layout

```
evals/
  images/eval-base/     agent CLIs (Node, Claude Code, Codex), pinned in its Dockerfile
  images/smoke-stack/   astra-tools + lightcone-cli under test, FROM eval-base
  images/docker-bake.hcl
  smoke/<task>/         Harbor tasks; each environment/Dockerfile is FROM lightcone-smoke-stack + its project
  bin/                  stack.sh, build-images.sh, stack-info.sh, smoke.sh, plugin_agent.py, judge.sh, report.py
  rubrics/              the pain-point judge's rubric and prompt
  tests/                the gate logic (uv run --with pytest pytest evals/tests)
```

The stack under test defaults to the plugin's pins in `skills.config.json`, so
a pin bump tests the new pins with no other edit. `ASTRA_REF` / `LIGHTCONE_REF`
(any branch, tag or sha) install from git instead; `evals/bin/stack.sh`
resolves them.

## Run locally

Needs Docker with a docker-driver buildx builder (`docker buildx use
desktop-linux` on Docker Desktop) and `uv tool install harbor==0.22.0`.

```bash
evals/bin/build-images.sh                      # or LIGHTCONE_REF=main evals/bin/build-images.sh
evals/bin/stack-info.sh                        # versions in the stack; exits 1 on astra-tools skew or override
K=1 evals/bin/smoke.sh oracle                  # reference solutions: every reward must be 1.0
K=1 evals/bin/smoke.sh claude-code:claude-sonnet-5-5:plugin   # what every PR runs
evals/bin/report.py select evals/jobs --all | evals/bin/judge.sh   # judge every trial
evals/bin/report.py render evals/jobs --judge evals/jobs/judge --out evals/jobs/report
open evals/jobs/report/report.html             # comment.md beside it is the PR comment
```

A leg is `<agent>:<model>:<config>`: `plugin` loads the whole plugin through
`claude --plugin-dir` (skills and hooks; claude-code only), `skill` the
plugin's skills through Harbor's `--skill` (no hooks), `bare` neither.
Credentials come from the environment: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`.
On a laptop, a Claude subscription token (`CLAUDE_CODE_OAUTH_TOKEN`, from
`claude setup-token`) or `CODEX_FORCE_AUTH_JSON=1` (your `~/.codex/auth.json`)
also work for small runs; CI uses API keys only, and `smoke.sh` refuses an
OAuth token on CI. Results land in `evals/jobs/<leg>/` (gitignored); a
finished leg is skipped on re-run, so delete its dir to redo it. Never edit a
task while a run is going: Harbor builds from the live tree.

## In CI

`.github/workflows/smoke.yml` runs on PRs that touch the plugins or `evals/`,
on pushes to main (which record the baseline), nightly against astra-tools and
lightcone-cli `main` (the latest leg), by hand, and as a reusable workflow
that lightcone-cli PRs call with their head sha.

1. **oracle** builds the images (GitHub Actions cache), checks astra-tools
   skew, and runs the reference solutions. No secrets, so it runs on fork PRs.
2. **legs**: one per PR, Claude Code with `claude-sonnet-5-5` and the whole
   plugin, K=1, all five tasks (`DEFAULT_LEGS`). The ablation legs (haiku
   `plugin` and `skill`, codex luna `skill`; `ALL_LEGS`) run on
   `workflow_dispatch` with `legs: all` or leg names. A missing API key fails
   its leg.
3. **report** judges every trial of the default leg (`harbor analyze`,
   `rubrics/pain-points.toml`, `claude-sonnet-5-5`; failures and outliers only
   on bigger dispatch runs), compares each (leg, task) cell with the baseline,
   and keeps one comment on the PR up to date. The comment leads with the
   verdict in words; each failed task gets the verifier's own output for its
   failing checks, the judge's account of what got in the agent's way, and the
   agent's last message; passes take a line each.
4. **smoke-publish.yml** (after the run) puts the full report on GitHub Pages
   at `https://lightconeresearch.github.io/agent-skills/smoke/<run id>/`: one
   card per task with the prompt, every verifier check, the judge's summary, a
   turn-by-turn timeline with hook messages inline, the deliverable diffed
   against the reference, and the task's history on main. Trial artifacts are
   redacted of API keys before any of this is uploaded or published.

Measured locally on 2026-10-03 for the default leg: Sonnet 5.5 passed all five
tasks in 3–6 turns; the agent cost $0.38 and the judge $0.32, so about $0.70
per PR, in about two minutes of agent time.

The baseline pools the last five pushes to main, published by
`.github/workflows/smoke-publish.yml` as `baseline.json` on the orphan branch
`smoke-baseline` and read without a token from raw.githubusercontent.com (so
lightcone-cli runs see the same one): each run's `summary.json`
carries the per-cell pass counts and turn samples of the previous pool plus
its own, oldest dropped. The check blocks when the oracle fails, when a cell
that passes at least 80% on main goes 0/K, or when a leg passes improbably few
trials against its cells' pooled rates (Poisson-binomial lower tail below
0.01, each cell's rate smoothed to (s + 1) / (t + 2)). Any other failure in a cell that is solid on
main is a warning, listed first; failures in cells already weak on main are
known. With no baseline yet, any 0/K cell blocks. A leg whose passing trials
mostly take more turns (or astra/lc calls) than their cells' pooled medians
(one-sided sign test p < 0.05, and at least 25% more in total) gets an effort
warning, never a block. Trials that died on the provider or harness (quota,
rate limit, auth, setup timeout) are not agent results: the leg shows as not
measured, and that blocks. Runs on main record and
gate only on the oracle.
