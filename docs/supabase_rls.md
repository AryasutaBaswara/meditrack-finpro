# Supabase Security Architecture (MediTrack)

This document outlines the "Zero Trust" security model implemented for the MediTrack Supabase backend.

## 🛡️ Core Security Principles

1.  **FastAPI as Authority**: All business logic and mutations (Writes) are handled by the FastAPI application layer using the `service_role` key, which bypasses RLS.
2.  **Zero Trust RLS**: Row Level Security is enabled on **EVERY** table in the `public` schema.
3.  **Default Deny**: Tables containing sensitive internal data or audit logs have RLS enabled with **ZERO policies**, making them inaccessible to direct client queries.
4.  **RPC as Gateway**: Complex data retrieval (Read Models) is provided through `SECURITY DEFINER` RPCs that perform explicit role and ownership validation.
5.  **Soft Delete Protection**: All SELECT policies and RPCs filter for `deleted_at IS NULL` to prevent accessing logically deleted data.

---

## 🏗️ Access Matrix

### Protected Tables (RLS with Policies)
These tables allow limited direct access via the Supabase client.

| Table | Access Level | Policy / Logic |
| :--- | :--- | :--- |
| `prescriptions` | Selective Read | Patient (Own), Doctor (Created), Pharmacist (Validated) |
| `patients` | Selective Read | Patient (Self), Doctor/Pharmacist (Any) |
| `storage_files` | Selective Read | Patient (Own/Linked), Doctor/Pharmacist (Any), Admin (All) |
| `profiles` | Self-Read | User can see only their own profile |
| `drugs` | Global Read | Any authenticated user can browse the catalog |
| `doctors` | Global Read | Any authenticated user can see doctor list |

### Backend-Only Tables (RLS WITHOUT Policies)
These tables are locked down. Access is only possible via `service_role` (FastAPI) or `SECURITY DEFINER` RPCs.

- `users` (Identity mapping handled by `current_app_user_id()`)
- `roles` / `user_roles`
- `dispensations`
- `stock_logs`
- `prescription_items` (Gated through `get_prescription_detail()` RPC)

---

## ⚡ Secure RPC Read Models
All RPCs are `SECURITY DEFINER` to allow joining restricted tables, but they implement strict manual guards.

### 🔐 Privilege Hardening
- **REVOKE FROM PUBLIC**: All RPC functions have `EXECUTE` rights revoked from `PUBLIC`.
- **GRANT TO authenticated**: Execution is explicitly granted only to the `authenticated` and `service_role` roles.

### 📝 RPC List
1.  **`get_prescription_detail(uuid)`**
    - **Akses**: Admin, Pharmacist, Doctor (Owner), Patient (Owner).
    - **Data**: Prescription + Items (JSONB) + Doctor/Patient Summaries.
2.  **`get_my_prescriptions(status?, limit, offset)`**
    - **Akses**: Patient only (Filters by current user identity).
    - **Data**: Paginated list of own prescriptions.
3.  **`get_pharmacist_queue(limit, offset)`**
    - **Akses**: Pharmacist & Admin only.
    - **Data**: FIFO queue of `validated`/`dispensing` prescriptions.
4.  **`get_patient_files(limit, offset)`**
    - **Akses**: Patient (Owner) & Admin.
    - **Data**: List of accessible storage metadata and URLs for files uploaded or linked to own prescriptions.

---

## 🔑 Identity Resolution
Since authentication is handled by Keycloak, we use a custom bridge:
- **`current_app_user_id()`**: Maps the JWT `sub` claim (Keycloak Subject) to our internal `users.id` (UUID).
- **`current_user_has_role(name)`**: Checks if the resolved `current_app_user_id()` possesses the specified role.
