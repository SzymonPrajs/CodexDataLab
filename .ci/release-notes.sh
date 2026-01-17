#!/usr/bin/env bash
set -euo pipefail

tag="${RELEASE_TAG:-${1:-}}"
if [[ -z "$tag" ]]; then
  echo "RELEASE_TAG is required (or pass tag as first arg)." >&2
  exit 1
fi

repo="${GITHUB_REPOSITORY:-}"
if [[ -z "$repo" ]]; then
  echo "GITHUB_REPOSITORY is required." >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
base_notes="$tmp_dir/base.md"
issues_md="$tmp_dir/issues.md"
final_notes="${RELEASE_NOTES_PATH:-release-notes.md}"

prev_tag=""
if git rev-parse "${tag}^" >/dev/null 2>&1; then
  prev_tag="$(git describe --tags --abbrev=0 "${tag}^")"
fi

if command -v gh >/dev/null 2>&1; then
  if [[ -n "$prev_tag" ]]; then
    gh api "repos/$repo/releases/generate-notes" \
      -f tag_name="$tag" \
      -f previous_tag_name="$prev_tag" > "$tmp_dir/gh.json"
  else
    gh api "repos/$repo/releases/generate-notes" \
      -f tag_name="$tag" > "$tmp_dir/gh.json"
  fi

  jq -r '.body // ""' "$tmp_dir/gh.json" > "$base_notes"
else
  echo "## What's Changed" > "$base_notes"
  if [[ -n "$prev_tag" ]]; then
    git log --pretty='- %s (%h)' "$prev_tag..$tag" >> "$base_notes"
  else
    git log --pretty='- %s (%h)' "$tag" >> "$base_notes"
  fi
fi

> "$issues_md"
if command -v gh >/dev/null 2>&1 && [[ -n "$prev_tag" ]]; then
  since="$(git log -1 --format=%cI "$prev_tag")"
  gh api "search/issues?q=repo:$repo+is:issue+is:closed+closed:>=$since" --paginate \
    | jq -r '.items[] | "- #\(.number) \(.title) (@\(.user.login))"' \
    | sort -u > "$issues_md" || true
fi

if command -v codex >/dev/null 2>&1 && [[ -n "${OPENAI_API_KEY:-}" ]]; then
  printenv OPENAI_API_KEY | codex login --with-api-key

  prompt_file=".ci/release-notes-prompt.txt"
  if [[ -f "$prompt_file" ]]; then
    prompt_header="$(cat "$prompt_file")"
  else
    prompt_header=$'You are drafting GitHub release notes.\nUse the base notes and closed issues below.\nOutput markdown with the following sections:\n## Highlights (3-6 bullets, user-facing)\n## What\'s Changed (preserve PR bullets from base notes if present)\n## Closed Issues (list issues; if none, say \'None.\')'
  fi

  {
    echo "$prompt_header"
    echo
    echo "<base_notes>"
    cat "$base_notes"
    echo "</base_notes>"
    echo
    echo "<closed_issues>"
    cat "$issues_md"
    echo "</closed_issues>"
  } | codex exec --color never --output-last-message "$final_notes" -
else
  {
    cat "$base_notes"
    echo
    echo "## Closed Issues"
    if [[ -s "$issues_md" ]]; then
      cat "$issues_md"
    else
      echo "None."
    fi
  } > "$final_notes"
fi

echo "Release notes written to $final_notes"
