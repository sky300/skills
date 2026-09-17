# Spot-Verification Workflow

When verifying ASR transcript claims against actual video visuals, use this lightweight protocol instead of full clip extraction.

## When to use

- You have a transcript with timestamps and need to confirm what's visually happening at specific moments.
- You need to upgrade/downgrade segment priority based on visual evidence.
- You want to check whether a transcript-claimed event (combat, item discovery, character death, etc.) actually has corresponding on-screen visuals.

## Procedure

1. **Extract frames at ASR-mentioned timestamps.** For each key transcript claim, extract a single frame:

   ```bash
   ffmpeg -y -ss <TIMESTAMP_IN_SECONDS> -i <VIDEO_PATH> -frames:v 1 -q:v 3 <VIDEO_DIR>/<video_stem>_frames/verify_<MM_SS>.jpg
   ```

   Use `-ss` before `-i` for fast keyframe seeking. This takes <1s per frame.

   **Important:** Save frames to the video file's directory, never to `/tmp/` or other temporary paths.

   **Parallel extraction:** Use a sequential `for` loop to extract multiple frames in one terminal call — each frame takes <1s so the total is still fast. Do not use shell `&` backgrounding inside a single terminal call; some terminal tools reject it.

   ```bash
   for ts in "00:05:17" "00:14:06" "00:28:00"; do
     fn="$DIR/spot_${ts//:/}.jpg"
     ffmpeg -hide_banner -y -ss "$ts" -i "$VIDEO" -frames:v 1 -q:v 3 "$fn" 2>/dev/null
     echo "$ts -> $fn ($(stat -c%s "$fn" 2>/dev/null) bytes)"
   done
   ```

2. **Send frames to vision analysis with targeted questions.** For each frame, ask about the specific transcript claim:
   - "The transcript says 'X' at this time. Can you see X happening?"
   - "Is there a boss/enemy visible? Is combat happening?"
   - "Is there a [specific item/UI] visible?"

3. **Handle timestamp discrepancies.** If the frame doesn't match the transcript claim:
   - Try ±5–10 seconds around the timestamp.
   - ASR timestamps can lag or lead the visual event by several seconds.
   - If still no match after ±10s, the claim may be about off-screen action or voice-only commentary.

4. **Record verification results.** For each verified segment, note:
   - Confirmed: visual matches transcript claim → keep or upgrade priority
   - Discrepancy: visual differs from transcript (e.g., menu open instead of combat) → downgrade or reclassify
   - Not found: no visual evidence for the claimed content → mark as "voice-only" or "needs manual check in NLE"

5. **Distinguish in the edit plan.** Label each segment as:
   - **Visually confirmed** — frames show the claimed content
   - **Transcript-grounded** — only ASR evidence; visual not yet checked
   - **Needs manual check** — frames inconclusive; must be verified in the NLE

## Verification table template

| ASR timestamp | Transcript claim | Frame result | Verification |
|---|---|---|---|
| MM:SS | Brief description of what transcript says | Description of what frame shows | Confirmed / Discrepancy / Not found |
| MM:SS | ... | ... | ... |

## Key lessons

- ASR segment `start`/`end` are in **milliseconds**, not seconds. Convert before filtering.
- ASR proper nouns are phonetic hints, not authoritative labels. Verify names against on-screen UI.
- ASR timestamps can be off by 5–12 seconds from the visual event. Always try ±5–10 seconds before concluding a claim is wrong.
- A transcript claiming an action is happening does not guarantee the action is visible on screen — the player may be in a menu, or the action may have happened off-screen or earlier.