"""data#22 卡片审查量表：五项自动评分；不进 route；第(5)项读本机/fixture 清单。"""
import ast
import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import DATE, make_repo, quote_line, source_line

from markjin import card_scale as CS
from markjin import route as R
from markjin import selfcheck as SC
from markjin.codes import ERROR_CODES
from markjin.selfcheck import check_text
from markjin.textnorm import compact


FIXTURE_LIST = """| id | phrase | kind | source_note |
|---|---|---|---|
| FC-T1 | 宏观中枢可以作为股市分析的上位状态机 | 猜想 | 测试用，非真实清单 |
| FC-T2 | 认知训练假说 | 假说 | 测试用 |
| FC-T3 | F⁺ | 待王总定 | 测试用短码 |
"""


def _write_frame_list(idir: Path, body: str = FIXTURE_LIST) -> Path:
    idir.mkdir(parents=True, exist_ok=True)
    p = idir / "frame-conjecture.md"
    p.write_text(body, encoding="utf-8")
    return p


class ParseFrameList(unittest.TestCase):
    def test_ok(self):
        rows = CS.parse_frame_list(FIXTURE_LIST)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["id"], "FC-T1")
        self.assertEqual(compact(rows[2]["phrase"]), compact("F⁺"))

    def test_rejects_bad(self):
        self.assertIsNone(CS.parse_frame_list(""))
        self.assertIsNone(CS.parse_frame_list("| a | b |\n|---|---|\n| 1 | 2 |\n"))
        self.assertIsNone(CS.parse_frame_list(
            "| id | phrase | kind | source_note |\n|---|---|---|---|\n"))  # 无数据行

    def test_load_missing_fail_closed(self):
        d = Path(tempfile.mkdtemp())
        self.assertIsNone(CS.load_frame_list(d / "nope.md"))


class FrameMatch(unittest.TestCase):
    def setUp(self):
        self.entries = CS.parse_frame_list(FIXTURE_LIST)

    def test_hit_and_tag_strip(self):
        # 去标签仍算命中
        t = "本文认为宏观中枢可以作为股市分析的上位状态机（猜想）。"
        self.assertGreaterEqual(CS.frame_hit_count(t, self.entries), 1)
        t2 = "讨论认知训练假说的公开表述。"
        self.assertGreaterEqual(CS.frame_hit_count(t2, self.entries), 1)

    def test_no_hit(self):
        self.assertEqual(CS.frame_hit_count("今日 arXiv 动态摘要。", self.entries), 0)

    def test_public_output_no_phrase(self):
        text = "宏观中枢可以作为股市分析的上位状态机"
        item = CS.score_item_frame(text, self.entries)
        blob = json.dumps(item, ensure_ascii=False)
        self.assertNotIn("宏观中枢", blob)
        self.assertEqual(item["status"], "fail")
        self.assertEqual(item["codes"], ["E-FRAME-CONJECTURE"])
        self.assertEqual(item["hit_count"], 1)


class ScaleMapping(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()
        self.flist = _write_frame_list(Path(tempfile.mkdtemp()) / "markjin-internal")

    def _sc(self, body, card_type="daily"):
        return check_text(
            body, self.repo, DATE, card_type,
            link_checker=lambda u: True, internal_terms="load",
        )

    def test_evidence_fail_on_replay(self):
        # 无来源断言 → E-REPLAY-001（及可能 E-INFER-UNCLEAR）
        sc = self._sc("这是一段无来源的断言，准确率 90%。\n")
        item = CS.score_item_evidence(sc)
        self.assertEqual(item["status"], "fail")
        self.assertTrue(any(c.startswith("E-REPLAY-") for c in item["codes"]))

    def test_evidence_pass_on_clean_quote(self):
        body = "\n".join([
            "# 动态",
            quote_line(),
            source_line(),
            "",
        ])
        sc = self._sc(body)
        # 可能仍有其他码，但证据项只看 E-REPLAY-*
        replay = [c for c in sc["error_codes"] if c.startswith("E-REPLAY-")]
        item = CS.score_item_evidence(sc)
        self.assertEqual(item["status"], "fail" if replay else "pass")

    def test_investment_fail(self):
        sc = {"error_codes": ["E-BLOCK-INVEST", "R-MACRO"], "flags": {}}
        self.assertEqual(CS.score_item_investment(sc)["status"], "fail")
        self.assertEqual(CS.score_item_investment({"error_codes": [], "flags": {}})["status"], "pass")

    def test_inference_mapping(self):
        self.assertEqual(
            CS.score_item_inference({"error_codes": ["E-INFER-UNCLEAR"], "flags": {}})["status"],
            "fail",
        )
        self.assertEqual(
            CS.score_item_inference({"error_codes": ["R-INFERENCE"], "flags": {"has_inference": True}})["status"],
            "pending_human",
        )
        self.assertEqual(
            CS.score_item_inference({"error_codes": [], "flags": {}})["status"],
            "pass",
        )

    def test_faithful_quote_fail(self):
        sc = {"error_codes": ["R-QUOTE-UNVERIFIED"], "flags": {"quote_unverified": True}}
        self.assertEqual(CS.score_item_faithful(sc)["status"], "fail")

    def test_faithful_pending_on_free_text(self):
        sc = {"error_codes": [], "flags": {"free_text": True}}
        self.assertEqual(CS.score_item_faithful(sc)["status"], "pending_human")

    def test_faithful_pass_clean(self):
        sc = {"error_codes": [], "flags": {}}
        self.assertEqual(CS.score_item_faithful(sc)["status"], "pass")

    def test_frame_missing_list_fail_closed(self):
        item = CS.score_item_frame("hello", None)
        self.assertEqual(item["status"], "fail")
        self.assertFalse(item["list_available"])
        self.assertEqual(item["codes"], [])

    def test_overall_and_public_summary(self):
        body = "\n".join(["# 动态", quote_line(), source_line(), ""])
        sc = self._sc(body)
        r = CS.score_card(body, sc, frame_list_path_override=self.flist)
        self.assertIn("overall_pass", r)
        self.assertEqual(set(r["items"]), set(CS.ITEM_KEYS))
        for it in r["items"].values():
            self.assertIn(it["status"], CS.STATUSES)
        s = r["summary"]
        self.assertEqual(s["item_count"], 5)
        self.assertEqual(s["pass_count"] + s["fail_count"] + s["pending_human_count"], 5)
        blob = json.dumps(r, ensure_ascii=False)
        # 不得含清单绝对路径或 fixture 命中原文（本样本无命中；另测命中样本）
        self.assertNotIn(str(self.flist), blob)
        self.assertNotIn("/" + "workspace" + "/", blob)

    def test_hit_public_no_leak(self):
        body = "宏观中枢可以作为股市分析的上位状态机\n"
        sc = self._sc(body)
        r = CS.score_card(body, sc, frame_list_path_override=self.flist)
        self.assertEqual(r["items"]["no_frame_conjecture"]["status"], "fail")
        self.assertIn("E-FRAME-CONJECTURE", r["items"]["no_frame_conjecture"]["codes"])
        blob = json.dumps(r, ensure_ascii=False)
        self.assertNotIn("宏观中枢可以作为股市分析的上位状态机", blob)
        self.assertNotIn(str(self.flist.parent), blob)

    def test_error_code_registered(self):
        self.assertIn("E-FRAME-CONJECTURE", ERROR_CODES)


class RouteIsolation(unittest.TestCase):
    """量表不得被 route import/调用；调用前后 route 行为不变。"""

    def test_route_source_has_no_card_scale(self):
        src = Path(R.__file__).read_text(encoding="utf-8")
        self.assertNotIn("card_scale", src)
        tree = ast.parse(src)
        names = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                names += [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom):
                names.append(n.module or "")
                names += [a.name for a in n.names]
        self.assertTrue(all("card_scale" not in (x or "") for x in names))

    def test_score_does_not_change_route_diagnose(self):
        # 最小合法 selfcheck 结果 + draft，调用 card_scale 前后 _diagnose 一致
        now = __import__("datetime").datetime(2026, 1, 5, 1, 0, tzinfo=__import__("datetime").timezone.utc)
        sc = {
            "status": "PASS",
            "error_codes": [],
            "errors": [],
            "flags": {k: False for k in SC.FLAG_KEYS},
            "counts": {**{k: 0 for k in SC.COUNT_KEYS}, "errors": 0, "quotes": 1, "replayable": 1},
            "card_type": "daily",
            "date": DATE,
            "low_risk": False,
        }
        draft = {"draft_id": "daily-2026-01-05", "date": DATE,
                 "content_sha256": "a" * 64}
        state = {
            "schema_version": 1,
            "updated_at": "2026-01-05T00:00:00+08:00",
            "mac_heartbeat_at": "2026-01-05T00:50:00+08:00",
            "drafts": {},
        }
        records = {"codex": {}, "wang": {}}
        before = R._diagnose(sc, draft, state, records, now)
        # 调用量表（注入空清单目录 → 第5项 fail，但不准影响 route）
        flist = _write_frame_list(Path(tempfile.mkdtemp()) / "mi")
        CS.score_card("# x\n", sc, frame_list_path_override=flist)
        after = R._diagnose(sc, draft, state, records, now)
        self.assertEqual(before.state, after.state)
        self.assertEqual(before.codes, after.codes)
        self.assertEqual(before.publishable, after.publishable)

    def test_importing_card_scale_does_not_wire_into_route(self):
        # 重新加载后 route 模块命名空间仍无 card_scale
        importlib.reload(R)
        self.assertFalse(hasattr(R, "card_scale"))
        self.assertFalse(hasattr(R, "score_card"))
        self.assertFalse(hasattr(R, "score_file"))


class InternalDirAlignment(unittest.TestCase):
    def test_path_uses_internal_dir(self):
        with mock.patch.dict(os.environ, {"MARKJIN_INTERNAL_DIR": "/tmp/fake-internal-xyz"}):
            p = CS.frame_list_path()
            self.assertEqual(p, Path("/tmp/fake-internal-xyz") / "frame-conjecture.md")
            # 公开 API 文档字符串/返回值不得把真实本机路径写进评分结果
            r = CS.score_item_frame("x", None)
            self.assertNotIn("fake-internal", json.dumps(r))


if __name__ == "__main__":
    unittest.main()
