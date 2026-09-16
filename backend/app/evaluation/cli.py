from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import select

from app.core.config import load_settings
from app.core.db import create_db_engine, create_session_factory
from app.evaluation.runner import run_evaluation, write_report
from app.models import User
from app.providers.factory import get_embedder
from app.retrieval.ingest import (
    default_instructions_path,
    load_instructions_payload,
    seed_instructions,
)
from app.seed import default_seed_path, load_seed_payload, seed_identities


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run synthetic evaluation harness (portfolio only)."
    )
    parser.add_argument("--split", default="held_out", choices=["train", "held_out", "all"])
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/results/evaluation-report.json"),
    )
    args = parser.parse_args()
    settings = load_settings()
    engine = create_db_engine(settings.database_url)
    factory = create_session_factory(engine)
    with factory() as session:
        seed_identities(session, load_seed_payload(default_seed_path()))
        seed_instructions(
            session,
            load_instructions_payload(default_instructions_path()),
            embedder=get_embedder(settings),
        )
        session.commit()
        requester = session.scalar(select(User).where(User.email == "aino.esimerkki@demo.invalid"))
        assert requester is not None
        split = None if args.split == "all" else args.split
        report = run_evaluation(session, requester, split=split)
    write_report(report, args.output)
    print(f"Cases passed: {report.cases_passed}/{report.cases_total}")
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
