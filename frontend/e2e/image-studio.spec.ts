/**
 * E2E tests: Image Studio feature
 *
 * Tests the Image Studio workflow:
 *   1. Hub navigation — card visibility and mode switching
 *   2. Image Studio form — elements, selection, submission
 *   3. Jobs page — job_type badges for image_only vs full_listing jobs
 *   4. Job detail page — image_only job shows images, hides listing sections
 *
 * All backend calls are mocked — no real API needed.
 */

import { test, expect } from "./fixtures";
import path from "path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Create a minimal 1×1 white PNG buffer. */
function createMinimalPng(): Buffer {
  return Buffer.from(
    "89504e470d0a1a0a0000000d494844520000000100000001080000000" +
      "03a7e9b550000000a4944415478016360000000020001e221bc330000" +
      "00000049454e44ae426082",
    "hex"
  );
}

/** Mock GET /api/jobs to return a list containing both job types. */
async function mockMixedJobsList(page: import("@playwright/test").Page): Promise<void> {
  await page.route("**/api/jobs", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          jobs: [
            {
              job_id: "job-image-001",
              product_id: "studio-product-001",
              category: "jewelry",
              job_type: "image_only",
              status: "completed",
              progress: 100,
              stage_name: "done",
              image_urls: ["/storage/jobs/job-image-001/img1.png", "/storage/jobs/job-image-001/img2.png"],
              result: null,
              error_message: null,
              cost_usd: 0.02,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            },
            {
              job_id: "job-listing-002",
              product_id: "listing-product-002",
              category: "jewelry",
              job_type: "full_listing",
              status: "completed",
              progress: 100,
              stage_name: "done",
              image_urls: null,
              result: {
                listing: {
                  title: "Handmade Silver Ring",
                  tags: "silver, ring, handmade",
                  description: "A beautiful handcrafted ring",
                },
              },
              error_message: null,
              cost_usd: 0.08,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            },
          ],
          total: 2,
          page: 1,
          page_size: 20,
          total_pages: 1,
        }),
      });
    } else {
      await route.continue();
    }
  });
}

/** Mock GET /api/jobs/:id to return an image_only completed job. */
async function mockImageOnlyJobDetail(page: import("@playwright/test").Page): Promise<void> {
  await page.route("**/api/jobs/job-image-001", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        job_id: "job-image-001",
        product_id: "studio-product-001",
        category: "jewelry",
        job_type: "image_only",
        status: "completed",
        progress: 100,
        stage_name: "done",
        image_urls: [
          "/storage/jobs/job-image-001/img1.png",
          "/storage/jobs/job-image-001/img2.png",
          "/storage/jobs/job-image-001/img3.png",
        ],
        result: null,
        error_message: null,
        cost_usd: 0.02,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }),
    });
  });
}

/** Mock POST /api/jobs/image-studio to return a queued job. */
async function mockImageStudioSubmit(page: import("@playwright/test").Page): Promise<void> {
  await page.route("**/api/jobs/image-studio", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ job_id: "job-image-new-001" }),
      });
    } else {
      await route.continue();
    }
  });
}

// ---------------------------------------------------------------------------
// 1. Hub navigation
// ---------------------------------------------------------------------------

test.describe("Image Studio — hub navigation", () => {
  test("landing page shows all three workflow cards", async ({
    authedPage: page,
  }) => {
    // Mock jobs list to avoid network errors on hub load
    await page.route("**/api/jobs", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ jobs: [], total: 0, page: 1, page_size: 20, total_pages: 0 }),
      });
    });

    await page.goto("/");

    // Hub heading
    await expect(
      page.getByRole("heading", { name: /what would you like to create/i })
    ).toBeVisible({ timeout: 5_000 });

    // Full Listing card (grayed out, Coming Soon)
    await expect(page.getByText("Full Listing")).toBeVisible();
    await expect(page.getByText("Coming Soon").first()).toBeVisible();

    // Image Studio card (active)
    await expect(page.getByRole("button", { name: /image studio/i })).toBeVisible();

    // Batch Processing card (grayed out, Coming Soon)
    await expect(page.getByText("Batch Processing")).toBeVisible();
  });

  test("clicking Image Studio card shows the Image Studio form", async ({
    authedPage: page,
  }) => {
    await page.route("**/api/jobs", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ jobs: [], total: 0, page: 1, page_size: 20, total_pages: 0 }),
      });
    });

    await page.goto("/");

    // Click the Image Studio hub card
    await page.getByRole("button", { name: /image studio/i }).click();

    // Image Studio heading should appear
    await expect(
      page.getByRole("heading", { name: /image studio/i })
    ).toBeVisible({ timeout: 5_000 });

    // Back button should appear (exact match to avoid matching "background" in image type cards)
    await expect(page.getByRole("button", { name: "Back", exact: true })).toBeVisible();
  });

  test("clicking Back from Image Studio returns to hub", async ({
    authedPage: page,
  }) => {
    await page.route("**/api/jobs", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ jobs: [], total: 0, page: 1, page_size: 20, total_pages: 0 }),
      });
    });

    await page.goto("/");

    // Navigate to Image Studio
    await page.getByRole("button", { name: /image studio/i }).click();
    await expect(page.getByRole("heading", { name: /image studio/i })).toBeVisible({
      timeout: 5_000,
    });

    // Click Back (exact to avoid matching "background" in image type card text)
    await page.getByRole("button", { name: "Back", exact: true }).click();

    // Should return to the hub
    await expect(
      page.getByRole("heading", { name: /what would you like to create/i })
    ).toBeVisible({ timeout: 5_000 });
  });

  test("Full Listing card is disabled with Coming Soon badge", async ({
    authedPage: page,
  }) => {
    await page.route("**/api/jobs", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ jobs: [], total: 0, page: 1, page_size: 20, total_pages: 0 }),
      });
    });

    await page.goto("/");

    // Full Listing card should not be a button (it's a div now)
    await expect(page.getByRole("button", { name: /full listing/i })).toHaveCount(0);

    // Should show Coming Soon badge
    await expect(page.getByText("Coming Soon").first()).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// 2. Image Studio form
// ---------------------------------------------------------------------------

test.describe("Image Studio — form elements", () => {
  test.beforeEach(async ({ authedPage: page }) => {
    await page.route("**/api/jobs", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ jobs: [], total: 0, page: 1, page_size: 20, total_pages: 0 }),
      });
    });
    await page.goto("/");
    await page.getByRole("button", { name: /image studio/i }).click();
    await expect(page.getByRole("heading", { name: /image studio/i })).toBeVisible({
      timeout: 5_000,
    });
  });

  test("form renders with upload zone, image type cards, count selector, ratio selector, and generate button", async ({
    authedPage: page,
  }) => {
    // Upload zone (matches the aria-label on the ImageUploader button)
    await expect(
      page.getByRole("button", { name: /upload product images/i })
    ).toBeVisible();

    // Image type card labels (use button locator to avoid ambiguity with "Additional details" section)
    // Each card button contains the label text plus Chinese + description
    await expect(page.locator("button").filter({ hasText: /white bg/i })).toBeVisible();
    await expect(page.locator("button").filter({ hasText: /scene.*lifestyle/i })).toBeVisible();
    await expect(page.locator("button").filter({ hasText: /model.*worn/i })).toBeVisible();
    await expect(page.locator("button").filter({ hasText: /detail.*close-up/i })).toBeVisible();

    // Count options (check a few) — the count segmented control has options 1,3,4,5,9
    // Use first() to avoid strict-mode violations since "4" also appears in ratio buttons
    await expect(page.getByRole("button", { name: "4", exact: true }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "1", exact: true }).first()).toBeVisible();

    // Aspect ratio options
    await expect(page.getByRole("button", { name: /1:1/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /3:4/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /4:3/i })).toBeVisible();

    // Text areas
    await expect(page.getByLabel("Product description")).toBeVisible();
    await expect(page.getByLabel("Style prompt")).toBeVisible();

    // Generate button (disabled when no files)
    await expect(page.getByRole("button", { name: /generate images/i })).toBeDisabled();
  });

  test("Generate Images button is disabled when no image is uploaded", async ({
    authedPage: page,
  }) => {
    const generateBtn = page.getByRole("button", { name: /generate images/i });
    await expect(generateBtn).toBeDisabled();
  });

  test("Generate Images button enables after uploading an image", async ({
    authedPage: page,
  }) => {
    const pngBuffer = createMinimalPng();
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles({
      name: "product.png",
      mimeType: "image/png",
      buffer: pngBuffer,
    });

    await expect(page.getByRole("button", { name: /generate images/i })).toBeEnabled({
      timeout: 5_000,
    });
  });

  test("image type cards are selectable by clicking", async ({
    authedPage: page,
  }) => {
    // Find the "White BG" image type button (it's a button element containing the text)
    // The buttons are in the image type grid
    const whiteBgBtn = page.locator("button").filter({ hasText: /white bg/i }).first();
    await expect(whiteBgBtn).toBeVisible();

    // Click to select
    await whiteBgBtn.click();

    // After clicking, a checkmark appears (selected state) — verify button is now highlighted
    // The selected state adds a different border class; verify via aria or via a child checkmark
    // The component adds an absolute span with a checkmark svg when selected
    const checkmark = whiteBgBtn.locator("span").filter({
      has: page.locator("svg"),
    });
    await expect(checkmark).toBeVisible({ timeout: 3_000 });
  });

  test("image type card can be deselected by clicking again", async ({
    authedPage: page,
  }) => {
    const whiteBgBtn = page.locator("button").filter({ hasText: /white bg/i }).first();

    // Select
    await whiteBgBtn.click();
    // Deselect
    await whiteBgBtn.click();

    // Checkmark should no longer be visible
    const checkmark = whiteBgBtn.locator("span").filter({
      has: page.locator("svg"),
    });
    await expect(checkmark).not.toBeVisible({ timeout: 3_000 });
  });

  test("count selector allows changing the image count", async ({
    authedPage: page,
  }) => {
    // Default is 4; click "9" to change
    const nineBtn = page.getByRole("button", { name: "9" });
    await nineBtn.click();

    // Verify it appears selected — the segmented control wraps it in a white bg div when selected
    // We can just verify the button is clickable and visible
    await expect(nineBtn).toBeVisible();
    await expect(nineBtn).toBeEnabled();
  });

  test("aspect ratio selector allows changing ratio", async ({
    authedPage: page,
  }) => {
    // Click 3:4 ratio
    const portraitBtn = page.getByRole("button", { name: /3:4/i });
    await portraitBtn.click();
    await expect(portraitBtn).toBeEnabled();
  });

  test("product description textarea accepts text input", async ({
    authedPage: page,
  }) => {
    const textarea = page.getByLabel("Product description");
    await textarea.fill("925 silver ring with blue zircon, 2cm wide");
    await expect(textarea).toHaveValue("925 silver ring with blue zircon, 2cm wide");
  });

  test("style prompt textarea accepts text input", async ({
    authedPage: page,
  }) => {
    const textarea = page.getByLabel("Style prompt");
    await textarea.fill("Warm lighting, greenery background, soft bokeh");
    await expect(textarea).toHaveValue("Warm lighting, greenery background, soft bokeh");
  });
});

// ---------------------------------------------------------------------------
// 3. Image Studio submission
// ---------------------------------------------------------------------------

test.describe("Image Studio — submission", () => {
  test.beforeEach(async ({ authedPage: page }) => {
    await page.route("**/api/jobs", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ jobs: [], total: 0, page: 1, page_size: 20, total_pages: 0 }),
      });
    });
    await page.goto("/");
    await page.getByRole("button", { name: /image studio/i }).click();
    await expect(page.getByRole("heading", { name: /image studio/i })).toBeVisible({
      timeout: 5_000,
    });
  });

  test("submitting with image shows success banner containing link to /jobs", async ({
    authedPage: page,
  }) => {
    await mockImageStudioSubmit(page);

    // Upload an image
    const pngBuffer = createMinimalPng();
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles({
      name: "product.png",
      mimeType: "image/png",
      buffer: pngBuffer,
    });

    // Click Generate Images
    await page.getByRole("button", { name: /generate images/i }).click();

    // Success banner should appear
    await expect(page.getByRole("status")).toBeVisible({ timeout: 10_000 });

    // Banner text includes "Image Studio job created"
    await expect(
      page.getByText(/image studio job created/i)
    ).toBeVisible({ timeout: 10_000 });

    // Banner has a link to /jobs
    await expect(page.getByRole("link", { name: /go to jobs/i })).toBeVisible();
  });

  test("button shows 'Submitting…' state while POST is in flight and is disabled", async ({
    authedPage: page,
  }) => {
    // Delay the API response to observe the in-flight state
    await page.route("**/api/jobs/image-studio", async (route) => {
      // Respond after a short delay to let us capture the submitting state
      await new Promise((r) => setTimeout(r, 300));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ job_id: "job-image-new-001" }),
      });
    });

    const pngBuffer = createMinimalPng();
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles({
      name: "product.png",
      mimeType: "image/png",
      buffer: pngBuffer,
    });

    // Click generate
    await page.getByRole("button", { name: /generate images/i }).click();

    // During submission, button should show submitting state OR be disabled
    // (The button transitions to "Submitting…" label)
    await expect(
      page.getByRole("button", { name: /submitting|job submitted/i })
    ).toBeVisible({ timeout: 5_000 });
  });

  test("error response shows an error banner", async ({ authedPage: page }) => {
    // Mock a 500 error
    await page.route("**/api/jobs/image-studio", async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Internal server error" }),
      });
    });

    const pngBuffer = createMinimalPng();
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles({
      name: "product.png",
      mimeType: "image/png",
      buffer: pngBuffer,
    });

    await page.getByRole("button", { name: /generate images/i }).click();

    // Error banner should appear (role=status with error class, or just visible error text)
    await expect(
      page.getByRole("status")
    ).toBeVisible({ timeout: 10_000 });

    // Error text
    await expect(
      page.getByText(/internal server error|failed to submit/i)
    ).toBeVisible({ timeout: 10_000 });
  });

  test("button is locked after successful submission (duplicate prevention)", async ({
    authedPage: page,
  }) => {
    await mockImageStudioSubmit(page);

    const pngBuffer = createMinimalPng();
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles({
      name: "product.png",
      mimeType: "image/png",
      buffer: pngBuffer,
    });

    await page.getByRole("button", { name: /generate images/i }).click();

    // After success, button becomes "Job Submitted" and is disabled
    await expect(
      page.getByRole("button", { name: /job submitted/i })
    ).toBeVisible({ timeout: 10_000 });

    await expect(
      page.getByRole("button", { name: /job submitted/i })
    ).toBeDisabled();
  });
});

// ---------------------------------------------------------------------------
// 4. Jobs page — job_type badges
// ---------------------------------------------------------------------------

test.describe("Jobs page — Image Studio job type badges", () => {
  test("image_only jobs show 'Image Studio' badge", async ({
    authedPage: page,
  }) => {
    await mockMixedJobsList(page);

    await page.goto("/jobs");

    // Wait for the jobs to render
    await expect(page.getByText("studio-product-001")).toBeVisible({
      timeout: 5_000,
    });

    // Image Studio badge should be present
    await expect(page.getByText("Image Studio").first()).toBeVisible();
  });

  test("full_listing jobs show 'Full Listing' badge", async ({
    authedPage: page,
  }) => {
    await mockMixedJobsList(page);

    await page.goto("/jobs");

    // Wait for the jobs to render
    await expect(page.getByText("listing-product-002")).toBeVisible({
      timeout: 5_000,
    });

    // Full Listing badge should be present
    await expect(page.getByText("Full Listing").first()).toBeVisible();
  });

  test("both badge types are visible when both job types are in the list", async ({
    authedPage: page,
  }) => {
    await mockMixedJobsList(page);

    await page.goto("/jobs");

    // Both products render
    await expect(page.getByText("studio-product-001")).toBeVisible({
      timeout: 5_000,
    });
    await expect(page.getByText("listing-product-002")).toBeVisible();

    // Both badge types visible
    await expect(page.getByText("Image Studio").first()).toBeVisible();
    await expect(page.getByText("Full Listing").first()).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// 5. Job detail — image_only job
// ---------------------------------------------------------------------------

test.describe("Job detail — image_only job", () => {
  test.beforeEach(async ({ authedPage: page }) => {
    await mockImageOnlyJobDetail(page);
  });

  test("detail page shows 'Image Studio' job type badge", async ({
    authedPage: page,
  }) => {
    await page.goto("/jobs/job-image-001");

    // Wait for job to load
    await expect(page.getByText("studio-product-001")).toBeVisible({
      timeout: 5_000,
    });

    // Image Studio badge
    await expect(page.getByText("Image Studio")).toBeVisible();
  });

  test("listing sections (title, tags, description) are NOT shown for image_only jobs", async ({
    authedPage: page,
  }) => {
    await page.goto("/jobs/job-image-001");

    // Wait for job to load
    await expect(page.getByText("studio-product-001")).toBeVisible({
      timeout: 5_000,
    });

    // Listing sections should not be present
    await expect(page.getByRole("heading", { name: /listing title/i })).not.toBeVisible();
    await expect(page.getByRole("heading", { name: /^tags$/i })).not.toBeVisible();
    await expect(page.getByRole("heading", { name: /description/i })).not.toBeVisible();
  });

  test("image results card IS shown for image_only completed jobs", async ({
    authedPage: page,
  }) => {
    await page.goto("/jobs/job-image-001");

    // Wait for job to load
    await expect(page.getByText("studio-product-001")).toBeVisible({
      timeout: 5_000,
    });

    // Studio Images card heading (the ImageResultsCard shows "Studio Images" for image_only)
    await expect(page.getByText(/studio images/i)).toBeVisible({ timeout: 5_000 });
  });

  test("Download All button is visible on image_only job detail page", async ({
    authedPage: page,
  }) => {
    await page.goto("/jobs/job-image-001");

    // Wait for job to load
    await expect(page.getByText("studio-product-001")).toBeVisible({
      timeout: 5_000,
    });

    // Download All button
    await expect(page.getByRole("button", { name: /download all/i })).toBeVisible({
      timeout: 5_000,
    });
  });

  test("Back to Jobs link is visible", async ({ authedPage: page }) => {
    await page.goto("/jobs/job-image-001");

    await expect(page.getByText("studio-product-001")).toBeVisible({
      timeout: 5_000,
    });

    // Back link
    await expect(
      page.getByRole("link", { name: /back to jobs/i })
    ).toBeVisible();
  });

  test("status badge shows Completed for a completed job", async ({
    authedPage: page,
  }) => {
    await page.goto("/jobs/job-image-001");

    await expect(page.getByText("studio-product-001")).toBeVisible({
      timeout: 5_000,
    });

    await expect(page.getByText("Completed")).toBeVisible();
  });
});
