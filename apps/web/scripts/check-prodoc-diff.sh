#!/usr/bin/env bash
# check-prodoc-diff.sh
#
# CI guard: fails the build if any file outside the Prodoc allowlist has more
# than 5 changed lines compared to the base branch.
#
# Usage:
#   ./apps/web/scripts/check-prodoc-diff.sh [base-branch]
#   base-branch defaults to "preview"

set -euo pipefail

BASE="${1:-preview}"
THRESHOLD=5
FAILED=0

# Allowlisted path prefixes — files under these directories may change freely.
is_allowlisted() {
  local file="$1"
  case "$file" in
    apps/api/plane/prodoc/*) return 0 ;;
    apps/web/core/components/prodoc/*) return 0 ;;
    apps/web/app/\(all\)/\[workspaceSlug\]/\(prodoc\)/*) return 0 ;;
    apps/web/scripts/check-prodoc-diff.sh) return 0 ;;
    .github/workflows/prodoc-*) return 0 ;;
    docs/*) return 0 ;;
  esac
  return 1
}

echo "Checking upstream edit ceiling (max ${THRESHOLD} lines per file outside allowlist)"
echo "Base: ${BASE}"
echo "---"

while IFS=$'\t' read -r added deleted file; do
  # Skip binary files (reported as "-" by git diff --numstat)
  [[ "$added" == "-" ]] && continue

  # Skip allowlisted paths
  if is_allowlisted "$file"; then
    continue
  fi

  total=$((added + deleted))
  if [[ $total -gt $THRESHOLD ]]; then
    echo "FAIL: ${file} changed ${total} lines (limit: ${THRESHOLD})"
    FAILED=1
  else
    echo "  ok: ${file} changed ${total} lines"
  fi
done < <(git diff --numstat "${BASE}...HEAD")

echo "---"
if [[ $FAILED -eq 1 ]]; then
  echo "ERROR: One or more upstream files exceed the ${THRESHOLD}-line edit ceiling."
  echo "Move Prodoc code into the allowlisted directories or justify the upstream edit."
  exit 1
fi

echo "All upstream edits within ceiling. OK."
