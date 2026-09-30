"""Tests for task metric units and aggregation."""

import shutil
import tempfile
import unittest

from backend.common.models import Job, Task
from backend.common.storage import Storage
from backend.master.metrics import Metrics


class TestMetrics(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.storage = Storage(self.tmp)
        self.metrics = Metrics(self.storage)
        self.job = Job(job_id="job-test", name="test", mapper="m", reducer="r",
                       num_map_tasks=1, num_reduce_tasks=1)
        self.task = Task(
            task_id="m-0000", job_id=self.job.job_id, kind="map",
            worker_id="worker-1", records_processed=3000, records_emitted=2000,
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_task_metrics_use_milliseconds(self):
        self.metrics.record_task(self.job, self.task, 2500)

        result = self.metrics.job_metrics(self.job.job_id)
        self.assertEqual(result["avg_throughput_rps"], 1200.0)
        self.assertEqual(result["peak_throughput_rps"], 1200.0)
        self.assertEqual(result["avg_latency_ms"], 2500.0)
        self.assertEqual(result["total_records_processed"], 3000)
        self.assertEqual(result["total_records_emitted"], 2000)

        sample = result["samples"][0]
        self.assertEqual(sample["records_per_sec"], 1200.0)
        self.assertEqual(sample["task_latency_ms"], 2500.0)

    def test_peak_is_maximum_throughput(self):
        self.metrics.record_task(self.job, self.task, 2500)
        self.task.records_processed = 6000
        self.metrics.record_task(self.job, self.task, 3000)

        result = self.metrics.job_metrics(self.job.job_id)
        self.assertEqual(result["peak_throughput_rps"], 2000.0)
        self.assertEqual(result["avg_throughput_rps"], 1600.0)

    def test_legacy_second_based_samples_are_normalized(self):
        self.storage.append({
            "ts_ms": 1,
            "job_id": self.job.job_id,
            "records_per_sec": 1200000.0,
            "task_latency_ms": 2.5,
            "throughput": 800000.0,
        }, "metrics", "jobs", f"{self.job.job_id}.jsonl")

        result = self.metrics.job_metrics(self.job.job_id)
        self.assertEqual(result["avg_throughput_rps"], 1200.0)
        self.assertEqual(result["peak_throughput_rps"], 1200.0)
        self.assertEqual(result["avg_latency_ms"], 2500.0)
        sample = result["samples"][0]
        self.assertEqual(sample["throughput"], 800.0)


if __name__ == "__main__":
    unittest.main()
