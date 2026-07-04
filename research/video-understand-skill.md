# video-understand skill — OSS choices (2026-07-03)

Skill at `.claude/skills/video-understand/` (SKILL.md + ingest.py glue).

Chosen (canonical, no real competitors on CPU):
- **ffmpeg 7.1** (apt) — scene-change keyframes (`select='gt(scene,0.30)'` + showinfo pts_time) + 1-frame/10s periodic fallback, capped 80; audio extraction 16 kHz mono.
- **faster-whisper 1.2.1** (pip, .venv) — CTranslate2 Whisper, `device=cpu, compute_type=int8`, VAD filter; default model `small` (use `--model tiny` for quick runs; first use of a size downloads weights).
- **yt-dlp 2026.06.09** (pip, .venv) — URL ingestion, `bv*[height<=1080]+ba/b` merged to mp4.

Rejected: openai-whisper (slower on CPU than CTranslate2 port), PySceneDetect (ffmpeg scene filter suffices — one fewer dep), moviepy (wrapper overhead, no gain).

Outputs land in `research/video/<slug>/` (frames/, transcript.md, manifest.json), then the
skill chain reads frames with vision + transcript → understanding.md → /research-projects
→ plan.md.

Smoke-tested end-to-end on a generated 20s clip: frames extracted with correct timestamps,
vision-readable; silent audio honestly reported as "No speech detected".
