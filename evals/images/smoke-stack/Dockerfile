# lightcone-smoke-stack: the ASTRA / Lightcone stack under test, on top of
# lightcone-eval-base (the agent CLIs). Every evals/smoke task image builds
# FROM this, adding only its project files.
#
# Built by evals/bin/build-images.sh (docker-bake.hcl), which fills the build
# args from skills.config.json's pins, or from git refs for the "latest" leg
# and for lightcone-cli PRs:
#   ASTRA_TOOLS    pip requirement for the astra-tools installed as `astra`
#   ASTRA_PIN      the plugin's astra-tools pin, the version the skills and
#                  hooks run through `uvx astra-tools@<pin>`
#   LIGHTCONE_CLI  pip requirement for lightcone-cli (`lc`)
FROM lightcone-eval-base

ARG ASTRA_TOOLS
ARG ASTRA_PIN
ARG LIGHTCONE_CLI
LABEL org.lightcone.smoke.astra-tools="${ASTRA_TOOLS}" \
      org.lightcone.smoke.astra-pin="${ASTRA_PIN}" \
      org.lightcone.smoke.lightcone-cli="${LIGHTCONE_CLI}"

ENV DEBIAN_FRONTEND=noninteractive \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib \
    PYTHONDONTWRITEBYTECODE=1

# uv must be >= 0.12: lc 0.5 scaffolds `[tool.uv] required-version = ">=0.12"`.
# ASTRA_TOOLS overrides lightcone-cli's own astra-tools requirement, so a leg
# can pair lc with an astra-tools it does not declare (evals/bin/stack-info.sh
# reports that skew); when the two agree the override changes nothing.
RUN : "${ASTRA_TOOLS:?}" "${ASTRA_PIN:?}" "${LIGHTCONE_CLI:?}" \
    && python -m pip install --no-cache-dir uv==0.12.22 \
    && printf '%s\n' "$ASTRA_TOOLS" > /tmp/astra-override.txt \
    && uv pip install --system --no-cache --override /tmp/astra-override.txt \
        "$ASTRA_TOOLS" \
        "$LIGHTCONE_CLI" \
        numpy==2.2.6 \
        pytest==8.4.1 \
        pyyaml==6.0.2 \
    && rm /tmp/astra-override.txt

# The skills and the session-start hook call `uvx astra-tools@<pin>`. One
# shared, writable uv cache, warmed at build time, so that works for the
# unprivileged agent user without a download.
ENV UV_CACHE_DIR=/opt/uv-cache
RUN uvx "astra-tools@${ASTRA_PIN}" --help >/dev/null \
    && chmod -R a+rwX /opt/uv-cache

# lc reads ~/.lightcone/config.yaml: seed it for root (oracle, verifier) and,
# through /etc/skel, for the agent user the harness creates at run time.
RUN mkdir -p /etc/skel/.lightcone \
    && printf '%s\n' \
        'container:' \
        '  runtime: none' \
        'slurm:' \
        '  account: null' \
        '  time_padding: 1.5' \
        > /etc/skel/.lightcone/config.yaml \
    && cp -a /etc/skel/.lightcone /root/.lightcone

# Never bake skills or plugins into the image: they are a run-time axis.

RUN chmod 711 /root
