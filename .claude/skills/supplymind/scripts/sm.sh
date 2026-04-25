#!/usr/bin/env bash
# SupplyMind Quick Runner — shortcut for Claude Code Bash execution
# Usage: ./scripts/sm.sh <command> [options...]
# Example: ./scripts/sm.sh demand-forecast --input data.csv --horizon 14

set -euo pipefail

# Resolve the project root (where pyproject.toml lives)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Ensure we're running from project root for correct module resolution
cd "$PROJECT_ROOT"

# Run supplymind CLI
exec python -m supplymind "$@"
