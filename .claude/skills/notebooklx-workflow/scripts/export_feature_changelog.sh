#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/export_feature_changelog.sh \
    --feature "Feature 1.3" \
    --slice "Text upload endpoint" \
    --status "passed" \
    --acceptance "Upload plain text content; Return source ID and initial status" \
    --verification "PYTHONPATH=$(pwd) pytest services/api/tests/test_sources.py -v" \
    --summary "Implemented text source endpoint and validation." \
    --next "Feature 1.3 - URL source upload" \
    [--file "services/api/modules/sources/routes.py"] \
    [--file "services/api/tests/test_sources.py"] \
    [--output "/tmp/notebooklx-workflow.log"]
EOF
}

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_path="$repo_root/.git/logs/notebooklx-workflow.log"
feature=""
slice=""
status=""
acceptance=""
verification=""
summary=""
next_slice=""
files=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --feature)
      feature="${2:-}"
      shift 2
      ;;
    --slice)
      slice="${2:-}"
      shift 2
      ;;
    --status)
      status="${2:-}"
      shift 2
      ;;
    --acceptance)
      acceptance="${2:-}"
      shift 2
      ;;
    --verification)
      verification="${2:-}"
      shift 2
      ;;
    --summary)
      summary="${2:-}"
      shift 2
      ;;
    --next)
      next_slice="${2:-}"
      shift 2
      ;;
    --file)
      files+=("${2:-}")
      shift 2
      ;;
    --output)
      output_path="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$feature" || -z "$slice" || -z "$status" || -z "$acceptance" || -z "$verification" || -z "$summary" || -z "$next_slice" ]]; then
  echo "Missing required arguments." >&2
  usage >&2
  exit 1
fi

timestamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
mkdir -p "$(dirname "$output_path")"

{
  printf '[%s]\n' "$timestamp"
  printf 'feature=%s\n' "$feature"
  printf 'slice=%s\n' "$slice"
  printf 'status=%s\n' "$status"
  printf 'acceptance=%s\n' "$acceptance"
  printf 'verification=%s\n' "$verification"
  printf 'summary=%s\n' "$summary"
  if [[ ${#files[@]} -gt 0 ]]; then
    printf 'files=%s\n' "$(IFS=', '; echo "${files[*]}")"
  else
    printf 'files=\n'
  fi
  printf 'next=%s\n' "$next_slice"
  printf '%s\n' '---'
} >> "$output_path"

printf 'Appended changelog entry to %s\n' "$output_path"
