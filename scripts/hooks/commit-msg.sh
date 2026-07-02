#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: commit-msg.sh <commit-msg-file>" >&2
  exit 2
fi

message_file="$1"
if [[ ! -f "$message_file" ]]; then
  echo "Commit message file not found: $message_file" >&2
  exit 1
fi

subject=""
while IFS= read -r line || [[ -n "$line" ]]; do
  trimmed="${line#"${line%%[![:space:]]*}"}"
  trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
  if [[ -n "$trimmed" ]]; then
    subject="$trimmed"
    break
  fi
done < "$message_file"

if [[ -z "$subject" ]]; then
  echo "Commit message subject is empty." >&2
  exit 1
fi

message_body="$(cat "$message_file")"
legacy_tokens=(
  "agent-memory"
  "agent_memory"
  "agent_memory_api"
  "agent_memory_worker"
  "@agent-memory"
  "Agent Memory"
)
for token in "${legacy_tokens[@]}"; do
  if [[ "$message_body" == *"$token"* ]]; then
    printf 'Commit message contains legacy name %q.\n' "$token" >&2
    exit 1
  fi
done

case "$subject" in
  Merge\ * | Revert\ * | fixup!\ * | squash!\ *)
    exit 0
    ;;
esac

commit_re='^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)(\([a-z0-9._-]+\))?!?: .{1,100}$'
if [[ ! "$subject" =~ $commit_re ]]; then
  cat >&2 <<'EOF'
Commit subject must follow Conventional Commits, for example 'feat(api): add retrieval endpoint'.
EOF
  exit 1
fi