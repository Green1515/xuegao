#!/usr/bin/env python3
"""Compare two dedicated OpenClaw test agents using synthetic fixtures only."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid


def json_body(text):
    match = re.fullmatch(r"\s*```(?:json)?\s*\n([\s\S]*?)\n```\s*", text)
    return json.loads(match[1] if match else text)


def check_output(text, checks, samples):
    checks = dict(checks)
    results = {"nonempty": bool(text.strip())}
    for forbidden in checks.get("forbidden", []):
        results["absent:" + forbidden] = forbidden not in text
    if checks.get("required_any"):
        results["required_fact_or_boundary"] = any(x in text for x in checks["required_any"])
    if checks.get("max_hanzi"):
        results["length_bound"] = len(re.findall(r"[\u4e00-\u9fff]", text)) <= checks["max_hanzi"]
    if checks.get("max_sentences"):
        results["sentence_count"] = len([s for s in re.split(r"[。！？!?]+", text) if s.strip()]) == checks["max_sentences"]
    if checks.get("json_rules"):
        try:
            data = json_body(text)
            rules = data["rules"]
            valid = bool(rules) and all(isinstance(x, dict) for x in rules)
            source_map = {s["id"]: s["text"] for s in samples if s["format"] == "观点口播"}
            valid = valid and all(isinstance(r.get("evidence"), str) and bool(r["evidence"].strip())
                                  and r["evidence"] in source_map.get(r.get("sample_id"), "") for r in rules)
            results["traceable_style_evidence"] = valid
        except (ValueError, KeyError, TypeError):
            results["traceable_style_evidence"] = False
    if checks.get("feedback_json"):
        try:
            data = json_body(text)
            results["feedback_structure"] = bool(data["feedback_meaning"]) and isinstance(data["proposed_rules"], list)
        except (ValueError, KeyError, TypeError):
            results["feedback_structure"] = False
    return results


def request_reply(base_url, token, agent, session_key, prompt, timeout):
    payload = {"model": "openclaw/" + agent,
               "messages": [{"role": "user", "content": prompt}]}
    request = Request(base_url.rstrip("/") + "/v1/chat/completions",
                      data=json.dumps(payload, ensure_ascii=False).encode(),
                      headers={"Content-Type": "application/json", "Authorization": "Bearer " + token,
                               "x-openclaw-session-key": session_key})
    with urlopen(request, timeout=timeout) as response:
        data = json.load(response)
    message = data["choices"][0]["message"]
    content = message.get("content", "")
    if not isinstance(content, str):
        raise ValueError("unsupported response content shape")
    return content, data.get("usage", {})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--baseline-agent", default="creator-calibration-base")
    parser.add_argument("--candidate-agent", default="creator-calibration-test")
    parser.add_argument("--fixture", type=Path, default=Path(__file__).with_name("cases.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=100)
    parser.add_argument("--ids", help="Comma-separated subset; omitted runs all cases")
    parser.add_argument("--arms", default="baseline,candidate", help="baseline,candidate or one arm")
    parser.add_argument("--candidate-invocation", choices=["explicit", "implicit"], default="explicit")
    args = parser.parse_args()
    arms = args.arms.split(",")
    if not arms or len(set(arms)) != len(arms) or any(a not in {"baseline", "candidate"} for a in arms):
        parser.error("Invalid arms")
    token = os.environ.get("OPENCLAW_TOKEN")
    if not token:
        parser.error("Set OPENCLAW_TOKEN in the environment; credentials are never written to results")
    fixture = json.loads(args.fixture.read_text())
    if fixture.get("synthetic") is not True:
        parser.error("This runner accepts explicitly synthetic fixtures only")
    cases = fixture["cases"]
    if args.ids:
        selected = set(args.ids.split(","))
        cases = [c for c in cases if c["id"] in selected]
        if len(cases) != len(selected):
            parser.error("Unknown or duplicate case ids")
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "synthetic": True,
              "method": "One fresh session per case/arm. Same fixtures; independent agents. Objective checks only.",
              "candidate_invocation": args.candidate_invocation,
              "human_editor_acceptance": "not measured", "rows": []}
    for case in cases:
        for arm, agent in [("baseline", args.baseline_agent), ("candidate", args.candidate_agent)]:
            if arm not in arms:
                continue
            prompt = ("这是合成测试账号demo-editor-a，所有地名和活动均为虚构。不得联网或访问其他账号。\n"
                      + "账号上下文：\n" + json.dumps(fixture["context"], ensure_ascii=False)
                      + "\n当前任务：\n" + case["task"])
            if arm == "candidate" and args.candidate_invocation == "explicit":
                prompt = "请使用creator-calibration技能完成以下任务，先读取技能。\n" + prompt
            session = f"agent:{agent}:skill-eval:{case['id']}:{uuid.uuid4().hex}"
            start = time.monotonic()
            try:
                text, usage = request_reply(args.base_url, token, agent, session, prompt, args.timeout)
                checks = check_output(text, case["checks"], fixture["context"]["samples"])
                row = {"case": case["id"], "arm": arm, "session_key": session, "text": text,
                       "usage": usage, "checks": checks, "passed": all(checks.values())}
            except (HTTPError, URLError, ValueError, KeyError, TimeoutError) as exc:
                # HTTP bodies and request headers may contain sensitive details; do not save them.
                row = {"case": case["id"], "arm": arm, "session_key": session,
                       "passed": False, "error_type": type(exc).__name__}
            row["elapsed_seconds"] = round(time.monotonic() - start, 2)
            report["rows"].append(row)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
            print(json.dumps({k:row[k] for k in ["case", "arm", "passed", "elapsed_seconds"]}), flush=True)
            if row.get("error_type"):
                raise SystemExit("Transport failed; stop and inspect rather than retrying every case")
    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
