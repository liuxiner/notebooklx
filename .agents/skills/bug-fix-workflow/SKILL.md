---
name: bug-fix-workflow
description: User asks to fix a bug, troubleshoot a broken flow, repair failing tests, or solve a problem; keywords include bug fix, fix bug, debug, troubleshoot, issue, regression.
---

# NotebookLX Bug Fix Workflow

Use this skill when the request is to fix a defect, regression, failing test, or broken behavior in this repository.

## Primary References

Read these files instead of restating their contents:

- `AGENTS.md`
- `CLAUDE.md`
- `DEVELOPMENT_PLAN.md`
- `TASK_CHECKLIST.md`

## Bug-Fix Contract

Every bug-fix loop must be a small, testable slice.

Before touching code, define:

- `Bug`: the observed failure or regression
- `Related plan item`: the nearest matching `DEVELOPMENT_PLAN.md` feature or acceptance-criteria section
- `Repro`: the failing test or concrete reproduction case
- `Verification`: the exact focused command(s) that prove the fix

If you cannot point to the failing behavior and a matching slice, narrow the scope first.

## Required Order

1. Read `AGENTS.md`, then the relevant `CLAUDE.md` sections.
2. Find the nearest relevant item in `DEVELOPMENT_PLAN.md` and `TASK_CHECKLIST.md`.
3. Convert the bug into explicit acceptance criteria or a failing repro test.
4. Write the failing test first.
5. Implement the minimum code change to make that test pass.
6. Run the focused test command(s) until green.
7. Run the smallest regression test set that covers the touched path.
8. Only then update `TASK_CHECKLIST.md` and any checked plan items.

## TDD Rules

- Reproduce the bug with a test before changing production code.
- Keep each test narrowly focused on one behavior.
- Fix one failing case at a time when possible.
- Do not add unrelated refactors, cleanup, or feature work in the same loop.
- Do not mark the work done while the repro or acceptance test is still red.

## Scope Rules

- Prefer the smallest plan slice that explains the bug.
- If the bug spans multiple plan items, fix the highest-priority failing slice first.
- If the bug is not named in `DEVELOPMENT_PLAN.md`, anchor it to the closest related area and keep the change minimal.
- If the fix requires changing behavior outside the current slice, stop and explain the gap before widening scope.

## Verification

Use the smallest command that proves the fix, for example:

- `PYTHONPATH=$(pwd) pytest services/api/tests/test_<area>.py -v`
- `PYTHONPATH=$(pwd) pytest services/api/tests -k <keyword> -v`
- `cd apps/web && pnpm test`
- `cd apps/web && pnpm run lint`

Prefer targeted commands first, then only broader regressions if the touched code warrants it.

## Progress Tracking

When the fix corresponds to an item in `TASK_CHECKLIST.md`, mark it `⚡` at the start of work and `✓` only after the test pass is verified.
