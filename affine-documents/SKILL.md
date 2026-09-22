---
name: affine-documents
description: "Use when reading or writing AFFiNE documents as an agent: conversion limits, equations, damage and repair."
---

# AFFiNE documents: agent read/write

Getting content into and out of an AFFiNE document (Notion-style docs plus a whiteboard) when the reader or writer is a tool rather than the editor. It assumes access already exists — an MCP endpoint or an API client — because obtaining that access is an instance-management matter, not a document matter.

The one thing to internalise: **a document is a block tree, and the editor is the only writer that can create every kind of block.** Everything below follows from those two facts.

## Read the stored blocks, not a read-back

- A markdown read-back is *reconstructed* from the block tree and is lossy: table row separators collapse, a leading `+` comes back escaped, and latex blocks and inline math cannot be serialized at all (they are reported as unsupported). Treat a read-back as a convenient summary, never as evidence.
- Ground truth is the document's stored snapshot. Count markers there before claiming anything about a document's content, and check prose against it when something looks missing.
- `references/reading-documents.md` covers the read tools, the block vocabulary, the snapshot layout, and the two shipped helpers.

## What a tool-written markdown body becomes

Tables, fenced code, quotes, headings, and lists convert to native blocks. `$...$` and `$$...$$` do **not**: no LaTeX handling exists in the converter, so the source is stored verbatim as paragraph text and displays as raw LaTeX.

Consequences worth stating before the work starts:

- **Equations cannot be created by any write path.** No delimiter style, escaping, or metadata flag changes that; equations in a document always came from the editor. Formula-heavy material (textbook notes, worked solutions) therefore either gets its equations re-inserted by hand or ships with the formula visible as source.
- **A line-leading `+ ` is a markdown bullet**, so a multi-line array equation gets split into a paragraph plus a list item — torn apart on top of not rendering. Keep an addend glued to its sign (`+876`, `+\876`) when the source is meant to survive as text.
- **Never whole-document rewrite a document that should keep its equations.** The reader cannot see them, so a rewrite computed against a read-back treats them as absent and drops them. Formula-bearing documents are editor-owned.

## The two delimiter rules for a repair

Repair markdown is written to be pasted into the editor, which is the only path that produces real equations.

- **Inline math: pad the opening `$`.** For a source that would otherwise sit flush against a digit, the space immediately after the **opening** delimiter is what pairs the run: `$ 20000 - 2868 - 2901$` renders, `$20000 - 2868 - 2901$` does not and swallows the prose after it, and padding only the closer still fails. A source that begins with a backslash command (`\frac{23}{19}`) pairs correctly without padding, so do not space-pad blindly.
- **Display math: no indentation.** A line-leading space inside a `$$` block reaches the equation as the literal entity `&#x20;`, which KaTeX rejects. Take alignment from the array's columns; every line starts with `&`, `\times`, `+`, or `\hline`, and `grep -c '^ ' repair.md` must print `0`.

## Repair work order

1. Find an intact master copy of the same content — the damaged document cannot supply what a mis-pairing ate. Migrated notes are the common case: the previous app's API usually returns clean `$…$` / `$$` markdown.
2. Rebuild it with the two delimiter rules and re-insert the prose the mis-pairing consumed.
3. Hand the text to the user (not only a file — a file regularly leaves them stuck) and have them paste into a **scratch document first**.
4. Verify from the stored snapshot: `\frac` / `\hline` / `\begin{array}` counts must equal the source's, and `&#x20;` plus leftover math source (`$ `, ` $`) must be zero. `\frac`-count equality is how a paste gets confirmed without asking anyone to eyeball a page.

Details, the five-line probe that established the delimiter rules, the damage fingerprint, and the verification recipe are in `references/markdown-and-formulas.md`.

## Hard stops

- Do not report a document as damaged from a read-back alone — an unsupported-blocks list and a missing separator both look like corruption; the snapshot settles it.
- Do not offer an agent-driven rewrite as the repair for a formula-bearing document.
- Do not claim a write landed without reading the same document back: absence of an error is not evidence.
- Say what a tool write cannot do **before** promising a formatting-heavy deliverable.

## Reference routing

- `references/markdown-and-formulas.md` — conversion table, delimiter rules and the probe behind them, damage fingerprint, snapshot verification, repair order, how to re-probe after a server upgrade.
- `references/reading-documents.md` — read tools and their aliases, block flavours and property keys, snapshot extraction, read-back caveats.

## Shipped files

- `scripts/snapshot-strings.py` — decode a snapshot blob (raw or hex, file or stdin) into readable block strings; stdlib only, no environment assumptions. Count markers by piping into `grep -o … | wc -l` — `grep -c` counts runs, not occurrences, and undercounts.
- `templates/read-doc-snapshot.sh` — copy-and-adapt snippet that fetches a document's snapshot row out of the database container and dumps either the block tree or a block-ID-annotated markdown read-back. The container runtime, container names, and database credentials are marked values to set from the deployment.
