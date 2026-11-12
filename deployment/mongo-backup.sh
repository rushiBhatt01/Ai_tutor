#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="${AI_TUTOR_ENV_FILE:-$root/.local-secrets/runtime.env}"
backup_dir="${1:?Usage: mongo-backup.sh /secure/backup/directory}"
project="${COMPOSE_PROJECT_NAME:-ai-tutor}"
compose=(docker compose --project-name "$project" --env-file "$env_file" -f "$root/compose.production.yaml")
[[ -f "$env_file" ]] || { echo 'Runtime env file is missing.' >&2; exit 2; }
install -d -m 700 -- "$backup_dir"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive="$backup_dir/video_tutorials-$stamp.archive.gz"
partial="$archive.partial"
checksum_partial="$archive.sha256.partial"
stopped=0
restart_app() {
    if (( stopped )); then
        "${compose[@]}" start api worker >/dev/null
    fi
}
cleanup() {
    rm -f -- "$partial" "$checksum_partial"
    restart_app
}
trap cleanup EXIT

# Quiesce writers so this standalone MongoDB dump is consistent without oplog.
"${compose[@]}" stop api worker
stopped=1
"${compose[@]}" exec -T mongo sh -ec '
    umask 077
    cfg=$(mktemp /tmp/mongodump.XXXXXX)
    trap '\''rm -f "$cfg"'\'' EXIT
    printf "username: \"%s\"\npassword: \"%s\"\nauthenticationDatabase: admin\n" \
        "$MONGO_INITDB_ROOT_USERNAME" "$MONGO_INITDB_ROOT_PASSWORD" > "$cfg"
    mongodump --config "$cfg" --db video_tutorials --archive --gzip
' > "$partial"
test -s "$partial"
sha256sum "$partial" | awk -v name="$(basename "$archive")" '{ print $1 "  " name }' > "$checksum_partial"
mv -- "$partial" "$archive"
mv -- "$checksum_partial" "$archive.sha256"
chmod 600 "$archive" "$archive.sha256"
"${compose[@]}" start api worker
stopped=0
trap - EXIT
printf 'MongoDB archive created: %s\nChecksum: %s\n' "$archive" "$archive.sha256"
