---
name: notebooklx-workflow
description: Use when working in the NotebookLX repository to load the canonical workflow and planning docs without duplicating them. This skill tells Codex which repository files are authoritative for implementation order, acceptance criteria, testing, and local commands.
---

# NotebookLX Workflow

Use this skill for any feature work, bug fix, test update, or repo planning task in this repository.

## Primary References

Read these files instead of restating their contents:

- `AGENTS.md`: concise Codex-facing repo guide and current commands.
- `CLAUDE.md`: working rules, product principles, target architecture, TDD workflow, testing standards, and commit/PR expectations.
- `DEVELOPMENT_PLAN.md`: feature roadmap, tasks, and acceptance criteria. Treat it as the delivery blueprint.
- `TASK_CHECKLIST.md`: progress tracking after a feature is completed or materially advanced.

## Context Budget Rule

Do not implement an entire roadmap feature in one pass unless it is already small.

Each development loop must target one bounded feature slice:

- one coherent behavior or vertical slice
- usually 1-3 closely related acceptance criteria
- a small, named test surface
- a limited file set that can be read, edited, and re-verified without context sprawl

If the candidate slice still feels large, crosses multiple subsystems, or would require loading large parts of the repo or plan, split it again before writing code.

Only read:

- the relevant section of `DEVELOPMENT_PLAN.md`
- the tests and source files needed for the current slice
- the minimum supporting files needed to make the change safely

Do not preload the whole roadmap or unrelated modules.

## Required Slice Contract

Before implementation, define the current slice in a compact form:

- `Feature`: the roadmap feature id/title
- `Slice`: the smallest shippable sub-scope for this loop
- `Acceptance Criteria`: only the criteria covered in this loop
- `Verification`: the exact test command(s) that prove the slice is done

If you cannot describe the slice that narrowly, it is too large.

## Delivery Loop

Follow this loop for every slice without skipping steps:

1. Read `AGENTS.md`, then the relevant rule sections in `CLAUDE.md`.
2. Read only the relevant `DEVELOPMENT_PLAN.md` feature section.
3. Pick the next unfinished feature item from `DEVELOPMENT_PLAN.md` and `TASK_CHECKLIST.md`.
4. Shrink it into the smallest workable slice that fits the context budget.
5. Write or update tests for the selected acceptance criteria first, or at minimum before closing the slice.
6. Implement the minimum code required for those tests to pass.
7. Run the slice verification loop:
   - run the focused test command(s)
   - if any acceptance-criteria test fails, fix the code and rerun
   - repeat until the selected acceptance criteria are green
   - then run any immediate regression tests needed for touched code
8. Only mark the slice `finished` when every selected acceptance criterion passes.

Hard rule:

- Acceptance criteria passed -> check finished
- Acceptance criteria failed -> keep fixing and rerunning until passed, then check finished

Do not mark work complete while any selected acceptance criterion is still red or unverified.

## Progress Updates After Green

When the slice is green:

1. Update the relevant checkboxes in `DEVELOPMENT_PLAN.md` for the acceptance criteria or tasks that are now truly complete.
2. Update `TASK_CHECKLIST.md` so the mirrored progress is visible there too.
3. Do not update either file optimistically. Checkboxes move only after verification passes.

## Changelog Export

After a slice reaches green and checklist updates are done, append a structured entry to the dedicated workflow log:

- `.git/logs/notebooklx-workflow.log`

Use:

- `./scripts/export_feature_changelog.sh`

The log entry should capture at least:

- timestamp
- feature id/title
- slice name
- status
- acceptance criteria covered
- verification command(s)
- touched files
- next recommended slice

Important:

- use a dedicated file under `.git/logs/`
- do not modify git-managed reflog files such as `.git/logs/HEAD` or `.git/logs/refs/*`

## Compact And Continue

After changelog export:

1. compact the session before starting the next slice
2. then begin the next unfinished feature slice with fresh, minimal context

If the client exposes a `compact` command, use it. If it does not, create a minimal handoff summary that includes only:

- completed slice
- proof of acceptance criteria passing
- checklist updates made
- changelog path
- next slice to start

Do not carry unnecessary context from the previous slice into the next one.

## Definition Of Done For A Slice

A slice is done only when all of the following are true:

- selected acceptance criteria are passing
- relevant `DEVELOPMENT_PLAN.md` items are checked
- `TASK_CHECKLIST.md` is checked too
- `.git/logs/notebooklx-workflow.log` has a changelog entry
- the session has been compacted or reduced to a minimal handoff before starting the next slice

## Current Repo Reality

The plan describes a larger future structure, but the current checked-in code is centered in:

- `services/api/` for the FastAPI backend
- `apps/web/` for the Next.js frontend

Do not assume other planned paths like `services/worker/` exist unless they are present in the tree.

## Local Commands

Use the real commands from the current repo state:

- `cd apps/web && pnpm install`
- `cd apps/web && pnpm run dev`
- `cd apps/web && pnpm run build`
- `cd apps/web && pnpm start`
- `cd apps/web && pnpm run lint`
- `cd apps/web && pnpm test`
- `cd services/api && pip install -r requirements.txt`
- `cd services/api && alembic upgrade head`
- `uvicorn services.api.main:app --reload`
- `PYTHONPATH=$(pwd) pytest services/api/tests -v`

Frontend note:

- create `apps/web/.env.local` with `NEXT_PUBLIC_API_URL=http://localhost:8000` before running the Next.js app against the local backend

Prefer targeted test commands for the active slice before broader regression runs.

## Non-Goals

- Do not mirror `.claude/settings.local.json` into Codex files.
- Do not duplicate large sections of `CLAUDE.md` or `DEVELOPMENT_PLAN.md` into new docs when a reference is enough.
- Do not start the next feature before the current slice is verified, checked, logged, and compacted.
