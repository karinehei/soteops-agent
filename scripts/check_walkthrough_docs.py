"""Lightweight walkthrough documentation checks. Stdlib only.

Verifies tracked Markdown and published GIFs/posters. Does not read
artifacts/walkthrough/, call FFmpeg, start servers, or fetch URLs.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

SCENARIOS = (
    "01-successful-request",
    "02-missing-end-date",
    "03-prohibited-access",
    "04-conflicting-instructions",
    "05-timeout-reconciliation",
    "06-stale-proposal",
)
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024
GIF_MAGIC = (b"GIF87a", b"GIF89a")
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "irc:", "ftp://")
FENCE_RE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`]+`")
INLINE_LINK_RE = re.compile(r"!?\[([^\]]*)\]\(([^)]+)\)")
REF_DEF_RE = re.compile(r"^ {0,3}\[([^\]]+)\]:\s+(\S+)", re.MULTILINE)
REF_USE_RE = re.compile(r"!?\[([^\]]*)\]\[([^\]]*)\]")


def log(message: str) -> None:
    print(message, flush=True)


def markdown_files(root: Path) -> list[Path]:
    files = [root / "README.md"]
    walkthrough = root / "docs" / "walkthrough"
    if walkthrough.is_dir():
        files.extend(sorted(walkthrough.rglob("*.md")))
    return [path for path in files if path.is_file()]


def strip_code(text: str) -> str:
    return INLINE_CODE_RE.sub(" ", FENCE_RE.sub(" ", text))


def split_destination(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        value = value[1 : value.index(">")].strip()
    else:
        value = value.split()[0] if value else value
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
    return value


def is_external(target: str) -> bool:
    lowered = target.lower()
    return lowered.startswith(EXTERNAL_PREFIXES) or "://" in target


def extract_local_targets(text: str) -> list[str]:
    body = strip_code(text)
    targets: list[str] = []
    definitions: dict[str, str] = {}
    for match in REF_DEF_RE.finditer(body):
        definitions[match.group(1).strip().lower()] = split_destination(match.group(2))
    for match in INLINE_LINK_RE.finditer(body):
        targets.append(split_destination(match.group(2)))
    for match in REF_USE_RE.finditer(body):
        label = (match.group(2) or match.group(1)).strip().lower()
        if label in definitions:
            targets.append(definitions[label])
        else:
            targets.append(f"missing-ref:{label}")
    return targets


def check_links(root: Path) -> list[str]:
    errors: list[str] = []
    for path in markdown_files(root):
        text = path.read_text(encoding="utf-8")
        for target in extract_local_targets(text):
            if target.startswith("missing-ref:"):
                errors.append(f"{path.relative_to(root)}: undefined reference [{target[12:]}]")
                continue
            if not target or target.startswith("#") or is_external(target):
                continue
            file_part = target.split("#", 1)[0]
            resolved = (path.parent / file_part).resolve()
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                errors.append(f"{path.relative_to(root)}: link leaves repository: {target}")
                continue
            if not resolved.exists():
                errors.append(f"{path.relative_to(root)}: missing {target}")
    return errors


def media_paths(root: Path) -> list[Path]:
    media = root / "docs" / "walkthrough" / "media"
    paths: list[Path] = []
    for scenario in SCENARIOS:
        paths.append(media / f"{scenario}.gif")
        paths.append(media / f"{scenario}-poster.png")
    return paths


def check_media(root: Path) -> list[str]:
    errors: list[str] = []
    total = 0
    for path in media_paths(root):
        rel = path.relative_to(root)
        if not path.is_file():
            errors.append(f"missing media {rel}")
            continue
        size = path.stat().st_size
        if size <= 0:
            errors.append(f"empty media {rel}")
            continue
        if size > MAX_FILE_BYTES:
            errors.append(f"{rel} is {size} bytes; budget is {MAX_FILE_BYTES} per file")
        total += size
        header = path.read_bytes()[:8]
        if path.suffix.lower() == ".gif" and not header.startswith(GIF_MAGIC):
            errors.append(f"{rel} is not a GIF")
        if path.suffix.lower() == ".png" and not header.startswith(PNG_MAGIC):
            errors.append(f"{rel} is not a PNG")
    if total > MAX_TOTAL_BYTES:
        errors.append(f"walkthrough media total {total} bytes exceeds {MAX_TOTAL_BYTES}")
    return errors


def check_provenance(root: Path) -> list[str]:
    path = root / "docs" / "walkthrough" / "media" / "provenance.md"
    if not path.is_file():
        return ["missing docs/walkthrough/media/provenance.md"]
    text = path.read_text(encoding="utf-8")
    errors = [
        f"provenance.md does not mention {scenario}"
        for scenario in SCENARIOS
        if scenario not in text
    ]
    return errors


def run_checks(root: Path) -> list[str]:
    errors: list[str] = []
    errors.extend(check_links(root))
    errors.extend(check_media(root))
    errors.extend(check_provenance(root))
    return errors


def media_summary(root: Path) -> str:
    paths = [path for path in media_paths(root) if path.is_file()]
    total = sum(path.stat().st_size for path in paths)
    return f"{len(paths)} files, {total} bytes ({total / (1024 * 1024):.2f} MiB)"


def self_check() -> int:
    """Broken fixture must fail. Does not touch repository deliverables."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "docs" / "walkthrough" / "media").mkdir(parents=True)
        (root / "README.md").write_text(
            "[missing page](docs/walkthrough/nope.md)\n",
            encoding="utf-8",
        )
        (root / "docs" / "walkthrough" / "README.md").write_text("# Walkthrough\n", encoding="utf-8")
        errors = run_checks(root)
        has_missing_link = any("nope.md" in item for item in errors)
        missing_media = sum(1 for item in errors if item.startswith("missing media"))
        if not has_missing_link or missing_media < 12:
            log("self-check did not report the expected broken link and missing media")
            for item in errors:
                log(f"  {item}")
            return 1
        log(
            f"self-check ok: {len(errors)} errors on the broken fixture "
            "(missing link + missing media)"
        )
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (default: parent of scripts/)",
    )
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="Run against a temporary broken fixture; expect failure detection.",
    )
    args = parser.parse_args()
    if args.self_check:
        return self_check()
    root = args.root.resolve()
    log("Unsupported syntax (not scanned): HTML href/src, autolinks, heading fragment IDs.")
    log("External URLs are skipped (no network). Reference-style links are resolved.")
    errors = run_checks(root)
    log(f"Media: {media_summary(root)}")
    if errors:
        log(f"{len(errors)} problem(s):")
        for item in errors:
            log(f"  {item}")
        return 1
    log("Walkthrough documentation checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
