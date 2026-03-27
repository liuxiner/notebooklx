# Repository Guidelines

## Source of Truth
Use [CLAUDE.md](CLAUDE.md) as the working-rules document for this repository. It defines the product principles, target architecture, TDD workflow, testing expectations, and PR discipline. Use [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) as the implementation blueprint: feature order, tasks, and acceptance criteria live there and should not be duplicated elsewhere. Update [TASK_CHECKLIST.md](TASK_CHECKLIST.md) when a feature moves forward.

## Project Structure & Module Organization
The current implementation is backend-first. Active code lives under `services/api/`: shared database code in `core/`, feature modules in `modules/<feature>/`, Alembic migrations in `alembic/versions/`, and pytest coverage in `tests/`. SQL bootstrap files live in `infra/sql/`. `DEVELOPMENT_PLAN.md` describes planned directories such as `apps/web/` and `services/worker/`; do not assume those exist until they are added.

## Build, Test, and Development Commands
Use the commands that match the current repository state:

- `cd services/api && python3 -m venv ../../venv && source ../../venv/bin/activate`
- `cd services/api && pip install -r requirements.txt`
- `cd services/api && alembic upgrade head`
- `cd services/api && uvicorn main:app --reload`
- `PYTHONPATH=$(pwd) pytest services/api/tests -v`
- `PYTHONPATH=$(pwd) pytest services/api/tests --cov=services.api --cov-report=html`

## Coding Style & Testing
Follow the existing Python style: 4-space indentation, `snake_case` for functions and modules, `PascalCase` for Pydantic and SQLAlchemy classes, and explicit type hints where already used. Write tests first from the acceptance criteria in `DEVELOPMENT_PLAN.md`; keep new tests in `services/api/tests/test_<feature>.py` and cover both success and failure paths.

## Agent Notes
Do not copy rules from `CLAUDE.md` into new files. Reference it. The `.claude/settings.local.json` file is Claude-specific permission metadata, not the source of truth for Codex. For Codex work, follow the repository docs above and the active Codex sandbox/approval model.
