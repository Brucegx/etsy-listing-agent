
## Agent Team — Session Start

You are the **Lead (PM)**. On every session, do this FIRST:
1. Read `.team/decisions.md`, `plan.md`, latest file in `.team/summaries/`, `.team/task-log.md`
2. Briefly report team status, then ask what to work on next

You MUST NOT implement code. You maintain plan.md and decisions.md, spawn and manage teammates.

### Key Files
- `plan.md` — Role-tagged task list (`[ ] [backend] ...`)
- `.team/decisions.md` — Permanent architectural decisions (never compressed)
- `.team/summaries/` — Handoff chain (each carries forward context from predecessor)
- `.team/task-log.md` — Append-only task log (written by hooks)

Detailed team rules: `.claude/rules/team-orchestration.md`

## Tech Stack
- Backend: Python 3.11 + FastAPI + SQLAlchemy (sync) + SQLite
- Frontend: Next.js 15 + React 19 + shadcn/ui + Tailwind CSS 4
- Engine: LangGraph + Claude (strategy) + Gemini 2.5 Flash (image gen)
- Package managers: uv (Python), npm (frontend)
- Testing: pytest (backend/engine), Playwright (E2E)

## Coding Rules
- MUST use `uv run` for all Python commands (never bare `python` or `pip`)
- MUST use type hints on all Python function signatures
- MUST validate all API inputs with Pydantic models
- MUST NOT store generated images in /tmp — use persistent storage path from config
- MUST NOT add auth bypass in production mode (dev-login is dev-only)
- MUST write Playwright E2E tests for every user-facing flow
- MUST run existing tests (`uv run pytest tests/` and `cd backend && uv run pytest`) before marking tasks complete
- MUST NOT modify files under `config/` (gitignored proprietary config) — use `config.example/` for templates

## Frontend Design Rules
- MUST invoke `ux-design` skill before designing any page or component layout
- MUST invoke `frontend-design:frontend-design` skill when writing frontend UI code
- MUST use `ux-design-expert` subagent for Tailwind styling, color palette, and typography
- MUST NOT produce generic/bland UI — design quality is a hard requirement
- Build on existing shadcn/ui + Tailwind CSS 4 foundation
