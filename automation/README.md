# Automation

This folder contains staging automation for MediTrack's backend-only API.

## Playwright smoke tests

These tests use Playwright's API testing support rather than browser UI automation.

Required environment variables:

- `MEDITRACK_BASE_URL`
- `MEDITRACK_KEYCLOAK_BASE_URL`
- `MEDITRACK_KEYCLOAK_REALM`
- `MEDITRACK_KEYCLOAK_CLIENT_ID`
- `MEDITRACK_KEYCLOAK_CLIENT_SECRET`
- `MEDITRACK_DOCTOR_USERNAME`
- `MEDITRACK_DOCTOR_PASSWORD`
- `MEDITRACK_PHARMACIST_USERNAME`
- `MEDITRACK_PHARMACIST_PASSWORD`
- `MEDITRACK_PATIENT_USERNAME`
- `MEDITRACK_PATIENT_PASSWORD`

Local run example:

```powershell
$env:MEDITRACK_BASE_URL = 'http://127.0.0.1:18000'
$env:MEDITRACK_KEYCLOAK_BASE_URL = 'http://127.0.0.1:18080'
$env:MEDITRACK_KEYCLOAK_CLIENT_SECRET = '...'
$env:MEDITRACK_PHARMACIST_USERNAME = 'pharmacist_stage'
$env:MEDITRACK_PHARMACIST_PASSWORD = '...'
$env:MEDITRACK_PATIENT_USERNAME = 'patient_stage'
$env:MEDITRACK_PATIENT_PASSWORD = '...'
$env:MEDITRACK_DOCTOR_PASSWORD = '...'
npm install
npm run test:smoke
```

## Locust load test

The load suite is read-only and targets search plus patient listing with a doctor token.

Required environment variables:

- `MEDITRACK_BASE_URL`
- `MEDITRACK_KEYCLOAK_BASE_URL`
- `MEDITRACK_KEYCLOAK_REALM`
- `MEDITRACK_KEYCLOAK_CLIENT_ID`
- `MEDITRACK_KEYCLOAK_CLIENT_SECRET`
- `MEDITRACK_DOCTOR_USERNAME`
- `MEDITRACK_DOCTOR_PASSWORD`

Local run example:

```powershell
$env:MEDITRACK_BASE_URL = 'http://127.0.0.1:18000'
$env:MEDITRACK_KEYCLOAK_BASE_URL = 'http://127.0.0.1:18080'
$env:MEDITRACK_KEYCLOAK_CLIENT_SECRET = '...'
$env:MEDITRACK_DOCTOR_PASSWORD = '...'
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r load/requirements.txt
locust -f load/locustfile.py --headless --users 10 --spawn-rate 2 --run-time 2m
```

## Recommended workflow usage

- Run smoke tests after a successful staging deployment.
- Run load tests manually with `workflow_dispatch` or on-demand from the self-hosted runner.
- Avoid running load tests automatically on every push.
