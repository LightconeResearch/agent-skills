# lc-wire-recipe: the stack under test (lightcone-smoke-stack, evals/bin/build-images.sh)
# plus this task's project.
FROM lightcone-smoke-stack

COPY project /root/toy-moments
WORKDIR /root/toy-moments
# One-time project setup: lc init (git + git-annex + .venv from the lock), a
# repo-local git identity so the agent's lc materialize can commit, and the
# starting commit. safe.directory lets root (verifier) read the agent-owned
# repo; a+rwX lets the unprivileged agent user write it whatever its uid.
RUN lc init . >/dev/null \
    && git config user.name "Smoke Agent" \
    && git config user.email "smoke-agent@example.invalid" \
    && git config --system --add safe.directory '*' \
    && git add -A && git commit -qm "Toy moments project; summary not yet wired" \
    && chmod -R a+rwX /root/toy-moments
