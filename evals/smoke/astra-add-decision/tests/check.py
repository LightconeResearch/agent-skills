"""One verifier dimension per argv[1], answered by astra's own helpers; exit 1 on any miss."""
import sys

from astra.helpers import get_decisions, load_yaml
from astra.resolve import resolve_outputs, resolve_universe

ROOT = "/root/line-fit"
failures = []


def expect(cond, msg):
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


try:
    spec = load_yaml(f"{ROOT}/astra.yaml")
except Exception as exc:
    print(f"FAIL could not load astra.yaml: {exc!r}")
    sys.exit(1)

if sys.argv[1] == "decision_declared":
    decision = get_decisions(spec).get("fit_model") or {}
    options = {k for k, v in (decision.get("options") or {}).items() if not (v or {}).get("excluded")}
    expect(bool(decision), "decision fit_model is declared")
    expect(options == {"linear", "quadratic"}, f"fit_model options are linear, quadratic (got {sorted(options)})")
    expect(decision.get("default") == "linear", f"fit_model default is linear (got {decision.get('default')!r})")

elif sys.argv[1] == "universe_resolves":
    try:
        universe = load_yaml(f"{ROOT}/universes/quadratic.yaml")
    except Exception as exc:
        print(f"FAIL could not load universes/quadratic.yaml: {exc!r}")
        sys.exit(1)
    expect(universe.get("id") == "quadratic", f"universe id is quadratic (got {universe.get('id')!r})")
    settled = resolve_universe(spec, universe)
    print("resolved universe:", settled)
    expect(settled.get("fit_model") == "quadratic", "universe quadratic settles fit_model=quadratic")
    fit = {o.id: o for o in resolve_outputs(spec, universe)}.get("fit_result")
    expect(fit is not None, "fit_result is produced in universe quadratic")
    if fit is not None:
        print("fit_result command:", fit.command)
        expect(fit.decisions.get("fit_model") == "quadratic", f"fit_result is parameterized by fit_model=quadratic (got {fit.decisions})")
        expect("{decisions.fit_model}" in (fit.command or ""), "fit_result recipe passes {decisions.fit_model} to the script")

sys.exit(1 if failures else 0)
