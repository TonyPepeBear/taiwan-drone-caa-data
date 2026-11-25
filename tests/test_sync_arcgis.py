import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import sync_arcgis


LAYER = {"slug": "temporary_area", "title": "臨時空域", "service": "fixture"}
FEATURE = {
    "type": "Feature",
    "id": 42,
    "properties": {"有效日期迄": "2026-12-17", "空域名稱": "測試"},
    "geometry": {
        "type": "Polygon",
        "coordinates": [[[121, 25], [122, 25], [122, 26], [121, 25]]],
    },
}


class SyncComparisonTests(unittest.TestCase):
    def run_sync(self, output, features, previous=None):
        argv = ["sync_arcgis.py", "--output-dir", str(output), "--sleep-seconds", "0"]
        if previous is not None:
            argv += ["--compare-manifest", str(previous)]
        with (
            patch.object(sys, "argv", argv),
            patch.object(sync_arcgis, "load_layers", return_value=[LAYER]),
            patch.object(sync_arcgis, "fetch_count", return_value=len(features)),
            patch.object(sync_arcgis, "fetch_geojson_page", return_value={"features": features}),
        ):
            self.assertEqual(sync_arcgis.main(), 0)

    def compare(self, before, after, *, legacy=False):
        with tempfile.TemporaryDirectory() as temp:
            before_dir, after_dir = Path(temp) / "before", Path(temp) / "after"
            self.run_sync(before_dir, before)
            manifest = before_dir / "manifest.json"
            if legacy:
                data = json.loads(manifest.read_text())
                data["layers"][0].pop("features_sha256")
                manifest.write_text(json.dumps(data))
            self.run_sync(after_dir, after, manifest)
            diff = json.loads((after_dir / "diff_report.json").read_text())
            path = after_dir / "changelog.md"
            return diff, path.read_text() if path.exists() else None

    def assert_detected_without_id_change(self, after):
        diff, changelog = self.compare([FEATURE], [after])
        layer = diff["layers"][LAYER["slug"]]
        self.assertTrue(diff["has_changes"])
        self.assertTrue(layer["content_changed"])
        self.assertEqual(layer["added_objectids"], [])
        self.assertEqual(layer["removed_objectids"], [])
        self.assertIn("objectid 不變", changelog)

    def test_detects_updated_date_with_same_id(self):
        after = copy.deepcopy(FEATURE)
        after["properties"]["有效日期迄"] = "2026-12-18"
        self.assert_detected_without_id_change(after)

    def test_detects_updated_polygon_with_same_id(self):
        after = copy.deepcopy(FEATURE)
        after["geometry"]["coordinates"][0][1][0] = 122.01
        self.assert_detected_without_id_change(after)

    def test_ignores_feature_order_and_json_object_key_order(self):
        other = {**FEATURE, "id": 43}
        reordered = dict(reversed(list(FEATURE.items())))
        reordered["properties"] = dict(reversed(list(FEATURE["properties"].items())))
        diff, changelog = self.compare([FEATURE, other], [other, reordered])
        self.assertFalse(diff["has_changes"])
        self.assertIsNone(changelog)

    def test_id_additions_and_removals_are_still_reported(self):
        diff, _ = self.compare([FEATURE], [{**FEATURE, "id": 43}])
        layer = diff["layers"][LAYER["slug"]]
        self.assertTrue(diff["has_changes"])
        self.assertEqual(layer["added_objectids"], [43])
        self.assertEqual(layer["removed_objectids"], [42])

    def test_legacy_manifest_creates_baseline_without_claiming_change(self):
        diff, changelog = self.compare([FEATURE], [FEATURE], legacy=True)
        layer = diff["layers"][LAYER["slug"]]
        self.assertTrue(diff["has_changes"])
        self.assertTrue(layer["content_baseline_missing"])
        self.assertFalse(layer["content_changed"])
        self.assertIn("建立後續比對基準", changelog)


if __name__ == "__main__":
    unittest.main()
