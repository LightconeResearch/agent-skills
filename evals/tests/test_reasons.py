"""The reason catalogue in evals/bin/report.py: one test per class.

Headlines are terse data (no explanatory prose); only the mechanical causes
(skew, override, missing key) carry a fix.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
import report  # noqa: E402

R = report.reason


def test_skew_names_both_versions_and_the_pin_line():
    r = R("skew", pin="0.2.17", required="==0.2.18", lightcone_cli="0.5.0rc5")
    assert r["headline"] == "version skew · lightcone-cli 0.5.0rc5 requires astra-tools ==0.2.18 · plugin pins 0.2.17"
    line = report.pin_line("astra-tools")
    assert r["fix"] == (f'`"astra-tools": "0.2.18"` in `skills.config.json`:{line}, '
                        "or a lightcone-cli that accepts 0.2.17; then `npm run build`")
    assert r["annotation"]["file"] == "skills.config.json" and r["annotation"]["line"] == line


def test_override_on_the_latest_leg():
    r = R("override", lightcone_cli="0.5.1.dev3", required="==0.2.18", installed="0.2.19.dev7")
    assert r["headline"] == ("override · lightcone-cli 0.5.1.dev3 requires astra-tools ==0.2.18 "
                             "· testing astra-tools 0.2.19.dev7")
    assert "0.2.19.dev7" in r["fix"]


def test_key_missing():
    r = R("key_missing", leg="claude-sonnet-plugin", label="Sonnet 5.5 + plugin", key="ANTHROPIC_API_KEY")
    assert r["headline"] == "not run · Sonnet 5.5 + plugin · ANTHROPIC_API_KEY not set"
    assert r["fix"].startswith("add the ANTHROPIC_API_KEY repository secret")


def test_infra_has_no_fix():
    r = R("infra", label="Luna (GPT-6) + skill", kinds=["ApiUsageLimitError"], infra=10, total=10, key="OPENAI_API_KEY")
    assert r["headline"] == "not measured · Luna (GPT-6) + skill · 10/10 ApiUsageLimitError"
    assert not r["fix"]


def test_oracle_red_names_task_checks_and_first_error():
    r = R("oracle_red", task="astra-author", checks=["spec_valid", "declares_pipeline"], astra="0.2.18",
          lc="0.5.0rc5", error="outputs.1.recipe.run: Extra inputs are not permitted",
          solution="evals/smoke/astra-author/solution/astra.yaml")
    assert r["headline"] == ("reference solution · astra-author · spec_valid ✗ declares_pipeline ✗ "
                             "· “outputs.1.recipe.run: Extra inputs are not permitted”")
    assert not r["fix"] and r["annotation"]["file"] == "evals/smoke/astra-author/solution/astra.yaml"


def test_no_oracle_and_coverage_gap():
    assert R("no_oracle", tasks=["astra-query"])["headline"] == "no reference run · astra-query"
    r = R("coverage_gap", label="Haiku 4.5 + skill", reason="4/6 trials missing: 4 never ran")
    assert r["headline"] == "partly measured · Haiku 4.5 + skill · 4/6 trials missing: 4 never ran"


def test_agent_check_is_data_only():
    r = R("agent_check", task="astra-author", checks=["spec_valid", "declares_pipeline"],
          error="analysis: Extra inputs are not permitted", verdict="blocking", k=0, n=1,
          base={"k": 5, "n": 5}, contradiction="validate-on-save hook said pass · contradicted")
    assert r["headline"] == ("astra-author · spec_valid ✗ declares_pipeline ✗ · “analysis: Extra inputs are not "
                             "permitted” · validate-on-save hook said pass · contradicted · 0/1 (main 5/5)")
    assert r["blocking"] and not r["fix"]


def test_agent_check_warning_without_baseline_text():
    r = R("agent_check", task="lc-materialize", checks=["output_value"], error="missing results/baseline/summary.txt",
          verdict="warning", k=1, n=2, base=None)
    assert r["headline"] == "lc-materialize · output_value ✗ · “missing results/baseline/summary.txt” · 1/2"
    assert not r["blocking"]


def test_leg_test_upstream_job_effort_and_baseline_error():
    r = R("leg_test", label="Sonnet 5.5 + plugin", x=1, n=5, base_k=25, base_n=25, tail=0.0004)
    assert r["headline"] == "leg test · Sonnet 5.5 + plugin · 1/5 vs 25/25 on main · P = 4.0e-04"
    assert R("upstream_job", job="oracle", result="failure")["headline"] == "oracle job · failure"
    e = R("effort", label="Haiku 4.5 + skill", metric="turns", ratio=1.45, cells_up=5, cells=5, above=9, n=9, p=0.002)
    assert e["headline"] == "effort · Haiku 4.5 + skill · +45% turns · 5/5 tasks above main · p = 0.002"
    assert not e["blocking"] and not e["fix"]
    assert not R("baseline_error")["blocking"]


def test_only_mechanical_causes_carry_a_fix():
    with_fix = {"skew", "override", "key_missing"}
    samples = {
        "skew": dict(pin="0.2.17", required="==0.2.18", lightcone_cli="0.5.0rc5"),
        "override": dict(lightcone_cli="x", required="==1", installed="2"),
        "key_missing": dict(leg="l", label="L", key="K"),
        "infra": dict(label="L", kinds=["ApiRateLimitError"], infra=1, total=2),
        "oracle_red": dict(task="t", checks=["c"], astra="a", lc="l"),
        "no_oracle": dict(tasks=["t"]),
        "coverage_gap": dict(label="L", reason="r"),
        "agent_check": dict(task="t", checks=["c"], verdict="new", k=0, n=1),
        "leg_test": dict(label="L", x=0, n=1, base_k=1, base_n=1, tail=0.1),
        "upstream_job": dict(job="j", result="failure"),
        "effort": dict(label="L", metric="turns", ratio=2.0, cells_up=1, cells=1, above=1, n=1, p=0.5),
        "baseline_error": {},
    }
    assert set(samples) == set(report.ORDER)
    for cls, data in samples.items():
        r = R(cls, **data)
        assert r["headline"], cls
        assert bool(r["fix"]) == (cls in with_fix), cls
        assert "consequence" not in r
