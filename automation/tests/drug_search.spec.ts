import { expect, test } from "@playwright/test";

import { createAuthorizedContext, getEnvelopeData } from "./helpers/auth";

test.describe("staging drug search smoke", () => {
  test("doctor can list paginated drugs", async ({ playwright, baseURL }) => {
    const api = await createAuthorizedContext(playwright, "doctor");
    const response = await api.get(`${baseURL}/api/v1/drugs?page=1&per_page=5`);

    expect(response.status()).toBe(200);

    const payload = await response.json();
    expect(payload.error).toBeNull();
    expect(payload.meta.total).toBeGreaterThan(0);
    expect(payload.data.length).toBeGreaterThan(0);
  });

  test("doctor can search drugs through Elasticsearch endpoint", async ({
    playwright,
    baseURL,
  }) => {
    const api = await createAuthorizedContext(playwright, "doctor");
    const response = await api.get(`${baseURL}/api/v1/drugs/search?q=para`);

    expect(response.status()).toBe(200);

    const data = getEnvelopeData<any[]>(await response.json());
    expect(data.length).toBeGreaterThan(0);
    expect(
      data.some((item) => String(item.name).toLowerCase().includes("para")),
    ).toBeTruthy();
  });
});
