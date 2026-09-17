#!/bin/sh
set -eu

# Copy reviewed Quadlet unit files into the target Quadlet directory.
# Update the variables below before using this template.
#
# QUADLET_TARGET_DIR must match the Quadlet search path this deployment uses.
# The value below is the rootless default documented in
# references/podman-systemd.unit.5.md; use the rootful path or a different
# user-chosen directory when those apply. The environment decides this, not
# the template.

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
QUADLET_PREFIX='app-'
QUADLET_TARGET_DIR="${HOME}/.config/containers/systemd"

list_quadlet_files() {
	for ext in container pod network volume build image kube; do
		for file in "$SCRIPT_DIR"/"$QUADLET_PREFIX"*."$ext"; do
			[ -e "$file" ] || continue
			printf '%s\n' "$file"
		done
	done | LC_ALL=C sort -u
}

files=$(list_quadlet_files)
[ -n "$files" ] || {
	printf 'No Quadlet files found for prefix %s\n' "$QUADLET_PREFIX" >&2
	exit 1
}

mkdir -p -- "$QUADLET_TARGET_DIR"
printf '%s\n' "$files" | while IFS= read -r file; do
	install -m 0644 -- "$file" "$QUADLET_TARGET_DIR/$(basename -- "$file")"
done
