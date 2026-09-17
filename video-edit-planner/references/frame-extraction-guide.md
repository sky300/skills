# Frame Extraction & Vision Token Guide

## Vision model token costs at common resolutions

All major vision models (OpenAI GPT-4o, Anthropic Claude, Google Gemini) process images as tiled patches. Higher resolution = more tokens = higher cost and latency.

### OpenAI GPT-4o / GPT-4.1

- **Low detail:** fixed 85 tokens per image.
- **High detail:** fit inside 2048×2048 box, scale shortest side to ~768px, count 512×512 tiles, then `85 + 170 × tiles`.
- 1024×1024 → ~765 tokens
- 1280×800 → ~935 tokens
- 1920×1080 → ~1105 tokens

Source: [OpenAI vision docs](https://platform.openai.com/docs/guides/vision), [Spoold token estimator](https://www.spoold.com/tools/vision-tokens)

### Anthropic Claude

- Images are processed in 28×28 pixel patches (visual tokens).
- Token cost: `⌈width / 28⌉ × ⌈height / 28⌉`
- **Standard tier** (most models): max long edge 1568px, max 1568 visual tokens.
- **High-res tier** (Opus 4.7/4.8, Sonnet 5, Fable 5, Mythos 5): max long edge 2576px, max 4784 visual tokens.
- Images larger than either limit are downscaled before processing.
- 1024×1024 → ~1296 tokens (standard)
- 1280×800 → ~1334 tokens (standard)
- 1920×1080 → ~1560 tokens (standard, capped), ~2691 tokens (high-res)
- > 20 images per request: each image must be ≤2000px on both sides.
- Max 100 images per API request (200k context models).

Source: [Claude vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)

### Google Gemini

- ≤384×384: 258 tokens per image.
- Larger: 768×768 tiles × 258 tokens per tile.
- 1280×800 → ~1032 tokens
- 1920×1080 → ~1548 tokens

Source: [Spoold token estimator](https://www.spoold.com/tools/vision-tokens)

## Recommended resolution by use case

| Clip duration | Recommended width | JPEG quality | Est. tokens/frame (GPT-4o) | Rationale                                               |
| ------------- | ----------------- | ------------ | -------------------------- | ------------------------------------------------------- |
| <15s          | 1920              | 2            | ~1105                      | Short clips need detail; few frames extracted           |
| 15–60s        | 1280              | 3            | ~935                       | Balance detail vs. token cost                           |
| 60–180s       | 1280              | 3            | ~935                       | Moderate length; standard default                       |
| >180s         | 854               | 5            | ~680                       | Long clips produce many frames; minimize per-frame cost |

## Batch size guidance

| Model context | Max images/batch | Practical batch | Notes                                             |
| ------------- | ---------------- | --------------- | ------------------------------------------------- |
| 8k tokens     | 3–4              | 2–3             | Leave room for text prompt + response             |
| 32k tokens    | 15–20            | 5–8             | Conservative; allows multi-turn follow-ups        |
| 128k tokens   | 60+              | 10–15           | Still batch to maintain response quality          |
| 200k tokens   | 100+             | 15–20           | Large batches ok but response quality may degrade |

**Rule of thumb:** start with 5–8 frames per batch. If the model handles it well, increase. If responses are shallow or cut off, decrease.

## Binary-search frame analysis workflow

```
1. Extract clip (e.g., 00:01:00–00:02:00, 60s)
2. Extract frames: scene + uniform (fps=0.5) → ~30 frames + scene changes
3. Select 5 representative frames (evenly spaced across the range)
4. Send to vision: "What is happening in these frames? Summarize the visual content."
5. Identify sub-range of interest (e.g., 00:01:20–00:01:35 looks relevant)
6. Extract denser frames from sub-range (fps=2, threshold=0.15)
7. Send sub-range frames to vision for detailed analysis
8. Use combined transcript + visual understanding to answer user question
```

## FFmpeg scene detection parameters

### Threshold guide

| Content type              | Recommended `scene` threshold | Notes                                              |
| ------------------------- | ----------------------------- | -------------------------------------------------- |
| Gameplay (subtle changes) | 0.1–0.2                       | Cuts between similar-looking scenes                |
| Standard video            | 0.25–0.35                     | Typical content with scene cuts                    |
| Dynamic/high-action       | 0.35–0.45                     | Many scene changes; higher threshold reduces noise |

### Hardware acceleration

Check support:

```bash
ffmpeg -hwaccels
```

Common methods:

- `cuda` — NVIDIA NVDEC/NVENC (preferred if available)
- `vaapi` — Intel/AMD
- `qsv` — Intel QuickSync
- `vulkan` — cross-platform GPU

### One-step vs two-step frame extraction

**One-step (recommended):** decode once, filter for scene changes + uniform sampling simultaneously.

```bash
ffmpeg -hwaccel cuda -i clip.mkv \
  -vf "scale=1280:-2,fps=0.5,select='gt(scene\,0.3)',showinfo" \
  -vsync vfr -q:v 3 frame_%04d.jpg
```

**Two-step:** run `scdet` filter first to get timestamps, then extract frames at those timestamps. Slower for many frames but allows precise per-timestamp extraction.

```bash
# Step 1: detect scene changes
ffmpeg -i clip.mkv -vf scdet -f null - 2> scdet.log
# Step 2: extract frame at each timestamp
for t in $(grep scdet.score scdet.log | ...); do
  ffmpeg -ss $t -i clip.mkv -frames:v 1 frame_${t}.jpg
done
```

Prefer one-step unless you need per-timestamp control.
