#!/bin/bash
# Shared .env loader for local development scripts.

set -e

load_env_file() {
    local env_file="$1"
    if [ ! -f "$env_file" ]; then
        return 0
    fi

    echo "Loading environment from $env_file"

    local seen_keys=""
    local line key value trimmed_key

    while IFS= read -r line || [ -n "$line" ]; do
        if [[ "$line" =~ ^[[:space:]]*# ]] || [[ -z "${line//[[:space:]]/}" ]]; then
            continue
        fi

        if [[ "$line" != *=* ]]; then
            echo "Error: invalid .env line: $line" >&2
            return 1
        fi

        key="${line%%=*}"
        value="${line#*=}"
        trimmed_key="$(echo "$key" | xargs)"

        case "$seen_keys" in
            *"
$trimmed_key
"*)
            echo "Error: duplicate env key '$trimmed_key' found in $env_file" >&2
            return 1
            ;;
        esac

        seen_keys="${seen_keys}
$trimmed_key
"
        export "$trimmed_key=$value"
    done < "$env_file"
}
