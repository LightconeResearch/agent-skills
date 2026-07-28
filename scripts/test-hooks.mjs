#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(fileURLToPath(import.meta.url), "..", "..");
const HOOK = join(ROOT, "hooks/astra/scripts/validate-on-save.sh");
const scratch = mkdtempSync(join(tmpdir(), "astra-hook-"));
const project = join(scratch, "project");
const bin = join(scratch, "bin");

mkdirSync(project);
mkdirSync(bin);
writeFileSync(join(project, "astra.yaml"), "id: test\n");
writeFileSync(join(bin, "astra"), "#!/bin/sh\nprintf 'fake validation: %s\\n' \"$*\"\nexit 1\n", { mode: 0o755 });

const patch = `*** Begin Patch
*** Update File: ${join(project, "astra.yaml")}
*** End Patch`;

function run(toolInput) {
  return spawnSync("bash", [HOOK], {
    cwd: project,
    encoding: "utf8",
    env: { ...process.env, PATH: `${bin}:${process.env.PATH}` },
    input: JSON.stringify({
      cwd: project,
      tool_name: "apply_patch",
      tool_input: toolInput,
      tool_response: {},
    }),
  });
}

function assertValidated(label, toolInput) {
  const result = run(toolInput);
  if (result.status !== 0 || !result.stdout.includes(`ASTRA validation FAILED for ${join(project, "astra.yaml")}`)) {
    throw new Error(`${label}: hook did not validate the patched ASTRA file\n${result.stdout}${result.stderr}`);
  }
}

try {
  assertValidated("Codex command payload", { command: patch });
  assertValidated("legacy patch payload", { patch });
  assertValidated("legacy raw payload", patch);

  const unrelated = run({ command: "*** Begin Patch\n*** Update File: README.md\n*** End Patch" });
  if (unrelated.status !== 0 || unrelated.stdout !== "") {
    throw new Error(`unrelated patch: expected silent success\n${unrelated.stdout}${unrelated.stderr}`);
  }

  console.log("✓ ASTRA save hook parses current and legacy apply_patch payloads.");
} finally {
  rmSync(scratch, { recursive: true, force: true });
}
