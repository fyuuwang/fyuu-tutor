#!/usr/bin/env bash
# Build the learning portal and optionally deploy to a Git remote.
# Uses a temporary git worktree - never switches branches in the current worktree.
#
# All paths are explicit; the script does not assume a repo layout.
#
# Usage:
#   Build only (preview, no push):
#     bash deploy_portal.sh --workspace <path> --repo <path> --markers <file> --project <id>
#   Build and publish:
#     bash deploy_portal.sh --workspace <path> --repo <path> --markers <file> --project <id> --publish
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

WORKSPACE=""
REPO_ROOT=""
MARKERS_FILE=""
PUBLISH=false
PROJECTS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --workspace) WORKSPACE="$2"; shift 2 ;;
    --repo) REPO_ROOT="$2"; shift 2 ;;
    --markers) MARKERS_FILE="$2"; shift 2 ;;
    --project) PROJECTS+=("$2"); shift 2 ;;
    --publish) PUBLISH=true; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$WORKSPACE" ]]; then
  echo "ERROR: --workspace <path> is required" >&2; exit 1
fi
if [[ -z "$REPO_ROOT" ]]; then
  echo "ERROR: --repo <path> (the git repository root) is required" >&2; exit 1
fi
if [[ -z "$MARKERS_FILE" ]]; then
  echo "ERROR: --markers <file> is required" >&2; exit 1
fi
if [[ ${#PROJECTS[@]} -eq 0 ]]; then
  echo "ERROR: at least one --project <id> is required" >&2; exit 1
fi
if ! git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: --repo must be a git repository: $REPO_ROOT" >&2; exit 1
fi
if [[ ! -f "$MARKERS_FILE" ]]; then
  echo "ERROR: markers file not found: $MARKERS_FILE" >&2; exit 1
fi

# Resolve to absolute paths
WORKSPACE="$(cd "$WORKSPACE" && pwd)"
REPO_ROOT="$(cd "$REPO_ROOT" && pwd)"
MARKERS_FILE="$(cd "$(dirname "$MARKERS_FILE")" && pwd)/$(basename "$MARKERS_FILE")"

if [[ "$PUBLISH" == "true" ]]; then
  if [[ "$(git -C "$REPO_ROOT" branch --show-current)" != "main" ]]; then
    echo "ERROR: --publish requires the main branch" >&2; exit 1
  fi
  if [[ -n "$(git -C "$REPO_ROOT" status --porcelain)" ]]; then
    echo "ERROR: --publish requires a clean worktree" >&2; exit 1
  fi
fi

TMP_PORTAL="$(mktemp -d)/portal"
TMP_TREE="$(mktemp -d)/gh-pages-tree"

cleanup() {
  local failed=0
  rm -rf "$(dirname "$TMP_PORTAL")"
  if [[ -d "$TMP_TREE" ]]; then
    git -C "$REPO_ROOT" worktree remove --force "$TMP_TREE" || failed=1
    git -C "$REPO_ROOT" worktree prune || failed=1
  fi
  return "$failed"
}
trap cleanup EXIT

# Build portal with explicit project selection
echo "Building portal..."
PROJECT_ARGS=()
for pid in "${PROJECTS[@]}"; do
  PROJECT_ARGS+=(--project "$pid")
done

# MARKERS_FILE was validated above; use as-is

python3 "$SCRIPT_DIR/build_portal.py" \
  --workspace "$WORKSPACE" \
  --out "$TMP_PORTAL" \
  --markers "$MARKERS_FILE" \
  "${PROJECT_ARGS[@]}"

echo "Checking links..."
python3 "$SCRIPT_DIR/check_links.py" --root "$TMP_PORTAL"

if [[ "$PUBLISH" == "false" ]]; then
  echo ""
  echo "Portal built at: $TMP_PORTAL"
  echo "Preview with: python3 -m http.server 8000 --directory \"$(dirname "$TMP_PORTAL")\""
  echo "Remove preview files with: rm -rf \"$(dirname "$TMP_PORTAL")\""
  echo "To publish: add --publish"
  # Keep temp dir alive for preview (don't cleanup yet)
  trap - EXIT
  exit 0
fi

echo "Publishing to gh-pages..."

# Check remote access before deciding whether gh-pages exists.
if ! git -C "$REPO_ROOT" ls-remote --heads origin >/dev/null 2>&1; then
  echo "ERROR: cannot query origin" >&2; exit 1
fi
if git -C "$REPO_ROOT" ls-remote --exit-code --heads origin gh-pages >/dev/null 2>&1; then
  # Fetch must succeed; a stale or missing FETCH_HEAD would publish from the
  # wrong commit. No || true here -- fetch failure stops deployment.
  git -C "$REPO_ROOT" fetch origin gh-pages:refs/remotes/origin/gh-pages
  git -C "$REPO_ROOT" worktree add --detach "$TMP_TREE" refs/remotes/origin/gh-pages
  # Clear old content in the worktree (safe: it is a temp dir)
  find "$TMP_TREE" -mindepth 1 ! -path "$TMP_TREE/.git" -delete
else
  # Create orphan branch in temp worktree
  git -C "$REPO_ROOT" worktree add --detach "$TMP_TREE" HEAD
  cd "$TMP_TREE"
  git checkout --orphan gh-pages
  if git ls-files --error-unmatch >/dev/null 2>&1; then
    git rm -rf .
  fi
  cd "$REPO_ROOT"
fi

# Copy build output into worktree
cp -r "$TMP_PORTAL"/* "$TMP_TREE"/
python3 "$SCRIPT_DIR/check_links.py" --root "$TMP_TREE"
PYTHONPATH="$SCRIPT_DIR" python3 -c '
from build_portal import scan_content
from pathlib import Path
import sys
markers = [line.strip() for line in Path(sys.argv[2]).read_text(encoding="utf-8").splitlines()
           if line.strip() and not line.startswith("#")]
errors = scan_content(Path(sys.argv[1]), markers)
print("\n".join(errors))
raise SystemExit(bool(errors))
' "$TMP_TREE" "$MARKERS_FILE"
cd "$TMP_TREE"
git add -A

if git diff --cached --quiet; then
  echo "No changes to deploy."
else
  git commit -m "deploy: learning portal $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  git push origin HEAD:gh-pages
  echo "Pushed branch: gh-pages"
fi

cd "$REPO_ROOT"
echo "Done."
