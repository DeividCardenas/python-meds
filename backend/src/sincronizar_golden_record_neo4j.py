from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

from app.core.db import create_task_session_factory  # type: ignore[import-not-found]
from app.services.neo4j_golden_record_service import (  # type: ignore[import-not-found]
    Neo4jGoldenRecordService,
)


def _build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sincroniza Golden Record desde SQL a Neo4j")
    parser.add_argument("--chunk-size", type=int, default=None, help="Tamano de chunk para lectura SQL")
    return parser.parse_args()


async def _run(chunk_size: int | None) -> dict[str, int]:
    engine, session_factory = create_task_session_factory()
    try:
        kwargs = {}
        if chunk_size is not None:
            kwargs["chunk_size"] = chunk_size

        with Neo4jGoldenRecordService(**kwargs) as service:
            return await service.build_golden_record(session_factory)
    finally:
        await engine.dispose()


def main() -> None:
    load_dotenv()
    args = _build_args()
    result = asyncio.run(_run(args.chunk_size))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
