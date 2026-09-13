#!/usr/bin/env bash
# Refuse commit messages carrying tool or AI attribution trailers.
#
# Two separate sources try to append one: agent tooling adds "Co-Authored-By:
# Claude" style footers, and a global prepare-commit-msg hook on this machine
# adds a session trailer. This history is a professional record that goes to
# employers, so the hook fails the commit rather than let one slip through.
set -euo pipefail

msg_file="${1:?usage: check-commit-msg.sh <path-to-commit-message>}"

banned='co-authored-by:[[:space:]]*claude|generated with \[?claude|claude-session:|bematist-session:|🤖'

if grep -qiE "$banned" "$msg_file"; then
  echo "error: commit message contains tool attribution; remove it before committing." >&2
  grep -inE "$banned" "$msg_file" >&2
  exit 1
fi
