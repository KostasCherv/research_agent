#!/usr/bin/env bash

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_ACTIVATE="source ${ROOT_DIR}/.venv/bin/activate"

echo "Starting all backend components..."

# API Server
osascript -e "tell app \"Terminal\" to do script \"cd ${ROOT_DIR} && ${VENV_ACTIVATE} && INNGEST_DEV=1 python -m src.main serve --reload\""

sleep 1

# Inngest Dev Server
osascript -e "tell app \"Terminal\" to do script \"cd ${ROOT_DIR} && npx --ignore-scripts=false inngest-cli@latest dev -u http://127.0.0.1:8000/api/inngest --no-discovery\""

sleep 1

# Outbox Dispatcher Loop
osascript -e "tell app \"Terminal\" to do script \"cd ${ROOT_DIR} && ${VENV_ACTIVATE} && while true; do python -m src.main rag-dispatch-outbox --limit 100; sleep 2; done\""

echo "All backend components started in new Terminal windows."
echo "Close the Terminal windows or press Ctrl+C in each to stop the services."