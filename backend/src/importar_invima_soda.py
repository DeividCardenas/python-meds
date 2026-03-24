from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys
from typing import Any

from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

from app.core.db import create_task_session_factory
from app.services.invima_soda_service import sincronizar_invima_soda


def _build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ETL INVIMA SODA 2.1 (vigentes, vencidos, en tramite, otros)",
    )
    parser.add_argument(
        "--no-load",
        action="store_true",
        help="Solo extract+transform. No hace upsert en BD.",
    )
    parser.add_argument(
        "--export-csv",
        type=Path,
        default=None,
        help="Ruta opcional para exportar el DataFrame consolidado a CSV.",
    )
    return parser.parse_args()


def _serialize_summary(summary: dict[str, Any]) -> dict[str, Any]:
    safe = dict(summary)
    if "dataframe" in safe:
        safe["dataframe"] = {
            "rows": int(safe["dataframe"].shape[0]),
            "cols": int(safe["dataframe"].shape[1]),
        }
    if "rows" in safe:
        safe["rows"] = f"{len(safe['rows'])} registros"
    return safe


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    engine, session_factory = create_task_session_factory()
    try:
        result = await sincronizar_invima_soda(
            session_factory,
            cargar_bd=not args.no_load,
            retornar_dataframe=True,
            retornar_rows=False,
        )
    finally:
        await engine.dispose()

    if args.export_csv is not None and "dataframe" in result:
        args.export_csv.parent.mkdir(parents=True, exist_ok=True)
        result["dataframe"].to_csv(args.export_csv, index=False)

    return result


def main() -> None:
    load_dotenv()
    args = _build_args()
    result = asyncio.run(_run(args))

    if args.export_csv is not None:
        print(f"CSV exportado en: {args.export_csv}")

    print(json.dumps(_serialize_summary(result), indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
