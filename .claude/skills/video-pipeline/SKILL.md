---
name: video-pipeline
description: How Schedler downloads, probes, classifies and normalizes videos (yt-dlp, ffprobe, ffmpeg) and routes them per platform by orientation and duration. Load before changing backend/app/pipeline or the routing rules.
---

# Video pipeline

## Steps

1. **Acquire**: TikTok link → yt-dlp (see the platform-apis skill), or MP4 upload → saved to `media/incoming/`.
2. **Probe**: `ffprobe -v error -select_streams v:0 -show_entries stream=width,height,codec_name,pix_fmt:stream_side_data=rotation -show_entries format=duration -of json`. Apply rotation metadata before computing orientation.
3. **Classify**:
   - ratio = width / height
   - `vertical` if ratio < 0.9, `square` if 0.9 ≤ ratio ≤ 1.1, `horizontal` if ratio > 1.1
4. **Route** (per target):
   - YouTube: `short` if vertical or square and duration ≤ 180 s; otherwise `video`
   - Instagram: always Reels. Warn if horizontal ("Akan tampil dengan bar hitam di Reels").
   - TikTok: allowed for any orientation. Warn if horizontal.
   - Warn if duration exceeds the platform max (IG Reels and TikTok limits change, so keep them in config, not hard-coded).
5. **Normalize** only if needed (codec not h264, pix_fmt not yuv420p, audio present but not aac, no faststart, or long side > 1920):
   `ffmpeg -i in.mp4 -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p -vf "scale='if(gt(iw,ih),-2,min(1080,iw))':'if(gt(iw,ih),min(1080,ih),-2)'" -c:a aac -b:a 128k -ar 48000 -movflags +faststart out.mp4`
   The filter caps the **short** side at 1080, so 1920x1080 stays 1920x1080 (a plain `scale='min(1080,iw)':-2` would shrink horizontal video to 1080 wide).
   If only faststart is missing, remux: `ffmpeg -i in.mp4 -c copy -movflags +faststart out.mp4`.
6. **Store**: hand the final file to `StorageBackend.put()` → `public_url`. Record `size_bytes` and `sha256`.

## Rules

- Never upscale. Never change the aspect ratio. No letterboxing in v1.
- Use the `veryfast` preset (the VPS is small). Run one ffmpeg job at a time (semaphore).
- Duplicate detection: same `sha256` within 30 days → warn in the composer ("Video ini sudah pernah dijadwalkan").
- Keep the original until the normalized file passes probing; then delete the original.
- Tests use tiny generated clips (`ffmpeg -f lavfi -i testsrc=size=1080x1920:duration=2 …`) in `backend/tests/fixtures/`, never real user videos.
