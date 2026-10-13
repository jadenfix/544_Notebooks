from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from econ544.ads_did import DEFAULT_DATASET, analyze_paid_search, load_paid_search


ROOT = Path(__file__).resolve().parents[1]


class PaidSearchDidTests(unittest.TestCase):
    def test_bundled_data_matches_regression_receipt(self) -> None:
        frame, source = load_paid_search()
        result, panel = analyze_paid_search(frame)
        self.assertEqual(source, DEFAULT_DATASET)
        self.assertEqual(result.rows, 23730)
        self.assertEqual(result.dmas, 210)
        self.assertEqual(result.treated_dmas, 68)
        self.assertEqual(result.control_dmas, 142)
        self.assertEqual(len(panel), 210)
        self.assertAlmostEqual(result.log_effect, -0.006586851844, places=12)
        self.assertAlmostEqual(result.revenue_ratio, 0.993434793912, places=12)

    def test_default_data_resolves_outside_repository(self) -> None:
        old_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                import os

                os.chdir(directory)
                frame, source = load_paid_search()
                self.assertEqual(len(frame), 23730)
                self.assertTrue(source.is_file())
            finally:
                os.chdir(old_cwd)

    def test_rejects_incomplete_panel(self) -> None:
        frame = pd.DataFrame(
            {
                "date": ["a", "b", "a", "b", "a", "b", "a"],
                "dma": [1, 1, 2, 2, 3, 3, 4],
                "treatment_period": [0, 1, 0, 1, 0, 1, 0],
                "search_stays_on": [0, 0, 0, 0, 1, 1, 1],
                "revenue": [10, 11, 12, 13, 14, 15, 16],
            }
        )
        with self.assertRaisesRegex(ValueError, "missing a pre or post period"):
            analyze_paid_search(frame)

    def test_rejects_nonpositive_revenue(self) -> None:
        frame = pd.read_csv(DEFAULT_DATASET).copy()
        frame.loc[frame.index[0], "revenue"] = 0
        with self.assertRaisesRegex(ValueError, "strictly positive"):
            analyze_paid_search(frame)

    def test_cli_writes_receipt_without_mutating_source(self) -> None:
        original = DEFAULT_DATASET.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / "receipt.json"
            unrelated_staging = receipt.with_name(".receipt.json.tmp")
            unrelated_staging.write_text("preserve me", encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts/run_ads_did.py"), "--output", str(receipt)],
                cwd="/",
                text=True,
                capture_output=True,
                check=True,
                env={"PYTHONPATH": str(ROOT)},
            )
            payload = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertEqual(payload, json.loads(completed.stdout))
            self.assertEqual(payload["result"]["dmas"], 210)
            self.assertEqual(unrelated_staging.read_text(encoding="utf-8"), "preserve me")
        self.assertEqual(DEFAULT_DATASET.read_bytes(), original)

    def test_cli_rejects_hardlink_output_alias(self) -> None:
        original = DEFAULT_DATASET.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            alias = Path(directory) / "receipt.json"
            alias.hardlink_to(DEFAULT_DATASET)
            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts/run_ads_did.py"), "--output", str(alias)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                env={"PYTHONPATH": str(ROOT)},
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("must not overwrite", completed.stderr)
        self.assertEqual(DEFAULT_DATASET.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
