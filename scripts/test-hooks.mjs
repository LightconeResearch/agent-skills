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

mkdirSync(join(project, "universes"), { recursive: true });
mkdirSync(bin);
writeFileSync(join(project, "astra.yaml"), "id: test\n");
writeFileSync(join(project, "README.md"), "not an ASTRA file\n");
writeFileSync(join(project, "universes", "fiducial.yaml"), "id: fiducial\n");
// The hook must resolve astra as a pinned `uvx` run and never use an `astra`
// from PATH: the fake uvx fails (driving the deterministic FAILED path with no
// network), while the fake astra succeeds — so any regression to PATH
// resolution flips the message to "passed" and breaks the assertions.
writeFileSync(join(bin, "uvx"), "#!/bin/sh\nprintf 'fake validation: %s\\n' \"$*\"\nexit 1\n", { mode: 0o755 });
writeFileSync(join(bin, "astra"), "#!/bin/sh\nexit 0\n", { mode: 0o755 });

const spec = join(project, "astra.yaml");
const patchFor = (...lines) => `*** Begin Patch\n${lines.join("\n")}\n*** End Patch`;

function run(toolName, toolInput) {
  return spawnSync("bash", [HOOK], {
    cwd: project,
    encoding: "utf8",
    env: { ...process.env, PATH: `${bin}:${process.env.PATH}` },
    input: JSON.stringify({
      cwd: project,
      tool_name: toolName,
      tool_input: toolInput,
      tool_response: {},
    }),
  });
}

function assertValidated(label, toolName, toolInput, expected) {
  const result = run(toolName, toolInput);
  if (result.status !== 0 || !result.stdout.includes(`ASTRA validation FAILED for ${expected}`)) {
    throw new Error(`${label}: hook did not validate ${expected}\n${result.stdout}${result.stderr}`);
  }
  return result;
}

function assertSilent(label, toolName, toolInput) {
  const result = run(toolName, toolInput);
  if (result.status !== 0 || result.stdout !== "") {
    throw new Error(`${label}: expected silent success\n${result.stdout}${result.stderr}`);
  }
}

try {
  // Claude Code sends a file path; Codex sends patch text.
  assertValidated("Write payload", "Write", { file_path: spec }, spec);
  assertValidated("apply_patch payload", "apply_patch", { command: patchFor(`*** Update File: ${spec}`) }, spec);
  assertValidated("relative patch path", "apply_patch", { command: patchFor("*** Update File: astra.yaml") }, spec);

  // Universe files validate too.
  const universe = join(project, "universes", "fiducial.yaml");
  assertValidated("universe file", "Write", { file_path: universe }, universe);

  // A Move header names both the old and the new path. Only the new one exists,
  // so the hook must report the destination and not the vanished source.
  const moved = assertValidated(
    "move header",
    "apply_patch",
    { command: patchFor("*** Update File: gone.yaml", `*** Move to: ${spec}`) },
    spec,
  );
  if (moved.stdout.includes("gone.yaml")) {
    throw new Error(`move header: hook validated the pre-rename source\n${moved.stdout}`);
  }

  assertSilent("unrelated file", "apply_patch", { command: patchFor("*** Update File: README.md") });
  assertSilent("missing file", "Write", { file_path: join(project, "nowhere", "astra.yaml") });

  console.log("✓ ASTRA save hook validates Write/Edit and apply_patch payloads.");
} finally {
  rmSync(scratch, { recursive: true, force: true });
}
