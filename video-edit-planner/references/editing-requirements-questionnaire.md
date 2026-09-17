# Editing Requirements Questionnaire

Structured questions for gathering video editing requirements. Ask one at a time with multiple-choice options via the runtime's clarify/prompt tool. Not all questions apply to every session — pick relevant ones based on the user's initial request.

Use English as the template language in this file. At runtime, ask the actual questions in the user's language.

## Questions

### 1. Target platform
Determines aspect ratio, pacing, subtitle density, and meme/sticker density.

- Bilibili-first (landscape, can be fairly fast-paced but still needs setup/context, heavier meme/sticker tolerance)
- Bilibili + Douyin/Shorts dual release (landscape master + vertical cut, very fast pace, high density)
- Bilibili + YouTube (landscape, medium pace, clearer context for broader audiences)
- Douyin/TikTok-first (vertical, extremely fast pace, high visual effect density)

### 2. Narrative style
Determines structure: pure clip reel vs. narrative arc.

- Funny moments compilation: stack the funniest/most chaotic moments, entertainment-first, lighter on story
- Story + comedy hybrid: keep a simple story line and weave funny moments into it
- Highlights montage: emphasize strong plays, clutch moments, wipes, reversals, or hype sections

### 3. Editing strategy
Determines whether to plan by deleting boring parts or by extracting and assembling clips.

- Subtractive: delete boring parts from the full recording, keep continuous segments (default, best for coherence)
- Additive: extract individual clips and assemble them (best for Shorts/highlight reels)
- Hybrid: subtractive backbone with optional inserts from elsewhere (recommended for most cases)

### 4. Planning mode
Determines whether to produce one focused timeline or multiple modular alternatives.

- Give me one strongest recommended full edit plan that is as directly executable as possible
- Give me multiple alternative strategies so I can mix and match pieces into my own final cut
- Give me one mainline plan plus optional replacement openings, endings, pacing choices, and insert ideas

### 5. Role distribution
Determines whose voice/reactions to prioritize.

- The uploader is the main point-of-view / main narrator; others mainly support the progression
- Everyone is equally important; whoever has the funniest line or play gets the focus
- The uploader is the host / commentator; their reactions and commentary drive the pacing

### 6. Effect density
Determines how many stickers, overlays, and effects to recommend.

- Minimal: mostly natural cuts and transitions; no extra stickers or meme overlays unless essential
- Medium: reinforce major punchlines with stickers/memes; visible transitions but not overly flashy
- High: heavily stylized; frequent zooms, shakes, stickers, subtitles-as-effects, meme inserts, and visual exaggeration

### 7. Editor tool
Determines how specific transition/effect instructions are phrased.

- Premiere Pro
- CapCut Desktop
- DaVinci Resolve
- Bcut

### 8. First edit or existing draft
Determines whether to plan from scratch or optimize existing cuts.

- This is the first edit; plan the structure from scratch
- I already have a rough cut / draft and want optimization suggestions
- I already marked some candidate segments and want help connecting them

### 9. BGM style
Determines BGM search/recommendation direction.

- Recommend automatically based on the content (light/funny for daily scenes, hype for combat/high-stakes sections)
- Mostly light / daily-life / relaxed
- Mostly comedic / rhythmic / punchline-driven
- Mostly hype / battle / high-energy

### 10. Number of participants
Determines how to handle multi-person interaction and voice allocation.

- 2-3 people (small co-op group)
- 4-5 people (medium team)
- 6-8 people (full large group)

### 11. Audio handling
Determines subtitle work, BGM vs voice balance, and narration needs.

- Keep original audio and add subtitles
- Keep original audio and do not add subtitles
- Replace much of the original audio with narration/voice-over; keep only the best live reactions
- Mixed approach: mostly keep original audio with subtitles, but add narration for key sections

### 12. Privacy
Determines face-cam handling and any masking needs.

- Face and voice can both be used normally
- Do not show face, but voice is fine
- Need masking / censoring / voice change processing

### 13. Output format
Determines deliverable detail level.

- Simple timestamp notes (for example, "00:12:30 this moment is very funny")
- Detailed editing script table (timecode, segment description, why to keep it, transition ideas, asset needs)
- Execution-ready storyboard / assembly plan (entry point, exit point, transition choice, asset placement, BGM timeline)

### 14. Target duration
Determines how aggressively to cut and pace the content.

- User specifies a target duration (for example 7-8 minutes, 10 minutes, 3 minutes)

## Usage notes

- Ask one question at a time. The runtime's clarify tool with multiple-choice options works best.
- Not all 14 questions are needed every session. If the user's initial request already answers some axes, skip those.
- The questions can be asked in any order, but platform → narrative style → editing strategy → planning mode → effect density → editor tool is a natural priority flow.
- If the user wants a full edit plan, ask the planning-mode question early so you know whether to produce one recommended timeline or multiple alternative strategies.
- If your runtime offers a deeper structured-questioning capability, use it for follow-up depth beyond this template.
