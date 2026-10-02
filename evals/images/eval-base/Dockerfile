# lightcone-eval-base: the agent CLIs, under lightcone-smoke-stack and so under
# every evals/smoke task image. Harbor's claude-code and codex agents would
# otherwise install them inside each trial container (apt-get, nvm, npm, a
# bootstrap download) during agent setup; both skip that step when `claude` /
# `codex` is already on PATH, so a trial on this image does no network
# installs at setup. The three versions below are the pins; bump them here.
ARG NODE_VERSION=22.23.3
FROM node:${NODE_VERSION}-trixie-slim AS node

FROM python:3.13-slim

ARG CLAUDE_CODE_VERSION=2.1.287
ARG CODEX_VERSION=0.160.0

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        procps \
        ripgrep \
        time \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# Installed globally as root into /usr/local, so the unprivileged agent user the
# harness creates finds them on its default PATH. The version checks fail the
# build, not a trial, if an npm optional platform package went missing.
ENV DISABLE_AUTOUPDATER=1
RUN npm install -g \
        "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
        "@openai/codex@${CODEX_VERSION}" \
    && npm cache clean --force \
    && claude --version | grep -F "${CLAUDE_CODE_VERSION}" \
    && codex --version | grep -F "${CODEX_VERSION}" \
    && rm -rf /root/.npm /root/.codex
