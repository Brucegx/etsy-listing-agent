/**
 * E2E tests: API key management (/settings/api-keys)
 *
 * Tests the full CRUD lifecycle for API keys:
 *   1. Page requires authentication
 *   2. Existing keys are listed
 *   3. User creates a new key and the full key is shown once
 *   4. User can copy the key value
 *   5. User can revoke an existing key
 *   6. Empty state shown when no keys exist
 *
 * All backend calls are mocked.
 */

import { test, expect } from "./fixtures";
import {
  mockApiKeysList,
  mockCreateApiKey,
  mockRevokeApiKey,
  MOCK_API_KEYS,
} from "./helpers/api-mocks";

const API_KEYS_URL = "/settings/api-keys";

// ---------------------------------------------------------------------------
// Auth gate
// ---------------------------------------------------------------------------

test.describe("API keys — authentication gate", () => {
  test("unauthenticated users are redirected to /", async ({
    unauthPage: page,
  }) => {
    await page.goto(API_KEYS_URL);
    await expect(page).toHaveURL("/", { timeout: 5_000 });
  });
});

// ---------------------------------------------------------------------------
// Listing existing keys
// ---------------------------------------------------------------------------

test.describe("API keys — listing", () => {
  test("shows existing keys for authenticated user", async ({
    authedPage: page,
  }) => {
    await mockApiKeysList(page);

    await page.goto(API_KEYS_URL);

    // Wait for keys to load
    await expect(page.getByTestId("keys-list")).toBeVisible({ timeout: 5_000 });

    // First key's name should be visible
    const firstKey = MOCK_API_KEYS[0];
    await expect(page.getByText(firstKey.name)).toBeVisible();

    // Key prefix should be visible
    await expect(page.getByText(new RegExp(firstKey.prefix))).toBeVisible();
  });

  test("shows empty state when no keys exist", async ({ authedPage: page }) => {
    // Mock empty keys list
    await page.route("**/api/keys", async (route) => {
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

    await page.goto(API_KEYS_URL);

    await expect(page.getByTestId("keys-empty")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText(/no api keys yet/i)).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Creating a key
// ---------------------------------------------------------------------------

test.describe("API keys — creation", () => {
  test.beforeEach(async ({ authedPage: page }) => {
    await mockApiKeysList(page);
    await mockCreateApiKey(page);
  });

  test("Create Key button is disabled when name is empty", async ({
    authedPage: page,
  }) => {
    await page.goto(API_KEYS_URL);

    const createBtn = page.getByTestId("create-key-btn");
    await expect(createBtn).toBeDisabled();
  });

  test("Create Key button enables when name is typed", async ({
    authedPage: page,
  }) => {
    await page.goto(API_KEYS_URL);

    await page.getByTestId("key-name-input").fill("Production");

    await expect(page.getByTestId("create-key-btn")).toBeEnabled();
  });

  test("creating a key shows the full key value in a banner", async ({
    authedPage: page,
  }) => {
    await page.goto(API_KEYS_URL);

    // Type a name and click Create
    await page.getByTestId("key-name-input").fill("My Test Key");
    await page.getByTestId("create-key-btn").click();

    // The new key banner should appear with the full key
    await expect(page.getByTestId("new-key-banner")).toBeVisible({
      timeout: 5_000,
    });

    // The full key value from the mock is "sk-live-abc123xyz456"
    await expect(page.getByTestId("new-key-value")).toContainText(
      "sk-live-abc123xyz456"
    );
  });

  test("copy button copies the new key to clipboard", async ({
    authedPage: page,
  }) => {
    // Grant clipboard permissions
    await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);

    await page.goto(API_KEYS_URL);

    await page.getByTestId("key-name-input").fill("Clipboard Test Key");
    await page.getByTestId("create-key-btn").click();

    // Wait for banner
    await expect(page.getByTestId("new-key-banner")).toBeVisible({
      timeout: 5_000,
    });

    // Click the copy button
    await page.getByTestId("copy-new-key-btn").click();

    // Button text should change to "Copied!"
    await expect(page.getByTestId("copy-new-key-btn")).toHaveText("Copied!", {
      timeout: 3_000,
    });

    // Verify clipboard content
    const clipboardText = await page.evaluate(() =>
      navigator.clipboard.readText()
    );
    expect(clipboardText).toBe("sk-live-abc123xyz456");
  });

  test("pressing Enter in the name input creates the key", async ({
    authedPage: page,
  }) => {
    await page.goto(API_KEYS_URL);

    await page.getByTestId("key-name-input").fill("Enter Key");
    await page.getByTestId("key-name-input").press("Enter");

    // Banner should appear
    await expect(page.getByTestId("new-key-banner")).toBeVisible({
      timeout: 5_000,
    });
  });

  test("input is cleared after key creation", async ({ authedPage: page }) => {
    await page.goto(API_KEYS_URL);

    await page.getByTestId("key-name-input").fill("Cleared After Create");
    await page.getByTestId("create-key-btn").click();

    // Wait for banner to appear (key created)
    await expect(page.getByTestId("new-key-banner")).toBeVisible({
      timeout: 5_000,
    });

    // Input should be empty
    await expect(page.getByTestId("key-name-input")).toHaveValue("");
  });
});

// ---------------------------------------------------------------------------
// Revoking a key
// ---------------------------------------------------------------------------

test.describe("API keys — revocation", () => {
  test("revoking a key removes it from the list", async ({
    authedPage: page,
  }) => {
    const keyToRevoke = MOCK_API_KEYS[0];

    // Setup mocks
    await mockApiKeysList(page);
    await mockRevokeApiKey(page, keyToRevoke.id);

    await page.goto(API_KEYS_URL);

    // Verify the key is visible
    await expect(
      page.getByTestId(`key-item-${keyToRevoke.id}`)
    ).toBeVisible({ timeout: 5_000 });

    // Click revoke
    await page.getByTestId(`revoke-key-btn-${keyToRevoke.id}`).click();

    // Key should be removed from the list
    await expect(
      page.getByTestId(`key-item-${keyToRevoke.id}`)
    ).not.toBeVisible({ timeout: 3_000 });
  });

  test("shows error when revoke fails", async ({ authedPage: page }) => {
    const keyToRevoke = MOCK_API_KEYS[0];

    await mockApiKeysList(page);

    // Mock revoke to fail
    await page.route(`**/api/keys/${keyToRevoke.id}`, async (route) => {
      if (route.request().method() === "DELETE") {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Internal server error" }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto(API_KEYS_URL);

    await expect(
      page.getByTestId(`key-item-${keyToRevoke.id}`)
    ).toBeVisible({ timeout: 5_000 });

    await page.getByTestId(`revoke-key-btn-${keyToRevoke.id}`).click();

    // Error message should appear
    await expect(page.getByTestId("keys-error")).toBeVisible({
      timeout: 3_000,
    });
  });

  test("copy prefix button shows Copied feedback", async ({
    authedPage: page,
  }) => {
    await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);

    await mockApiKeysList(page);

    const keyId = MOCK_API_KEYS[0].id;
    await page.goto(API_KEYS_URL);

    await expect(page.getByTestId(`copy-key-btn-${keyId}`)).toBeVisible({
      timeout: 5_000,
    });

    await page.getByTestId(`copy-key-btn-${keyId}`).click();

    await expect(page.getByTestId(`copy-key-btn-${keyId}`)).toHaveText(
      "Copied!",
      { timeout: 3_000 }
    );
  });
});

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

test.describe("API keys — navigation", () => {
  test("Dashboard button navigates to /dashboard", async ({
    authedPage: page,
  }) => {
    await mockApiKeysList(page);

    await page.goto(API_KEYS_URL);

    await page.getByRole("button", { name: /dashboard/i }).click();

    await expect(page).toHaveURL("/dashboard", { timeout: 5_000 });
  });

  test("page heading is visible", async ({ authedPage: page }) => {
    await mockApiKeysList(page);

    await page.goto(API_KEYS_URL);

    await expect(
      page.getByRole("heading", { name: /api keys/i })
    ).toBeVisible();
  });
});
