#!/usr/bin/env bash
#
# File Line Count Gate Checker
#
# This script enforces the <400 line limit for all Python files.
# It's designed to be run locally or in CI to prevent large files.
#
# Usage:
#   ./scripts/check_max_lines.sh [--max-lines N] [--path PATH]
#
# Exit codes:
#   0 - All files under limit
#   1 - One or more files exceed limit
#
# Options:
#   --max-lines N    Maximum lines allowed (default: 400)
#   --path PATH      Path to check (default: rule_tagger2)
#   --strict         Fail on any file over limit (default: warn only for borderline)
#   --verbose        Show all file sizes
#

set -euo pipefail

# Default configuration
MAX_LINES=400
CHECK_PATH="rule_tagger2"
STRICT_MODE=false
VERBOSE=false
FAILED=false

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --max-lines)
            MAX_LINES="$2"
            shift 2
            ;;
        --path)
            CHECK_PATH="$2"
            shift 2
            ;;
        --strict)
            STRICT_MODE=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "========================================"
echo "File Line Count Gate Checker"
echo "========================================"
echo "Max lines: $MAX_LINES"
echo "Path: $CHECK_PATH"
echo "Strict mode: $STRICT_MODE"
echo ""

# Find all Python files and check their line counts
while IFS= read -r file; do
    line_count=$(wc -l < "$file" | tr -d ' ')

    if [ "$line_count" -gt "$MAX_LINES" ]; then
        echo -e "${RED}✗ FAIL${NC} $file: $line_count lines (limit: $MAX_LINES)"
        FAILED=true
    elif [ "$line_count" -gt $((MAX_LINES - 50)) ] && [ "$STRICT_MODE" = true ]; then
        # Warn about files approaching limit in strict mode
        echo -e "${YELLOW}⚠ WARN${NC} $file: $line_count lines (approaching limit)"
    elif [ "$VERBOSE" = true ]; then
        echo -e "${GREEN}✓ OK${NC}   $file: $line_count lines"
    fi
done < <(find "$CHECK_PATH" -name "*.py" -type f ! -path "*/venv/*" ! -path "*/.venv/*" ! -path "*/__pycache__/*" 2>/dev/null)

echo ""
echo "========================================"

if [ "$FAILED" = true ]; then
    echo -e "${RED}❌ GATE CHECK FAILED${NC}"
    echo ""
    echo "One or more files exceed the $MAX_LINES line limit."
    echo ""
    echo "Action Required:"
    echo "1. Refactor large files into smaller modules"
    echo "2. Follow the single responsibility principle"
    echo "3. See REFACTORING_GUIDE.md for strategies"
    echo ""
    exit 1
else
    echo -e "${GREEN}✅ GATE CHECK PASSED${NC}"
    echo "All files are under $MAX_LINES lines."
    exit 0
fi
