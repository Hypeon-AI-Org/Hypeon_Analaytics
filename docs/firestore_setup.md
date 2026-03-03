# Firestore setup for Auth and ad-channel data

The app uses Firebase Authentication (email/password) and Firestore for user and organization data. The backend resolves `organization_id` and role from the authenticated user's Firestore document.

## Schema

### Collection: `users`

Document ID = Firebase Auth UID.

| Field             | Type   | Description                          |
|-------------------|--------|--------------------------------------|
| `email`           | string | User email (optional, from Auth)     |
| `displayName`     | string | Display name (optional)              |
| `organization_id`| string | **Required.** Links user to an org.  |
| `role`            | string | One of: `admin`, `analyst`, `viewer` (default: `analyst`) |

### Collection: `organizations`

Document ID = `organization_id` (e.g. `default`, or your tenant id).

| Field         | Type  | Description |
|---------------|-------|-------------|
| `name`        | string| Display name for the organization. |
| `ad_channels` | array | Optional. List of client/dataset configs (e.g. `client_id`, BigQuery dataset, GA4 property, Ads customer ID). |
| `datasets`    | object| Optional. Alternative to `ad_channels`; map of client id to dataset config. |

## Creating initial data

1. **Create a user in Firebase Authentication** (Console > Authentication > Users > Add user) with email and password.

2. **Get the user UID** from Firebase Console after creating the user.

3. **Create the organization document** in Firestore (Console > Firestore > Start collection):

   - Collection ID: `organizations`
   - Document ID: e.g. `default`
   - Fields: `name` (string): `"Default Org"`, and optionally `ad_channels` (array) or `datasets` (map).

4. **Create the user document** in Firestore:

   - Collection ID: `users`
   - Document ID: the **Firebase Auth UID** from step 2
   - Fields:
     - `email` (string): user's email
     - `displayName` (string): optional
     - `organization_id` (string): same as the organization document ID (e.g. `default`)
     - `role` (string): `admin`, `analyst`, or `viewer`

After this, the user can sign in on the login page; the backend will read `users/{uid}` and use `organization_id` and `role` for all requests.

## Optional: seed scripts

**Dummy users (recommended for testing)** — creates Auth users and Firestore docs in one go:

**Option A — gcloud auth (dev, no key file):**
1. Create the Firestore database first (Firebase Console > Build > Firestore Database > Create database, Native mode).
2. Set `FIREBASE_PROJECT_ID` or `BQ_PROJECT` in `.env` to your Firebase project (e.g. `hypeon-ai-prod`).
3. Run:
```bash
gcloud auth application-default login
gcloud config set project YOUR_FIREBASE_PROJECT_ID   # e.g. hypeon-ai-prod
python -m backend.scripts.seed_firestore_dummy_users
```

**Option B — service account key:** set `GOOGLE_APPLICATION_CREDENTIALS` in `.env` to your Firebase service account JSON path, then from repo root:

```bash
python -m backend.scripts.seed_firestore_dummy_users
```

This creates `organizations/default` and two test users you can log in with:
- `test@hypeon.example.com` / `TestPass123!` (role: admin)
- `analyst@hypeon.example.com` / `TestPass123!` (role: analyst)

**Manual UID** — if you already created a user in Firebase Console:

```bash
python -m backend.scripts.seed_firestore_example
```

Creates `organizations/default` and prompts for the Firebase Auth UID to create `users/{uid}`.

## Testing

1. **Auth for dev**: run `gcloud auth application-default login` and `gcloud config set project YOUR_FIREBASE_PROJECT_ID` (or set `GOOGLE_APPLICATION_CREDENTIALS` in `.env` to a key file).
2. **Seed dummy users** (once): from repo root:
   ```bash
   python -m backend.scripts.seed_firestore_dummy_users
   ```
3. **Start backend** (e.g. from repo root: `cd backend && uvicorn app.main:app --port 8000`).
4. **Run auth test**: `python -m backend.scripts.test_auth_flow` (checks `/health` and `/api/v1/dashboard/ping` with header auth).
5. **Log in** in the app at `/login` with `test@hypeon.example.com` / `TestPass123!`.

6. **Automated user-auth test** (after seed): `python -m backend.scripts.test_user_auth` — signs in with Firebase, calls backend with Bearer token, asserts 200.
