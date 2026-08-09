from collections.abc import Iterator

import pytest
from pdf2word import sidecar
from pdf2word.pipeline import JobControl


@pytest.fixture(autouse=True)
def isolated_jobs() -> Iterator[None]:
    with sidecar.JOBS_LOCK:
        sidecar.JOBS.clear()
    yield
    with sidecar.JOBS_LOCK:
        sidecar.JOBS.clear()


def test_start_rejects_a_second_active_job(monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[dict[str, object]] = []
    monkeypatch.setattr(sidecar, "emit", messages.append)
    with sidecar.JOBS_LOCK:
        sidecar.JOBS["existing"] = {"status": "running", "control": JobControl()}

    sidecar.handle({"command": "start", "request_id": "request-1", "job_id": "new"})

    assert messages[-1]["ok"] is False
    assert "existing" in str(messages[-1]["error"])
    assert set(sidecar.JOBS) == {"existing"}


def test_terminal_job_cannot_be_paused(monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[dict[str, object]] = []
    monkeypatch.setattr(sidecar, "emit", messages.append)
    with sidecar.JOBS_LOCK:
        sidecar.JOBS["finished"] = {"status": "success", "control": JobControl()}

    sidecar.handle({"command": "pause", "request_id": "request-2", "job_id": "finished"})

    assert messages[-1]["ok"] is False
    assert sidecar.JOBS["finished"]["status"] == "success"
