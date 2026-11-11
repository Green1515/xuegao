import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("profile_store", ROOT / "skills/creator-calibration/scripts/profile.py")
store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(store)


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "profile.json"
        store.initialize(self.path, "demo-a")

    def test_cross_account_read_and_write_are_rejected(self):
        original = self.path.read_bytes()
        with self.assertRaises(ValueError):
            store.context(self.path, "demo-b", "口播")
        with self.assertRaises(ValueError):
            store.record(self.path, "demo-b", 0, "address", "不喊家人们", "口播", "author message", True)
        self.assertEqual(original, self.path.read_bytes())

    def test_hypothesis_never_becomes_active_without_confirmation(self):
        store.record(self.path, "demo-a", 0, "address", "常喊朋友们", "口播", "one sample")
        self.assertEqual(store.context(self.path, "demo-a", "口播")["confirmed_preferences"], [])

    def test_supersession_survives_a_new_process_read_and_preserves_history(self):
        data = store.record(self.path, "demo-a", 0, "address", "常喊朋友们", "口播", "old author request", True)
        old_id = data["rules"][0]["id"]
        store.record(self.path, "demo-a", 1, "address", "直接开场，不喊朋友们", "口播", "new author request", True, old_id)
        result = subprocess.run([sys.executable, str(ROOT / "skills/creator-calibration/scripts/profile.py"),
                                 "--profile", str(self.path), "--account", "demo-a", "context", "--scope", "口播"],
                                capture_output=True, text=True, check=True)
        fresh = json.loads(result.stdout)
        self.assertEqual(fresh["profile_version"], 2)
        self.assertEqual([x["value"] for x in fresh["confirmed_preferences"]], ["直接开场，不喊朋友们"])
        old = json.loads((Path(str(self.path) + ".history") / "1.json").read_text())
        self.assertEqual(old["rules"][0]["status"], "confirmed")

    def test_stale_update_cannot_overwrite_a_newer_revision(self):
        store.record(self.path, "demo-a", 0, "voice", "短句", "口播", "author request", True)
        original = self.path.read_bytes()
        with self.assertRaises(ValueError):
            store.record(self.path, "demo-a", 0, "opening", "直接开头", "口播", "author request", True)
        self.assertEqual(original, self.path.read_bytes())

    def test_conflicting_rule_requires_explicit_replacement(self):
        store.record(self.path, "demo-a", 0, "voice", "短句", "口播", "author request", True)
        with self.assertRaises(ValueError):
            store.record(self.path, "demo-a", 1, "voice", "长句", "口播", "new request", True)

    def test_scope_and_global_conflicts_cannot_silently_mix(self):
        store.record(self.path, "demo-a", 0, "voice", "长句", "长文", "author request", True)
        self.assertEqual(store.context(self.path, "demo-a", "口播")["confirmed_preferences"], [])
        store.record(self.path, "demo-a", 1, "voice", "短句", "*", "author request", True)
        with self.assertRaises(ValueError):
            store.context(self.path, "demo-a", "长文")


if __name__ == "__main__":
    unittest.main()
