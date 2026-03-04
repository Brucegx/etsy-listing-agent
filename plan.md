# Plan

## Phase 1-4: COMPLETE ✅

## Phase 5: UX Fixes — Smoke Test Issues (2026-02-25)

### Critical Bugs
- [ ] [backend] Fix image size error: compress/resize uploaded images to <5MB before sending to Claude API (current: 6.7MB → Claude rejects with 400)
- [ ] [backend] Return user-friendly error messages, not raw API error dicts (e.g., "Image too large" not `{'type': 'error', 'error': {'type': 'invalid_request_error'...}}`)
- [x] [frontend] Add submit feedback: loading spinner on button + success toast "Job #xxx created — track it in Jobs" with link + disable button after click (899aaae)
- [x] [frontend] Prevent duplicate submissions: disable Generate button for 5s after click, or detect same images within session (899aaae)

### Auth & Navigation
- [x] [frontend] Landing page redesign (DEC-011): limited demo mode (1 image preview, no full generation), CTA = "Sign in with Google" (526eccb)
- [x] [frontend] After login, show combined home page with two paths: "Upload Photos" and "From Google Drive" (526eccb)
- [x] [frontend] NavBar: always show Home / Dashboard / Jobs / API Keys links when logged in. Add Home link (currently missing). (899aaae)

### Google Drive Issues
- [x] [frontend] Fix Drive folder name display — truncate long names with ellipsis (526eccb)
- [ ] [backend] Fix Drive data sync — verify API returns real user folders, check sort order, investigate stale/wrong data
- [x] [frontend] Drive dashboard: add loading states, better error messages for auth token expiry (526eccb)

### UX Polish
- [x] [frontend] API Keys page: add explanation header ("For developers: use our API to generate listings programmatically") (526eccb)
- [x] [frontend] Jobs page: show friendly error messages, not raw error strings (526eccb, 7e21872)
- [x] [frontend] Add usage guide / example on Dashboard: "How to organize your product photos" with folder structure example (526eccb)

### Additional Work Done (not in original plan)
- [x] [frontend] Job detail page — view individual job results (a86dc2f)
- [x] [frontend] Delete jobs from dashboard (a86dc2f)
- [x] [backend] Security hardening — strip sensitive data from API responses (a86dc2f)
- [x] [engine] Switch image model to Gemini 3.1 Flash (b57cb8d)

## Phase 6: Image Studio — Standalone Image Generation (2026-03-04)

Design doc: `docs/plans/2026-03-04-image-studio-design.md`

### Phase 6A: Backend — Image Studio Service
- [ ] [backend] Add `job_type` and `image_config` columns to Job model + migration
- [ ] [backend] Create `image_studio.py` service — prompt builder that reuses preprocessing (ANCHOR) + prompt_node (jewelry-prompt-generator skill), skips strategy
- [ ] [backend] Implement multi-image variation logic (variation_index + hints for angle/lighting/composition)
- [ ] [backend] Add aspect ratio post-processing (Pillow crop to 1:1 / 3:4 / 4:3)
- [ ] [backend] Update job worker to branch on `job_type` (`full_listing` vs `image_only`)
- [ ] [backend] Update job API to accept `image_config` (category, additional_prompt, count, aspect_ratio) + `product_info` (free text)
- [ ] [backend] Tests for image studio service

### Phase 6B: Frontend — Image Studio UI
- [ ] [frontend] Add tab switcher on home page (Full Listing / Image Studio)
- [ ] [frontend] Build Image Studio form: image type card picker (白底图/场景图/模特图/细节图), additional prompt textarea, product info textarea, count selector (1-9), aspect ratio selector (1:1/3:4/4:3)
- [ ] [frontend] Submit `image_only` job to API, reuse existing job creation flow + toast
- [ ] [frontend] Update Jobs page to handle `image_only` results — image grid (no listing section), job_type badge
- [ ] [frontend] Add download-all-as-ZIP for image results

### Phase 6C: Integration & Testing
- [ ] [qa] E2E Playwright tests for Image Studio flow
- [ ] [qa] Real browser smoke test (mandatory per DEC-013)
