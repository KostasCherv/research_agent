#!/usr/bin/env bash
# demo.sh — Quick demonstration of the Research Agent CLI
# Usage:  bash scripts/demo.sh [query]
set -euo pipefail

QUERY="${1:-What is LangGraph and how does it work?}"

echo "============================================="
echo "  Research Agent Demo"
echo "============================================="
echo "Query: $QUERY"
echo ""

# Ensure we're in the project root
cd "$(dirname "$0")/.."

# Run the CLI search command
python -m src.main search "$QUERY" --output /tmp/research_report.md

echo ""
echo "============================================="
echo "  Report saved to /tmp/research_report.md"
echo "  You can also start the API server with:"
echo "  python -m src.main serve --reload"
echo "============================================="
