#!/usr/bin/env bash
# Read git diff --name-status lines on stdin. Print dry-run, apply, or none.
# Only a Modified trigger file starts a run. Added files (a merge) yield none.
set -euo pipefail
dry=0
apply=0
while IFS=$'\t' read -r status name; do
  [[ -n "${status:-}" ]] || continue
  if [[ "$status" == "M" && "$name" == "ops/cleanup-dryrun-trigger.txt" ]]; then
    dry=1
  fi
  if [[ "$status" == "M" && "$name" == "ops/cleanup-apply-trigger.txt" ]]; then
    apply=1
  fi
done
if [[ "$apply" -eq 1 && "$dry" -eq 0 ]]; then
  echo apply
elif [[ "$dry" -eq 1 ]]; then
  echo dry-run
else
  echo none
fi
