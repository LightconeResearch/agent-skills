# Sharing: publishing, cloning, pulling

Read this when the user wants to put the project online, share it with
collaborators, work from a clone, or take in someone else's work.

The project itself is the publishable object — its commits on GitHub, and
the bytes of its data and results in a **store** of their own, since GitHub
holds git and not what git-annex keeps. There is no export step and no
bundle. One verb converges it: `lc publish`.

- [The two choices that are never yours](#the-two-choices-that-are-never-yours)
- [Publishing for the first time](#publishing-for-the-first-time)
- [Publishing again](#publishing-again)
- [Working from a clone](#working-from-a-clone)
- [What never to do](#what-never-to-do)

## The two choices that are never yours

`lc publish` asks them once, at the first publication, and every clone
learns the answers:

| Choice | Options |
|---|---|
| Who can read the project | `--private` (people the owner invites; can go public later) or `--public` (anyone, **permanently** — copies made while public remain, and there is no way back; needs an SPDX `license` under `[project]` in `pyproject.toml`) |
| Where its data lives (`--data`) | `github-lfs` (the repository's own Git LFS: no other account, but 2 GB per file, 10 GiB free then billed to the owner, and nothing in it can be deleted), a directory on the group's cluster (`/DIRECTORY`, reached by filesystem, or `ssh://HOST/DIRECTORY`; never readable by the public) |

Ask, lay out these options as above, and **recommend none** — and never
make anything public unasked. `lc status` and `lc init` end by suggesting
`lc publish`: that is a hint for the user, not a task for you. Where no one
can be asked (headless, CI), leave the project offline.

## Publishing for the first time

1. **Commit first.** `lc init` leaves its scaffold uncommitted, and
   `lc publish` refuses a project with no commit. Review `git status`, then
   `git add` the project files by path and `git commit`.
2. **A GitHub token**, for `lc` to create the repository: `GH_TOKEN` or
   `GITHUB_TOKEN` in the environment, or `gh auth login` — the user's to
   set up. Without one, the user creates the repository, empty, themselves.
3. **Check, then publish**, with the user's two answers:

   ```bash
   lc publish github.com/OWNER/NAME --private --data github-lfs --check
   lc publish github.com/OWNER/NAME --private --data github-lfs
   ```

   It sends, in order, the bytes of what the commit names to the store,
   git-annex's log of where they are, and the current branch — so no commit
   reaches a clone before the bytes it names can be fetched. Where some
   bytes could not be sent, nothing else is, and it exits 1: run it again to
   send the rest.

A commit with `stale` or `missing` results publishes as it is, and says so;
materialize first when the user wants what they share to be current.

## Publishing again

`lc publish`, with no URL, whenever there is something new: it publishes to
the project's one repository and store, and with nothing to send says so.
`lc publish --check --json` reports what is not yet published — `unsent`
bytes, `unpushed` commits, `uncommitted` changes — and exits 1 if anything
is not. Uncommitted changes are never published, no tag or other branch is
sent, nothing is deleted, and nothing is merged: where GitHub has commits
this clone lacks, `git pull` first.

## Working from a clone

```bash
git clone <url> && cd <name> && lc init   # environment, git-annex, the project's store
lc status                                 # ok results marked `unfetched` are on a remote
lc fetch                                  # every current result's bytes; or name ids
```

- `lc fetch [targets]` brings the bytes of current (`ok` or `behind`)
  results — `fit`, `fit#robust` — or of an input, by its id. No cluster,
  nothing made or committed. A `stale` or `missing` result is not fetched:
  `lc materialize` makes it again. `lc materialize` fetches by itself
  whatever its recipes read.
- Take others' work in with plain `git pull`, then `lc fetch` what you want
  to read.
- **A clone that did not choose the store** confirms it once before it can
  publish: `lc publish --confirm-data WHERE`, after `lc` has shown where the
  data goes. Reading needs no confirmation. Confirming is the user's call,
  like the two choices above — show them where it points and ask.

## What never to do

- **`git push`.** It sends the commits without their bytes, and every clone
  then sees those results as `missing`. Nothing breaks — the next
  `lc publish` from a clone that holds the bytes sends them — but `git push`
  is not how a project is shared.
- **Any git-annex command** (`git annex get`, `push`, `sync`, `copy`,
  `enableremote`, `verifyremote`). `lc fetch` and `lc publish` own every
  data movement; `git annex sync` merges and `push` can drop.
- **Confirming a store, choosing visibility, or choosing where data lives**
  on your own.
