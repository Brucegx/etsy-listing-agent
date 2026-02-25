# Plan

## Phase 1: Infrastructure — Storage, Jobs & Batch Generation
- [x] [backend] Design and implement persistent image storage (local disk with configurable path, S3-ready interface)
- [x] [backend] Enhance `Job` model — status tracking (queued → strategy → batch_submitted → generating → completed → failed), progress %, result URLs, user_id FK
- [x] [backend] Implement async job submission — `POST /api/generate/*` returns `job_id` immediately, queues work in background
- [x] [backend] Add job status endpoint: `GET /api/jobs/{job_id}` (status, progress, stage name, result URLs when done)
- [x] [backend] Add job history endpoint: `GET /api/jobs` (list all jobs for authenticated user, with pagination)
- [ ] [backend] Replace sync Gemini calls with Gemini Batch API — submit all 10 image prompts as one batch, poll for results
- [ ] [backend] Migrate image serving from ephemeral /tmp to persistent storage with stable URLs
- [ ] [backend] Add email notification service — send email when job completes (using user's Google email from OAuth)
- [ ] [qa] Write backend integration tests for job lifecycle (submit → poll → batch complete → retrieve images)

## Phase 2: Public API
- [ ] [backend] Design public API schema — API key auth, rate limiting, OpenAPI docs
- [ ] [backend] Implement API key management (generate, revoke, per-user keys stored in DB)
- [ ] [backend] Add API key auth middleware for `/api/v1/*` endpoints
- [ ] [backend] Create public generation endpoint: `POST /api/v1/generate` (accepts images as multipart or URLs)
- [ ] [backend] Add webhook callback support — notify caller when job completes (optional callback_url param)
- [ ] [backend] Handle large image uploads — chunked upload or presigned URL pattern for 8MB+ images
- [ ] [qa] Write API integration tests — auth, generation, polling, webhooks, error cases

## Phase 3: Frontend — Full Product UI
- [ ] [frontend] Redesign landing page — product marketing, CTA, demo
- [ ] [frontend] Build job dashboard — list all jobs with status badges, thumbnails, re-download
- [ ] [frontend] Build API key management page — generate/revoke keys, usage stats, docs link
- [ ] [frontend] Improve generation flow — show stage name + progress %, "we'll email you when done" messaging
- [ ] [frontend] Polish Google Drive integration — better folder picker, preview images before generating
- [ ] [frontend] Add responsive design and mobile support
- [ ] [qa] Set up Playwright test infrastructure (config, fixtures, helpers)
- [ ] [qa] Write E2E tests: upload flow (upload images → submit → see job in dashboard → results ready)
- [ ] [qa] Write E2E tests: Drive flow (login → browse → select product → generate → check dashboard)
- [ ] [qa] Write E2E tests: API key management (create, copy, revoke)

## Phase 4: Production Readiness
- [ ] [backend] Add Dockerfile and docker-compose.yml (backend + frontend + DB)
- [ ] [backend] Add structured logging and error tracking
- [ ] [backend] Add rate limiting per API key and per user
- [ ] [frontend] Add error boundaries and user-friendly error pages
- [ ] [qa] Run full E2E regression suite, fix flaky tests
- [ ] [qa] Write load test for concurrent generation requests
