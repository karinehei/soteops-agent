"""Local walkthrough recorder. Uses an isolated database. Never drops the developer DB."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

REPO_ROOT = Path(__file__).resolve().parents[1]
WALKTHROUGH_DB = "soteops_walkthrough"
DEFAULT_PORTS = {"api": 8010, "mock": 8011, "web": 3010}
CONFLICT_A = "SYN-OHJE-RISTIRIITA-A-01-v1"
CONFLICT_B = "SYN-OHJE-RISTIRIITA-B-01-v1"
SCENARIOS: dict[str, dict[str, str]] = {
    "01-successful-request": {
        "grep": "01 successful request",
        "gif": "docs/walkthrough/media/01-successful-request.gif",
    },
    "02-missing-end-date": {
        "grep": "02 missing end date",
        "gif": "docs/walkthrough/media/02-missing-end-date.gif",
    },
    "03-prohibited-access": {
        "grep": "03 prohibited access",
        "gif": "docs/walkthrough/media/03-prohibited-access.gif",
    },
    "04-conflicting-instructions": {
        "grep": "04 conflicting instructions",
        "gif": "docs/walkthrough/media/04-conflicting-instructions.gif",
    },
    "05-timeout-reconciliation": {
        "grep": "05 lost-response",
        "gif": "docs/walkthrough/media/05-timeout-reconciliation.gif",
    },
    "06-stale-proposal": {
        "grep": "06 stale proposal",
        "gif": "docs/walkthrough/media/06-stale-proposal.gif",
    },
}
CONFLICT_PAYLOAD = {
    "original_text": (
        "Pyydän kirjaaja-oikeutta demo-hr-testi -järjestelmään EMP-4004 määräaikaisena "
        "ilman loppupäivää. Ristiriitaiset ohjeet voivat tulla näkyviin. "
        "Yksikkö demo-osasto, alkaen 2026-12-01."
    ),
    "employee_identifier": "EMP-4004",
    "employment_type": "maaraaikainen",
    "job_role": "sairaanhoitaja",
    "unit": "demo-osasto",
    "target_system": "demo-hr-testi",
    "requested_access_role": "kirjaaja",
    "start_date": "2026-12-01",
    "end_date": None,
}


def log(message: str) -> None:
    print(message, flush=True)


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def to_psycopg_url(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        return "postgresql://" + url.removeprefix("postgresql+psycopg://")
    return url


def with_database(url: str, database: str) -> str:
    parsed = urlparse(to_psycopg_url(url))
    return urlunparse(parsed._replace(path=f"/{database}"))


def database_name(url: str) -> str:
    return urlparse(to_psycopg_url(url)).path.lstrip("/")


def sqlalchemy_url(url: str) -> str:
    psycopg_url = to_psycopg_url(url)
    if psycopg_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + psycopg_url.removeprefix("postgresql://")
    return url


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def allocate_ports() -> dict[str, int]:
    ports = DEFAULT_PORTS.copy()
    for name, port in list(ports.items()):
        if port_open(port):
            ports[name] = free_port()
            log(f"Default walkthrough {name} port {port} is busy; using {ports[name]}.")
    return ports


def wait_http(
    url: str,
    timeout: float,
    *,
    process: subprocess.Popen[bytes] | None = None,
    log_path: Path | None = None,
) -> None:
    deadline = time.time() + timeout
    last_error = "no response"
    while time.time() < deadline:
        if process is not None and process.poll() is not None:
            raise RuntimeError(
                f"{url} process exited {process.returncode}."
                + _log_tail(log_path)
            )
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if 200 <= response.status < 500:
                    return
                last_error = f"status {response.status}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
        time.sleep(0.4)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}" + _log_tail(log_path))


def _log_tail(log_path: Path | None, limit: int = 2000) -> str:
    if log_path is None or not log_path.is_file():
        return ""
    text = log_path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return ""
    return f"\n--- {log_path.name} ---\n{text[-limit:]}"


def git_meta() -> tuple[str, bool]:
    def _run(args: list[str]) -> str:
        result = subprocess.run(
            args,
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"

    return _run(["git", "rev-parse", "HEAD"]), bool(_run(["git", "status", "--porcelain"]))


def which(name: str) -> str:
    from shutil import which as find

    candidates = [name]
    if os.name == "nt":
        candidates = [f"{name}.cmd", f"{name}.exe", name]
    for item in candidates:
        found = find(item)
        if found:
            return found
    raise RuntimeError(f"Required executable not found: {name}")


def bundled_chromium_ok(frontend: Path) -> bool:
    script = (
        "const {chromium}=require('playwright');"
        "const fs=require('fs');"
        "process.exit(fs.existsSync(chromium.executablePath())?0:1);"
    )
    result = subprocess.run(
        [which("node"), "-e", script],
        cwd=str(frontend),
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def system_browser_channel() -> str:
    program_files = Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
    program_files_x86 = Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
    local = Path.home() / "AppData" / "Local"
    chrome = [
        program_files / "Google" / "Chrome" / "Application" / "chrome.exe",
        program_files_x86 / "Google" / "Chrome" / "Application" / "chrome.exe",
        local / "Google" / "Chrome" / "Application" / "chrome.exe",
    ]
    if any(path.is_file() for path in chrome):
        return "chrome"
    edge = [
        program_files / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        program_files_x86 / "Microsoft" / "Edge" / "Application" / "msedge.exe",
    ]
    if any(path.is_file() for path in edge):
        return "msedge"
    return ""


def resolve_playwright_channel(npx: str, frontend: Path, artifact_root: Path) -> str:
    if bundled_chromium_ok(frontend):
        log("Using installed Playwright Chromium.")
        return ""
    channel = system_browser_channel()
    if channel:
        log(
            "Playwright Chromium is missing; recording with installed "
            f"{channel} instead of downloading from cdn.playwright.dev."
        )
        return channel
    log("Playwright Chromium is missing; installing without removing other browsers.")
    env = os.environ.copy()
    env["PLAYWRIGHT_SKIP_BROWSER_GC"] = "1"
    env["PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT"] = "120000"
    install_log = artifact_root / "logs" / "playwright-install.log"
    install_log.parent.mkdir(parents=True, exist_ok=True)
    with install_log.open("w", encoding="utf-8") as handle:
        subprocess.run(
            [npx, "playwright", "install", "chromium"],
            cwd=frontend,
            env=env,
            check=False,
            stdout=handle,
            stderr=subprocess.STDOUT,
        )
    if bundled_chromium_ok(frontend):
        log("Installed Playwright Chromium.")
        return ""
    raise RuntimeError(
        "Playwright Chromium is not installed and no system Chrome/Edge was found. "
        "See artifacts/walkthrough/logs/playwright-install.log. Capture is not complete."
    )


def uv_cmd() -> list[str]:
    from shutil import which as find

    for name in ("uv", "uv.exe"):
        found = find(name)
        if found:
            return [found]
    scripts = Path(sys.executable).resolve().parent / "Scripts" / "uv.exe"
    roaming = Path.home() / "AppData" / "Roaming" / "Python" / "Python312" / "Scripts" / "uv.exe"
    for candidate in (scripts, roaming):
        if candidate.is_file():
            return [str(candidate)]
    return [sys.executable, "-m", "uv"]


def uv_python(*module_and_args: str) -> list[str]:
    """Run a Python module through uv. Avoids Windows Application Control
    blocking generated console-script wrappers such as soteops-seed.exe.
    """
    return [*uv_cmd(), "run", "python", "-m", *module_and_args]


def spawn(
    args: list[str], env: dict[str, str], log_path: Path, cwd: Path | None = None
) -> subprocess.Popen[bytes]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handle = log_path.open("wb")
    kwargs: dict[str, Any] = {
        "args": args,
        "cwd": str(cwd or REPO_ROOT),
        "env": env,
        "stdout": handle,
        "stderr": subprocess.STDOUT,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    process = subprocess.Popen(**kwargs)
    process._walkthrough_log = handle  # type: ignore[attr-defined]
    return process


def stop(process: subprocess.Popen[bytes] | None) -> None:
    if process is None:
        return
    handle = getattr(process, "_walkthrough_log", None)
    if process.poll() is None:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                capture_output=True,
            )
        else:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
    if handle is not None:
        handle.close()


def ensure_walkthrough_database(developer_url: str, file_env: dict[str, str]) -> str:
    from psycopg import connect, sql

    developer_db = database_name(developer_url)
    if developer_db == WALKTHROUGH_DB:
        raise RuntimeError(
            "Refusing to reset the developer database: DATABASE_URL already uses "
            f"{WALKTHROUGH_DB}."
        )
    admin_url = with_database(developer_url, "postgres")
    last_error = ""
    try:
        with connect(admin_url, autocommit=True, connect_timeout=8) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = %s AND pid <> pg_backend_pid()",
                    (WALKTHROUGH_DB,),
                )
                cur.execute(
                    sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(WALKTHROUGH_DB))
                )
                cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(WALKTHROUGH_DB)))
        return sqlalchemy_url(with_database(developer_url, WALKTHROUGH_DB))
    except Exception as exc:
        last_error = type(exc).__name__

    user = file_env.get("POSTGRES_USER") or "soteops"
    created = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            user,
            "-d",
            "postgres",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            (
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = '{WALKTHROUGH_DB}' AND pid <> pg_backend_pid(); "
                f'DROP DATABASE IF EXISTS "{WALKTHROUGH_DB}"; '
                f'CREATE DATABASE "{WALKTHROUGH_DB}";'
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if created.returncode == 0:
        log(f"Created {WALKTHROUGH_DB} via docker compose exec postgres.")
        return sqlalchemy_url(with_database(developer_url, WALKTHROUGH_DB))
    raise RuntimeError(
        "PostgreSQL is not reachable for the isolated walkthrough database. "
        "Start local Postgres (for example `docker compose up -d postgres`) "
        "without dropping the developer volume. "
        f"(psycopg {last_error}; docker exit {created.returncode})"
    )


def requester_password() -> str:
    payload = json.loads((REPO_ROOT / "seed" / "identities.json").read_text(encoding="utf-8"))
    for user in payload["users"]:
        if user["email"] == "aino.esimerkki@demo.invalid":
            return str(user["password"])
    raise RuntimeError("Requester identity missing from seed/identities.json")


def probe_conflict_sources(api_base: str) -> tuple[bool, list[str]]:
    import httpx

    password = requester_password()
    with httpx.Client(base_url=api_base, timeout=60.0) as client:
        csrf = client.get("/auth/csrf").json()["csrf_token"]
        login = client.post(
            "/auth/login",
            json={"email": "aino.esimerkki@demo.invalid", "password": password},
            headers={"X-CSRF-Token": csrf},
        )
        login.raise_for_status()
        csrf = client.get("/auth/csrf").json()["csrf_token"]
        created = client.post(
            "/requests",
            json=CONFLICT_PAYLOAD,
            headers={"X-CSRF-Token": csrf},
        )
        created.raise_for_status()
        refs = created.json()["current_proposal"]["source_references"]
        ids = [str(item.get("document_id") or "") for item in refs]
        return CONFLICT_A in ids and CONFLICT_B in ids, [item for item in ids if item]


def build_api_env(
    *,
    file_env: dict[str, str],
    walkthrough_db_url: str,
    ports: dict[str, int],
    retrieval_top_k: int,
) -> dict[str, str]:
    env = os.environ.copy()
    env.update(file_env)
    env.update(
        {
            "UV_PROJECT_ENVIRONMENT": os.environ.get(
                "UV_PROJECT_ENVIRONMENT", str(REPO_ROOT / "artifacts" / "walkthrough" / ".venv")
            ),
            "ENVIRONMENT": "local",
            "LLM_PROVIDER": "fake",
            "EMBEDDING_PROVIDER": "fake",
            "AZURE_OPENAI_ENABLED": "false",
            "DEMO_AUTH_ENABLED": "true",
            "COOKIE_SECURE": "false",
            "DATABASE_URL": walkthrough_db_url,
            "MOCK_INTEGRATION_URL": f"http://127.0.0.1:{ports['mock']}",
            "CORS_ORIGINS": f"http://127.0.0.1:{ports['web']}",
            "RETRIEVAL_TOP_K": str(retrieval_top_k),
            "POLICY_FILE": str(REPO_ROOT / "seed" / "policy" / "v1.json"),
            "SOTEOPS_SEED_FILE": str(REPO_ROOT / "seed" / "identities.json"),
            "SOTEOPS_INSTRUCTIONS_FILE": str(REPO_ROOT / "seed" / "instructions.json"),
            "SESSION_SECRET": file_env.get("SESSION_SECRET")
            or os.environ.get("SESSION_SECRET")
            or "walkthrough-local-session-secret",
        }
    )
    return env


def write_manifest(
    artifact_root: Path,
    *,
    retrieval_top_k: int,
    retrieval_reason: str,
    selected: list[str],
    playwright_code: int,
    ports: dict[str, int],
    browser_channel: str = "",
) -> Path:
    commit, dirty = git_meta()
    results_dir = artifact_root / "results"
    scenarios: list[dict[str, Any]] = []
    for scenario_id in selected:
        path = results_dir / f"{scenario_id}.json"
        if path.is_file():
            scenarios.append(json.loads(path.read_text(encoding="utf-8")))
        else:
            scenarios.append(
                {
                    "id": scenario_id,
                    "fixture": "",
                    "assertions": [],
                    "assertions_passed": False,
                    "outcome": "failed" if playwright_code != 0 else "skipped",
                    "video_segments": [],
                    "planned_gif": SCENARIOS[scenario_id]["gif"],
                    "limitation": "No scenario result file was written.",
                    "notes": "",
                }
            )
    manifest = {
        "source_commit": commit,
        "working_tree_dirty": dirty,
        "capture_date": date.today().isoformat(),
        "providers": {
            "llm": "fake",
            "embedding": "fake",
            "azure_openai_enabled": False,
        },
        "retrieval_top_k": retrieval_top_k,
        "retrieval_top_k_reason": retrieval_reason,
        "database": WALKTHROUGH_DB,
        "ports": ports,
        "browser": browser_channel or "playwright-chromium",
        "gifs_generated": False,
        "planned_gif_paths": {key: value["gif"] for key, value in SCENARIOS.items()},
        "scenarios": scenarios,
    }
    path = artifact_root / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Record walkthrough videos against an isolated local stack."
    )
    parser.add_argument(
        "--scenario",
        default="all",
        help="Scenario id (01-successful-request … 06-stale-proposal) or all",
    )
    args = parser.parse_args()
    selected = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    unknown = [item for item in selected if item not in SCENARIOS]
    if unknown:
        log(f"Unknown scenario: {unknown[0]}")
        return 2

    artifact_root = REPO_ROOT / "artifacts" / "walkthrough"
    artifact_root.mkdir(parents=True, exist_ok=True)
    walkthrough_venv = artifact_root / ".venv"
    os.environ["UV_PROJECT_ENVIRONMENT"] = str(walkthrough_venv)
    file_env = load_dotenv(REPO_ROOT / ".env")
    developer_url = file_env.get("DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not developer_url:
        log("DATABASE_URL is missing. Copy .env.example to .env for local Postgres settings.")
        return 2

    ports = allocate_ports()
    os.environ["WALKTHROUGH_PORTS_JSON"] = json.dumps(ports)
    log(f"Walkthrough ports: {ports}")
    try:
        walkthrough_url = ensure_walkthrough_database(developer_url, file_env)
    except RuntimeError as exc:
        log(str(exc))
        return 2

    npx = which("npx")
    migrate_env = build_api_env(
        file_env=file_env,
        walkthrough_db_url=walkthrough_url,
        ports=ports,
        retrieval_top_k=4,
    )
    log(f"Migrating isolated database {WALKTHROUGH_DB} (developer DB not touched).")
    subprocess.run(
        uv_python("alembic", "upgrade", "head"),
        cwd=REPO_ROOT / "backend",
        env=migrate_env,
        check=True,
    )
    subprocess.run(
        uv_python("app.seed"),
        cwd=REPO_ROOT / "backend",
        env=migrate_env,
        check=True,
    )

    processes: list[subprocess.Popen[bytes]] = []
    api_process: subprocess.Popen[bytes] | None = None
    retrieval_top_k = 4
    retrieval_reason = "default RETRIEVAL_TOP_K=4"
    try:
        mock_env = os.environ.copy()
        mock_env.update({"ENVIRONMENT": "local", "LOG_LEVEL": "INFO"})
        mock_process = spawn(
            [
                *uv_python(
                    "uvicorn",
                    "mock_integration.main:create_app",
                    "--factory",
                    "--app-dir",
                    "mock-integration",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(ports["mock"]),
                ),
            ],
            mock_env,
            artifact_root / "logs" / "mock.log",
        )
        processes.append(mock_process)
        wait_http(f"http://127.0.0.1:{ports['mock']}/health", 30)

        def start_api(top_k: int) -> subprocess.Popen[bytes]:
            env = build_api_env(
                file_env=file_env,
                walkthrough_db_url=walkthrough_url,
                ports=ports,
                retrieval_top_k=top_k,
            )
            return spawn(
                [
                    *uv_python(
                        "uvicorn",
                        "app.main:create_app",
                        "--factory",
                        "--app-dir",
                        "backend",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(ports["api"]),
                    ),
                ],
                env,
                artifact_root / "logs" / "api.log",
            )

        api_process = start_api(4)
        processes.append(api_process)
        wait_http(f"http://127.0.0.1:{ports['api']}/health", 40)

        conflict_recordable = "1"
        conflict_blocker = ""
        needs_conflict = "04-conflicting-instructions" in selected
        if needs_conflict:
            log("Probing conflicting instruction retrieval at RETRIEVAL_TOP_K=4.")
            found, ids = probe_conflict_sources(f"http://127.0.0.1:{ports['api']}")
            if not found:
                log(f"Default top_k=4 returned {ids}; restarting API with RETRIEVAL_TOP_K=8.")
                stop(api_process)
                processes.remove(api_process)
                retrieval_top_k = 8
                retrieval_reason = (
                    "recording-specific RETRIEVAL_TOP_K=8; both conflict documents were absent at 4"
                )
                api_process = start_api(8)
                processes.append(api_process)
                wait_http(f"http://127.0.0.1:{ports['api']}/health", 40)
                found, ids = probe_conflict_sources(f"http://127.0.0.1:{ports['api']}")
            if found:
                log(f"Conflict sources present: {ids}")
                if retrieval_top_k == 4:
                    retrieval_reason = "default RETRIEVAL_TOP_K=4; both conflict documents present"
            else:
                conflict_recordable = "0"
                conflict_blocker = (
                    "Both SYN-OHJE-RISTIRIITA-A-01-v1 and SYN-OHJE-RISTIRIITA-B-01-v1 were not "
                    f"retrieved at RETRIEVAL_TOP_K=8 (got {ids})."
                )
                log(f"BLOCKED: {conflict_blocker}")
                if selected == ["04-conflicting-instructions"]:
                    (artifact_root / "results").mkdir(parents=True, exist_ok=True)
                    (artifact_root / "results" / "04-conflicting-instructions.json").write_text(
                        json.dumps(
                            {
                                "id": "04-conflicting-instructions",
                                "fixture": "conflicting-instructions",
                        "assertions": [
                            "Both conflict instruction documents must appear"
                        ],
                                "assertions_passed": False,
                                "outcome": "blocked",
                                "video_segments": [],
                                "planned_gif": SCENARIOS["04-conflicting-instructions"]["gif"],
                                "limitation": conflict_blocker,
                        "notes": (
                            "needs_clarification on this fixture is caused by the "
                            "missing end date, not by automatic conflict routing."
                        ),
                            },
                            indent=2,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                    manifest = write_manifest(
                        artifact_root,
                        retrieval_top_k=retrieval_top_k,
                        retrieval_reason=retrieval_reason,
                        selected=selected,
                        playwright_code=0,
                        ports=ports,
                    )
                    log(f"Wrote {manifest}")
                    return 1

        web_env = os.environ.copy()
        web_env["NEXT_PUBLIC_API_BASE_URL"] = f"http://127.0.0.1:{ports['api']}"
        web_env["NEXT_DIST_DIR"] = ".next-walkthrough"
        next_bin = REPO_ROOT / "frontend" / "node_modules" / "next" / "dist" / "bin" / "next"
        if not next_bin.is_file():
            raise RuntimeError(
                "frontend/node_modules/next is missing; run npm install in frontend."
            )
        web_log = artifact_root / "logs" / "web.log"
        web_process = spawn(
            [
                which("node"),
                str(next_bin),
                "dev",
                "--hostname",
                "127.0.0.1",
                "--port",
                str(ports["web"]),
            ],
            web_env,
            web_log,
            cwd=REPO_ROOT / "frontend",
        )
        processes.append(web_process)
        wait_http(
            f"http://127.0.0.1:{ports['web']}",
            90,
            process=web_process,
            log_path=web_log,
        )

        try:
            browser_channel = resolve_playwright_channel(
                npx, REPO_ROOT / "frontend", artifact_root
            )
        except RuntimeError as exc:
            log(str(exc))
            write_manifest(
                artifact_root,
                retrieval_top_k=retrieval_top_k,
                retrieval_reason=retrieval_reason,
                selected=selected,
                playwright_code=2,
                ports=ports,
            )
            return 2

        play_env = os.environ.copy()
        play_env.update(
            {
                "PLAYWRIGHT_BASE_URL": f"http://127.0.0.1:{ports['web']}",
                "WALKTHROUGH_API_BASE_URL": f"http://127.0.0.1:{ports['api']}",
                "WALKTHROUGH_MOCK_BASE_URL": f"http://127.0.0.1:{ports['mock']}",
                "WALKTHROUGH_ARTIFACT_DIR": str(artifact_root),
                "WALKTHROUGH_PLAYWRIGHT_JSON": str(artifact_root / "playwright-results.json"),
                "WALKTHROUGH_RETRIEVAL_TOP_K": str(retrieval_top_k),
                "WALKTHROUGH_CONFLICT_RECORDABLE": conflict_recordable,
                "WALKTHROUGH_CONFLICT_BLOCKER": conflict_blocker,
                "WALKTHROUGH_BROWSER_CHANNEL": browser_channel,
                "PLAYWRIGHT_SKIP_BROWSER_GC": "1",
                "LLM_PROVIDER": "fake",
                "EMBEDDING_PROVIDER": "fake",
            }
        )
        cmd = [npx, "playwright", "test", "-c", "playwright.record.config.ts"]
        if args.scenario != "all":
            setup = subprocess.run(
                [npx, "playwright", "test", "-c", "playwright.record.config.ts", "--project=setup"],
                cwd=REPO_ROOT / "frontend",
                env=play_env,
                check=False,
            )
            if setup.returncode != 0:
                log(
                    "Walkthrough auth setup failed. "
                    "See artifacts/walkthrough/logs and Playwright output."
                )
                write_manifest(
                    artifact_root,
                    retrieval_top_k=retrieval_top_k,
                    retrieval_reason=retrieval_reason,
                    selected=selected,
                    playwright_code=setup.returncode,
                    ports=ports,
                    browser_channel=browser_channel,
                )
                return setup.returncode
            cmd.extend(["--project=record", f"e2e-record/{args.scenario}.spec.ts"])
        log("Recording with Playwright (video on per labeled context).")
        play = subprocess.run(cmd, cwd=REPO_ROOT / "frontend", env=play_env, check=False)
        manifest = write_manifest(
            artifact_root,
            retrieval_top_k=retrieval_top_k,
            retrieval_reason=retrieval_reason,
            selected=selected,
            playwright_code=play.returncode,
            ports=ports,
            browser_channel=browser_channel,
        )
        log(f"Wrote {manifest}")
        log("GIFs were not generated. Raw videos are under artifacts/walkthrough/.")
        return play.returncode
    finally:
        for process in reversed(processes):
            stop(process)


if __name__ == "__main__":
    sys.exit(main())
