# Walkthrough media

GIFs and posters from the local application. Filenames match [`../recording-plan.md`](../recording-plan.md).

| File | Role |
| --- | --- |
| `0N-*.gif` | Animated clip |
| `0N-*-poster.png` | Still from the scenario’s key finding or outcome |

Do not add generated artwork, staged mockups, or captures from a hosted public environment. Keep `LLM_PROVIDER=fake` and `EMBEDDING_PROVIDER=fake`.

Labels burned into the GIFs: **Requester** / **Reviewer**, plus `Local demo · Simulated AI · Synthetic data`. Extra captions are scenario-specific and do not cover findings, source cards, buttons, or status messages.

Waiting periods are shortened. GIF duration is not measured application latency.

## Conversion

From the repo root, after recordings exist under `artifacts/walkthrough/`:

```powershell
python scripts/walkthrough_gif.py
python scripts/walkthrough_gif.py --scenario 01-successful-request
```

Requires FFmpeg (`winget install Gyan.FFmpeg`, or set `FFMPEG_DIR`). Temporary files stay under gitignored `artifacts/walkthrough/gif-work/`. The capture manifest `artifacts/walkthrough/manifest.json` is not modified. Conversion settings are recorded in `artifacts/walkthrough/media-manifest.json`.

## Provenance

This set was converted from the 2026-09-17 capture: installed Chrome, fake LLM/embeddings, recording-stack `RETRIEVAL_TOP_K=8`.
