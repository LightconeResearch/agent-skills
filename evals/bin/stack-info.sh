#!/usr/bin/env bash
# What the built lightcone-smoke-stack holds, as one JSON object on stdout, and
# two checks against the astra-tools requirement lightcone-cli declares:
#   skew      the plugin's astra-tools pin does not satisfy it;
#   override  the installed astra-tools does not (the latest leg installs
#             astra-tools main over lc's pin on purpose; this makes that loud).
# Each one found is named in the JSON and on stderr, and the script exits 1.
# Either way a plugin user would run one astra through the skill's uvx and
# another under lc.
#
#   evals/bin/stack-info.sh > stack.json
set -euo pipefail

pin="$(docker image inspect lightcone-smoke-stack \
  --format '{{ index .Config.Labels "org.lightcone.smoke.astra-pin" }}')"
docker run --rm -i -e ASTRA_PIN="$pin" lightcone-smoke-stack python - <<'PY'
import json, os, re, sys
from importlib import metadata as md

from pip._vendor.packaging.specifiers import SpecifierSet

pin = os.environ["ASTRA_PIN"]
reqs = [r for r in md.requires("lightcone-cli") or [] if re.match(r"astra-tools\b", r)]
required = re.sub(r"^astra-tools\s*", "", reqs[0]).split(";")[0].strip() if reqs else ""
info = {
    "astra_tools": md.version("astra-tools"),
    "lightcone_cli": md.version("lightcone-cli"),
    "lightcone_cli_requires_astra_tools": required,
    "plugin_astra_tools_pin": pin,
    "skew": None,
    "override": None,
}
spec = SpecifierSet(required) if required else None
if spec is not None and not spec.contains(pin, prereleases=True):
    info["skew"] = (f"lightcone-cli {info['lightcone_cli']} requires astra-tools {required}, "
                    f"the plugin pins astra-tools {pin}")
if spec is not None and not spec.contains(info["astra_tools"], prereleases=True):
    info["override"] = (f"lightcone-cli {info['lightcone_cli']} requires astra-tools {required}, "
                        f"testing astra-tools {info['astra_tools']}")
print(json.dumps(info))
for key, label in (("skew", "version skew"), ("override", "override")):
    if info[key]:
        print(f"{label}: {info[key]}", file=sys.stderr)
if info["skew"] or info["override"]:
    sys.exit(1)
PY
