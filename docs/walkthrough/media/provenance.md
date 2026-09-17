# Walkthrough media provenance

Tracked summary for the published GIFs. Detailed capture JSON, raw WebM, and conversion work files stay under gitignored `artifacts/walkthrough/`. Relative paths below are from the repository root.

## Capture vs conversion

`gifs_generated=false` on capture manifests describes the **video-capture stage only**. Those files are not updated when GIFs are written. Current conversion status is `artifacts/walkthrough/media-manifest.json` (`gifs_generated=true` after a successful convert).

Environment for every listed run: `LLM_PROVIDER=fake`, `EMBEDDING_PROVIDER=fake`, database `soteops_walkthrough`, local Chrome, no hosting, no paid model calls.

## `RETRIEVAL_TOP_K`

Published GIFs used two recording configurations. Default app/CI `RETRIEVAL_TOP_K` remains **4**.

| Published scenarios | Value | Recording |
| --- | --- | --- |
| 01, 05, 06 | 8 | Original full-stack capture |
| 02, 03 | 4 | Isolated recapture stacks (those runs only) |
| 04 | 8 | Isolated recapture stack (default 4 did not return both conflict documents) |

`TOP_K=8` is therefore on **four** published scenarios (01, 04, 05, 06), not only 04. The 04 GIF overlay names that recapture’s isolated API process; it does not mean 04 is the only clip recorded at 8.

Ignored `artifacts/walkthrough/manifest.json` currently reports `retrieval_top_k=8` because that field is the **latest recapture run** (04), not a roll-up of every published GIF.

## Historical records (gitignored)

| Path | What it is |
| --- | --- |
| `artifacts/walkthrough/history/manifest-2026-09-17-initial.json` | Original six-scenario capture |
| `artifacts/walkthrough/history/media-manifest-2026-09-17-initial.json` | Original conversion |
| `artifacts/walkthrough/history/media-2026-09-17-initial/` | Original GIFs/posters |
| `artifacts/walkthrough/manifest-recapture-20260917-142414.json` | 03 recapture (top_k=4, dirty tree) |
| `artifacts/walkthrough/manifest-recapture-20260917-142523.json` | 02 recapture (top_k=4, dirty tree) |
| `artifacts/walkthrough/manifest-recapture-20260917-143249.json` | 04 recapture (top_k=8, dirty tree) |
| `artifacts/walkthrough/history/manifest-20260917-*.json` | Merged manifests archived before later recaptures |
| `artifacts/walkthrough/history/videos-20260917-*/` | Previous 02/03/04 WebM files |
| `artifacts/walkthrough/history/media-20260917-pre-hold/` | 02–04 GIFs from recapture before still-hold conversion |
| `artifacts/walkthrough/manifest.json` | Current merged capture index |
| `artifacts/walkthrough/media-manifest.json` | Current conversion (input hashes, trims, sizes) |

Recapture source revision: `1b948715194950b9b9cddf9854d9709efe2b9168`, working tree dirty. Original 01/05/06 capture: `eb0b56da96a762f0c03e531fcaf6eabd54ffc768`, working tree dirty.

## Published media

Converted at 960px wide, 10 fps, 128-color bayer GIF. Waiting periods are shortened; GIF duration is not measured application latency. Extra overlay captions are documentation labels, not application UI.

| File | Duration | Size | SHA-256 |
| --- | --- | --- | --- |
| `docs/walkthrough/media/01-successful-request.gif` | 11.8s | 3.42 MiB | `8c9e1412e89df697966e00ac52341ffcc0c5175d2ac22a0520b695eb8a544bd8` |
| `docs/walkthrough/media/02-missing-end-date.gif` | 9.0s | 0.57 MiB | `290f3aa0d6605c92df662bdcbb26de917684524d355302581625b11fc552cd69` |
| `docs/walkthrough/media/03-prohibited-access.gif` | 7.9s | 0.36 MiB | `e597aad078cf9be1ea06f4e6d5c56e9fbbfe788143cd0b8eaf563b70b678a912` |
| `docs/walkthrough/media/04-conflicting-instructions.gif` | 9.2s | 0.44 MiB | `99ebabe1b0a0f8262b42156e7d6bb3cd54b0d950e9d610371d11fde8d8de16b2` |
| `docs/walkthrough/media/05-timeout-reconciliation.gif` | 10.9s | 3.99 MiB | `9aa41b378968cc708f19c658139a036dc34900a0a984c5f6dc0165add466fc41` |
| `docs/walkthrough/media/06-stale-proposal.gif` | 12.3s | 1.59 MiB | `8af92eeb843bff491d0b3ae61813b99ce8c5f570ebc82640a210834db4494d4b` |

Posters: `docs/walkthrough/media/0N-*-poster.png`. 02 poster is **Odottaa tarkastusta** after re-preparation. 03 poster is **Kielletty käyttöoikeus**. 04 poster is **Ristiriita A**.

01, 05, and 06 GIFs/posters were not regenerated. 02–04 GIFs are held stills from inspected recapture frames (VP8 keyframe seeks skipped those frames when trimming motion windows).

### Recapture inputs used for 02–04

| Scenario | Input | Duration | SHA-256 |
| --- | --- | --- | --- |
| 02 | `artifacts/walkthrough/02-missing-end-date/requester.webm` | 9.56s | `09ad946446783675f558bb4d62c046cb49c7d39fed062f8cbff1ad1af208b6dd` |
| 03 | `artifacts/walkthrough/03-prohibited-access/requester.webm` | 9.72s | `e0175be032ea5250720c5282bcf2d33f7183de84e9fbadb4d7a951c328ecd61e` |
| 03 | `artifacts/walkthrough/03-prohibited-access/reviewer-queue.webm` | 2.92s | `9966da5f4233a1c20c989aafaead2aa26bff9a19fdb4baa7fca38e93c096e23c` |
| 04 | `artifacts/walkthrough/04-conflicting-instructions/requester.webm` | 12.44s | `abd61c89f0082082663f16c211070b10412cd8c29400536fae292d7cebc0c774` |
