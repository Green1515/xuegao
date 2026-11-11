import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("xuegao_learning", ROOT / "skills/xuegao/scripts/learn.py")
learn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(learn)


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.profile = self.root / "state.json"
        learn.store.initialize(self.profile, "demo")

    def text(self, name, body):
        p = self.root / name
        p.write_text(body)
        return p

    def ingest_two(self, kind="author_sample"):
        a = self.text("one.txt", "挑灯先看眼睛舒不舒服。先试亮度，再挑样子。")
        b = self.text("two.md", "买椅子先试坐。先看腰背能不能靠稳，再挑颜色。")
        return learn.ingest(self.profile, "demo", 0, [a, b], "口播", kind)

    def analysis(self, data, evidence_count=2, **changes):
        rule = {"key": "structure", "dimension": "structure", "scope": "口播",
                "value": "从实际使用条件切入，先功能后外观", "evidence": [
                    {"sample_id": s["id"], "quote": quote} for s, quote in
                    zip(data["samples"][:evidence_count], ["先试亮度，再挑样子", "先看腰背能不能靠稳，再挑颜色"])]}
        rule.update(changes)
        return {"account_id": "demo", "rules": [rule]}

    def test_docx_extracts_paragraphs_and_final_revision_text(self):
        p = self.root / "sample.docx"
        xml = '''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
        <w:p><w:r><w:t>第一段</w:t></w:r></w:p><w:p><w:del><w:r><w:delText>已删除</w:delText></w:r></w:del>
        <w:ins><w:r><w:t>保留新内容</w:t></w:r></w:ins></w:p></w:body></w:document>'''
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("word/document.xml", xml)
        self.assertEqual(learn.extract(p), "第一段\n保留新内容")

    def test_duplicate_manuscripts_do_not_inflate_evidence_or_version(self):
        data = self.ingest_two()
        duplicate = self.text("copy.txt", data["samples"][0]["text"])
        newer = learn.ingest(self.profile, "demo", 1, [duplicate], "口播")
        self.assertEqual(len(newer["samples"]), 2)
        self.assertEqual(newer["revision"], 1)

    def test_multiple_sources_activate_style_without_manual_confirmation(self):
        data = self.ingest_two()
        result = learn.apply(self.profile, "demo", 1, self.analysis(data))
        self.assertEqual(result["rules"][0]["status"], "learned")
        ctx = learn.context(self.profile, "demo", "口播")
        self.assertEqual(len(ctx["learned_preferences"]), 1)
        self.assertEqual(len(ctx["style_examples"]), 2)

    def test_one_source_is_immediately_usable_but_tentative(self):
        data = self.ingest_two()
        learn.apply(self.profile, "demo", 1, self.analysis(data, evidence_count=1))
        self.assertEqual(len(learn.context(self.profile, "demo", "口播")["tentative_preferences"]), 1)

    def test_fabricated_quote_and_ai_draft_are_not_author_evidence(self):
        data = self.ingest_two(kind="ai_draft")
        with self.assertRaises(ValueError):
            learn.apply(self.profile, "demo", 1, self.analysis(data))
        self.assertEqual(learn.store.read_profile(self.profile, "demo")["rules"], [])

    def test_nonexistent_quote_cannot_be_saved(self):
        data = self.ingest_two()
        a = self.analysis(data)
        a["rules"][0]["evidence"][0]["quote"] = "原稿没有的口头禅"
        with self.assertRaises(ValueError):
            learn.apply(self.profile, "demo", 1, a)
        self.assertEqual(learn.store.read_profile(self.profile, "demo")["revision"], 1)

    def test_promotion_merges_independent_evidence(self):
        data = self.ingest_two()
        learn.apply(self.profile, "demo", 1, self.analysis(data, evidence_count=1))
        result = learn.apply(self.profile, "demo", 2, self.analysis(data))
        self.assertEqual(result["rules"][0]["status"], "learned")
        self.assertEqual(result["rules"][0]["support_count"], 2)

    def test_confirmed_user_rule_is_not_overwritten_by_automatic_learning(self):
        data = self.ingest_two()
        learn.store.record(self.profile, "demo", 1, "structure", "本账号先讲外观", "口播", "explicit author directive", True)
        result = learn.apply(self.profile, "demo", 2, self.analysis(data))
        self.assertEqual(result["rules"][0]["status"], "confirmed")
        self.assertEqual(result["rules"][1]["status"], "proposed")

    def test_human_revision_requires_real_changed_evidence(self):
        before = self.text("before.txt", "这款灯照明稳定。先说结论：选灯看亮度。")
        after = self.text("after.txt", "这款灯照明稳定。选灯先看眼睛舒不舒服。")
        data = learn.revise(self.profile, "demo", 0, before, after, "口播", "human_edit")
        sid = data["samples"][0]["id"]
        a = {"account_id": "demo", "rules": [{"key": "opening", "dimension": "opening", "scope": "口播",
             "value": "直接讲使用条件", "evidence": [{"sample_id": sid, "quote": "这款灯照明稳定"}]}]}
        with self.assertRaises(ValueError):
            learn.apply(self.profile, "demo", 1, a)
        a["rules"][0]["evidence"][0]["quote"] = "选灯先看眼睛舒不舒服"
        self.assertEqual(learn.apply(self.profile, "demo", 1, a)["rules"][0]["status"], "tentative")

    def test_inferred_rule_can_be_replaced_by_actual_human_edit(self):
        data = self.ingest_two()
        data = learn.apply(self.profile, "demo", 1, self.analysis(data))
        old_id = data["rules"][0]["id"]
        before = self.text("before.txt", "先讲功能，再挑外观。")
        after = self.text("after.txt", "这次先看外观，再试功能。")
        data = learn.revise(self.profile, "demo", 2, before, after, "口播", "human_edit")
        a = {"account_id": "demo", "rules": [{"key": "structure", "dimension": "structure", "scope": "口播",
             "value": "当前体裁先外观后功能，暂定", "supersedes": old_id,
             "evidence": [{"sample_id": data["samples"][-1]["id"], "quote": "这次先看外观，再试功能"}]}]}
        result = learn.apply(self.profile, "demo", 3, a)
        self.assertEqual(result["rules"][0]["status"], "superseded")
        self.assertEqual(result["rules"][1]["status"], "tentative")

    def test_deleted_phrase_can_only_teach_avoidance(self):
        before = self.text("before.txt", "先给结论：选灯看眼睛舒不舒服。")
        after = self.text("after.txt", "选灯看眼睛舒不舒服。")
        data = learn.revise(self.profile, "demo", 0, before, after, "口播", "human_edit")
        a = {"account_id": "demo", "rules": [{"key": "opening", "dimension": "opening", "scope": "口播",
             "value": "避免先给结论的铺垫", "evidence": [{"sample_id": data["samples"][0]["id"],
                                                        "quote": "先给结论", "side": "before"}]}]}
        with self.assertRaises(ValueError):
            learn.apply(self.profile, "demo", 1, a)
        a["rules"][0]["operation"] = "avoid"
        self.assertEqual(learn.apply(self.profile, "demo", 1, a)["rules"][0]["status"], "tentative")

    def test_sync_preserves_other_soul_content_and_replaces_one_managed_block(self):
        data = self.ingest_two()
        learn.apply(self.profile, "demo", 1, self.analysis(data))
        soul = self.root / "SOUL.md"
        soul.write_text("# 人设\n保留其他业务规则\n")
        learn.sync(self.profile, "demo", self.root)
        self.assertIn("保留其他业务规则", soul.read_text())
        self.assertIn("从实际使用条件切入", soul.read_text())
        self.assertNotIn(data["samples"][0]["text"], soul.read_text())
        self.assertEqual(learn.sync(self.profile, "demo", self.root)["updated_files"], [])
        self.assertEqual(soul.read_text().count(learn.START), 1)

    def test_recent_human_revision_is_not_crowded_out_by_old_short_samples(self):
        self.ingest_two()
        before = self.text("before.txt", "先讲功能。" * 30)
        after = self.text("after.txt", "这件事，我先看用起来顺不顺。" + "再看具体条件。" * 30)
        data = learn.revise(self.profile, "demo", 1, before, after, "口播", "human_edit")
        ctx = learn.context(self.profile, "demo", "口播", limit=1)
        self.assertEqual(ctx["style_examples"][0]["id"], data["samples"][-1]["id"])

    def test_unchanged_ai_sentences_are_not_new_author_examples(self):
        before = self.text("before.txt", "先给结论：这里可以坐。模型原句没改，不代表作者认可。")
        after = self.text("after.txt", "先看这里坐着舒服不舒服。模型原句没改，不代表作者认可。")
        learn.revise(self.profile, "demo", 0, before, after, "口播", "human_edit")
        example = learn.context(self.profile, "demo", "口播")["style_examples"][0]["text"]
        self.assertIn("舒服不舒服", example)
        self.assertNotIn("模型原句没改", example)
        self.assertEqual(learn.example_text({"kind": "human_revision", "text": "新句。未改旧句。",
                                             "changed_ranges": [[0, 3]]}), "新句。")

    def test_format_and_account_boundaries_are_preserved(self):
        data = self.ingest_two()
        a = self.analysis(data)
        a["rules"][0]["scope"] = "长文"
        with self.assertRaises(ValueError):
            learn.apply(self.profile, "demo", 1, a)
        with self.assertRaises(ValueError):
            learn.sync(self.profile, "other-account", self.root)
        self.assertFalse((self.root / "SOUL.md").exists())


if __name__ == "__main__":
    unittest.main()
