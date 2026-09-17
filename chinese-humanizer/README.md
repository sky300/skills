# Chinese Humanizer

[English](./README.md) | [简体中文](./README.zh-CN.md)

A Chinese-first skill for stripping the AI flavor out of Simplified Chinese prose — bureaucratic register, nominalization, translationese sentence structure, template rhythm — while keeping facts, terminology, and the author's voice intact.

**Repository**: https://git.nite07.com/nite/skills (subdirectory: `chinese-humanizer/`)

## What it solves

Model-written Chinese usually carries two borrowed layers. One is bureaucratic
register, picked up from official documents and press-release corpora — the
words `赋能`, `抓手`, `闭环` doing the work of plain verbs. The other is
translationese: English sentence skeletons wearing Chinese characters, where
`进行了研究` mirrors "conduct a study" rather than how a Chinese writer would put
it. On top of those sit the model's own habits: regression to the mean, and
phrasing rewarded by RLHF for being agreeable. The result reads as *correct but
voiceless*.

The skill supplies the criteria, the rewrite moves, and the boundaries: what to
change, what must not be touched, what is only editorial craft, and what is
backed by corpus statistics.

## Install

```bash
npx skills add https://git.nite07.com/nite/skills.git -g -s chinese-humanizer
```

Or copy the directory into your agent's skills folder:

```bash
git clone https://git.nite07.com/nite/skills.git
cp -r skills/chinese-humanizer <your agent's skills directory>
```

`<your agent's skills directory>` is a deliberate placeholder: where skills live is
your environment's decision, not the skill's.

## Structure

```
chinese-humanizer/
├── SKILL.md                    # Main file: mechanism, criteria, workflow, rewrite moves, checklist
├── README.md                   # This file (English, canonical)
├── README.zh-CN.md             # Chinese README
├── references/
│   ├── symptoms.md             # Symptom catalogue, four layers, with triggers and protected cases
│   ├── translationese.md       # Europeanized Chinese (Yu Guangzhong's 13 symptoms + 12 EN->ZH fixes)
│   ├── vocabulary.md           # Graded table of high-frequency AI words, substitutes, allow-list
│   ├── evidence.md             # Measured data and evidence grades; why detectors are not proof
│   ├── boundaries.md           # What not to touch, genre matrix, voice calibration
│   └── sources.md              # Provenance of the material, licences, citation caveats
```

## Usage

Ask in whatever language you speak; the text being edited is Chinese:

```
Use chinese-humanizer to rewrite this so it reads like a person wrote it.
Keep the facts and the terminology.
```

```
Check this blog post for the most obvious AI register. List what you find
before rewriting anything.
```

Supplying a writing sample of the author's own prose switches on voice
calibration; the sample outranks the word lists in the skill.

## Basis

Rules come from public corpus research (CCL 2023/2025, ACL 2024, EMNLP 2024,
arXiv 2402.01158, arXiv 2304.02819), Yu Guangzhong's 1987 essay on
Europeanized Chinese, and the rule design of six open-source humanizer skills.
Per-item provenance is in `references/sources.md`; which conclusions have
statistical support and which are only editorial craft is in
`references/evidence.md`.

## Boundaries

It does not perform authorship attribution, does not promise "undetectable after
rewriting", and is not for identity fraud or academic misconduct. Formal genre,
terminology, quotations, and code are left alone.

## License

MIT
