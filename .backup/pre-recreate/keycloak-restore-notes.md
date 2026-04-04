# Keycloak Backup Notes

Backed up from live pod `staging-keycloak-585fb489b5-f4xhj` in namespace `meditrack-staging` on 2026-04-04.

Files:

- `keycloak-realm-live.json`: live realm settings export
- `keycloak-users-live.json`: live user list export
- `keycloak-roles-live.json`: live realm roles export
- `keycloak-client-secret-live.json`: active client secret for `meditrack-backend`

Important limitation:

- Current user passwords cannot be exported in plaintext from Keycloak admin API.
- After cluster recreation, users may need password reset unless the imported realm definition already contains the intended passwords.

Observed live state:

- Realm: `meditrack-staging`
- Users: `admin_stage`, `doctor_stage`, `patient_stage`, `pharmacist_stage`
- Client `meditrack-backend` secret currently resolves to `replace-with-staging-client-secret`
- Keycloak admin login in deployment is still `admin` / `admin`

Recommended post-recreate actions:

1. Restore the cluster and deploy staging manifests.
2. Verify `staging-keycloak-realm-import` still contains the intended realm seed.
3. Validate login for the four staging users.
4. If any login fails, reset the user password and re-run smoke/load auth validation.
