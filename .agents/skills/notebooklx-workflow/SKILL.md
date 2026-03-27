---
name: notebooklx-workflow
description: Use when working in the NotebookLX repository to load the canonical workflow and planning docs without duplicating them. This skill tells Codex which repository files are authoritative for implementation order, acceptance criteria, testing, and local commands.
---

# NotebookLX Workflow

Use this skill for any feature work, bug fix, test update, or repo planning task in this repository.

## Primary References

Read these files instead of restating their contents:

- `CLAUDE.md`: working rules, product principles, target architecture, TDD workflow, testing standards, and commit/PR expectations.
- `DEVELOPMENT_PLAN.md`: feature roadmap, tasks, and acceptance criteria. Treat it as the delivery blueprint.
- `TASK_CHECKLIST.md`: progress tracking after a feature is completed or materially advanced.
- `AGENTS.md`: concise Codex-facing repo guide and current commands.

## Workflow

1. Read `AGENTS.md` for the current repo shape and executable commands.
2. Read `CLAUDE.md` before making implementation choices that depend on workflow or quality rules.
3. Read only the relevant section of `DEVELOPMENT_PLAN.md` for the feature being changed.
4. Write or update tests from the acceptance criteria before or alongside implementation.
5. After finishing a feature slice, update `TASK_CHECKLIST.md` if the status changed.

## Current Repo Reality

The plan describes a larger future structure, but the current checked-in code is mostly under `services/api/`. Do not assume planned paths like `apps/web/` or `services/worker/` exist unless they are present in the tree.

## Local Commands

Use the real commands from the current repo:

- `cd services/api && pip install -r requirements.txt`
- `cd services/api && alembic upgrade head`
- `cd services/api && uvicorn main:app --reload`
- `PYTHONPATH=$(pwd) pytest services/api/tests -v`

## Non-Goals

- Do not mirror `.claude/settings.local.json` into Codex files.
- Do not duplicate acceptance criteria or workflow rules into new docs when a reference to the source document is enough.
