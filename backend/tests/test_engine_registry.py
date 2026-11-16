"""Narrated 2D engine selection tests. No external test runner dependency."""
import unittest

from backend.app.engines.registry import engine_catalog, selected_render_engine, validate_engine


class EngineRegistryTests(unittest.TestCase):
    def test_narrated_2d_is_the_only_production_engine(self):
        catalog = engine_catalog()
        self.assertEqual(catalog["selected"], "2d")
        self.assertFalse(catalog["separation"]["gpu_required"])
        self.assertFalse(catalog["separation"]["blender_required"])
        self.assertFalse(catalog["separation"]["image_api_required"])
        self.assertEqual(catalog["engines"][0]["id"], "2d")
        self.assertEqual(catalog["engines"][0]["worker"], "vps-cpu")

    def test_never_requires_remote_worker(self):
        self.assertEqual(engine_catalog(worker_connected=False)["selected"], "2d")
        self.assertEqual(engine_catalog(worker_connected=True)["selected"], "2d")

    def test_render_engine_validation_is_strict(self):
        self.assertEqual(selected_render_engine(), "2d")
        self.assertEqual(validate_engine("2d"), "2d")
        with self.assertRaises(ValueError):
            validate_engine("3d")


if __name__ == "__main__":
    unittest.main()
