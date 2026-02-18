import os
import time

from celery import Celery


celery_app = Celery(
    "meds_worker",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1"),
)


@celery_app.task(name="task_procesar_archivo")
def task_procesar_archivo(carga_id: str, filename: str) -> dict[str, str]:
    # Placeholder para ETL pesado en background.
    time.sleep(1)
    return {"carga_id": carga_id, "filename": filename, "status": "COMPLETED"}
