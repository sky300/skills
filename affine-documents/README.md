# AFFiNE Documents

[English](./README.md) | [简体中文](./README.zh-CN.md)

Reading and writing AFFiNE (Notion-style documents plus a whiteboard) documents as an agent: what survives when markdown is written by a tool instead of typed in the editor, why equations can never be created that way, how to tell an intact document from a damaged one, and what repairing one actually requires.

**Repository**: https://git.nite07.com/nite/skills (subdirectory: `affine-documents/`)

## What It Covers

- **Reading** — the read tools an instance exposes, why a markdown read-back is a lossy reconstruction, and how to get ground truth from the stored block tree instead.
- **Writing** — the constructs a tool-written markdown body does and does not convert into native blocks, and the markdown parsers that tear an equation apart on the way.
- **Equations** — the two delimiter rules a repair must follow (padding the opening `$` for inline math; no indentation inside `$$` blocks), each derived from a probe you can re-run.
- **Damage** — the fingerprint of a mis-paired paste, what is genuinely unrecoverable, and the empty latex run that looks like damage but is not.
- **Repair** — the work order: an intact master copy, a rebuild, an editor paste by the user, then verification from the stored snapshot rather than from the page.
- **Verification** — marker counting that proves a paste landed, including the count that proves nothing and the prose-sampling method for text.

## Installation

```bash
# Global install (available across all projects)
npx skills add https://git.nite07.com/nite/skills.git -g -s affine-documents

# List available skills without installing
npx skills add https://git.nite07.com/nite/skills.git --list
```

**Manual install** (any agent, including Hermes Agent):

```bash
git clone https://git.nite07.com/nite/skills.git
cp -r skills/affine-documents <your agent's skills directory>/
```

`<your agent's skills directory>` is a deliberate placeholder — where skills are read from is the user's and the agent's decision, so this skill does not assume a location.

## When To Use It

Use this skill when you want to:

- read what a document actually contains instead of what a reader reconstructs
- write content into a document and know in advance what will not survive
- find out why formulas in a document show as source text
- repair a document whose formulas were damaged by a markdown round trip
- prove that a paste or a write landed, without asking anyone to eyeball the page

## How To Use It

1. Say which document, and whether the concern is reading it faithfully or writing into it.
2. For a write: expect a check of what the converter supports before any promise about formatting, especially for formula-heavy material.
3. For a repair: expect the skill to look for an intact master copy of the text first — the damaged document cannot supply what a mis-pairing consumed.
4. Expect the fix to end in the **editor**, with the user pasting corrected markdown; verification then runs against the stored snapshot.

## Project Structure

```text
affine-documents/
├── SKILL.md                        # Entry point: the two facts, the rules, the repair order
├── README.md                       # This file (English, canonical)
├── README.zh-CN.md                 # Simplified Chinese translation
├── references/
│   ├── markdown-and-formulas.md    # Conversion table, delimiter probes, damage, verification
│   └── reading-documents.md        # Read tools, block vocabulary, snapshot extraction
├── scripts/
│   └── snapshot-strings.py         # Decode a snapshot blob into readable block strings
└── templates/
    └── read-doc-snapshot.sh        # Copy-and-adapt: fetch a snapshot, dump blocks or markdown
```

## Notes

- **No write path can create an equation.** Equations in an AFFiNE document always came from the editor; that is structural, not a syntax problem to work around.
- **Never whole-document rewrite a formula-bearing document.** The reader cannot serialize latex blocks or inline math, so a rewrite computed against a read-back drops them.
- **The stored snapshot is the evidence**, not the rendered page and not the read-back.
- Marked values in `templates/` and placeholders in the references are deliberate: they are the reader's decision, not defaults this skill can pick.

## License

MIT
