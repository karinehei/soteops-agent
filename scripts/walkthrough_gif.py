"""Convert walkthrough WebM recordings into documentation GIFs and posters.

Uses FFmpeg. Temporary files stay under artifacts/walkthrough/. Does not modify
artifacts/walkthrough/manifest.json. Does not fabricate application frames.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CAPTURE_MANIFEST = REPO_ROOT / "artifacts" / "walkthrough" / "manifest.json"
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "walkthrough"
WORK_DIR = ARTIFACT_ROOT / "gif-work"
MEDIA_DIR = REPO_ROOT / "docs" / "walkthrough" / "media"
MEDIA_MANIFEST = ARTIFACT_ROOT / "media-manifest.json"
DEMO_LABEL = "Local demo · Simulated AI · Synthetic data"
WAITING_DISCLOSURE = (
    "Waiting periods are shortened. GIF duration is not measured application latency."
)
FONT_CANDIDATES = [
    Path(r"C:\Windows\Fonts\segoeui.ttf"),
    Path(r"C:\Windows\Fonts\arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]

# Trim points were chosen by inspecting extracted frames of the capture videos.
# Times are seconds from the start of that source file.
SCENARIOS: dict[str, dict[str, Any]] = {
    "01-successful-request": {
        "gif": "01-successful-request.gif",
        "poster": "01-successful-request-poster.png",
        "poster_from": "reviewer-outcome",
        "segments": [
            {
                "id": "requester-prepare",
                "source": "requester.webm",
                "start": 1.00,
                "end": 3.20,
                "role": "Requester",
                "freeze": 1.0,
            },
            {
                "id": "reviewer-approve",
                "source": "reviewer.webm",
                "start": 1.90,
                "end": 4.90,
                "role": "Reviewer",
                "freeze": 1.0,
            },
            {
                "id": "reviewer-outcome",
                "source": "reviewer.webm",
                "start": 4.90,
                "end": 7.48,
                "role": "Reviewer",
                "freeze": 2.0,
                "extra": "Mock record received — no account provisioned",
            },
        ],
    },
    "02-missing-end-date": {
        "gif": "02-missing-end-date.gif",
        "poster": "02-missing-end-date-poster.png",
        "poster_from": "requester-result",
        "visual_limitation": (
            "Correction is a held frame of the open editor; the filled 2026-12-31 date "
            "is visible after re-preparation. The status badge is then scrolled off-screen. "
            "No reviewer approve is in this clip."
        ),
        "segments": [
            {
                "id": "requester-clarification",
                "source": "requester.webm",
                "start": 1.50,
                "end": 3.20,
                "role": "Requester",
                "freeze": 2.0,
            },
            {
                "id": "requester-correction",
                "source": "requester.webm",
                "start": 3.20,
                "end": 3.40,
                "role": "Requester",
                "freeze": 2.0,
                "hold_frame": True,
            },
            {
                "id": "requester-result",
                "source": "requester.webm",
                "start": 3.95,
                "end": 4.92,
                "role": "Requester",
                "freeze": 2.8,
            },
        ],
    },
    "03-prohibited-access": {
        "gif": "03-prohibited-access.gif",
        "poster": "03-prohibited-access-poster.png",
        "poster_from": "requester-finding",
        "visual_limitation": (
            "The Kielletty käyttöoikeus title is below the captured 1440×900 viewport; "
            "the clip shows the requested role tuotanto-superadmin, status Odottaa täsmennystä, "
            "and a reviewer queue that lists other ready cases, not this request. "
            "The tested API 409 is not in the video."
        ),
        "segments": [
            {
                "id": "requester-finding",
                "source": "requester.webm",
                "start": 1.85,
                "end": 2.96,
                "role": "Requester",
                "freeze": 4.0,
            },
            {
                "id": "reviewer-queue",
                "source": "reviewer-queue.webm",
                "start": 0.90,
                "end": 2.28,
                "role": "Reviewer",
                "freeze": 4.0,
            },
        ],
    },
    "04-conflicting-instructions": {
        "gif": "04-conflicting-instructions.gif",
        "poster": "04-conflicting-instructions-poster.png",
        "poster_from": "requester-sources",
        "visual_limitation": (
            "Ristiriita B is in the captured viewport. Ristiriita A was asserted in the DOM "
            "during recording but scrolled out of frame; it is not fabricated here."
        ),
        "segments": [
            {
                "id": "requester-clarification",
                "source": "requester.webm",
                "start": 1.45,
                "end": 1.56,
                "role": "Requester",
                "freeze": 3.2,
                "hold_frame": True,
            },
            {
                "id": "requester-sources",
                "source": "requester.webm",
                "start": 1.72,
                "end": 3.48,
                "role": "Requester",
                "freeze": 5.0,
                "extra": "Recording configuration: RETRIEVAL_TOP_K=8",
            },
        ],
    },
    "05-timeout-reconciliation": {
        "gif": "05-timeout-reconciliation.gif",
        "poster": "05-timeout-reconciliation-poster.png",
        "poster_from": "reviewer-reconcile",
        "segments": [
            {
                "id": "requester-prepare",
                "source": "requester.webm",
                "start": 0.70,
                "end": 3.20,
                "role": "Requester",
                "freeze": 0.8,
            },
            {
                "id": "reviewer-approve",
                "source": "reviewer.webm",
                "start": 1.80,
                "end": 4.10,
                "role": "Reviewer",
                "freeze": 1.0,
            },
            {
                "id": "reviewer-reconcile",
                "source": "reviewer.webm",
                "start": 4.10,
                "end": 6.20,
                "role": "Reviewer",
                "freeze": 2.2,
                "extra": "Simulated lost response; automatic reconciliation",
            },
        ],
    },
    "06-stale-proposal": {
        "gif": "06-stale-proposal.gif",
        "poster": "06-stale-proposal-poster.png",
        "poster_from": "reviewer-stale",
        "segments": [
            {
                "id": "requester-ready",
                "source": "requester.webm",
                "start": 1.70,
                "end": 3.40,
                "role": "Requester",
                "freeze": 1.0,
            },
            {
                "id": "reviewer-opens",
                "source": "reviewer.webm",
                "start": 1.25,
                "end": 3.20,
                "role": "Reviewer",
                "freeze": 1.2,
            },
            {
                "id": "requester-edits",
                "source": "requester.webm",
                "start": 5.48,
                "end": 5.70,
                "role": "Requester",
                "freeze": 1.8,
                "hold_frame": True,
            },
            {
                "id": "reviewer-stale",
                "source": "reviewer.webm",
                "start": 5.30,
                "end": 8.28,
                "role": "Reviewer",
                "freeze": 1.4,
                "extra": "Stale proposal rejected during review",
            },
        ],
    },
}


def log(message: str) -> None:
    print(message, flush=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_ffmpeg() -> tuple[Path, Path]:
    env_dir = os.environ.get("FFMPEG_DIR")
    names = ("ffmpeg.exe", "ffmpeg") if os.name == "nt" else ("ffmpeg",)
    probe_names = ("ffprobe.exe", "ffprobe") if os.name == "nt" else ("ffprobe",)
    candidates: list[Path] = []
    if env_dir:
        candidates.append(Path(env_dir) / names[0])
    which = shutil.which("ffmpeg")
    if which:
        candidates.append(Path(which))
    winget = (
        Path.home()
        / "AppData/Local/Microsoft/WinGet/Packages"
        / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
        / "ffmpeg-9.0.1-full_build/bin/ffmpeg.exe"
    )
    candidates.append(winget)
    for candidate in candidates:
        if candidate.is_file():
            probe = candidate.with_name(
                "ffprobe.exe" if candidate.suffix.lower() == ".exe" else "ffprobe"
            )
            if not probe.is_file():
                found_probe = shutil.which(probe_names[0])
                if not found_probe:
                    raise RuntimeError(f"ffprobe not found next to {candidate}")
                probe = Path(found_probe)
            return candidate, probe
    raise RuntimeError(
        "FFmpeg is not available. Install it (for example `winget install Gyan.FFmpeg`) "
        "or set FFMPEG_DIR to the directory that contains ffmpeg. GIFs were not generated."
    )


def find_font() -> Path:
    for path in FONT_CANDIDATES:
        if path.is_file():
            return path
    raise RuntimeError("No UI font found for FFmpeg drawtext (tried Segoe UI and Arial).")


def ffprobe_duration(ffprobe: Path, path: Path) -> float:
    result = subprocess.run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def drawtext_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "\\%")
    )


def overlay_filter(font: Path, role: str, extra: str) -> str:
    """Draw labels on the top banner so findings and source cards stay visible."""
    fontfile = str(font).replace("\\", "/").replace(":", "\\:")
    role_text = drawtext_escape(f"{role}  ·  {DEMO_LABEL}")
    parts = [
        "drawbox=x=0:y=0:w=iw:h=34:color=0x163028@0.96:t=fill",
        (
            f"drawtext=fontfile='{fontfile}':text='{role_text}'"
            ":x=16:y=8:fontsize=15:fontcolor=white"
        ),
    ]
    if extra:
        extra_text = drawtext_escape(extra)
        parts.extend(
            [
                "drawbox=x=0:y=34:w=iw:h=28:color=0x163028@0.92:t=fill",
                (
                    f"drawtext=fontfile='{fontfile}':text='{extra_text}'"
                    ":x=16:y=40:fontsize=14:fontcolor=0xf3efe4"
                ),
            ]
        )
    return ",".join(parts)


def run_ffmpeg(ffmpeg: Path, args: list[str]) -> None:
    result = subprocess.run(
        [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "ffmpeg failed")


def load_capture() -> dict[str, Any]:
    if not CAPTURE_MANIFEST.is_file():
        raise RuntimeError(f"Missing capture manifest: {CAPTURE_MANIFEST}")
    return json.loads(CAPTURE_MANIFEST.read_text(encoding="utf-8"))


def scenario_record(capture: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    for item in capture["scenarios"]:
        if item["id"] == scenario_id:
            return item
    raise RuntimeError(f"{scenario_id} is missing from the capture manifest.")


def encode_segment_video(
    ffmpeg: Path,
    args_before_output: list[str],
    output: Path,
    fps: int,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        ffmpeg,
        [
            *args_before_output,
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(fps),
            "-fps_mode",
            "cfr",
            str(output),
        ],
    )


def render_segment(
    *,
    ffmpeg: Path,
    ffprobe: Path,
    font: Path,
    source: Path,
    spec: dict[str, Any],
    output: Path,
    width: int,
    fps: int,
) -> dict[str, Any]:
    start = float(spec["start"])
    end = float(spec["end"])
    freeze = float(spec.get("freeze") or 0)
    extra = str(spec.get("extra") or "")
    hold_frame = bool(spec.get("hold_frame"))
    vf = (
        f"scale={width}:-1:flags=lanczos,fps={fps},setsar=1,"
        + overlay_filter(font, spec["role"], extra)
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    duration = end - start
    if hold_frame:
        duration = max(duration, 0.20)
        still = output.with_name(output.stem + "-hold.png")
        run_ffmpeg(
            ffmpeg,
            [
                "-ss",
                f"{start:.3f}",
                "-i",
                str(source),
                "-frames:v",
                "1",
                str(still),
            ],
        )
    if duration <= 0.05:
        raise RuntimeError(f"Segment {spec['id']} has a non-positive duration.")
    # Seek with input -ss/-t (before -i). Output -t would clip tpad freezes.
    # Input seek matches the inspected -ss stills; trim-filter PTS on VP8 can skip the shot.
    if freeze > 0:
        vf += f",tpad=stop_mode=clone:stop_duration={freeze:.3f}"
    encode_segment_video(
        ffmpeg,
        [
            "-ss",
            f"{start:.3f}",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(source),
            "-vf",
            vf,
        ],
        output,
        fps,
    )
    return {
        "id": spec["id"],
        "source": source.name,
        "role": spec["role"],
        "start": start,
        "end": start + duration,
        "hold_frame": hold_frame,
        "freeze_seconds": freeze,
        "extra_caption": extra,
        "duration_seconds": round(ffprobe_duration(ffprobe, output), 3),
        "output": str(output),
    }


def concat_segments(ffmpeg: Path, parts: list[Path], output: Path) -> None:
    list_path = output.with_suffix(".txt")
    list_path.write_text(
        "".join(f"file '{part.as_posix()}'\n" for part in parts),
        encoding="utf-8",
    )
    run_ffmpeg(
        ffmpeg,
        [
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-an",
            "-c",
            "copy",
            str(output),
        ],
    )


def encode_gif(ffmpeg: Path, source: Path, output: Path, fps: int) -> None:
    palette = source.with_name(source.stem + "-palette.png")
    run_ffmpeg(
        ffmpeg,
        [
            "-i",
            str(source),
            "-vf",
            f"fps={fps},palettegen=max_colors=128:stats_mode=full",
            str(palette),
        ],
    )
    run_ffmpeg(
        ffmpeg,
        [
            "-i",
            str(source),
            "-i",
            str(palette),
            "-lavfi",
            f"fps={fps} [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=4",
            "-loop",
            "0",
            str(output),
        ],
    )


def extract_poster(ffmpeg: Path, source: Path, output: Path, seconds: float) -> None:
    run_ffmpeg(
        ffmpeg,
        [
            "-ss",
            f"{max(seconds, 0):.3f}",
            "-i",
            str(source),
            "-frames:v",
            "1",
            str(output),
        ],
    )


def extract_gif_stills(
    ffmpeg: Path, ffprobe: Path, gif: Path, dest: Path, fps: int
) -> dict[str, str]:
    dest.mkdir(parents=True, exist_ok=True)
    duration = ffprobe_duration(ffprobe, gif)
    n_frames = max(int(round(duration * fps)), 1)
    stills = {
        "first": 0,
        "key": min(max(int(n_frames * 0.45), 0), n_frames - 1),
        "final": n_frames - 1,
    }
    paths: dict[str, str] = {}
    for name, frame in stills.items():
        path = dest / f"{name}.png"
        # Select by decoded frame index. Input -ss on palette GIFs can skip held frames.
        run_ffmpeg(
            ffmpeg,
            [
                "-i",
                str(gif),
                "-vf",
                f"select=eq(n\\,{frame})",
                "-fps_mode",
                "vfr",
                "-frames:v",
                "1",
                str(path),
            ],
        )
        paths[name] = str(path)
    return paths


def gif_decodes(ffprobe: Path, path: Path) -> bool:
    try:
        duration = ffprobe_duration(ffprobe, path)
    except (subprocess.CalledProcessError, ValueError):
        return False
    return duration > 0 and path.stat().st_size > 0


def convert_scenario(
    *,
    ffmpeg: Path,
    ffprobe: Path,
    font: Path,
    capture: dict[str, Any],
    scenario_id: str,
    fps: int,
    width: int,
) -> dict[str, Any]:
    record = scenario_record(capture, scenario_id)
    if not record.get("assertions_passed") or record.get("outcome") != "passed":
        raise RuntimeError(
            f"{scenario_id} capture assertions did not pass "
            f"(outcome={record.get('outcome')}). GIF not generated."
        )
    plan = SCENARIOS[scenario_id]
    source_dir = ARTIFACT_ROOT / scenario_id
    work = WORK_DIR / scenario_id
    work.mkdir(parents=True, exist_ok=True)
    inputs: list[dict[str, Any]] = []
    for path_str in record["video_segments"]:
        path = Path(path_str)
        if not path.is_file():
            raise RuntimeError(f"Missing input video: {path}")
        inputs.append(
            {
                "path": str(path),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "duration_seconds": round(ffprobe_duration(ffprobe, path), 3),
            }
        )
    rendered: list[dict[str, Any]] = []
    part_files: list[Path] = []
    for index, spec in enumerate(plan["segments"]):
        source = source_dir / spec["source"]
        if not source.is_file():
            raise RuntimeError(f"Missing source {source} for {scenario_id}")
        part = work / f"{index:02d}-{spec['id']}.mp4"
        rendered.append(
            render_segment(
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
                font=font,
                source=source,
                spec=spec,
                output=part,
                width=width,
                fps=fps,
            )
        )
        part_files.append(part)
    concat_path = work / "concat.mp4"
    concat_segments(ffmpeg, part_files, concat_path)
    gif_path = MEDIA_DIR / plan["gif"]
    poster_path = MEDIA_DIR / plan["poster"]
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    encode_gif(ffmpeg, concat_path, gif_path, fps)
    concat_duration = ffprobe_duration(ffprobe, concat_path)
    poster_seconds = concat_duration - 0.2
    for index, spec in enumerate(plan["segments"]):
        if spec["id"] == plan["poster_from"]:
            poster_seconds = sum(item["duration_seconds"] for item in rendered[:index]) + (
                rendered[index]["duration_seconds"] * 0.72
            )
            break
    extract_poster(ffmpeg, concat_path, poster_path, poster_seconds)
    stills = extract_gif_stills(ffmpeg, ffprobe, gif_path, work / "verify", fps)
    decoded = gif_decodes(ffprobe, gif_path)
    size = gif_path.stat().st_size
    return {
        "id": scenario_id,
        "assertions_passed": True,
        "inputs": inputs,
        "segment_order": [item["id"] for item in rendered],
        "segments": rendered,
        "fps": fps,
        "width": width,
        "palette_max_colors": 128,
        "dither": "bayer",
        "gif": str(gif_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "poster": str(poster_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "gif_bytes": size,
        "gif_duration_seconds": round(ffprobe_duration(ffprobe, gif_path), 3),
        "poster_seconds": round(poster_seconds, 3),
        "decoded": decoded,
        "verify_frames": stills,
        "waiting_disclosure": WAITING_DISCLOSURE,
        "capture_limitation": record.get("limitation") or "",
        "visual_limitation": plan.get("visual_limitation") or "",
        "oversized": size > 5 * 1024 * 1024,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create walkthrough GIFs from captured WebM files."
    )
    parser.add_argument("--scenario", default="all")
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument("--width", type=int, default=960)
    args = parser.parse_args()
    selected = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    unknown = [item for item in selected if item not in SCENARIOS]
    if unknown:
        log(f"Unknown scenario: {unknown[0]}")
        return 2

    try:
        ffmpeg, ffprobe = find_ffmpeg()
        font = find_font()
        capture = load_capture()
    except RuntimeError as exc:
        log(str(exc))
        return 2

    log(f"FFmpeg: {ffmpeg}")
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    previous_by_id: dict[str, dict[str, Any]] = {}
    if args.scenario != "all" and MEDIA_MANIFEST.is_file():
        previous = json.loads(MEDIA_MANIFEST.read_text(encoding="utf-8"))
        previous_by_id = {
            item["id"]: item
            for item in previous.get("scenarios", [])
            if isinstance(item, dict) and item.get("id")
        }
    results: list[dict[str, Any]] = []
    failed = 0
    converted: dict[str, dict[str, Any]] = {}
    for scenario_id in selected:
        log(f"Converting {scenario_id}")
        try:
            converted[scenario_id] = convert_scenario(
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
                font=font,
                capture=capture,
                scenario_id=scenario_id,
                fps=args.fps,
                width=args.width,
            )
            item = converted[scenario_id]
            megabytes = item["gif_bytes"] / (1024 * 1024)
            log(
                f"  {item['gif']} {item['gif_duration_seconds']}s "
                f"{megabytes:.2f} MiB decoded={item['decoded']}"
            )
        except RuntimeError as exc:
            failed += 1
            log(f"  BLOCKED: {exc}")
            previous = previous_by_id.get(scenario_id) or {}
            if previous.get("decoded") and not previous.get("blocked"):
                log(f"  Keeping previous successful {scenario_id} media-manifest entry.")
                converted[scenario_id] = previous
            else:
                converted[scenario_id] = {
                    "id": scenario_id,
                    "blocked": True,
                    "limitation": str(exc),
                }

    merged = {**previous_by_id, **converted}
    results = [merged[key] for key in SCENARIOS if key in merged]
    gifs_ok = bool(results) and all(not item.get("blocked") for item in results)

    media_manifest = {
        "created": date.today().isoformat(),
        "capture_manifest": str(CAPTURE_MANIFEST.relative_to(REPO_ROOT)).replace("\\", "/"),
        "capture_manifest_sha256": sha256_file(CAPTURE_MANIFEST),
        "capture_source_commit": capture.get("source_commit"),
        "capture_working_tree_dirty": capture.get("working_tree_dirty"),
        "capture_date": capture.get("capture_date"),
        "providers": capture.get("providers"),
        "retrieval_top_k": capture.get("retrieval_top_k"),
        "retrieval_top_k_reason": capture.get("retrieval_top_k_reason"),
        "browser": capture.get("browser"),
        "gifs_generated": gifs_ok,
        "waiting_disclosure": WAITING_DISCLOSURE,
        "ffmpeg": str(ffmpeg),
        "scenarios": results,
    }
    MEDIA_MANIFEST.write_text(json.dumps(media_manifest, indent=2) + "\n", encoding="utf-8")
    log(f"Wrote {MEDIA_MANIFEST}")
    log("Capture manifest was not modified.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
