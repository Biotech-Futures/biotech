import http.client
import json
import math
import random
import threading
import unittest
from unittest.mock import MagicMock, patch

from dataset import DatasetConfig
from gui_server import LocalDbGuiHandler, LocalDbGuiServer, config_from_payload
from scale_preset import SCALED_FIELDS, scale_preview


def payload(**overrides):
    return {"students": 120, "variation_percent": 0, "seed": "3888", "as_of": "2026-11-06T04:30:00Z", **overrides}


class ScalePresetTests(unittest.TestCase):
    def test_baseline_exactly_replays_default_config(self):
        actual = scale_preview(payload())["config"]
        expected = DatasetConfig(as_of=payload()["as_of"]).to_manifest()
        expected["seed"] = "3888"
        self.assertEqual(actual, expected)

    def test_1000_students_produces_expected_proportions(self):
        result = scale_preview(payload(students=1000))
        config = result["config"]
        expected = {"admins": 2, "students": 1000, "supervisors": 100, "mentors": 200,
                    "groups": 200, "messages": 6000, "login_events": 5000, "tasks": 1500,
                    "resources": 250, "resource_accesses": 10000, "announcements": 100,
                    "deliveries": 200, "email_batches": 400, "events": 100, "rsvps": 1000}
        for name, value in expected.items():
            self.assertEqual(config[name], value, name)
        self.assertEqual(config["email_mode"], "coverage")
        self.assertEqual(config["scenario"], "analytics_coverage")
        config_from_payload({"config": config, "confirm_replace": True})

    def test_variation_bounds_exact_students_and_independent_counts(self):
        baseline = DatasetConfig()
        samples = set()
        for seed in range(100):
            result = scale_preview(payload(students=1000, variation_percent=10, seed=str(seed)))["config"]
            self.assertEqual(result["students"], 1000)
            self.assertEqual(result["admins"], 2)
            for name in SCALED_FIELDS:
                target = getattr(baseline, name) * 1000 / 120
                self.assertGreaterEqual(result[name], math.floor(target * .9 + .5), name)
                self.assertLessEqual(result[name], math.floor(target * 1.1 + .5), name)
            samples.add(tuple(result[name] for name in SCALED_FIELDS))
            config_from_payload({"config": result, "confirm_replace": True})
        self.assertEqual(len(samples), 100)

    def test_same_input_replays_without_changing_global_random_state(self):
        inputs = payload(students=1000, variation_percent=10.5, seed="123456789012345678901234567890")
        old_state = random.getstate()
        self.assertEqual(scale_preview(inputs), scale_preview(inputs))
        self.assertEqual(random.getstate(), old_state)
        self.assertEqual(scale_preview(inputs)["config"]["seed"], inputs["seed"])

    def test_small_presets_keep_required_relationships_valid(self):
        for students in (1, 2, 10, 119):
            for seed in range(30):
                config = scale_preview(payload(students=students, variation_percent=50, seed=str(seed)))["config"]
                self.assertTrue(all(config[name] >= 1 for name in SCALED_FIELDS))
                config_from_payload({"config": config, "confirm_replace": True})

    def test_large_presets_reject_recipient_work_above_budget(self):
        for spread in (0, 10, 50):
            with self.assertRaisesRegex(ValueError, "recipient estimate exceeds 2,000,000"):
                scale_preview(payload(students=10000, variation_percent=spread))

    def test_invalid_inputs_are_rejected_without_coercion(self):
        invalid = {
            "students": [0, -1, 10001, True, 1.5, "1000", None],
            "variation_percent": [-1, 50.01, True, "10", None, float("nan"), float("inf"), 10**400],
            "seed": [True, 1.2, "01", "", "$(id)", "9" * 201, 10**201],
            "as_of": [True, "", None, "2026-11-06T04:30:00", "not a date"],
        }
        for name, values in invalid.items():
            for value in values:
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    scale_preview(payload(**{name: value}))
        for value in (None, [], {}, {**payload(), "confirm_replace": True}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                scale_preview(value)

    def test_timezone_is_normalised_and_seed_remains_exact(self):
        config = scale_preview(payload(as_of="2026-11-06T15:30:00+11:00", seed="-99"))["config"]
        self.assertEqual(config["as_of"], "2026-11-06T04:30:00+00:00")
        self.assertEqual(config["seed"], "-99")


class ScalePreviewHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class QuietHandler(LocalDbGuiHandler):
            def log_message(self, *_args):
                pass
        cls.handler = QuietHandler
        cls.handler.csrf_token = "scale-test-token"
        cls.handler.manager = MagicMock()
        cls.server = LocalDbGuiServer(("127.0.0.1", 0), cls.handler)
        cls.port = cls.server.server_address[1]
        cls.origin = f"http://127.0.0.1:{cls.port}"
        cls.handler.allowed_origins = {cls.origin}
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=1)

    def request(self, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        connection.request("POST", "/api/scale-preview", body=json.dumps(payload() if body is None else body), headers={
            "Content-Type": "application/json", "Origin": self.origin,
            "X-Local-DB-Token": "scale-test-token", **(headers or {}),
        })
        response = connection.getresponse()
        result = response.status, json.loads(response.read())
        connection.close()
        return result

    def test_preview_has_no_database_or_job_side_effect(self):
        self.handler.manager.reset_mock()
        with patch("gui_server.bootstrap_dataset") as bootstrap, patch("gui_server.get_dataset_status") as status, patch("gui_server.setup_django") as setup:
            code, body = self.request(payload(students=1000, variation_percent=10))
        self.assertEqual(code, 200, body)
        self.assertEqual(body["config"]["students"], 1000)
        config_from_payload({"config": body["config"], "confirm_replace": True})
        self.assertEqual(self.handler.manager.mock_calls, [])
        bootstrap.assert_not_called()
        status.assert_not_called()
        setup.assert_not_called()

    def test_preview_has_same_host_origin_token_and_json_guards(self):
        for headers, expected in [
            ({"Host": "example.invalid"}, 421),
            ({"Origin": "https://example.invalid"}, 403),
            ({"X-Local-DB-Token": "wrong"}, 403),
            ({"Content-Type": "text/plain"}, 415),
        ]:
            with self.subTest(headers=headers):
                code, body = self.request(headers=headers)
                self.assertEqual(code, expected, body)

    def test_bad_scale_returns_stable_validation_error(self):
        for body in (payload(students=0), payload(variation_percent=float("nan")), payload(students=10000)):
            code, result = self.request(body)
            self.assertEqual(code, 400)
            self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
