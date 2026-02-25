/**
 * E2E tests: Jobs dashboard (/jobs)
 *
 * Tests the job tracking page that shows all generation jobs and their statuses:
 *   1. Auth gate — unauthenticated users are redirected
 *   2. Jobs list renders with correct status badges
 *   3. Empty state is shown when no jobs exist
 *   4. Navigation works (Dashboard button)
 *
 * All backend calls are mocked.
 */

import { test, expect } from "./fixtures";
import { mockJobsList, MOCK_JOBS_LIST } from "./helpers/api-mocks";

const JOBS_URL = "/jobs";

// ---------------------------------------------------------------------------
// Auth gate
// ---------------------------------------------------------------------------

test.describe("Jobs dashboard — authentication gate", () => {
  test("unauthenticated users are redirected to /", async ({
    unauthPage: page,
  }) => {
    await page.goto(JOBS_URL);
    await expect(page).toHaveURL("/", { timeout: 5_000 });
  });
});

// ---------------------------------------------------------------------------
// Jobs list
// ---------------------------------------------------------------------------

test.describe("Jobs dashboard — listing", () => {
  test("shows heading and user email for authenticated user", async ({
    authedPage: page,
  }) => {
    await mockJobsList(page);

    await page.goto(JOBS_URL);

    await expect(page.getByRole("heading", { name: /jobs/i })).toBeVisible();
    await expect(page.getByText("test@example.com")).toBeVisible();
  });

  test("renders job list with product IDs and status badges", async ({
    authedPage: page,
  }) => {
    await mockJobsList(page);

    await page.goto(JOBS_URL);

    // Wait for job list to load
    await expect(page.getByTestId("jobs-list")).toBeVisible({ timeout: 5_000 });

    // Both mock jobs should be visible
    for (const job of MOCK_JOBS_LIST) {
      await expect(page.getByTestId(`job-item-${job.id}`)).toBeVisible();
      await expect(page.getByText(job.product_id)).toBeVisible();

      // Status badge
      const statusBadge = page.getByTestId(`job-status-${job.id}`);
      await expect(statusBadge).toBeVisible();
      await expect(statusBadge).toContainText(job.status);
    }
  });

  test("completed job has green-ish status badge", async ({
    authedPage: page,
  }) => {
    await mockJobsList(page);

    await page.goto(JOBS_URL);

    // job.id=1 has status "completed"
    const completedBadge = page.getByTestId("job-status-1");
    await expect(completedBadge).toBeVisible({ timeout: 5_000 });
    await expect(completedBadge).toContainText("completed");

    // Check it has the green styling class
    const className = await completedBadge.getAttribute("class");
    expect(className).toContain("green");
  });

  test("queued job has yellow-ish status badge", async ({
    authedPage: page,
  }) => {
    await mockJobsList(page);

    await page.goto(JOBS_URL);

    // job.id=2 has status "queued"
    const queuedBadge = page.getByTestId("job-status-2");
    await expect(queuedBadge).toBeVisible({ timeout: 5_000 });
    await expect(queuedBadge).toContainText("queued");

    const className = await queuedBadge.getAttribute("class");
    expect(className).toContain("yellow");
  });

  test("category badge is shown for each job", async ({
    authedPage: page,
  }) => {
    await mockJobsList(page);

    await page.goto(JOBS_URL);

    await expect(page.getByTestId("jobs-list")).toBeVisible({ timeout: 5_000 });

    // Both jobs have category "jewelry"
    const badges = page.getByText("jewelry");
    await expect(badges.first()).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

test.describe("Jobs dashboard — empty state", () => {
  test("shows empty state and upload link when no jobs", async ({
    authedPage: page,
  }) => {
    // Mock empty jobs list
    await page.route("**/api/jobs", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([]),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto(JOBS_URL);

    await expect(page.getByTestId("jobs-empty")).toBeVisible({
      timeout: 5_000,
    });
    await expect(page.getByText(/no jobs yet/i)).toBeVisible();

    // Upload Product button should be visible
    await expect(
      page.getByRole("button", { name: /upload product/i })
    ).toBeVisible();
  });

  test("Upload Product button navigates to home page", async ({
    authedPage: page,
  }) => {
    await page.route("**/api/jobs", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    await page.goto(JOBS_URL);

    await page.getByRole("button", { name: /upload product/i }).click();

    await expect(page).toHaveURL("/", { timeout: 5_000 });
  });
});

// ---------------------------------------------------------------------------
// Error state
// ---------------------------------------------------------------------------

test.describe("Jobs dashboard — error state", () => {
  test("shows error when jobs API fails", async ({ authedPage: page }) => {
    await page.route("**/api/jobs", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Database connection failed" }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto(JOBS_URL);

    await expect(page.getByTestId("jobs-error")).toBeVisible({
      timeout: 5_000,
    });
    await expect(page.getByText(/failed to fetch jobs/i)).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

test.describe("Jobs dashboard — navigation", () => {
  test("Dashboard button navigates to /dashboard", async ({
    authedPage: page,
  }) => {
    await mockJobsList(page);

    await page.goto(JOBS_URL);

    await page.getByRole("button", { name: /dashboard/i }).click();

    await expect(page).toHaveURL("/dashboard", { timeout: 5_000 });
  });

  test("introductory description text is visible", async ({
    authedPage: page,
  }) => {
    await mockJobsList(page);

    await page.goto(JOBS_URL);

    await expect(
      page.getByText(/track the status of your product listing generation jobs/i)
    ).toBeVisible();
  });
});
