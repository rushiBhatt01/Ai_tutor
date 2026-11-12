#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="${AI_TUTOR_ENV_FILE:-$root/.local-secrets/runtime.env}"
archive="${1:?Usage: mongo-restore.sh /secure/backup/archive.gz fresh-compose-project-name}"
project="${2:?Supply a new, empty Compose project name for restore verification}"
[[ "$project" =~ ^[a-z0-9][a-z0-9_-]{0,35}$ ]] || { echo 'Invalid Compose project name.' >&2; exit 2; }
[[ "$project" != "${COMPOSE_PROJECT_NAME:-ai-tutor}" ]] || { echo 'Restore requires a distinct fresh project/volume.' >&2; exit 2; }
[[ -f "$env_file" && -f "$archive" ]] || { echo 'Runtime env or backup archive is missing.' >&2; exit 2; }
if docker volume inspect "${project}_mongo_data" >/dev/null 2>&1; then
    echo 'Restore project already has a Mongo data volume; choose a new project name to protect existing data.' >&2
    exit 2
fi
(cd "$(dirname "$archive")" && sha256sum -c "$(basename "$archive").sha256")
compose=(docker compose --project-name "$project" --env-file "$env_file" -f "$root/compose.production.yaml")

# This creates a new named mongo_data volume for this project. Never restore
# into the active Compose project and never pass --drop.
"${compose[@]}" up -d mongo
restore_from_stdin() {
    local dry_run="$1"
    "${compose[@]}" exec -T mongo sh -ec '
        umask 077
        cfg=$(mktemp /tmp/mongorestore.XXXXXX)
        trap '\''rm -f "$cfg"'\'' EXIT
        printf "username: \"%s\"\npassword: \"%s\"\nauthenticationDatabase: admin\n" \
            "$MONGO_INITDB_ROOT_USERNAME" "$MONGO_INITDB_ROOT_PASSWORD" > "$cfg"
        if [ "$1" = dry-run ]; then
            mongorestore --config "$cfg" --archive --gzip --dryRun --stopOnError
        else
            mongorestore --config "$cfg" --archive --gzip --stopOnError
        fi
    ' sh "$dry_run"
}
restore_from_stdin dry-run < "$archive"
restore_from_stdin restore < "$archive"
echo "Restore completed into fresh Compose project '$project'. Verify app collections and GridFS, then keep or remove that test volume deliberately."
