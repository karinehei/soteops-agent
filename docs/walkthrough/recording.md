# Recording walkthrough videos

Raw Playwright videos for [`recording-plan.md`](recording-plan.md). Output is gitignored under `artifacts/walkthrough/`. Planned GIF paths stay `docs/walkthrough/media/*.gif`. Convert those GIFs with `scripts/walkthrough_gif.py` (see below); this recorder does not write GIFs.

## Commands

Isolated stack (creates/resets **only** database `soteops_walkthrough`; never drops the developer database):

```bash
# All six scenarios
uv run python scripts/walkthrough_record.py

# One scenario
uv run python scripts/walkthrough_record.py --scenario 01-successful-request
uv run python scripts/walkthrough_record.py --scenario 02-missing-end-date
uv run python scripts/walkthrough_record.py --scenario 03-prohibited-access
uv run python scripts/walkthrough_record.py --scenario 04-conflicting-instructions
uv run python scripts/walkthrough_record.py --scenario 05-timeout-reconciliation
uv run python scripts/walkthrough_record.py --scenario 06-stale-proposal
```

The recorder prefers ports `8010` / `8011` / `3010`. If those are busy it picks free localhost ports (developer `3000`/`8000`/`8001` can stay running). A developer `next dev` that already holds `frontend/.next` is left alone; the recorder uses `NEXT_DIST_DIR=.next-walkthrough` so the capture instance can bind its own port. It never drops the database named in `DATABASE_URL`; it only creates/resets `soteops_walkthrough`.

If the repo-root `.venv` is a leftover WSL symlink, the recorder uses `artifacts/walkthrough/.venv` via `UV_PROJECT_ENVIRONMENT`.

On Windows, the recorder invokes Alembic, seed, and Uvicorn as `uv run python -m …` instead of console-script wrappers such as `soteops-seed`. That avoids Application Control (WDAC) blocking newly generated `.exe` shims in the isolated venv.

Playwright Chromium is used when already installed. The recorder does not prune other browsers. If the bundled browser is missing and `cdn.playwright.dev` is unreachable, recording falls back to installed Chrome or Edge and records that in the manifest.

If the isolated stack is already running, Playwright alone (still not the ordinary E2E suite):

```bash
cd frontend
npx playwright test -c playwright.record.config.ts
npx playwright test -c playwright.record.config.ts --grep "01 successful request"
```

Ordinary CI E2E remains `cd frontend && npm run test:e2e` (`playwright.config.ts`, `e2e/`). Recording lives in `e2e-record/` and `playwright.record.config.ts`.

## Capture rules (implemented)

- Authenticate in a setup project with video off; recording contexts start already signed in (password field is not in the clips).
- Viewport 1440×900. Readiness uses Playwright assertions; short reading pauses run only after those checks.
- Requester and reviewer use separate contexts and labeled `requester.webm` / `reviewer.webm` files.
- Contexts are closed so WebM files finish writing.
- Manifest: `artifacts/walkthrough/manifest.json`.

## GIF conversion

Uses the existing WebM files. Does not recapture, host, or call models.

```powershell
python scripts/walkthrough_gif.py
python scripts/walkthrough_gif.py --scenario 01-successful-request
```

FFmpeg is required (`winget install Gyan.FFmpeg`, or set `FFMPEG_DIR` to the directory that contains `ffmpeg`). If FFmpeg is missing, the script reports that and writes no GIFs.

Outputs: `docs/walkthrough/media/0N-*.gif` and matching `0N-*-poster.png`. Temporary conversion files: `artifacts/walkthrough/gif-work/`. Settings, input hashes, trim ranges, sizes, and durations: `artifacts/walkthrough/media-manifest.json`. Capture-stage `gifs_generated=false` means videos only; see [`media/provenance.md`](media/provenance.md). The capture manifest is left unchanged.

Waiting periods in the GIFs are shortened. GIF duration is not measured application latency.
