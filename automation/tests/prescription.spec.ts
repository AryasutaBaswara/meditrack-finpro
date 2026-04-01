import { expect, test } from "@playwright/test";

import { createAuthorizedContext, getEnvelopeData } from "./helpers/auth";

test.describe("staging prescription smoke", () => {
  test("doctor can list patients", async ({ playwright, baseURL }) => {
    const api = await createAuthorizedContext(playwright, "doctor");
    const response = await api.get(
      `${baseURL}/api/v1/patients?page=1&per_page=10`,
    );

    expect(response.status()).toBe(200);

    const payload = await response.json();
    expect(payload.error).toBeNull();
    expect(payload.meta.total).toBeGreaterThan(0);
    expect(payload.data.length).toBeGreaterThan(0);
  });

  test("doctor can list prescriptions", async ({ playwright, baseURL }) => {
    const api = await createAuthorizedContext(playwright, "doctor");
    const response = await api.get(
      `${baseURL}/api/v1/prescriptions?page=1&per_page=10`,
    );

    expect(response.status()).toBe(200);

    const payload = await response.json();
    expect(payload.error).toBeNull();
    expect(Array.isArray(payload.data)).toBeTruthy();
  });

  test("doctor can call interaction check with seeded drugs", async ({
    playwright,
    baseURL,
  }) => {
    const api = await createAuthorizedContext(playwright, "doctor");
    const listResponse = await api.get(
      `${baseURL}/api/v1/drugs?page=1&per_page=2`,
    );
    expect(listResponse.status()).toBe(200);

    const drugs = getEnvelopeData<Array<{ id: string }>>(
      await listResponse.json(),
    );
    expect(drugs.length).toBeGreaterThanOrEqual(2);

    const response = await api.post(`${baseURL}/api/v1/ai/check-interactions`, {
      data: { drug_ids: drugs.slice(0, 2).map((drug) => drug.id) },
    });

    expect(response.status()).toBe(200);

    const payload = await response.json();
    expect(payload.error).toBeNull();
    expect(payload.data.details).toBeTruthy();
    expect(Array.isArray(payload.data.drugs_checked)).toBeTruthy();
  });
});
