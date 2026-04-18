# Repository Guidelines

## Source of Truth
Use [CLAUDE.md](CLAUDE.md) as the working-rules document for this repository. It defines the product principles, target architecture, TDD workflow, testing expectations, and PR discipline. Use [apps/web/DESIGN.md](apps/web/DESIGN.md) as the visual source of truth for `apps/web`: colors, typography, spacing, component patterns, workspace layout, and transparency UX should be implemented from there rather than re-invented ad hoc. Use [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) as the implementation blueprint: feature order, tasks, and acceptance criteria live there and should not be duplicated elsewhere. Update [TASK_CHECKLIST.md](TASK_CHECKLIST.md) when a feature moves forward.

## Project Structure & Module Organization
Active code lives under both `services/api/` and `apps/web/`. The backend keeps shared database code in `core/`, feature modules in `modules/<feature>/`, Alembic migrations in `alembic/versions/`, and pytest coverage in `tests/`. The frontend lives in `apps/web/` with routes in `app/`, reusable UI in `components/`, and client helpers in `lib/`. SQL bootstrap files live in `infra/sql/`. `DEVELOPMENT_PLAN.md` still describes future directories such as `services/worker/`; do not assume those exist until they are added.

## Build, Test, and Development Commands
Use the commands that match the current repository state:

- `cd apps/web && pnpm install`
- `cd apps/web && pnpm run dev`
- `cd apps/web && pnpm run build`
- `cd apps/web && pnpm test`
- `cd services/api && python3 -m venv ../../venv && source ../../venv/bin/activate`
- `cd services/api && pip install -r requirements.txt`
- `cd services/api && alembic upgrade head`
- `uvicorn services.api.main:app --reload`
- `PYTHONPATH=$(pwd) pytest services/api/tests -v`
- `PYTHONPATH=$(pwd) pytest services/api/tests --cov=services.api --cov-report=html`

## Coding Style & Testing
Follow the existing Python style: 4-space indentation, `snake_case` for functions and modules, `PascalCase` for Pydantic and SQLAlchemy classes, and explicit type hints where already used. For frontend work, keep shared styling aligned with `apps/web/DESIGN.md` before introducing one-off patterns, and prefer changes in shared primitives when the design affects multiple surfaces. Write tests first from the acceptance criteria in `DEVELOPMENT_PLAN.md`; keep backend tests in `services/api/tests/test_<feature>.py` and frontend tests next to the affected `apps/web` surface, covering both success and failure paths.

## Agent Notes
Do not copy rules from `CLAUDE.md` into new files. Reference it. The `.claude/settings.local.json` file is Claude-specific permission metadata, not the source of truth for Codex. For Codex work, follow the repository docs above and the active Codex sandbox/approval model.
