# Copyright (c) 2026 Ninon
# SPDX-License-Identifier: MIT
"""Byte-level regression checks with synthetic inputs, golden bytes, and fresh processes."""

import os
from pathlib import Path
import subprocess
import sys
import unittest

from local_examiner import Capsule, canon_json, demo, hexify_floats
from local_examiner.local_examiner import retrieve
from local_examiner.textnorm import f64_hex, f64_unhex
from tests.snapshot import snapshot_bytes

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests/fixtures/synthetic-output.json"


class DeterminismTests(unittest.TestCase):
    def test_canonical_json_matches_literal_utf8_vector(self):
        self.assertEqual(
            canon_json({"z": [True, None, 2], "a": "cafe"}), b'{"a":"cafe","z":[true,null,2]}'
        )
        self.assertEqual(canon_json({"e": "\u00e9"}), b'{"e":"\xc3\xa9"}')
        with self.assertRaises(ValueError):
            canon_json({"nested": [1.0]})

    def test_binary64_vectors_and_capsule_float_round_trip(self):
        self.assertEqual(f64_hex(2.5), "4004000000000000")
        self.assertEqual(f64_hex(-0.0), "8000000000000000")
        self.assertEqual(f64_hex(f64_unhex("8000000000000000")), "8000000000000000")
        self.assertEqual(hexify_floats((True, 2.5)), [True, {"~f64": "4004000000000000"}])
        cap = demo.make_demo_capsule()
        cap.task_records[0].input_provenance["synthetic_float"] = -0.0
        cap.seal()
        back = Capsule.import_json(cap.export_json())
        self.assertTrue(back.verify_digest())
        self.assertEqual(
            f64_hex(back.task_records[0].input_provenance["synthetic_float"]), "8000000000000000"
        )
        self.assertEqual(back.canonical_bytes(), cap.canonical_bytes())

    def test_complete_outputs_match_frozen_synthetic_bytes(self):
        self.assertEqual(snapshot_bytes(), GOLDEN.read_bytes())

    def test_eight_fresh_processes_match_frozen_synthetic_bytes(self):
        code = "import sys; from tests.snapshot import snapshot_bytes; sys.stdout.buffer.write(snapshot_bytes())"
        expected = GOLDEN.read_bytes()
        for seed in ("0", "1", "42", "random"):
            for locale in ("C", "en_US.UTF-8"):
                with self.subTest(hash_seed=seed, locale=locale):
                    env = dict(
                        os.environ,
                        PYTHONHASHSEED=seed,
                        LC_ALL=locale,
                        PYTHONDONTWRITEBYTECODE="1",
                        PYTHONIOENCODING="utf-8",
                    )
                    result = subprocess.run(
                        [sys.executable, "-B", "-c", code],
                        cwd=ROOT,
                        env=env,
                        capture_output=True,
                        check=True,
                        timeout=30,
                    )
                    self.assertEqual(result.stdout, expected)

    def test_fixed_capsule_metadata_is_repeatable(self):
        left, right = demo.make_demo_capsule(), demo.make_demo_capsule()
        self.assertEqual(left.export_json(), right.export_json())
        self.assertEqual(left.content_digest, right.content_digest)
        right.task_records[0].response_snapshot += " A synthetic extra sentence."
        self.assertFalse(right.verify_digest())
        self.assertNotEqual(right.canonical_bytes(), left.canonical_bytes())

    def test_retrieval_ties_use_timestamp_then_id(self):
        caps = [demo.make_demo_capsule() for _ in range(3)]
        for cap, cid, date in zip(
            caps,
            ("z", "b", "a"),
            ("2025-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
        ):
            cap.capsule_id, cap.issued_at = cid, date
            cap.seal()
        options = dict(capability_id=demo.CAPABILITY, genre="proposal", reader_terms=["manager"])
        for order in (caps, list(reversed(caps)), [caps[1], caps[0], caps[2]]):
            self.assertEqual([c.capsule_id for c in retrieve(order, **options)], ["a", "b", "z"])

    def test_signing_metadata_does_not_change_content_digest(self):
        cap = demo.make_demo_capsule()
        expected = cap.canonical_bytes()
        cap.signer_key_id = "synthetic-key"
        cap.signature_algorithm = "fake-test-only"
        cap.issuer_signature = "synthetic-signature"
        self.assertEqual(cap.canonical_bytes(), expected)
        self.assertTrue(cap.verify_digest())
        self.assertIsNone(cap.verify_signature(None))
