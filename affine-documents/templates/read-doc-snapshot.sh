#!/usr/bin/env bash
# Read a document's stored block tree, or its block-ID-annotated markdown.
#
# Copy this file, then set the marked values for your deployment. Every marked
# value is the user's decision, not a default this template can pick:
#
#   RUNTIME        the container runtime in use (podman, docker, …)
#   DB_CONTAINER   the container running AFFiNE's Postgres
#   APP_CONTAINER  the container running AFFiNE (only needed for --markdown)
#   STRINGS_SCRIPT the snapshot-strings.py shipped with this skill — correct as
#                  written while this file sits in templates/ next to scripts/;
#                  set it explicitly if you copy the file somewhere else
#   DB_USER/DB_NAME the database holding the `snapshots` table
#
# Both modes start from the same row: `select encode(blob,'hex') from snapshots
# where guid='<docId>'` — the column is `guid`, not `id`. Reading the blob
# directly is the only faithful way to see what a document contains: the
# markdown a reader reconstructs from it cannot represent equations, and quotes
# the stored text in ways that make intact content look damaged.
#
# usage: read-doc-snapshot.sh <docId>            # block tree as readable strings
#        read-doc-snapshot.sh <docId> --markdown # block-ID-annotated read-back
set -euo pipefail

RUNTIME=${RUNTIME:-podman}
DB_CONTAINER=${DB_CONTAINER:?set DB_CONTAINER to the AFFiNE Postgres container}
APP_CONTAINER=${APP_CONTAINER:-}
STRINGS_SCRIPT=${STRINGS_SCRIPT:-$(dirname "$0")/../scripts/snapshot-strings.py}
DB_USER=${DB_USER:-affine}
DB_NAME=${DB_NAME:-affine}

doc=${1:?usage: read-doc-snapshot.sh <docId> [--markdown]}
mode=${2:-strings}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

"$RUNTIME" exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tAc \
  "select encode(blob,'hex') from snapshots where guid='${doc}';" > "$tmp/doc.hex"

# A missing row and an empty document both look like silence — say which one it is.
[ -s "$tmp/doc.hex" ] || { echo "no snapshot row for guid=$doc" >&2; exit 1; }

python3 - "$tmp/doc.hex" "$tmp/doc.bin" <<'PY'
import binascii, sys
raw = binascii.unhexlify(''.join(open(sys.argv[1]).read().split()))
open(sys.argv[2], 'wb').write(raw)
PY

if [ "$mode" = "--markdown" ]; then
  : "${APP_CONTAINER:?set APP_CONTAINER for --markdown mode}"
  cat > "$tmp/read.js" <<'JS'
// parseDocToMarkdown(blob, docId, aiEditable) — aiEditable prefixes every block
// with '<!-- block_id=… flavour=… -->'; knownUnsupportedBlocks lists the blocks
// the reader cannot serialize, which is exactly what a rewrite would drop.
const fs = require('fs');
const native = require('/app/dist/server-native.x64.node');
const result = native.parseDocToMarkdown(fs.readFileSync('/tmp/doc.bin'), process.argv[2], true, undefined);
process.stderr.write('unsupported blocks (invisible to a rewrite): ' + JSON.stringify(result.knownUnsupportedBlocks) + '\n');
process.stdout.write(result.markdown || '');
JS
  "$RUNTIME" cp "$tmp/doc.bin" "$APP_CONTAINER:/tmp/doc.bin"
  "$RUNTIME" cp "$tmp/read.js" "$APP_CONTAINER:/tmp/read.js"
  "$RUNTIME" exec "$APP_CONTAINER" node /tmp/read.js "$doc"
else
  python3 "$STRINGS_SCRIPT" "$tmp/doc.bin"
fi
