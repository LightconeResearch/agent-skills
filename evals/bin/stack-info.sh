#!/usr/bin/env bash
# What the built lightcone-smoke-stack holds, as one JSON object on stdout, and
# the version-skew check: "skew" in the JSON names it, and the script exits 1
# with a one-line message, if the astra-tools
# lightcone-cli requires differs from the plugin's astra-tools pin. With that
# split, a plugin user runs one astra through the skill's uvx and another
# under lc.
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
}
if required and not SpecifierSet(required).contains(pin, prereleases=True):
    info["skew"] = (f"lightcone-cli {info['lightcone_cli']} requires astra-tools {required}, "
                    f"the plugin pins astra-tools {pin}")
print(json.dumps(info))
if info["skew"]:
    sys.exit(f"version skew: {info['skew']}")
PY
