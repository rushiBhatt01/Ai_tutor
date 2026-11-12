# Local secret inventory (names only)

This file intentionally records no credential values, fingerprints, hashes, or key material. Secret payloads live only in Git-ignored `.local-secrets/` files or the user's private `.ssh` directory. Do not attach or commit those files.

| Location | Names / contents | Purpose | Handling |
| --- | --- | --- | --- |
| `.local-secrets/oci/ssh-key-2026-11-07.key` | SSH private key copy | Historical local draft copy; not required for transfer | Restricted current-user Windows ACL; excluded by `.gitignore` and `.dockerignore`; original retained under the user's non-OneDrive `.ssh` directory. Workspace is under OneDrive, so remove this duplicate before deployment or allow sync explicitly. |
| `.local-secrets/oci/ssh-key-2026-11-07.key.pub` | Matching SSH public key | Configure SSH authorized key in the future VM draft | Private directory; ignored by Git/Docker with the private key |
| `.local-secrets/runtime.env` | `API_USERNAME`, `API_PASSWORD`, `PROXY_PASSWORD_HASH`, `MONGO_ROOT_USER`, `MONGO_ROOT_PASSWORD`, `MONGO_APP_USER`, `MONGO_APP_PASSWORD`, `MONGO_URI`, `CEREBRAS_API_KEY`, deployment settings | Local production Compose configuration; provider key reused from an existing local backend configuration at the user's request | Current-user-only ACL; Git/Docker ignored; never print or send as a whole. It is below the OneDrive workspace path and may sync. Move it outside OneDrive before transfer; `transfer-runtime.ps1` refuses a synced source. |

The runtime file contains generated application/database passwords and a proxy password hash. Provider keys are optional for image/search integrations and are included only when already locally configured. Additional keys must be added by the user locally when needed. Do not use `docker compose config` without `--quiet` against the runtime env. No provider or OCI calls were made while generating this file. Git/Docker ignore rules and Windows ACLs do not prevent OneDrive synchronization.

Check tracking and ignore status without revealing contents:

```powershell
git check-ignore -v .local-secrets/runtime.env .local-secrets/oci/ssh-key-2026-11-07.key
git status --short --ignored .local-secrets
```

Update 2026-11-07: The active runtime env and newly generated SSH key are now in `%USERPROFILE%\.ssh\ai-tutor-runtime`, outside OneDrive. The previous workspace runtime file and old private-key copy were removed after runtime copy hash verification. OneDrive online versions and recycle bin still require review. Older location descriptions above are historical.
