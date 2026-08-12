"""Core tests for 月相羅針 計算PoC v0.7｜Vue.js画面版."""

from __future__ import annotations

import os
import sys
import unittest

# Allow tests to import modules from the project root.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from app import app
except ModuleNotFoundError as exc:
    if exc.name != "flask":
        raise
    app = None

from astronomy import calculate_birth_astronomy, calculate_birth_date_astronomy
from phase_classifier import classify_phase, classify_possible_phases


class TestAstronomy(unittest.TestCase):
    def test_reference_birth_data_known_time(self) -> None:
        """Test 1: known birth time keeps the existing exact calculation."""
        result = calculate_birth_astronomy(
            birth_date="1964-09-03",
            birth_time="11:23",
            timezone_name="Asia/Tokyo",
        )

        self.assertEqual(
            result["utc_datetime"].strftime("%Y-%m-%d %H:%M:%S UTC"),
            "1964-09-03 02:23:00 UTC",
        )

        # The original PoC reference values are approximate. A tolerance of
        # 0.0001 degree (= 0.36 arcsec) avoids brittle float comparisons.
        tolerance = 0.0001
        self.assertAlmostEqual(
            float(result["sun_longitude"]), 160.60945188, delta=tolerance
        )
        self.assertAlmostEqual(
            float(result["moon_longitude"]), 119.86709682, delta=tolerance
        )
        self.assertAlmostEqual(
            float(result["angle_difference"]), 319.25764494, delta=tolerance
        )

        phase = classify_phase(float(result["angle_difference"]))
        self.assertEqual(phase["id"], "P08")
        self.assertEqual(phase["name"], "欠けていく三日月")


class TestProvisionalPhaseBoundaries(unittest.TestCase):
    def test_boundaries(self) -> None:
        """Test 2: 45-degree boundaries and 360->0 normalization."""
        cases = [
            (0.0, "P01"),
            (44.9999, "P01"),
            (45.0, "P02"),
            (315.0, "P08"),
            (359.9999, "P08"),
            (360.0, "P01"),
        ]
        for angle, expected_id in cases:
            with self.subTest(angle=angle):
                self.assertEqual(classify_phase(angle)["id"], expected_id)

    def test_possible_phases_handles_wraparound(self) -> None:
        result = classify_possible_phases([359.5, 0.5])
        self.assertEqual(result["classification_status"], "ambiguous")
        self.assertEqual(
            [phase["id"] for phase in result["possible_phases"]],
            ["P08", "P01"],
        )


class TestUnknownBirthTime(unittest.TestCase):
    def test_stable_day_returns_one_candidate(self) -> None:
        """Test 3: 1964-09-04 stays within P08 for the whole JST date."""
        day = calculate_birth_date_astronomy(
            birth_date="1964-09-04",
            timezone_name="Asia/Tokyo",
            interval_minutes=30,
        )
        result = classify_possible_phases(day["angle_differences"])

        self.assertEqual(result["classification_status"], "stable")
        self.assertEqual(len(result["possible_phases"]), 1)
        self.assertEqual(result["possible_phases"][0]["id"], "P08")

    def test_ambiguous_day_returns_multiple_candidates(self) -> None:
        """Test 4: 1964-09-03 crosses the 315-degree P07/P08 boundary."""
        day = calculate_birth_date_astronomy(
            birth_date="1964-09-03",
            timezone_name="Asia/Tokyo",
            interval_minutes=30,
        )
        result = classify_possible_phases(day["angle_differences"])

        self.assertEqual(result["classification_status"], "ambiguous")
        self.assertGreaterEqual(len(result["possible_phases"]), 2)
        self.assertEqual(
            [phase["id"] for phase in result["possible_phases"]],
            ["P07", "P08"],
        )


class TestCalculateAPI(unittest.TestCase):
    def setUp(self) -> None:
        if app is None:
            self.skipTest("Flask is not installed in this execution environment.")
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def test_known_time_api_returns_exact_p08(self) -> None:
        response = self.client.post(
            "/api/calculate",
            json={
                "birth_date": "1964-09-03",
                "birth_time": "11:23",
                "birth_place": "兵庫県小野市",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        result = data["result"]
        self.assertTrue(result["birth_time_known"])
        self.assertEqual(result["classification_status"], "exact")
        self.assertEqual(result["phase_id"], "P08")
        self.assertEqual(result["phase_name"], "欠けていく三日月")
        self.assertAlmostEqual(result["angle_difference"], 319.25764494, delta=0.0001)

    def test_unknown_time_api_returns_stable(self) -> None:
        response = self.client.post(
            "/api/calculate",
            json={
                "birth_date": "1964-09-04",
                "birth_time": "",
                "birth_place": "兵庫県小野市",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        result = data["result"]
        self.assertFalse(result["birth_time_known"])
        self.assertEqual(result["classification_status"], "stable")
        self.assertEqual([p["id"] for p in result["possible_phases"]], ["P08"])

    def test_unknown_time_api_returns_ambiguous(self) -> None:
        response = self.client.post(
            "/api/calculate",
            json={
                "birth_date": "1964-09-03",
                "birth_time": "",
                "birth_place": "兵庫県小野市",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        result = data["result"]
        self.assertEqual(result["classification_status"], "ambiguous")
        self.assertEqual(
            [p["id"] for p in result["possible_phases"]],
            ["P07", "P08"],
        )

    def test_validation_errors_are_returned_as_json(self) -> None:
        response = self.client.post(
            "/api/calculate",
            json={"birth_date": "", "birth_time": "", "birth_place": ""},
        )

        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(
            data["errors"],
            ["生年月日を入力してください。", "出生地を入力してください。"],
        )


class TestVueInputUI(unittest.TestCase):
    def _read(self, relative_path: str) -> str:
        with open(os.path.join(PROJECT_ROOT, relative_path), encoding="utf-8") as handle:
            return handle.read()

    def test_root_serves_vue_screen_and_static_app(self) -> None:
        if app is None:
            self.skipTest("Flask is not installed in this execution environment.")
        app.config.update(TESTING=True)
        client = app.test_client()
        response = client.get("/")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("月相羅針 計算PoC v0.7", html)
        self.assertIn("vue@3/dist/vue.global.prod.js", html)
        self.assertIn("/static/app.js?v=0.7", html)
        self.assertIn('id="app"', html)

    def test_template_uses_vue_models_without_server_result_rendering(self) -> None:
        html = self._read("templates/index.html")

        self.assertIn('v-model="form.birth_date"', html)
        self.assertIn('v-model="form.birth_time"', html)
        self.assertIn('v-model="form.birth_place"', html)
        self.assertIn('@submit.prevent="calculate"', html)
        self.assertNotIn("{% if result %}", html)
        self.assertNotIn("{{ result.", html)

    def test_form_reset_clears_all_three_fields_in_vue(self) -> None:
        html = self._read("templates/index.html")
        js = self._read("static/app.js")

        self.assertIn('@reset="resetForm"', html)
        self.assertIn('resetForm()', js)
        self.assertIn('this.form.birth_date = "";', js)
        self.assertIn('this.form.birth_time = "";', js)
        self.assertIn('this.form.birth_place = "";', js)

    def test_all_input_types_keep_v06_fixed_height_and_top_alignment(self) -> None:
        css = self._read("static/style.css")

        self.assertIn("align-content: start;", css)
        self.assertIn("align-self: start;", css)
        self.assertIn("--form-control-height: 48px;", css)
        self.assertIn('input[type="date"]', css)
        self.assertIn('input[type="time"]', css)
        self.assertIn('input[type="text"]', css)
        self.assertIn("max-block-size: var(--form-control-height);", css)

    def test_empty_date_and_time_are_primed_with_device_local_now(self) -> None:
        html = self._read("templates/index.html")
        js = self._read("static/app.js")

        self.assertIn("const now = new Date();", js)
        self.assertIn("now.getFullYear()", js)
        self.assertIn("now.getMonth() + 1", js)
        self.assertIn("now.getDate()", js)
        self.assertIn("now.getHours()", js)
        self.assertIn("now.getMinutes()", js)
        self.assertIn('@pointerdown="primeCurrentDateIfEmpty"', html)
        self.assertIn('@focus="primeCurrentDateIfEmpty"', html)
        self.assertIn('@pointerdown="primeCurrentTimeIfEmpty"', html)
        self.assertIn('@focus="primeCurrentTimeIfEmpty"', html)
        self.assertIn("if (this.form.birth_date || event.currentTarget.value) return;", js)
        self.assertIn("if (this.form.birth_time || event.currentTarget.value) return;", js)

    def test_vue_calls_flask_api_and_has_loading_state(self) -> None:
        html = self._read("templates/index.html")
        js = self._read("static/app.js")

        self.assertIn('fetch("/api/calculate"', js)
        self.assertIn('method: "POST"', js)
        self.assertIn('"Content-Type": "application/json"', js)
        self.assertIn("JSON.stringify", js)
        self.assertIn("loading: false", js)
        self.assertIn("計算中...", html)


if __name__ == "__main__":
    unittest.main()
