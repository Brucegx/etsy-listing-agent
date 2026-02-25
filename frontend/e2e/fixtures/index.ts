/**
 * Playwright fixtures that extend the base test with:
 *  - `authedPage`   — a page pre-configured with auth mock (GET /api/auth/me returns a user)
 *  - `apiMocks`     — convenience helper already bound to the current page
 *
 * Usage:
 *   import { test, expect } from '../fixtures';
 *   test('my test', async ({ authedPage }) => { ... });
 */

import { test as base, type Page } from "@playwright/test";
import { mockAuthenticatedUser, mockUnauthenticated } from "../helpers/api-mocks";

export type Fixtures = {
  /** A page where /api/auth/me returns a logged-in user. */
  authedPage: Page;
  /** A page where /api/auth/me returns 401 (unauthenticated). */
  unauthPage: Page;
};

export const test = base.extend<Fixtures>({
  authedPage: async ({ page }, use) => {
    await mockAuthenticatedUser(page);
    await use(page);
  },

  unauthPage: async ({ page }, use) => {
    await mockUnauthenticated(page);
    await use(page);
  },
});

export { expect } from "@playwright/test";
