"""Tests for task performance metric units and aggregation."""

import shutil
import tempfile
import types
import unittest

from backend.common.jsonutil import now_ms
from backend.common.storage import Storage
from backend.master.metrics import Metrics
from backend.worker.executor import Executor


class TestTaskMetrics(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.storage = Storage(self.tmp)
        self.metrics = Metrics(self.storage)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_duration_ms_drives_throughput_and_latency(self):
        job = types.SimpleNamespace(job_id="job-test")
        task = types.SimpleNamespace(
            worker_id="worker-test",
            records_processed=5_000,
            records_emitted=2_500,
        )

        self.metrics.record_task(job, task, duration_ms=2_500)
        summary = self.metrics.job_metrics("job-test")

        self.assertEqual(summary["total_records_processed"], 5_000)
        self.assertEqual(summary["total_records_emitted"], 2_500)
        self.assertEqual(summary["avg_throughput_rps"], 2_000.0)
        self.assertEqual(summary["peak_throughput_rps"], 2_000.0)
        self.assertEqual(summary["avg_latency_ms"], 2_500.0)

        sample = summary["samples"][0]
        self.assertEqual(sample["records_per_sec"], 2_000.0)
        self.assertEqual(sample["task_latency_ms"], 2_500.0)

    def test_peak_throughput_uses_maximum(self):
        job = types.SimpleNamespace(job_id="job-peak")
        slow = types.SimpleNamespace(worker_id="w1", records_processed=1_000, records_emitted=1)
        fast = types.SimpleNamespace(worker_id="w2", records_processed=4_000, records_emitted=1)

        self.metrics.record_task(job, slow, duration_ms=2_000)
        self.metrics.record_task(job, fast, duration_ms=1_000)

        summary = self.metrics.job_metrics("job-peak")
        self.assertEqual(summary["peak_throughput_rps"], 4_000.0)
        self.assertEqual(summary["avg_throughput_rps"], 2_250.0)


class TestExecutorReporting(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_completion_reports_elapsed_time_in_milliseconds(self):
        executor = Executor(
            worker_id="worker-test",
            data_root=self.tmp,
            master_url="http://127.0.0.1:0",
            config=types.SimpleNamespace(),
            exec_mode="thread",
        )
        captured = {}
        executor._post = lambda path, payload: captured.update(payload)
        executor._handles["task-test"] = {
            "spec": {"job_id": "job-test"},
            "started_ms": now_ms() - 1_234,
            "cancel": None,
            "last_status_ms": 0,
        }

        executor._complete("task-test", {
            "records_processed": 10,
            "records_emitted": 5,
        })

        self.assertGreaterEqual(captured["duration_ms"], 1_234)
        self.assertLess(captured["duration_ms"], 2_000)


if __name__ == "__main__":
    unittest.main()
