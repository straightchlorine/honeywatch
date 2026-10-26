#!/usr/bin/env bash
# Git worktrees for the bench: one per release, one per experiment. The checkout
# that hosts bench/ holds the tooling only; whatever is measured lives in a worktree.
#
#   worktrees.sh add <ref> [name]            detached tree for a tag, sha or branch
#                                            (`add v0.8.2`, `add master current`)
#   worktrees.sh add-branch <name> [base]    branch perf/<name> off base (default master)
#   worktrees.sh list
#   worktrees.sh remove <name>               refuses a tree with uncommitted changes
#   worktrees.sh prune                       drop records of worktrees deleted by hand
#
# Trees live in ../honeywatch-wt/<name>, outside the checkout (BENCH_WT_ROOT overrides).
# Nothing here commits, pushes, tags, stashes or deletes a branch.
set -euo pipefail

SELF="$(readlink -f "${BASH_SOURCE[0]}")"
REPO="$(cd "$(dirname "$SELF")/.." && pwd)"
WT_ROOT="${BENCH_WT_ROOT:-$(cd "$REPO/.." && pwd)/honeywatch-wt}"
MAIN="$(git -C "$REPO" rev-parse --show-toplevel)"

slug() { printf '%s' "$1" | tr '/:@ ' '----'; }
dest_of() { printf '%s/%s' "$WT_ROOT" "$(slug "${1:?name required}")"; }
usage() { sed -n 2,12p "$0"; exit 1; }

case "${1:-}" in
  add)
    ref="${2:?add <ref> [name]}"
    dest="$(dest_of "${3:-$ref}")"
    [ -e "$dest" ] && { echo "already exists: $dest" >&2; exit 1; }
    mkdir -p "$WT_ROOT"
    git -C "$REPO" worktree add --detach "$dest" "$ref" >/dev/null
    echo "worktree: $dest ($(git -C "$dest" rev-parse --short HEAD))" ;;
  add-branch)
    name="${2:?add-branch <name> [base]}"
    base="${3:-master}"
    dest="$(dest_of "$name")"
    [ -e "$dest" ] && { echo "already exists: $dest" >&2; exit 1; }
    mkdir -p "$WT_ROOT"
    git -C "$REPO" worktree add -b "perf/$(slug "$name")" "$dest" "$base" >/dev/null
    echo "worktree: $dest (branch perf/$(slug "$name") from $base)" ;;
  list) git -C "$REPO" worktree list ;;
  remove)
    dest="$(dest_of "${2:?remove <name>}")"
    [ "$(readlink -f "$dest")" = "$MAIN" ] && { echo "refusing to remove the main checkout" >&2; exit 1; }
    git -C "$REPO" worktree remove "$dest"
    echo "removed: $dest" ;;
  prune) git -C "$REPO" worktree prune ;;
  *) usage ;;
esac
