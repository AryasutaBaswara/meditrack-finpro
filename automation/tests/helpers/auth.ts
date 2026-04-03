import process from "node:process";

import { APIRequestContext, expect } from "@playwright/test";

type RequestContextOptions = {
  baseURL?: string;
  extraHTTPHeaders?: Record<string, string>;
};

type PlaywrightLike = {
  request: {
    newContext(options?: RequestContextOptions): Promise<APIRequestContext>;
  };
};

type Role = "doctor" | "pharmacist" | "patient";

type RuntimeConfig = {
  baseUrl: string;
  keycloakBaseUrl: string;
  keycloakRealm: string;
  keycloakClientId: string;
  keycloakClientSecret: string;
  doctorUsername: string;
  doctorPassword: string;
  pharmacistUsername: string;
  pharmacistPassword: string;
  patientUsername: string;
  patientPassword: string;
};

type Credentials = {
  username: string;
  password: string;
};

type ApiEnvelope<T> = {
  data: T | null;
  error: { code: string; message: string } | null;
  meta: Record<string, unknown> | null;
};

function requireEnv(name: string, fallback?: string): string {
  const value = process.env[name] ?? fallback;
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

export function getRuntimeConfig(): RuntimeConfig {
  return {
    baseUrl: requireEnv("MEDITRACK_BASE_URL", "http://127.0.0.1:18000"),
    keycloakBaseUrl: requireEnv(
      "MEDITRACK_KEYCLOAK_BASE_URL",
      "http://127.0.0.1:18080",
    ),
    keycloakRealm: requireEnv("MEDITRACK_KEYCLOAK_REALM", "meditrack-staging"),
    keycloakClientId: requireEnv(
      "MEDITRACK_KEYCLOAK_CLIENT_ID",
      "meditrack-backend",
    ),
    keycloakClientSecret: requireEnv("MEDITRACK_KEYCLOAK_CLIENT_SECRET"),
    doctorUsername: requireEnv("MEDITRACK_DOCTOR_USERNAME", "doctor_stage"),
    doctorPassword: requireEnv("MEDITRACK_DOCTOR_PASSWORD"),
    pharmacistUsername: requireEnv(
      "MEDITRACK_PHARMACIST_USERNAME",
      "pharmacist_stage",
    ),
    pharmacistPassword: requireEnv("MEDITRACK_PHARMACIST_PASSWORD"),
    patientUsername: requireEnv("MEDITRACK_PATIENT_USERNAME", "patient_stage"),
    patientPassword: requireEnv("MEDITRACK_PATIENT_PASSWORD"),
  };
}

export async function requestAccessToken(
  request: APIRequestContext,
  credentials: Credentials,
): Promise<string> {
  const config = getRuntimeConfig();
  const response = await request.post(
    `${config.keycloakBaseUrl}/realms/${config.keycloakRealm}/protocol/openid-connect/token`,
    {
      form: {
        grant_type: "password",
        client_id: config.keycloakClientId,
        client_secret: config.keycloakClientSecret,
        username: credentials.username,
        password: credentials.password,
      },
    },
  );

  if (response.status() !== 200) {
    const responseBody = await response.text();
    throw new Error(
      [
        "Failed to obtain Keycloak access token",
        `status=${response.status()}`,
        `realm=${config.keycloakRealm}`,
        `client_id=${config.keycloakClientId}`,
        `username=${credentials.username}`,
        `body=${responseBody}`,
      ].join(" | "),
    );
  }

  const payload = await response.json();
  expect(payload.access_token).toBeTruthy();

  return payload.access_token as string;
}

export async function createAuthorizedContext(
  playwright: PlaywrightLike,
  role: Role,
  options: RequestContextOptions = {},
): Promise<APIRequestContext> {
  const config = getRuntimeConfig();
  const request = await playwright.request.newContext();

  let credentials: Credentials;
  switch (role) {
    case "doctor":
      credentials = {
        username: config.doctorUsername,
        password: config.doctorPassword,
      };
      break;
    case "pharmacist":
      credentials = {
        username: config.pharmacistUsername,
        password: config.pharmacistPassword,
      };
      break;
    case "patient":
      credentials = {
        username: config.patientUsername,
        password: config.patientPassword,
      };
      break;
    default:
      throw new Error(`Unsupported role: ${role satisfies never}`);
  }

  const token = await requestAccessToken(request, credentials);
  await request.dispose();

  return playwright.request.newContext({
    baseURL: config.baseUrl,
    extraHTTPHeaders: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
    ...options,
  });
}

export function getEnvelopeData<T>(payload: ApiEnvelope<T>): T {
  expect(payload.error).toBeNull();
  expect(payload.data).not.toBeNull();
  return payload.data as T;
}
