from __future__ import annotations

import json
import shutil
import sys
import threading
import uuid
from pathlib import Path
from typing import Any

from .config import ConversionConfig
from .models import ProgressEvent
from .pipeline import ConversionPipeline, JobControl, preflight_pdf

WRITE_LOCK = threading.Lock()
JOBS_LOCK = threading.Lock()
JOBS: dict[str, dict[str, Any]] = {}


def emit(message: dict[str, object]) -> None:
    with WRITE_LOCK:
        sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def on_progress(event: ProgressEvent) -> None:
    emit(event.model_dump(mode="json"))


def run_job(job_id: str, request: dict[str, Any], control: JobControl) -> None:
    try:
        config = ConversionConfig.model_validate(request.get("config", {}))
        pipeline = ConversionPipeline(config=config, progress=on_progress, control=control, job_id=job_id)
        summary = pipeline.convert(
            Path(request["input_path"]),
            Path(request["output_docx"]),
        )
        with JOBS_LOCK:
            JOBS[job_id]["status"] = summary.status.value
            JOBS[job_id]["summary"] = summary.model_dump(mode="json")
    except Exception as exc:
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "failed"
            JOBS[job_id]["error"] = str(exc)
        emit({"type": "error", "job_id": job_id, "message": str(exc)})


def handle(request: dict[str, Any]) -> None:
    command = request.get("command")
    request_id = str(request.get("request_id") or uuid.uuid4())
    try:
        if command == "preflight":
            result = preflight_pdf(Path(request["input_path"]), request.get("password"))
            emit({"type": "response", "request_id": request_id, "ok": True, "data": result.model_dump(mode="json")})
            return
        if command == "start":
            job_id = str(request.get("job_id") or uuid.uuid4())
            control = JobControl()
            thread = threading.Thread(target=run_job, args=(job_id, request, control), daemon=True)
            with JOBS_LOCK:
                JOBS[job_id] = {"status": "running", "control": control, "thread": thread}
            thread.start()
            emit({"type": "response", "request_id": request_id, "ok": True, "job_id": job_id})
            return
        job_id = str(request.get("job_id", ""))
        with JOBS_LOCK:
            job = JOBS.get(job_id)
        if command in {"pause", "resume", "cancel", "status"}:
            if not job:
                raise KeyError("任务不存在")
            control = job["control"]
            if command == "pause":
                control.pause()
                job["status"] = "paused"
            elif command == "resume":
                control.resume()
                job["status"] = "running"
            elif command == "cancel":
                control.cancel()
                job["status"] = "cancelling"
            data = {key: value for key, value in job.items() if key not in {"control", "thread"}}
            emit({"type": "response", "request_id": request_id, "ok": True, "job_id": job_id, "data": data})
            return
        if command == "cleanup":
            target = Path(request["path"]).expanduser().resolve()
            allowed_name = ".pdf2word-state" in target.parts or target.name.startswith("pdf2word-")
            if not allowed_name:
                raise ValueError("拒绝清理非应用临时目录")
            shutil.rmtree(target, ignore_errors=True)
            emit({"type": "response", "request_id": request_id, "ok": True})
            return
        raise ValueError(f"不支持的命令：{command}")
    except Exception as exc:
        emit({"type": "response", "request_id": request_id, "ok": False, "error": str(exc)})


def main() -> None:
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise TypeError("请求必须是 JSON 对象")
            handle(request)
        except Exception as exc:
            emit({"type": "protocol_error", "message": str(exc)})


if __name__ == "__main__":
    main()
