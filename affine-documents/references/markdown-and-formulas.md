# Markdown and formulas written into AFFiNE by a tool

Two write paths into a document, and they do not have the same power. The editor
converts what the user types — including equations — into native blocks. A tool (an
MCP `create_document` / `update_document` call, any API client) can only send
**markdown**, which the server runs through a *partial* markdown→blocks converter —
feature parity is not implied: a construct the editor supports natively can still
arrive as literal text.

Probe before promising formatting, and never promise formula-heavy material —
textbook notes, worked solutions, anything whose value is its equations — until the
limit below is on the table; it decides whether agent-written documents are usable.

Verified on 2026-09-22 against AFFiNE 0.27.4: the conversion table, the inline-math
probe table, the `&#x20;` display-math failure and a full-document repair paste were
all reproduced on that version.
Unverified, and not to be repeated as measured: the UI's Import → Markdown path,
non-x64 module filenames, and any server version other than the one above.
Placeholders are deliberate: `<app-container>`, `<postgres-container>`, `<doc-id>`
and `<snapshot-blob>` (a scratch file you own) — substitute your deployment's names.

## The writer of record

The converter is the server-native Rust module shipped inside the app image
(`server-native.<arch>.node` in the app's `dist` directory; the x64 build is
`server-native.x64.node`), entry points `createDocWithMarkdown` /
`updateDocWithMarkdown` — the same path behind `create_document` and
`update_document`. It contains **no LaTeX handling whatsoever**. That is why the
equation limit is structural rather than a syntax problem to work around: no
delimiter style, no escaping, no `$$$$` variant and no metadata flag makes a tool
write produce an equation. Equations in an AFFiNE document always came from the
editor, and adding or repairing one is editor-side work.

## What converts, what lands as literal text

| markdown | resulting block |
| --- | --- |
| `#`…`######` heading | `affine:paragraph` with `prop:type=h1`…`h6` |
| paragraph text | `affine:paragraph`, `prop:type=text` |
| fenced code + language | `affine:code` with `prop:language` |
| `\| a \| b \|` table | `affine:table` with real `prop:columns.*` / `prop:rows.*` |
| `> quote` | `affine:paragraph`, `prop:type=quote` |
| `- ` / `1. ` / `- [ ]` | `affine:list`, `prop:type=bulleted\|numbered\|todo` (todo keeps its checked state) |

Does **not** convert: `$...$` and `$$...$$`. No `affine:latex` block is produced —
the source, delimiters included, is stored verbatim as paragraph text
(`prop:text = "$$E = mc^2$$"`), which displays as raw LaTeX and not a rendered
equation: KaTeX rendering lives in the latex block, and only the editor's own insert
creates one. "AFFiNE renders amsmath" is true of the block, false of a tool write.
Consequence: agent-generated material that leans on formulas needs its equations
re-inserted by hand, or has to ship with the formula shown as source.

### Read the stored blocks, not the read-back

`read_document` returns markdown *reconstructed* from the block tree, and the
reconstruction is lossy — row separators collapse and `+` comes back escaped. Judge
conversion fidelity from the stored blocks, never from the read-back, which makes a
plain-text paragraph look like a corrupted equation and sends you hunting a data-loss
bug that does not exist.

The document lives in `snapshots`; the state column is `blob` and the key column is
`guid` (not `id`). Pull the blob out and count the block flavours in it:

```bash
podman exec <postgres-container> psql -U affine -d affine -tAc \
  "select encode(blob,'hex') from snapshots where guid='<doc-id>';" \
  | python3 -c 'import binascii,sys; sys.stdout.buffer.write(binascii.unhexlify(sys.stdin.read().strip()))' \
  > <snapshot-blob>
python3 - <<'PY'
b = open('<snapshot-blob>', 'rb').read()
for f in ['affine:paragraph', 'affine:list', 'affine:code', 'affine:table', 'affine:latex']:
    print(f, b.count(f.encode()))
PY
```

Read the blob as `sys:flavour` = block type
(`affine:paragraph|list|code|table|latex|page|note|surface`), `prop:type` = subtype,
`prop:text` = that block's literal text. A value string that still contains markdown
syntax is proof the construct was **not** parsed into a block. The shipped helpers
wrap these two calls: `scripts/snapshot-strings.py` prints the blob's readable
strings, and `templates/read-doc-snapshot.sh <doc-id> [--markdown]` fetches the row
and dumps the block tree in that form — or, with `--markdown`, feeds the same
snapshot back through the server's own reader with `aiEditable=true`, prefixing every
block with `<!-- block_id=… flavour=… -->` and listing the blocks the reader cannot
serialize.

Stop there: hand-decoding the y-octo byte stream (varints, interleaved attribute
tables) costs hours and adds nothing actionable. An empty `updates` result for the
same `guid` is normal and does not mean the document is missing.

## Pitfall: a line starting with a bare plus becomes a bullet

A line-leading `+` followed by a space is a markdown bullet, so a multi-line array
equation written as

```
$$
\begin{array}{r}
1234 \\
+ \ 876 \\
\hline
2110
\end{array}
$$
```

is split into a paragraph (the opening lines) **and** an `affine:list` bullet
holding the rest — the equation is torn in half on top of not rendering. Keep the
addend glued to its sign (`+876`, `+\876`) if the source is to survive as text.

## Display math: a line-leading space arrives as `&#x20;`

Whitespace at the **start of a line inside a `$$` block** reaches the equation as
the literal text `&#x20;`, which KaTeX rejects (the array then renders as a syntax
error):

```
\begin{array}{rrrrr}
&#x20;&   & 3 & 2 & 4 \\
\times &   &   &   & 4 \\
```

Only the *leading* space is affected: space runs between `&` separators survive
verbatim, and `&`, `\hline`, `\\` arrive untouched — so nothing entity-encodes `&`,
only line-leading whitespace gets encoded.

Fix: **no indentation inside display math.** Every line starts with `&`, `\times`,
`+` or `\hline`; alignment comes from the array columns, never from leading spaces.
Check a repair file before handing it to anyone: `grep -c '^ ' repair.md` must
print `0`.

## Inline math: the space right after the opening `$`

The paste importer pairs `$` runs itself, and a source sitting flush against a digit
mis-pairs. The deciding character is the space right after the **opening** `$`:

| pasted inline math | renders as an equation? |
| --- | --- |
| `$20000 - 2868 - 2901$` | ✗ not an equation, and the prose after it is swallowed |
| `$ 20000 - 2868 - 2901$` | ✓ |
| `$20000 - 2868 - 2901 $` | ✗ still broken — a space before the closer does not pair the run |
| `$ 20000 - 2868 - 2901 $` | ✓ |
| prose containing `分子 $ 23 > 19 $、分母 $ 41 > 33 $ → 同大同小` | ✓ both render |

Rule: write repair markdown with a space after **every opening `$`** whose source
starts flush with a digit; padding the closer as well is harmless (that is the form
the delivered repair document uses). A source that starts with a backslash command
(`\frac{23}{19}`) renders fine flush against the delimiters — its command token
anchors the pair — so do not space-pad all math blindly. Re-run this five-line probe
in a scratch document when the server version changes, or when a repair still shows
source text where an equation should be.

## Damage fingerprint of a mis-paired paste

A document whose content came in through a markdown hop with mis-paired `$` shows
some formulas rendering, others as source text, and — the tell that matters —
sentences chopped in half on the rendered page because the prose between two
formulas disappeared. The block dump names the mechanism: the importer pairs `$`
runs itself, and a mis-pair yields an **empty inline-latex run** (`latex null`) in
place of the formula source *plus* the prose that followed it. The missing prose is
the damage marker, not the empty run.

Genuinely unrecoverable: the prose consumed by the mis-pair. It is no longer in the
document — the snapshot holds only what survived — so recovery depends on an
external master copy of the same content. Rebuild from that copy; nothing inside the
damaged document can restore the text.

Not damage, and never report it as such: the correctly padded form makes the
importer emit, per formula, `latex(<source>)`, a one-space text run, then an empty
`latex null` run. Measured on a full-document repair that renders correctly: 45
inline formulas → 45 `latex null` runs, zero missing prose. One empty latex run per
formula is the expected tail of a good paste.

## Verifying a finished paste from the stored snapshot

Do not judge a paste from the rendered page or from a read-back — count markers in
the document's stored blob. A bare `$` count is meaningless there: the byte stream
already contains structural `$` (`$blocksuite:internal:native$`, `w$<uuid>`), so a
raw `$` count proves nothing either way. Count the latex-level markers instead:

```bash
podman exec <postgres-container> psql -U affine -d affine -tAc \
  "select encode(blob,'hex') from snapshots where guid='<doc-id>';" \
  | python3 -c 'import binascii,sys; sys.stdout.buffer.write(binascii.unhexlify(sys.stdin.read().strip()))' \
  > <snapshot-blob>
python3 - <<'PY'
s = open('<snapshot-blob>', 'rb').read().decode('utf-8', 'replace')
for k in [chr(92)+'frac', chr(92)+'hline', chr(92)+'begin{array}', '&#x20;', '$ ', ' $']:
    print(k, s.count(k))
PY
```

Reading it:

- `&#x20;` > 0 → indentation damage inside a display-math block.
- `$ ` or ` $` > 0 → math source is still stored as literal text, i.e. that formula
  never became an equation.
- `\frac` / `\hline` / `\begin{array}` counts must **equal the same counts in the
  source markdown**. That equality is what proves every formula and every array
  survived the hop, and it is how a repair gets confirmed without asking the user to
  eyeball the page. Snapshot persistence is near-immediate — the client pushes within
  seconds of the paste — so read the blob after the paste settles rather than during it.

For non-formula text, sample windows of 8+ CJK characters from the source markdown
and test each for presence in the blob. Windows that straddle a bold run or an
inline-math run always miss, so confirm their components instead (`说的是` +
`从左边分数到右边分数`, not the joined phrase) — that discriminates cleanly from
real loss. Finish with the `$ ` / ` $` counts above: both 0 means no math source was
left as text.

## Repair work order

1. Find the intact master copy of the same content whenever one exists — the damaged
   document cannot supply what the mis-pair ate. Notes migrated out of another
   notes app are the common case: that app's own document API usually returns clean
   `$…$` / `$$` markdown to repair from.
2. Rebuild that markdown with the delimiter rule (space after every opening `$` that
   would sit flush against a digit) and the no-indentation rule for display math,
   and re-insert the prose the mis-pairing ate (the block dump shows where it ends).
3. Hand it to the user to paste in the editor, or via the UI's Import → Markdown —
   the editor's paste path is the only one that produces real equations. Deliver the
   markdown in a form the user can actually copy from; a file alone regularly leaves
   them stuck, so send the text itself and keep the file as the archive copy. Count
   the formulas in the delivered text against the source before calling it ready.
4. Have the user paste into a **scratch document first** and check that the
   surrounding text survives and the formulas render. The editor's markdown adapter
   is both the path that can create equations and the hop that damaged this one —
   verify before it goes over the original.
5. Do not offer an agent-driven whole-document rewrite (`update_document`) as the
   fix. The same module's reader cannot serialize inline-latex runs or
   `affine:latex` blocks — they come back in `knownUnsupportedBlocks` and vanish
   from the markdown — so any rewrite or diff computed against a read-back cannot
   see the equations that already work, and can drop them. Treat formula-bearing
   documents as editor-owned.

## Re-probe rather than trusting this file

The converter ships with the server, so an image bump can change it. Cheapest proof,
creating nothing: print the module's exports from inside the container to find the
entry points, then feed it a markdown string and read what comes back.

```bash
podman exec <app-container> node -e \
  "console.log(Object.keys(require('/app/dist/server-native.x64.node')).filter(k => /Markdown|Doc/.test(k)))"
```

Adjust that filename to your image's architecture. A `create_document` + block dump
round trip also works but leaves a document behind, and there is no delete tool — the
user has to remove it in the UI.
