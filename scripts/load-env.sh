#!/bin/bash
# Shared .env loader for local development scripts.

set -e

trim_whitespace() {
    local value="$1"

    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"

    printf '%s' "$value"
}

normalize_env_value() {
    local raw_value="$1"
    local parsed=""
    local char prev_char
    local in_single_quote=0
    local in_double_quote=0
    local idx

    for ((idx = 0; idx < ${#raw_value}; idx++)); do
        char="${raw_value:idx:1}"

        if [[ "$char" == "'" && $in_double_quote -eq 0 ]]; then
            if [[ $in_single_quote -eq 0 ]]; then
                in_single_quote=1
            else
                in_single_quote=0
            fi
            parsed+="$char"
            continue
        fi

        if [[ "$char" == '"' && $in_single_quote -eq 0 ]]; then
            prev_char="${raw_value:idx-1:1}"
            if [[ $prev_char != "\\" ]]; then
                if [[ $in_double_quote -eq 0 ]]; then
                    in_double_quote=1
                else
                    in_double_quote=0
                fi
            fi
            parsed+="$char"
            continue
        fi

        if [[ "$char" == "#" && $in_single_quote -eq 0 && $in_double_quote -eq 0 ]]; then
            prev_char="${parsed: -1}"
            if [[ -z "$parsed" || "$prev_char" =~ [[:space:]] ]]; then
                break
            fi
        fi

        parsed+="$char"
    done

    parsed="$(trim_whitespace "${parsed%$'\r'}")"

    if [[ ${#parsed} -ge 2 ]]; then
        if [[ "$parsed" == \"*\" && "$parsed" == *\" ]]; then
            parsed="${parsed:1:${#parsed}-2}"
        elif [[ "$parsed" == \'*\' && "$parsed" == *\' ]]; then
            parsed="${parsed:1:${#parsed}-2}"
        fi
    fi

    printf '%s' "$parsed"
}

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
        value="$(normalize_env_value "$value")"

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
