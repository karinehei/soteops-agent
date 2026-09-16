from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def resolve_repo_file(configured: str | None, *default_parts: str) -> Path:
    """Resolve seed and policy files from the repository root, not the process cwd.

    CI and `cd backend && uv run soteops-seed` set `SOTEOPS_SEED_FILE=seed/identities.json`
    while the working directory is `backend/`. Absolute paths (Compose) are kept as-is.
    """
    default = REPO_ROOT.joinpath(*default_parts)
    if configured is None or not configured.strip():
        return default
    path = Path(configured)
    if path.is_absolute():
        return path
    repo_relative = (REPO_ROOT / path).resolve()
    if repo_relative.is_file():
        return repo_relative
    cwd_relative = Path(path).resolve()
    if cwd_relative.is_file():
        return cwd_relative
    return repo_relative
