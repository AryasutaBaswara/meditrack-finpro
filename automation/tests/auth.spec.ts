import { expect, test } from "@playwright/test";

import {
  createAuthorizedContext,
  getRuntimeConfig,
  requestAccessToken,
} from "./helpers/auth";

test.describe("staging auth smoke", () => {
  test("health endpoint responds with ok envelope", async ({
    request,
    baseURL,
  }) => {
    const response = await request.get(`${baseURL}/api/v1/health`);

    expect(response.status()).toBe(200);

    const payload = await response.json();
    expect(payload.error).toBeNull();
    expect(payload.data.status).toBe("ok");
  });

  test("unauthenticated drug listing is rejected", async ({
    request,
    baseURL,
  }) => {
    const response = await request.get(
      `${baseURL}/api/v1/drugs?page=1&per_page=5`,
    );

    expect(response.status()).toBe(401);

    const payload = await response.json();
    expect(payload.data).toBeNull();
    expect(payload.error.code).toBeTruthy();
  });

  test("doctor credentials can obtain an access token", async ({
    playwright,
  }) => {
    const config = getRuntimeConfig();
    const token = await requestAccessToken(
      await playwright.request.newContext(),
      {
        username: config.doctorUsername,
        password: config.doctorPassword,
      },
    );

    expect(token.length).toBeGreaterThan(20);
  });

  test("doctor token can access protected drugs endpoint", async ({
    playwright,
    baseURL,
  }) => {
    const api = await createAuthorizedContext(playwright, "doctor");
    const response = await api.get(`${baseURL}/api/v1/drugs?page=1&per_page=5`);

    expect(response.status()).toBe(200);

    const payload = await response.json();
    expect(payload.error).toBeNull();
    expect(Array.isArray(payload.data)).toBeTruthy();
    expect(payload.meta.page).toBe(1);
  });
});
