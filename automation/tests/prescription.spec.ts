import { expect, test } from "@playwright/test";

import { createAuthorizedContext, getEnvelopeData } from "./helpers/auth";

test.describe("staging prescription smoke", () => {
  test("doctor can create prescription with interaction and stock results", async ({
    playwright,
    baseURL,
  }) => {
    const api = await createAuthorizedContext(playwright, "doctor");

    const patientResponse = await api.get(
      `${baseURL}/api/v1/patients?page=1&per_page=1`,
    );
    expect(patientResponse.status()).toBe(200);
    const patients = getEnvelopeData<Array<{ id: string }>>(
      await patientResponse.json(),
    );
    expect(patients.length).toBeGreaterThan(0);

    const drugsResponse = await api.get(
      `${baseURL}/api/v1/drugs?page=1&per_page=2`,
    );
    expect(drugsResponse.status()).toBe(200);
    const drugs = getEnvelopeData<Array<{ id: string }>>(
      await drugsResponse.json(),
    );
    expect(drugs.length).toBeGreaterThanOrEqual(1);

    const createResponse = await api.post(`${baseURL}/api/v1/prescriptions`, {
      data: {
        patient_id: patients[0].id,
        notes: "Smoke test prescription",
        items: [
          {
            drug_id: drugs[0].id,
            dosage: "500mg",
            frequency: "2x daily",
            duration: "3 days",
            quantity: 1,
          },
        ],
      },
    });

    expect(createResponse.status()).toBe(201);

    const payload = await createResponse.json();
    expect(payload.error).toBeNull();
    expect(payload.data.id).toBeTruthy();
    expect(payload.data.interaction_check_result).toBeTruthy();
    expect(payload.data.interaction_check_result.details).toBeTruthy();
    expect(payload.data.stock_check_result).toBeTruthy();
    expect(payload.data.stock_check_result.status).toBeTruthy();
    expect(payload.data.items).toHaveLength(1);
  });

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

  test("pharmacist can dispense a validated prescription", async ({
    playwright,
    baseURL,
  }) => {
    const doctorApi = await createAuthorizedContext(playwright, "doctor");

    const patientResponse = await doctorApi.get(
      `${baseURL}/api/v1/patients?page=1&per_page=1`,
    );
    expect(patientResponse.status()).toBe(200);
    const patients = getEnvelopeData<Array<{ id: string }>>(
      await patientResponse.json(),
    );
    expect(patients.length).toBeGreaterThan(0);

    const drugsResponse = await doctorApi.get(
      `${baseURL}/api/v1/drugs?page=1&per_page=1`,
    );
    expect(drugsResponse.status()).toBe(200);
    const drugs = getEnvelopeData<Array<{ id: string }>>(
      await drugsResponse.json(),
    );
    expect(drugs.length).toBeGreaterThan(0);

    const createResponse = await doctorApi.post(
      `${baseURL}/api/v1/prescriptions`,
      {
        data: {
          patient_id: patients[0].id,
          notes: "Smoke test for dispensation",
          items: [
            {
              drug_id: drugs[0].id,
              dosage: "250mg",
              frequency: "1x daily",
              duration: "2 days",
              quantity: 1,
            },
          ],
        },
      },
    );
    expect(createResponse.status()).toBe(201);
    const createdPrescription = getEnvelopeData<{
      id: string;
      status: string;
    }>(await createResponse.json());
    expect(createdPrescription.status).toBe("validated");

    const pharmacistApi = await createAuthorizedContext(
      playwright,
      "pharmacist",
    );
    const dispenseResponse = await pharmacistApi.post(
      `${baseURL}/api/v1/dispensations`,
      {
        data: {
          prescription_id: createdPrescription.id,
          notes: "Dispensed during smoke test",
        },
      },
    );

    expect(dispenseResponse.status()).toBe(201);
    const dispensation = getEnvelopeData<{
      id: string;
      prescription_id: string;
      pharmacist_id: string;
    }>(await dispenseResponse.json());
    expect(dispensation.id).toBeTruthy();
    expect(dispensation.prescription_id).toBe(createdPrescription.id);
    expect(dispensation.pharmacist_id).toBeTruthy();
  });

  test("patient can download own prescription report", async ({
    playwright,
    baseURL,
  }) => {
    const patientApi = await createAuthorizedContext(playwright, "patient");
    const prescriptionsResponse = await patientApi.get(
      `${baseURL}/api/v1/prescriptions?page=1&per_page=5`,
    );

    expect(prescriptionsResponse.status()).toBe(200);
    const prescriptions = getEnvelopeData<Array<{ id: string }>>(
      await prescriptionsResponse.json(),
    );
    expect(prescriptions.length).toBeGreaterThan(0);

    const reportResponse = await patientApi.get(
      `${baseURL}/api/v1/reports/prescription/${prescriptions[0].id}`,
    );

    expect(reportResponse.status()).toBe(200);
    expect(reportResponse.headers()["content-type"]).toContain(
      "application/pdf",
    );
    expect(reportResponse.headers()["content-disposition"]).toContain(
      `prescription-${prescriptions[0].id}.pdf`,
    );
  });
});
