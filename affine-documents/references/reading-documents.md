# Reading an AFFiNE document

How to get a document's real content out of AFFiNE, why the obvious path is
lossy, and where the ground truth lives.

Verified on 2026-09-22 against AFFiNE **0.27.4** (image channel tag `stable`).

**Placeholders are deliberate** — each stands for a value only the operator
knows: `<doc-id>`, `<workspace-id>`, `<postgres-container>` (the container
running AFFiNE's Postgres), `<app-container>` (the container running the app),
`<snapshot-blob>` (a scratch file you own). Paths beginning `/app/` are paths
**inside the app image**, identical for every deployment of that image — not
paths on anyone's host.

## The read tools

An AFFiNE instance that exposes the official MCP server registers these
unconditionally (read-only access is enough):

| name | what it returns |
|---|---|
| `doc_read` / `doc_search` / client alias `read_document` | document body as reconstructed markdown |
| `doc_canvas_read` | whiteboard content |
| `frontend_read_selection`, `frontend_read_nodes`, `frontend_snapshot_document` | state of an open editor session |

Two facts that change how you plan:

- **There is no delete or trash tool.** A document created while testing can only
  be removed by a human in the UI — prefer writing into a scratch document the
  user can delete, and say so when test content is left behind.
- **A markdown read-back is a reconstruction, not a copy.** Row separators
  collapse, a leading `+` comes back escaped, and inline math and latex blocks
  cannot be serialized at all — the reader lists them as unsupported blocks
  instead. A read-back is fine for orientation and wrong for evidence: a plain
  paragraph holding `$…$` looks like a corrupted equation, and a collapsed table
  looks like a conversion bug that is not there.

## Ground truth: the stored snapshot

A document lives in the `snapshots` table: the state column is `blob`, and the key
column is **`guid`**, not `id`. Pull it out and decode it:

```bash
podman exec <postgres-container> psql -U affine -d affine -tAc \
  "select encode(blob,'hex') from snapshots where guid='<doc-id>';" > /tmp/doc.hex
python3 scripts/snapshot-strings.py --hex /tmp/doc.hex > /tmp/doc.txt
```

`scripts/snapshot-strings.py` accepts the raw blob file, a hex dump
(`--hex`), or hex on stdin (`--hex -`), and prints the ASCII runs in the byte
stream. `templates/read-doc-snapshot.sh <doc-id>` wraps the fetch and does the
same in one step.

Read the output as the block tree:

| key | meaning |
|---|---|
| `sys:flavour` | block type: `affine:paragraph`, `affine:list`, `affine:code`, `affine:table`, `affine:latex`, `affine:page`, `affine:note`, `affine:surface` (whiteboard) |
| `prop:type` | the subtype: `text`, `h1`…`h6`, `quote`, `bulleted`, `numbered`, `todo`, `code` |
| `prop:text` | that block's literal text |

A value string that still contains markdown syntax is proof the construct was
**not** parsed into a block — that is how a tool-written equation shows up
(paragraph text containing `$$E = mc^2$$`, with no `affine:latex` block anywhere
in the dump).

Timer notes: snapshot persistence is near-immediate — the client pushes within
seconds of an edit — so read after the edit settles rather than during it. An
empty `updates` result for the same `guid` is normal and does not mean the
document is missing; the row can also be a snapshot taken slightly before the
last keystroke.

## The block-ID-annotated read-back

`templates/read-doc-snapshot.sh <doc-id> --markdown` feeds the same snapshot back
through the server's own reader with `aiEditable=true`. It prefixes every block
with `<!-- block_id=… flavour=… -->` (useful for pointing at one block when
talking to a user) and prints `knownUnsupportedBlocks` on stderr — **that list is
exactly what a rewrite would silently drop**, so read it before proposing any
document-wide edit.

## Do not hand-decode the byte stream

The blob is a y-octo stream: varints, interleaved attribute tables, per-item keys.
Decoding it by hand costs hours and adds nothing — the readable runs above already
answer "which blocks exist and what do they hold", and marker counting answers
"did this content survive". Stop at that level.

## Counting markers as evidence

To answer "does this document still contain everything", count markers in the
decoded blob and compare against the source:

```bash
python3 scripts/snapshot-strings.py <snapshot-blob> | grep -o '\\frac' | wc -l
python3 scripts/snapshot-strings.py <snapshot-blob> | grep -o 'begin{array}' | wc -l
```

Two traps:

- **`grep -c` counts lines, not occurrences.** Several markers usually share one
  decoded run, so `grep -c 'frac'` can report 24 where the answer is 39 — always
  `grep -o … | wc -l`. Measured on a repaired document: 39 occurrences in the
  decoded runs against 39 in the source markdown, while the line count was 24.
- **A bare `$` count proves nothing.** The byte stream contains structural dollar
  signs — `$blocksuite:internal:native$` once, `w$<uuid>` hundreds of times — so
  count the *source patterns* you care about (`$ `, ` $`, a specific command),
  never a raw `$`.

For prose, do not count — sample. Take windows of 8+ CJK characters from the
source and test each for presence in the decoded blob; a window that straddles a
bold run or an inline-math run always misses, so confirm its components instead
of reporting loss. Finish with the leftover-source check (`$ ` and ` $` both 0)
from `references/markdown-and-formulas.md`.
