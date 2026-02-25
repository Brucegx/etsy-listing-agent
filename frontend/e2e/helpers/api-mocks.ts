/**
 * API mock helpers for Playwright tests.
 *
 * All mocks intercept requests to http://localhost:8000 (the backend) and
 * return controlled JSON responses so tests run without a real backend.
 *
 * The Next.js frontend proxies `/api/*` to the backend via NEXT_PUBLIC_API_URL
 * which defaults to http://localhost:8000. Playwright intercepts at the network
 * level using page.route(), so we match both the direct backend URL and the
 * Next.js relative path.
 */

import type { Page, Route } from "@playwright/test";

// ---------------------------------------------------------------------------
// Fixture data
// ---------------------------------------------------------------------------

export const MOCK_USER = {
  google_id: "123456789",
  email: "test@example.com",
  name: "Test User",
};

export const MOCK_JOB_QUEUED = {
  job_id: "job-abc-123",
  status: "queued",
  product_id: "product-001",
  created_at: new Date().toISOString(),
};

export const MOCK_JOB_COMPLETED = {
  job_id: "job-abc-123",
  status: "completed",
  product_id: "product-001",
  created_at: new Date().toISOString(),
  results: {
    listing: {
      title: "Handmade Silver Ring",
      description: "Beautiful handcrafted ring",
      tags: "silver, ring, handmade",
    },
  },
};

export const MOCK_JOBS_LIST = [
  {
    id: 1,
    product_id: "product-001",
    category: "jewelry",
    status: "completed",
    cost_usd: 0.05,
    created_at: new Date().toISOString(),
  },
  {
    id: 2,
    product_id: "product-002",
    category: "jewelry",
    status: "queued",
    cost_usd: 0,
    created_at: new Date().toISOString(),
  },
];

export const MOCK_DRIVE_FOLDERS = {
  folders: [
    {
      id: "folder-001",
      name: "Silver Rings Collection",
      mimeType: "application/vnd.google-apps.folder",
      modifiedTime: "2024-01-15T10:00:00Z",
    },
    {
      id: "folder-002",
      name: "Gold Necklaces",
      mimeType: "application/vnd.google-apps.folder",
      modifiedTime: "2024-01-14T09:00:00Z",
    },
  ],
};

export const MOCK_DRIVE_FILES = {
  files: [
    {
      id: "file-excel-001",
      name: "products.xlsx",
      mimeType:
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      size: "12345",
      modifiedTime: "2024-01-15T10:00:00Z",
    },
    {
      id: "file-img-001",
      name: "ring-front.jpg",
      mimeType: "image/jpeg",
      size: "234567",
      modifiedTime: "2024-01-15T09:30:00Z",
    },
  ],
};

export const MOCK_PRODUCTS = {
  products: ["product-001", "product-002", "product-003"],
  category: "jewelry",
};

export const MOCK_API_KEYS = [
  {
    id: "key-001",
    name: "My API Key",
    prefix: "sk-test",
    created_at: new Date().toISOString(),
    last_used: null,
  },
];

// ---------------------------------------------------------------------------
// Route pattern helpers
// ---------------------------------------------------------------------------

/** Match any URL that ends with the given path suffix. */
function matchesPath(url: string, path: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.pathname === path || parsed.pathname.startsWith(path + "?");
  } catch {
    return url.includes(path);
  }
}

// ---------------------------------------------------------------------------
// Auth mocks
// ---------------------------------------------------------------------------

/** Mock /api/auth/me to return a signed-in user. */
export async function mockAuthenticatedUser(page: Page): Promise<void> {
  await page.route("**/api/auth/me", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_USER),
    });
  });
}

/** Mock /api/auth/me to return 401 (not signed in). */
export async function mockUnauthenticated(page: Page): Promise<void> {
  await page.route("**/api/auth/me", async (route: Route) => {
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Not authenticated" }),
    });
  });
}

// ---------------------------------------------------------------------------
// Upload / Generate mocks
// ---------------------------------------------------------------------------

/**
 * Mock POST /api/generate/upload to return a queued job.
 * The mock SSE stream sends: start → progress → complete events.
 */
export async function mockUploadAndGenerate(page: Page): Promise<void> {
  await page.route("**/api/generate/upload", async (route: Route) => {
    // SSE response
    const sseLines = [
      `event: start\ndata: ${JSON.stringify({ product_id: "upload-product", status: "running" })}\n\n`,
      `event: progress\ndata: ${JSON.stringify({ stage: "preprocessing", node: "preprocess", message: "Preprocessing images" })}\n\n`,
      `event: progress\ndata: ${JSON.stringify({ stage: "strategy", node: "strategy", message: "Analyzing product" })}\n\n`,
      `event: strategy_complete\ndata: ${JSON.stringify({ strategy: { $schema: "v2", product_id: "upload-product", analysis: { product_usps: ["Handmade"], target_customer: "Etsy shoppers", purchase_barriers: [], competitive_gap: "" }, slots: [] } })}\n\n`,
      `event: complete\ndata: ${JSON.stringify({ product_id: "upload-product", status: "completed", results: { listing: { title: "Test Listing", description: "Test description", tags: "test, listing" } } })}\n\n`,
    ];

    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
      body: sseLines.join(""),
    });
  });
}

// ---------------------------------------------------------------------------
// Job dashboard mocks
// ---------------------------------------------------------------------------

/** Mock GET /api/jobs to return a list of jobs. */
export async function mockJobsList(page: Page): Promise<void> {
  await page.route("**/api/jobs", async (route: Route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_JOBS_LIST),
      });
    } else {
      await route.continue();
    }
  });
}

/** Mock GET /api/jobs/:id to return a specific job. */
export async function mockJobStatus(
  page: Page,
  jobId: string,
  job: object
): Promise<void> {
  await page.route(`**/api/jobs/${jobId}`, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(job),
    });
  });
}

// ---------------------------------------------------------------------------
// Drive mocks
// ---------------------------------------------------------------------------

/** Mock GET /api/drive/folders to return folder list. */
export async function mockDriveFolders(page: Page): Promise<void> {
  await page.route("**/api/drive/folders**", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_DRIVE_FOLDERS),
    });
  });
}

/** Mock GET /api/drive/files/:folderId to return file list. */
export async function mockDriveFiles(page: Page): Promise<void> {
  await page.route("**/api/drive/files/**", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_DRIVE_FILES),
    });
  });
}

/** Mock GET /api/products to return product list. */
export async function mockProducts(page: Page): Promise<void> {
  await page.route("**/api/products**", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_PRODUCTS),
    });
  });
}

/**
 * Mock POST /api/generate/single to return SSE stream for product generation.
 */
export async function mockProductGenerate(page: Page): Promise<void> {
  await page.route("**/api/generate/single", async (route: Route) => {
    const sseLines = [
      `event: start\ndata: ${JSON.stringify({ product_id: "product-001", status: "running" })}\n\n`,
      `event: progress\ndata: ${JSON.stringify({ stage: "preprocessing", node: "preprocess", message: "Loading product data" })}\n\n`,
      `event: progress\ndata: ${JSON.stringify({ stage: "listing", node: "listing", message: "Generating listing" })}\n\n`,
      `event: complete\ndata: ${JSON.stringify({ product_id: "product-001", status: "completed", results: { listing: { title: "Silver Ring", description: "Handmade ring", tags: "ring, silver, handmade" }, prompts: { prompts: [{ index: 1, type: "macro_detail", prompt: "Close-up of silver ring on white marble" }] } } })}\n\n`,
    ];

    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
      body: sseLines.join(""),
    });
  });
}

// ---------------------------------------------------------------------------
// API key mocks
// ---------------------------------------------------------------------------

/** Mock GET /api/keys to return key list. */
export async function mockApiKeysList(page: Page): Promise<void> {
  await page.route("**/api/keys", async (route: Route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_API_KEYS),
      });
    } else {
      await route.continue();
    }
  });
}

/** Mock POST /api/keys to create a new key. */
export async function mockCreateApiKey(page: Page): Promise<void> {
  await page.route("**/api/keys", async (route: Route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: "key-new-001",
          name: "New Key",
          key: "sk-live-abc123xyz456",
          prefix: "sk-live",
          created_at: new Date().toISOString(),
        }),
      });
    } else {
      await route.continue();
    }
  });
}

/** Mock DELETE /api/keys/:id to revoke a key. */
export async function mockRevokeApiKey(page: Page, keyId: string): Promise<void> {
  await page.route(`**/api/keys/${keyId}`, async (route: Route) => {
    if (route.request().method() === "DELETE") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "deleted" }),
      });
    } else {
      await route.continue();
    }
  });
}
