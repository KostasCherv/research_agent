#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PID=""
UI_PID=""

cleanup() {
  local exit_code=${1:-$?}
  trap - EXIT INT TERM

  if [[ -n "${BACKEND_PID}" ]] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
    kill "${BACKEND_PID}" 2>/dev/null || true
  fi

  if [[ -n "${UI_PID}" ]] && kill -0 "${UI_PID}" 2>/dev/null; then
    kill "${UI_PID}" 2>/dev/null || true
  fi

  if [[ -n "${BACKEND_PID}" ]]; then
    wait "${BACKEND_PID}" 2>/dev/null || true
  fi

  if [[ -n "${UI_PID}" ]]; then
    wait "${UI_PID}" 2>/dev/null || true
  fi

  exit "${exit_code}"
}

trap 'cleanup 130' INT
trap 'cleanup 143' TERM
trap 'cleanup $?' EXIT

echo "Starting backend and UI..."

(
  cd "${ROOT_DIR}"
  INNGEST_DEV=1 python -m src.main serve --reload
) &
BACKEND_PID=$!

(
  cd "${ROOT_DIR}/ui"
  npm run dev
) &
UI_PID=$!

echo "Backend PID: ${BACKEND_PID}"
echo "UI PID: ${UI_PID}"
echo "Press Ctrl+C to stop both services."

backend_status=0
ui_status=0

while true; do
  if ! kill -0 "${BACKEND_PID}" 2>/dev/null; then
    wait "${BACKEND_PID}" || backend_status=$?
    echo "Backend exited (status ${backend_status}). Shutting down UI..."
    break
  fi

  if ! kill -0 "${UI_PID}" 2>/dev/null; then
    wait "${UI_PID}" || ui_status=$?
    echo "UI exited (status ${ui_status}). Shutting down backend..."
    break
  fi

  sleep 1
done

exit_code=0
if [[ ${backend_status} -ne 0 ]]; then
  exit_code=${backend_status}
elif [[ ${ui_status} -ne 0 ]]; then
  exit_code=${ui_status}
fi

cleanup "${exit_code}"
