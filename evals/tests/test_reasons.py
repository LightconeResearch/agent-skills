"""The reason catalogue in evals/bin/report.py: one test per class, headlines built from data."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
import report  # noqa: E402

R = report.reason


def test_skew_names_both_versions_and_the_pin_line():
    r = R("skew", pin="0.2.17", required="==0.2.18", lightcone_cli="0.5.0rc5")
    assert r["headline"] == "The plugin pins an astra-tools that its own lightcone-cli rejects"
    assert "pins astra-tools 0.2.17, but lightcone-cli 0.5.0rc5 requires astra-tools ==0.2.18" in r["consequence"]
    assert r["fix"].startswith('Set `"astra-tools": "0.2.18"` in `skills.config.json` (line ')
    assert r["annotation"]["file"] == "skills.config.json" and r["annotation"]["line"] == report.pin_line("astra-tools")


def test_override_on_the_latest_leg():
    r = R("override", lightcone_cli="0.5.1.dev3", required="==0.2.18", installed="0.2.19.dev7")
    assert r["headline"] == ("lightcone-cli 0.5.1.dev3 requires astra-tools ==0.2.18, "
                             "but this run tests astra-tools 0.2.19.dev7")
    assert "0.2.19.dev7" in r["fix"]


def test_infra_quota_names_the_secret():
    r = R("infra", label="Luna (GPT-6) + skill", kinds=["ApiUsageLimitError"], infra=10, total=10, key="OPENAI_API_KEY")
    assert r["headline"] == "Luna (GPT-6) + skill was not measured: 10/10 trials hit ApiUsageLimitError (provider quota)"
    assert "OPENAI_API_KEY" in r["fix"] and "not the agent" in r["consequence"]


def test_key_missing():
    r = R("key_missing", leg="claude-sonnet-plugin", label="Sonnet 5.5 + plugin", key="ANTHROPIC_API_KEY")
    assert r["headline"] == "The agent did not run: ANTHROPIC_API_KEY is not set"
    assert r["fix"].startswith("Add the ANTHROPIC_API_KEY repository secret")


def test_oracle_red_names_task_checks_stack_and_first_error():
    r = R("oracle_red", task="astra-author", checks=["spec_valid", "declares_pipeline"], astra="0.2.18",
          lc="0.5.0rc5", error="outputs.1.recipe.run: Extra inputs are not permitted",
          solution="evals/smoke/astra-author/solution/astra.yaml")
    assert r["headline"] == ("The reference solution for astra-author fails `spec_valid` and `declares_pipeline` "
                             "on astra-tools 0.2.18 / lightcone-cli 0.5.0rc5")
    assert "outputs.1.recipe.run" in r["consequence"] and not r["fix"]
    assert r["annotation"]["file"] == "evals/smoke/astra-author/solution/astra.yaml"


def test_coverage_gap():
    r = R("coverage_gap", label="Haiku 4.5 + skill", reason="4/6 trials missing: 4 never ran")
    assert r["headline"] == "Haiku 4.5 + skill is partly measured: 4/6 trials missing: 4 never ran"


def test_agent_check_with_a_contradicting_hook():
    r = R("agent_check", task="astra-author", checks=["spec_valid", "declares_pipeline"],
          error="version: Input should be a valid string", verdict="blocking", k=0, n=1,
          base={"k": 5, "n": 5}, contradiction="validate-on-save hook reported pass on a file the verifier rejects")
    assert r["headline"] == ("astra-author: `spec_valid` and `declares_pipeline` failed — the validate-on-save "
                             "hook reported pass on a file the verifier rejects")
    assert r["consequence"] == "It passes on main (5/5); it failed every attempt here." and r["blocking"]


def test_agent_check_quotes_the_first_error_without_a_contradiction():
    r = R("agent_check", task="lc-materialize", checks=["output_value"], error="missing results/baseline/summary.txt",
          verdict="warning", k=1, n=2, base={"k": 9, "n": 10})
    assert r["headline"] == "lc-materialize: `output_value` failed (“missing results/baseline/summary.txt”)"
    assert not r["blocking"]


def test_leg_test_upstream_job_and_effort():
    r = R("leg_test", label="Sonnet 5.5 + plugin", x=1, n=5, base_k=25, base_n=25, tail=0.0004)
    assert r["headline"] == "Sonnet 5.5 + plugin passed 1/5 trials, against 25/25 on main"
    assert R("upstream_job", job="oracle", result="failure")["headline"] == "The oracle job ended in failure"
    e = R("effort", label="Haiku 4.5 + skill", metric="turns", ratio=1.45, cells_up=5, cells=5, above=9, n=9, p=0.002)
    assert e["headline"] == "Haiku 4.5 + skill took +45% turns against main across 5/5 tasks" and not e["blocking"]


def test_every_class_in_the_order_has_a_template():
    for cls in report.ORDER:
        if cls in ("warning", "known"):
            continue
        assert cls in open(report.__file__).read(), cls
