# Decisions

Architectural decisions made during this project. Maintained by the Lead.
This file is the permanent record — never compressed, never summarized.
New entries are appended, never removed.

---

## DEC-001: Tech Stack (2026-02-24)
- Backend: Python 3.11 + FastAPI + SQLAlchemy + SQLite (upgradeable to PostgreSQL)
- Frontend: Next.js 15 + React 19 + shadcn/ui + Tailwind CSS 4
- Engine: LangGraph + Claude (strategy) + Gemini 2.5 Flash (image gen)
- E2E Testing: Playwright (patchright already installed)
- Rationale: Existing stack, proven working, no reason to change

## DEC-002: Image Storage Strategy (2026-02-24)
- Phase 1: Persistent local storage with configurable base path (replaces ephemeral /tmp)
- Interface designed for S3 drop-in replacement later
- Images served via stable URLs: `/api/images/{job_id}/{filename}`
- Rationale: Current /tmp + 1hr TTL is unusable for a real product; local-first keeps deployment simple

## DEC-003: Async Job Architecture (2026-02-24)
- Generation requests return immediately with `job_id`
- Background worker processes the LangGraph workflow
- Clients poll `GET /api/jobs/{job_id}` or receive webhook callback
- SSE streaming preserved for real-time UI progress (existing feature)
- Rationale: 10-minute generation time requires async pattern; polling works for API clients, SSE for UI

## DEC-006: Gemini Batch API for Image Generation (2026-02-24)
- Replace synchronous Gemini 2.5 Flash calls with Gemini Batch API
- Batch API is ~50% cheaper than synchronous API
- Flow: strategy → build all 10 prompts → submit as one batch → poll/callback for results
- Decouples image generation from user session entirely
- Rationale: Users can't wait 10 min; batch is async by nature and costs half as much

## DEC-007: User Notification — Dashboard + Email (2026-02-24)
- Primary: Dashboard shows all jobs with status (queued → generating → complete/failed)
- User closes browser → comes back → logs in → sees results in Dashboard
- Secondary: Email notification when job completes (Google OAuth already provides user email)
- API users: webhook callback (optional `callback_url` parameter)
- Rationale: Dashboard is essential for "close and come back" UX; email covers offline notification

## DEC-004: Public API Auth (2026-02-24)
- API keys (bearer tokens) for programmatic access
- Google OAuth preserved for web UI
- Per-key rate limits stored in DB
- Rationale: API keys are standard for B2B/developer APIs; separate from user auth

## DEC-005: Team Structure (2026-02-24)
- 3 roles: backend, frontend, qa
- QA owns Playwright setup and all E2E tests
- QA writes user stories as test specs — no manual testing required
- Frontend handles all UI/UX design decisions autonomously
- Rationale: User wants zero involvement in design and testing

## DEC-009: Git Branch Strategy (2026-02-24)
- Feature branches per Phase: `feat/phase1-jobs`, `feat/phase2-api`, `feat/phase3-ui`, etc.
- Each branch gets PR'd to main when phase is complete
- Parallel agents use git worktrees for isolation (no conflicts)
- Lead reviews PRs before merge
- Sequential agents on the same phase share the same feature branch
- Rationale: Safe for parallel work, reviewable, clean main history

## DEC-008: Frontend Design Process (2026-02-24)
- Frontend teammate MUST use `ux-design` skill for layout/component design workflow
- Frontend teammate MUST use `frontend-design:frontend-design` skill for polished, distinctive UI code
- Frontend teammate MUST use `ux-design-expert` subagent for Tailwind styling, color, typography decisions
- Design quality is a hard requirement — no generic/bland AI-generated look
- Existing stack: shadcn/ui + Tailwind CSS 4 — build on top, don't replace
- Rationale: User expects production-grade design without personal involvement

## DEC-010: Core User Workflows (2026-02-25)
- TWO primary workflows, both equal:
  1. **Upload**: User uploads product photos directly → system generates listing + images → results in Job Dashboard
  2. **Google Drive**: User has photos in Drive → browse/select folder → system reads + generates → results saved back to Drive
- BOTH require login to track user and persist results
- All generation jobs appear in `/jobs` dashboard regardless of source
- Rationale: Users work differently; both paths must be first-class

## DEC-011: Landing Page & Auth (2026-02-25)
- Landing page allows LIMITED trial without login: upload 1 image, see a preview/demo, NOT full generation
- CTA is "Sign in with Google" to unlock full features
- After login, user lands on a combined home with both Upload and Drive options
- MUST NOT allow full generation without login — results are untrackable
- Rationale: Let users taste the product before committing, but don't create orphaned results

## DEC-012: UX Fixes from Smoke Test (2026-02-25)
- Submit button: MUST show loading state + clear success message ("Job #xxx created") + link to /jobs
- MUST prevent duplicate submissions (disable button after click, or dedup same images within N minutes)
- Navigation: Logged-in user MUST always see nav links: Home (upload), Dashboard (Drive), Jobs, API Keys
- API Keys page: MUST explain purpose ("For developers: programmatic access to our generation API")
- Google Drive dashboard: Fix folder name display (truncate long names), fix data sync, verify real Drive data
- Error messages: Show user-friendly errors, not raw API error dicts
- Rationale: Real smoke test revealed all these gaps

## DEC-014: Image Studio — Standalone Image Generation (2026-03-04)
- New "Image Studio" mode alongside existing Full Listing flow
- Skips strategy node — user controls image type, count, aspect ratio, additional prompt
- Reuses: preprocessing (ANCHOR), prompt_node (jewelry-prompt-generator skill), Gemini image gen
- Image types simplified to 4 UI categories: 白底图→hero, 场景图→scene_daily, 模特图→wearing_a, 细节图→macro_detail
- Product info = single free-text textarea (not structured fields)
- Additional prompt = free-text for extra instructions (not a fixed style picker)
- Same async job queue as full listing (job_type = "image_only")
- Multi-image variation via variation_index + hints (angle/lighting/composition)
- Aspect ratio (1:1, 3:4, 4:3) via prompt guidance + Pillow crop post-processing
- Model: Gemini 3.1 Flash (same as current, already switched)
- Frontend: Two tabs on home page — "Full Listing" | "Image Studio"
- Design doc: `docs/plans/2026-03-04-image-studio-design.md`
- Rationale: Customer wants standalone image gen as the most valuable standalone feature

## DEC-013: Mandatory Real Smoke Testing (2026-02-25)
- After EVERY phase completion, a Smoke Test Agent MUST run before claiming "done"
- Smoke Test Agent uses `mcp__claude-in-chrome__*` browser tools (NOT mock Playwright)
- Agent opens real browser → navigates real pages → verifies real API data renders correctly
- Follows actual user stories: login → upload → check jobs → view results → Drive workflow
- Takes screenshots, checks console errors, validates field names match API responses
- Mock-based Playwright tests are supplementary, NOT a replacement for real smoke testing
- Frontend types MUST be validated against actual backend API responses (not assumed)
- Any field name mismatch (e.g., `id` vs `job_id`) is a P0 bug that blocks release
- Rationale: Phase 3 passed 44 Playwright tests but the Jobs page crashed on real data because `GenerateJob` type had wrong field names. User had to find this manually — unacceptable.

