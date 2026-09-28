from __future__ import annotations

import threading
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import web.routes as routes_module


def test_get_pipeline_constructs_only_once_under_concurrency(monkeypatch):
    construction_count = 0
    count_lock = threading.Lock()

    class FakePipeline:
        def __init__(self) -> None:
            nonlocal construction_count
            with count_lock:
                construction_count += 1

    monkeypatch.setattr(routes_module, "RAGPipeline", FakePipeline)
    monkeypatch.setattr(routes_module, "_pipeline", None)

    thread_count = 8
    barrier = threading.Barrier(thread_count)
    results: list[object] = []
    results_lock = threading.Lock()

    def worker() -> None:
        barrier.wait()
        pipeline = routes_module._get_pipeline()
        with results_lock:
            results.append(pipeline)

    threads = [threading.Thread(target=worker) for _ in range(thread_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert construction_count == 1
    assert len({id(r) for r in results}) == 1
