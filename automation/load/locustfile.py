from __future__ import annotations

import os
from typing import Any

from locust import HttpUser, between, task

from helpers.auth import fetch_access_token


class MediTrackBaseUser(HttpUser):
    wait_time = between(1, 3)
    abstract = True
    username_env: str = ""
    password_env: str = ""
    default_username: str = ""

    def on_start(self) -> None:
        base_url = os.environ.get("MEDITRACK_BASE_URL", "http://127.0.0.1:18000")
        keycloak_base_url = os.environ.get(
            "MEDITRACK_KEYCLOAK_BASE_URL",
            "http://127.0.0.1:18080",
        )
        realm = os.environ.get("MEDITRACK_KEYCLOAK_REALM", "meditrack-staging")
        client_id = os.environ.get("MEDITRACK_KEYCLOAK_CLIENT_ID", "meditrack-backend")
        client_secret = os.environ.get("MEDITRACK_KEYCLOAK_CLIENT_SECRET")
        username = os.environ.get(self.username_env, self.default_username)
        password = os.environ.get(self.password_env)

        if not client_secret:
            raise RuntimeError("Missing MEDITRACK_KEYCLOAK_CLIENT_SECRET")
        if not password:
            raise RuntimeError(f"Missing {self.password_env}")

        self.client.base_url = base_url.rstrip("/")
        access_token = fetch_access_token(
            keycloak_base_url=keycloak_base_url,
            realm=realm,
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            password=password,
        )
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        host_header = os.environ.get("MEDITRACK_HTTP_HOST_HEADER")
        if host_header:
            self.headers["Host"] = host_header

    def _assert_success_envelope(self, response, *, expect_meta: bool = False) -> None:
        if response.status_code != 200:
            response.failure(f"unexpected status: {response.status_code}")
            return

        payload: dict[str, Any] = response.json()
        if payload.get("error") is not None:
            response.failure(f"unexpected envelope error: {payload['error']}")
            return

        if expect_meta and payload.get("meta") is None:
            response.failure("expected pagination metadata in response envelope")
            return

        response.success()


class DoctorLoadUser(MediTrackBaseUser):
    weight = 4
    username_env = "MEDITRACK_DOCTOR_USERNAME"
    password_env = "MEDITRACK_DOCTOR_PASSWORD"
    default_username = "doctor_stage"

    @task(3)
    def search_drugs(self) -> None:
        with self.client.get(
            "/api/v1/drugs/search?q=para",
            headers=self.headers,
            name="GET /api/v1/drugs/search",
            catch_response=True,
        ) as response:
            self._assert_success_envelope(response)

    @task(2)
    def list_drugs(self) -> None:
        with self.client.get(
            "/api/v1/drugs?page=1&per_page=10",
            headers=self.headers,
            name="GET /api/v1/drugs",
            catch_response=True,
        ) as response:
            self._assert_success_envelope(response, expect_meta=True)

    @task(1)
    def list_patients(self) -> None:
        with self.client.get(
            "/api/v1/patients?page=1&per_page=10",
            headers=self.headers,
            name="GET /api/v1/patients",
            catch_response=True,
        ) as response:
            self._assert_success_envelope(response, expect_meta=True)

    @task(1)
    def list_prescriptions(self) -> None:
        with self.client.get(
            "/api/v1/prescriptions?page=1&per_page=10",
            headers=self.headers,
            name="GET /api/v1/prescriptions (doctor)",
            catch_response=True,
        ) as response:
            self._assert_success_envelope(response, expect_meta=True)


class PharmacistLoadUser(MediTrackBaseUser):
    weight = 2
    username_env = "MEDITRACK_PHARMACIST_USERNAME"
    password_env = "MEDITRACK_PHARMACIST_PASSWORD"
    default_username = "pharmacist_stage"

    @task(2)
    def list_prescriptions(self) -> None:
        with self.client.get(
            "/api/v1/prescriptions?page=1&per_page=10",
            headers=self.headers,
            name="GET /api/v1/prescriptions (pharmacist)",
            catch_response=True,
        ) as response:
            self._assert_success_envelope(response, expect_meta=True)


class PatientLoadUser(MediTrackBaseUser):
    weight = 1
    username_env = "MEDITRACK_PATIENT_USERNAME"
    password_env = "MEDITRACK_PATIENT_PASSWORD"
    default_username = "patient_stage"

    @task(2)
    def list_own_prescriptions(self) -> None:
        with self.client.get(
            "/api/v1/prescriptions?page=1&per_page=10",
            headers=self.headers,
            name="GET /api/v1/prescriptions (patient)",
            catch_response=True,
        ) as response:
            self._assert_success_envelope(response, expect_meta=True)
