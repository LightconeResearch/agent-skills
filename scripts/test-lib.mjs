// Shared scaffolding for the hermetic hook tests (test-hooks.mjs,
// test-opencode.mjs, test-pi.mjs): a scratch tree with an ASTRA project, a
// non-project directory, and a fake `uvx` on PATH that logs every invocation
// and answers the way the real `--json` modes do — ONE JSON-encoded string
// (with embedded quotes and a backslash, to prove the scripts' splice needs no
// re-escaping), exit code from FAKE_UVX_RC (default 1 = validation failed).
// FAKE_UVX_GARBAGE simulates a toolchain that never got to astra (uvx
// resolution failure, crash): non-JSON noise on stdout. A fake `astra` that
// always SUCCEEDS also sits on PATH: if any script ever regresses to running a
// PATH astra instead of uvx, the expected FAILED message flips to passed.

import { existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = join(fileURLToPath(import.meta.url), "..", "..");

export const fail = (msg) => { throw new Error(msg); };
export const assertIncludes = (label, haystack, needle) => {
  if (!haystack.includes(needle)) fail(`${label}: missing ${JSON.stringify(needle)}\n${haystack}`);
};

/** Build the scratch tree. Returns its paths, `uvxCalls()` (the fake's
 *  invocation log, one argv string per call) and `cleanup()`. */
export function makeScratch(prefix) {
  const scratch = mkdtempSync(join(tmpdir(), prefix));
  const project = join(scratch, "project");
  const elsewhere = join(scratch, "elsewhere");
  const bin = join(scratch, "bin");
  const uvxLog = join(scratch, "uvx-invocations.log");

  mkdirSync(project, { recursive: true });
  mkdirSync(elsewhere, { recursive: true });
  mkdirSync(bin);
  writeFileSync(join(project, "astra.yaml"), "id: test\n");
  writeFileSync(
    join(bin, "uvx"),
    `#!/bin/sh
echo "$*" >> "${uvxLog}"
if [ -n "\${FAKE_UVX_GARBAGE}" ]; then
  echo "error: no interpreter found"
  exit 2
fi
printf '%s\\n' "\\"fake report: $* | with \\\\\\"quotes\\\\\\" and a \\\\\\\\backslash\\""
exit "\${FAKE_UVX_RC:-1}"
`,
    { mode: 0o755 },
  );
  writeFileSync(join(bin, "astra"), "#!/bin/sh\nexit 0\n", { mode: 0o755 });

  return {
    scratch,
    project,
    elsewhere,
    bin,
    uvxCalls: () => (existsSync(uvxLog) ? readFileSync(uvxLog, "utf8").trim().split("\n").filter(Boolean) : []),
    cleanup: () => rmSync(scratch, { recursive: true, force: true }),
  };
}

/** Put the fake tools first on PATH for this process (what the harness
 *  adapters spawn with), with none of the variables the lightcone hook reads
 *  to pick its ask/act mode, and no real `lc`. */
export function hermeticEnv(bin) {
  process.env.PATH = `${bin}:/usr/bin:/bin`;
  delete process.env.CLAUDE_CODE_ENTRYPOINT;
  delete process.env.CI;
}
