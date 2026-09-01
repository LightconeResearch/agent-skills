# Publishing

Read this when the user wants to share, archive, deposit, or cite the
analysis.

The project itself is the publishable object — there is no export step, and
no bundle directory. Declaring a license turns on the publication view:

1. Add an SPDX `license` (e.g. `license = "CC-BY-4.0"`) under `[project]`
   in `pyproject.toml`, and set authorship in the spec per the astra skill.
2. Commit, then run `lc materialize` — nothing is remade; it converges
   `ro-crate-metadata.json` (a Workflow/Provenance Run RO-Crate rendered
   from repository state) and commits it. `lc status`'s `crate:` line says
   whether the view is current.
3. Gate: the astra skill's validation passes, `lc materialize --check`
   passes, and `ro-crate-metadata.json` exists.
