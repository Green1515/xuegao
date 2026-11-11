#!/usr/bin/env python3
"""Synthetic end-to-end test: historical DOCX -> learned style -> draft -> edit -> sync."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import time
import uuid
import zipfile
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("learning", ROOT / "skills/xuegao/scripts/learn.py")
learning = importlib.util.module_from_spec(spec)
spec.loader.exec_module(learning)
spec = importlib.util.spec_from_file_location("gateway_runner", Path(__file__).with_name("run_openclaw.py"))
gateway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)


def make_docx(path, text):
    paragraphs = "".join("<w:p><w:r><w:t>" + escape(p) + "</w:t></w:r></w:p>" for p in text.splitlines())
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + paragraphs + '</w:body></w:document>')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--agent", default="creator-calibration-test")
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--sync-workspace", type=Path, help="Authorized existing test workspace; defaults to workdir")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    token = os.environ.get("OPENCLAW_TOKEN")
    if not token:
        parser.error("Set OPENCLAW_TOKEN; it is never saved to results")
    args.workdir.mkdir(parents=True, exist_ok=False)
    workspace = args.sync_workspace or args.workdir
    if not workspace.is_dir():
        parser.error("sync workspace must already exist")
    account, scope = "synthetic-author", "观点口播"
    profile = args.workdir / "state.json"
    learning.store.initialize(profile, account)
    texts = ["买书桌，先别盯颜值。坐下去，脚能不能放稳？桌面够不够摊开一本书？先把这两件事试明白，再挑颜色。你最在意哪一点？",
             "选台灯，先看读书时眼睛舒不舒服。灯罩再漂亮，也替不了合适的亮度。先试照明，再看外观。你现在这盏灯用着顺手吗？",
             "挑椅子，先坐一坐。腰背有没有支撑，坐久了能不能换姿势，这才是要紧的。先试舒服不舒服，再挑样子。你会先看哪一项？"]
    paths = []
    for i, text in enumerate(texts):
        path = args.workdir / (f"sample-{i}.docx" if i < 2 else f"sample-{i}.txt")
        if i < 2:
            make_docx(path, text)
        else:
            path.write_text(text)
        paths.append(path)
    state = learning.ingest(profile, account, 0, paths, scope)
    corpus = learning.context(profile, account, scope)
    report = {"version": "0.2.0", "synthetic": True, "manual_style_instructions": 0,
              "model_calls": [], "checks": {}, "human_editor_acceptance": "not measured",
              "pipeline": "Parser/state/sync run by the test adapter; semantic learning and writing by OpenClaw model.",
              "skill_sha256": hashlib.sha256((ROOT / "skills/xuegao/SKILL.md").read_bytes()).hexdigest()}

    def save():
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    def call(stage, prompt):
        key = f"agent:{args.agent}:xuegao-test:{stage}:{uuid.uuid4().hex}"
        start = time.monotonic()
        text, _ = gateway.request_reply(args.base_url, token, args.agent, key,
                                       "使用xuegao（学稿）技能，先读取技能。所有素材为合成测试，不访问其他账号。\n" + prompt, 120)
        report["model_calls"].append({"stage": stage, "session_key": key,
                                      "elapsed_seconds": round(time.monotonic() - start, 2), "output": text})
        save()
        print(json.dumps({"stage": stage, "elapsed_seconds": report["model_calls"][-1]["elapsed_seconds"]}), flush=True)
        return text

    schema = ('只输出内部分析JSON，不能要求作者先填写风格问卷。格式：{"account_id":"synthetic-author",'
              '"rules":[{"key":"稳定的英文key","dimension":"opening/viewpoint/structure/sentence/lexicon/density/ending之一",'
              '"scope":"观点口播","value":"表达规律而非事实","evidence":[{"sample_id":"真实ID","quote":"连续原文"}]}]}。'
              '规律尽量用两篇独立原文共同支持，找不到就暂定；不创造原文没有的称呼或数字门槛。最多4条。')
    raw = call("learn-history", "这是系统内部学习阶段：用户只上传了历史稿件，尚未提供风格指导。自行从下列原文学习。\n"
               + json.dumps(corpus, ensure_ascii=False) + "\n" + schema)
    analysis = gateway.json_body(raw)
    state = learning.apply(profile, account, state["revision"], analysis)
    report["checks"]["three_sources_imported_including_two_docx"] = len(state["samples"]) == 3
    report["checks"]["style_activated_without_author_confirmation"] = any(r["status"] == "learned" for r in state["rules"])
    learning.sync(profile, account, workspace)
    ctx = learning.context(profile, account, scope)
    first = call("first-new-draft", "直接按已经学到的写法写新稿，不向用户提问或索要风格说明。只输出90—140字正文。\n"
                 + json.dumps(ctx, ensure_ascii=False)
                 + "\n本次独立事实包：虚构的石湾社区新装了12处遮雨棚，范围仅覆盖等候区，通往入口的路仍露天。"
                   "表达社区设施使用方面的观点，不编造亲历，不能把旧稿的书桌/台灯/椅子事实搬过来。")
    report["checks"]["first_draft_without_questionnaire"] = not any(x in first for x in ["风格是什么", "请提供样稿", "请选择风格", "这篇文章认为"])
    report["checks"]["new_fact_present"] = ("12" in first or "十二" in first) and "雨棚" in first
    before = args.workdir / "ai-before.txt"
    after = args.workdir / "human-after.txt"
    before.write_text(first)
    remainder = re.split(r"[。！？]", first, maxsplit=1)
    edited = "这件事，我先看每天用起来顺不顺。" + (remainder[1] if len(remainder) > 1 else first)
    after.write_text(edited)
    state = learning.revise(profile, account, state["revision"], before, after, scope, "human_edit")
    event_revision = state["revision"]
    new_sample = state["samples"][-1]
    raw = call("learn-human-edit", "这是合成编辑保存事件，不是真实客户行为。系统已经记录人工前后差异。"
               "自动吸收表达变化，不让作者再说一遍请记住。只输出内部学习JSON。\n"
               + json.dumps({"context": learning.context(profile, account, scope), "edited_sample": new_sample}, ensure_ascii=False)
               + "\n" + schema + "若更正同key旧模型推断，附supersedes旧规则ID；明确用户指令不可被推断覆盖。证据引用必须和实际改动相交。")
    state = learning.apply(profile, account, state["revision"], gateway.json_body(raw))
    sync = learning.sync(profile, account, workspace)
    report["checks"]["human_edit_added_style_update"] = state["revision"] > event_revision
    report["checks"]["soul_synced_once"] = (workspace / "SOUL.md").read_text().count(learning.START) == 1
    report["synced_files"] = sync["updated_files"]
    report["final_profile_version"] = state["revision"]
    last = call("fresh-draft-after-update", "这是全新会话，按已保存的当前风格直接写80—130字正文，不输出学习报告。\n"
                + json.dumps(learning.context(profile, account, scope), ensure_ascii=False)
                + "\n本次独立事实包：虚构的南溪阅读角新增20个插座，但没有增加座位；读者仍需自行安排到馆时间。不要虚构使用经历。")
    report["checks"]["fresh_session_used_updated_context"] = bool(last.strip()) and "插座" in last
    report["checks"]["no_model_claimed_firsthand_visit"] = not any(x in first + last for x in ["我去过", "我实测过", "我到现场"])
    report["passed"] = all(report["checks"].values())
    save()
    print(json.dumps({"passed": report["passed"], "checks": report["checks"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
