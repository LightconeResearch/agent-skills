---
name: feedback
description: >
  File feedback on the Lightcone Research stack as a GitHub issue in the
  LightconeResearch/feedback repository, with evidence gathered and sanitized
  from the session.
  Use when the user asks to report a bug, file or open an issue, send
  feedback, or suggest a feature for a tool in the Lightcone Research stack.
  Not for bugs in the user's own analysis code, and never file anything
  without the user's approval.
---

# Lightcone feedback

Gather everything a maintainer needs to understand, analyze and act on the
issue without a follow-up. Build it from what this session already shows, and
ask the user only about gaps that would block a maintainer from diagnosing and
fixing the problem.

When the skill is first invoked, make sure the user has the GitHub CLI (`gh`)
installed and signed in (`gh auth status`). If not, walk them through setting
it up: install it from <https://cli.github.com/>, then run `gh auth login`.
Then follow the steps below.

## 1. Gather the evidence

Capture the goal, what was done, what was expected, what happened, and the
impact. Keep observations apart from suspected causes; never present steps you
haven't run as a tested reproduction. Then add what the report type needs:

- **Command or API failure**: the command and the relevant error, plus the
  smallest config, script or input that reproduces it, or a note on what
  private dependency prevents that.
- **UI**: page or panel, actions, what appeared; a screenshot or console error
  only if it adds something.
- **Agent skill or plugin**: what was invoked, the tool or hook error, agent
  and plugin versions.
- **Docs**: page URL, the wrong or unclear instruction, what should happen.
- **Feature request**: use case, friction, desired outcome, workaround. No
  versions or reproduction.

Capture the logs a maintainer needs. Don't install anything, change the
project, or rerun computationally expensive work to collect evidence. If you
need to, ask the user for clarification, then file a best-effort report.
Balance completeness against asking the user for too much.

**Never include credentials, tokens, signed URLs, personal path prefixes or
unpublished research. Keep paths relative and keep the shape of errors. Never
dump full transcripts, environments or datasets. If the report is useless
without private material, don't proceed. Never report a security
vulnerability in a public issue.**

## 2. Check for duplicates

Every report goes to [LightconeResearch/feedback](https://github.com/LightconeResearch/feedback).
Search its open and closed issues
(`gh issue list --repo LightconeResearch/feedback --state all --search '<symptom>'`)
and read the plausible matches. If one looks like the same problem, show it to
the user and ask whether it covers what they're reporting, and whether to file
a new issue anyway, add a comment to the existing one, or do nothing. If they
choose nothing, stop there. A comment goes through the same draft and approval
as an issue.

## 3. Draft and get approval

Start the body by naming the product the user was using (`lc`, Lightcone Lab,
ASTRA, MySTRA, the docs, the agent skills), so maintainers can triage, and give
any suspected cause as evidence. Then: summary and impact, steps and result,
environment; drop empty sections. Long sanitized logs go in a collapsed
`<details>` block.

Show the user the title and the complete body, collapsed parts included. File
only after the user approves that exact content; material changes need approval
again. For a draft-only request, stop here.

## 4. File it once

Before filing or retrying, search the repository for an issue this session
already created. If you can't tell whether an earlier attempt landed, stop and
show the user what you found.

Prefer a structured GitHub tool. With `gh`, write the approved body verbatim to
a temp file with your file tool, never through shell code, and quote the title
as one argument:

```bash
gh issue create --repo LightconeResearch/feedback --title '<title>' --body-file <tmp>
```

Comments work the same way
(`gh issue comment <n> --repo LightconeResearch/feedback --body-file <tmp>`). On
failure, show the draft; on success, give the issue URL and delete the temp
file.
