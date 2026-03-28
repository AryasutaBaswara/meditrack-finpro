# Supabase Row Level Security (RLS) & Table Boundaries

Dokumen ini menjelaskan batas akses antara client Supabase murni dan backend FastAPI. FastAPI tetap menjadi **Source of Truth** untuk proses *write* dan *business logic*. Supabase RLS hanya digunakan secara selektif untuk read-heavy models atau edge functions.

## 1. Actor Matrix (Client-Side Read via Supabase/Edge)

RLS diaktifkan pada tabel-tabel berikut dengan struktur pembagian peran (Role):

| Actor      | `prescriptions` | `patients` | `storage_files` |
|------------|-----------------|------------|-----------------|
| **Admin**  | Full Access (Semua resep) | Full Access (Semua pasien) | Full Access (Semua file) |
| **Doctor** | Hanya resep yang mereka buat (`doctor_id`) | Semua Pasien (Akses view dasar klinik) | Semua File storage (butuh rujukan ke resep) |
| **Patient**| Hanya resep diri mereka sendiri | Hanya data mereka sendiri | File yang diupload sendiri atau untuk resepnya |
| **Pharmacist** | Melihat resep yang berstatus `validated`, `dispensing`, atau `completed` | Semua Pasien untuk view saat dispensing | Semua File storage terkait |

> **Catatan:** Semua *mutation* (INSERT/UPDATE/DELETE) dilakukan melalui API FastAPI yang memiliki kredensial *Service Role Key* (Melewati bypass RLS).

## 2. Backend-Only Tables

Tabel-tabel di bawah ini **TIDAK TERBUKA** untuk direct Supabase Client (RLS secara default disabled / denied untuk anon/authenticated), karena berisiko tinggi / menjadi source of truth FastAPI:

1. **`users`**, **`profiles`**, **`roles`**, **`user_roles`**
   - Berisi informasi pengguna sensitif (identity, PII) yang disinkronisasi dengan Keycloak.
2. **`clinics`**, **`doctors`**
   - Data administratif.
3. **`drugs`**, **`drug_interactions`**
   - Katalog utama sistem. Semua mutasi dilakukan oleh Admin, sedangkan client meread menggunakan Elasticsearch atau Redis Cache.
4. **`dispensations`**
   - Bukti otentik dispensing obat oleh Pharmacist. Harus melewati validasi kompleks FastAPI.
5. **`stock_logs`**
   - Log mutasi stok. Dikelola secara otoritatif oleh sistem (FastAPI).
6. **`prescription_items`**
   - Detail dari `prescriptions`. Bisa digabung saat di-fetch namun sebaiknya dirangkai oleh RPC atau backend response.

## 3. Pengecekan Peran (Role Checking)

Pengecekan peran *authenticated user* dilakukan via database function:
```sql
public.current_user_has_role(role_name text)
```
Function ini memetakan relasi dari `auth.uid()` (ID Supabase request) dengan `users`, dan mencari kaitan peran-nya di tabel `roles` dan `user_roles`.
