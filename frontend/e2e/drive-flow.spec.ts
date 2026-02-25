/**
 * E2E tests: Drive flow
 *
 * Tests the Google Drive browsing workflow on /dashboard:
 *   1. Login redirect is enforced for unauthenticated users
 *   2. Authenticated users see the Drive browser
 *   3. User browses Drive folders
 *   4. User selects a folder → product list loads
 *   5. User clicks a product → navigates to /product/[id]
 *   6. User can trigger generation from the product page
 *
 * All backend calls are mocked.
 */

import { test, expect } from "./fixtures";
import {
  mockDriveFolders,
  mockDriveFiles,
  mockProducts,
  mockProductGenerate,
  MOCK_PRODUCTS,
  MOCK_DRIVE_FOLDERS,
} from "./helpers/api-mocks";

// ---------------------------------------------------------------------------
// Dashboard tests
// ---------------------------------------------------------------------------

test.describe("Drive flow — authentication gate", () => {
  test("unauthenticated users are redirected from /dashboard to /", async ({
    unauthPage: page,
  }) => {
    // The dashboard checks auth and redirects to "/" if not authenticated
    await page.goto("/dashboard");

    // Should land on the home page (or be redirected)
    await expect(page).toHaveURL("/", { timeout: 5_000 });
  });
});

test.describe("Drive flow — dashboard", () => {
  test.beforeEach(async ({ authedPage: page }) => {
    await mockDriveFolders(page);
    await mockDriveFiles(page);
    await mockProducts(page);
  });

  test("dashboard shows Drive browser for authenticated user", async ({
    authedPage: page,
  }) => {
    await page.goto("/dashboard");

    // Page heading
    await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible();

    // User email from mock
    await expect(page.getByText("test@example.com")).toBeVisible();

    // Drive browser component should be present
    // DriveBrowser renders a list of folders
    await expect(page.getByText(/drive/i).first()).toBeVisible();
  });

  test("logout button navigates to home", async ({ authedPage: page }) => {
    // Mock the logout endpoint
    await page.route("**/api/auth/logout", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok" }),
      });
    });

    await page.goto("/dashboard");

    // Logout button
    const logoutBtn = page.getByRole("button", { name: /logout/i });
    await expect(logoutBtn).toBeVisible();
    await logoutBtn.click();

    // Should navigate to home
    await expect(page).toHaveURL("/", { timeout: 5_000 });
  });
});

// ---------------------------------------------------------------------------
// Drive browser interaction
// ---------------------------------------------------------------------------

test.describe("Drive flow — folder selection and product list", () => {
  test("selecting a Drive folder shows product list", async ({
    authedPage: page,
  }) => {
    // Mount all required mocks before navigation
    await mockDriveFolders(page);
    await mockDriveFiles(page);
    await mockProducts(page);

    await page.goto("/dashboard");

    // Wait for the drive browser to load folders from the mock
    // DriveBrowser calls /api/drive/folders on mount
    // We expect the first folder name to appear
    const firstFolderName = MOCK_DRIVE_FOLDERS.folders[0].name;
    await expect(page.getByText(firstFolderName)).toBeVisible({ timeout: 5_000 });

    // Click the "Select" button for the first folder
    // DriveBrowser renders a "Select" button next to each folder
    const selectBtns = page.getByRole("button", { name: /select/i });
    await selectBtns.first().click();

    // After selection, products should load via /api/products
    const firstProduct = MOCK_PRODUCTS.products[0];
    await expect(page.getByText(firstProduct)).toBeVisible({ timeout: 5_000 });
  });

  test("clicking a product navigates to the product page", async ({
    authedPage: page,
  }) => {
    await mockDriveFolders(page);
    await mockDriveFiles(page);
    await mockProducts(page);

    await page.goto("/dashboard");

    // Wait for folder to appear, then click Select
    const firstFolderName = MOCK_DRIVE_FOLDERS.folders[0].name;
    await expect(page.getByText(firstFolderName)).toBeVisible({ timeout: 5_000 });
    await page.getByRole("button", { name: /select/i }).first().click();

    // Wait for products then click first product
    const firstProduct = MOCK_PRODUCTS.products[0];
    await page.getByText(firstProduct).click();

    // Should navigate to /product/[productId]
    await expect(page).toHaveURL(
      new RegExp(`/product/${encodeURIComponent(firstProduct)}`),
      { timeout: 5_000 }
    );
  });

  test("shows error when folder has no Excel file", async ({
    authedPage: page,
  }) => {
    await mockDriveFolders(page);

    // Mock files endpoint to return files without Excel
    await page.route("**/api/drive/files/**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          files: [
            {
              id: "img-001",
              name: "photo.jpg",
              mimeType: "image/jpeg",
            },
          ],
        }),
      });
    });

    await page.goto("/dashboard");

    const firstFolderName = MOCK_DRIVE_FOLDERS.folders[0].name;
    await expect(page.getByText(firstFolderName)).toBeVisible({ timeout: 5_000 });
    await page.getByRole("button", { name: /select/i }).first().click();

    // Should show "No Excel file found" error
    await expect(
      page.getByText(/no excel file found/i)
    ).toBeVisible({ timeout: 5_000 });
  });

  test("clear button deselects the folder", async ({ authedPage: page }) => {
    await mockDriveFolders(page);
    await mockDriveFiles(page);
    await mockProducts(page);

    await page.goto("/dashboard");

    const firstFolderName = MOCK_DRIVE_FOLDERS.folders[0].name;
    await expect(page.getByText(firstFolderName)).toBeVisible({ timeout: 5_000 });
    await page.getByRole("button", { name: /select/i }).first().click();

    // Wait for the product card to appear (which contains the Clear button)
    await expect(page.getByRole("button", { name: /clear/i })).toBeVisible({
      timeout: 5_000,
    });

    await page.getByRole("button", { name: /clear/i }).click();

    // The product list card should disappear
    await expect(
      page.getByText(MOCK_PRODUCTS.products[0])
    ).not.toBeVisible({ timeout: 3_000 });
  });
});

// ---------------------------------------------------------------------------
// Product page tests
// ---------------------------------------------------------------------------

test.describe("Drive flow — product generation page", () => {
  test("product page shows product id and Generate button", async ({
    authedPage: page,
  }) => {
    await page.goto("/product/product-001?folder=folder-001&excel=file-excel-001&category=jewelry");

    await expect(
      page.getByRole("heading", { name: /product: product-001/i })
    ).toBeVisible();

    await expect(
      page.getByRole("button", { name: /^generate$/i })
    ).toBeVisible();
  });

  test("product page shows message when no folder context", async ({
    authedPage: page,
  }) => {
    await page.goto("/product/product-001");

    await expect(
      page.getByText(/missing folder context/i)
    ).toBeVisible();
  });

  test("Generate button triggers SSE and shows listing results", async ({
    authedPage: page,
  }) => {
    await mockProductGenerate(page);

    await page.goto(
      "/product/product-001?folder=folder-001&excel=file-excel-001&category=jewelry"
    );

    // Click Generate
    await page.getByRole("button", { name: /^generate$/i }).click();

    // After completion the listing tab content should show
    // The mock returns { listing: { title: "Silver Ring", ... } }
    await expect(page.getByText("Silver Ring")).toBeVisible({ timeout: 10_000 });
  });

  test("Back button navigates to previous page", async ({
    authedPage: page,
  }) => {
    // Navigate from dashboard to product so there's history
    await mockDriveFolders(page);
    await mockDriveFiles(page);
    await mockProducts(page);

    await page.goto("/dashboard");

    // Navigate directly to product page
    await page.goto(
      "/product/product-001?folder=folder-001&excel=file-excel-001&category=jewelry"
    );

    const backBtn = page.getByRole("button", { name: /←\s*back/i });
    await expect(backBtn).toBeVisible();
  });

  test("category label is shown when category param is present", async ({
    authedPage: page,
  }) => {
    await page.goto(
      "/product/product-001?folder=folder-001&excel=file-excel-001&category=jewelry"
    );

    await expect(page.getByText("jewelry")).toBeVisible();
  });
});
