#!/bin/sh
set -e
# Inject runtime config from env into /usr/share/nginx/html/config.js

escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

CONFIG_FILE="${CONFIG_FILE:-/usr/share/nginx/html/config.js}"
mkdir -p "$(dirname "$CONFIG_FILE")"

{
  echo 'window.__APP_CONFIG__ = {'
  echo "  \"VITE_API_BASE\": \"$(escape "${VITE_API_BASE:-}")\","
  echo "  \"VITE_API_KEY\": \"$(escape "${VITE_API_KEY:-}")\","
  echo "  \"VITE_FIREBASE_API_KEY\": \"$(escape "${VITE_FIREBASE_API_KEY:-}")\","
  echo "  \"VITE_FIREBASE_AUTH_DOMAIN\": \"$(escape "${VITE_FIREBASE_AUTH_DOMAIN:-}")\","
  echo "  \"VITE_FIREBASE_PROJECT_ID\": \"$(escape "${VITE_FIREBASE_PROJECT_ID:-}")\","
  echo "  \"VITE_FIREBASE_STORAGE_BUCKET\": \"$(escape "${VITE_FIREBASE_STORAGE_BUCKET:-}")\","
  echo "  \"VITE_FIREBASE_MESSAGING_SENDER_ID\": \"$(escape "${VITE_FIREBASE_MESSAGING_SENDER_ID:-}")\","
  echo "  \"VITE_FIREBASE_APP_ID\": \"$(escape "${VITE_FIREBASE_APP_ID:-}")\","
  echo "  \"VITE_FIREBASE_MEASUREMENT_ID\": \"$(escape "${VITE_FIREBASE_MEASUREMENT_ID:-}")\""
  echo '};'
} > "$CONFIG_FILE"

exec nginx -g 'daemon off;'
