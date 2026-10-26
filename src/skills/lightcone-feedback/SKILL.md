---
name: lightcone-feedback
description: >
  File feedback on the Lightcone Research stack (a bug report, a feature
  request, a docs problem) as a GitHub issue in the right Lightcone repository:
  lc / lightcone-cli, Lightcone Lab, the ASTRA spec and tools, MySTRA, the
  docs, or these agent skills. Gathers and sanitizes evidence from the session,
  routes the report, checks for duplicates, and files only after the user
  approves the exact draft. Use when the user asks to report a bug, file or
  open an issue, send feedback, or suggest a feature for a Lightcone tool:
  "report this", "file a bug", "open an issue on lc", "tell the Lightcone
  team", "send this as feedback". Not for bugs in the user's own analysis
  code, and never file without being asked.
---

# Lightcone feedback

Write an issue a maintainer can act on without a follow-up question. Build it
from what this session already shows, ask only about gaps that would block a
maintainer, and file nothing the user hasn't approved word for word.

## 1. Gather the evidence

Capture the goal, what was done, what was expected, what happened, and the
impact. Keep observations apart from suspected causes; never present steps you
haven't run as a tested reproduction. Then add what the report type needs:

- **Command or API failure**: the command and the relevant error, plus the
  smallest config, script or input that reproduces it, or a note on what
  private dependency prevents that.
- **UI**: page or panel, actions, what appeared; a screenshot or console error
  only if it adds something.
- **Agent skill or plugin**: what was invoked, the tool or hook error, agent
  and plugin versions.
- **Docs**: page URL, the wrong or unclear instruction, what should happen.
- **Feature request**: use case, friction, desired outcome, workaround. No
  versions or reproduction.

Take versions from where the problem happened (local, remote/HPC, Jupyter); a
laptop says nothing about a cluster, and a lockfile is intent, not what ran.
Use logs, installed metadata and read-only commands like `lc --version`. Don't
install anything, change the project, or rerun expensive work for evidence.

What fell out of the session or was compacted away is unknown. Ask at most one
grouped question, only when a maintainer couldn't act without the answer;
otherwise note the gap and file a best-effort report.

**Sanitize** text and images: credentials, tokens, signed URLs, personal path
prefixes (`/home/<user>/…` → `~/…`), unpublished research. Keep relative paths
and the shape of errors. No full transcripts, environment dumps or datasets. If
the report is useless without private material, stop at a sanitized draft. A
security vulnerability never goes in a public issue: point the user to the
repository's private vulnerability reporting or `SECURITY.md`.

## 2. Route it and check for duplicates

Pick the repository from [the repository map](references/repositories.md) by
the product the user was using, not the suspected cause (put that in the body).
A destination the user names wins. Don't make the user work out ownership.

```bash
gh auth status   # never print the token
gh repo view LightconeResearch/<repo> --json nameWithOwner,visibility,hasIssuesEnabled
gh issue list --repo LightconeResearch/<repo> --state all --search '<distinctive symptom>'
```

Read plausible matches. For a duplicate, link it instead of filing, and offer
a comment only if you have new evidence (same approval as an issue). If the
search failed, the preview says "duplicates not checked". Without GitHub
access or an available destination, hand over the draft and
`https://github.com/LightconeResearch/<repo>/issues/new`; never quietly switch
repositories.

## 3. Draft and get approval

Body: summary and impact, steps and result, environment; drop empty sections.
Long sanitized logs go in a collapsed `<details>` block. End with
`<sub>Filed with the Lightcone feedback skill.</sub>` so maintainers can find
reports that couldn't be labeled.

Show the destination with its visibility and a one-line reason, the title, and
the complete body, collapsed parts included. File only after the user approves
that exact content; material changes need approval again. For a draft-only
request, stop here.

## 4. File it once

Before filing or retrying, search the destination for an issue this session
already created. If you can't tell whether an earlier attempt landed, stop and
show the user what you found.

Prefer a structured GitHub tool. With `gh`, write the approved body verbatim to
a temp file with your file tool, never through shell code, and quote the title
as one argument:

```bash
gh issue create --repo LightconeResearch/<repo> --title '<title>' --body-file <tmp>
gh issue edit <n> --repo LightconeResearch/<repo> --add-label feedback
gh issue view <n> --repo LightconeResearch/<repo> --json url,labels
```

Comments work the same way (`gh issue comment <n> --body-file <tmp>`). Label
only after the issue exists, never create the label, and never let labeling
block or repeat the filing. Most reporters can't label; if `feedback` is
missing, say a maintainer will add it. On failure, show the draft; on success,
give the verified URL and delete the temp file.
