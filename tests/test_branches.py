import json, subprocess, tempfile, unittest
from pathlib import Path
import helpers  # noqa: F401
from markjin import branches as B

SHA = "a" * 64
RAWP = "raw/2026-10-20/src/X.csv"
RSHA = "d" * 64
LU = "2025Q1:1.5@2025-04-16#raw/2025-04-16/src/X.csv:" + "c" * 64 + "|https://example.org/series/X"
QR1 = f"2026Q3:1.2@2026-10-20#{RAWP}:{RSHA}"
QR2 = QR1 + f";2026Q4:1.3@2027-01-20#raw/2027-01-20/src/X.csv:{RSHA}"
EVID = f"{RAWP}:{RSHA}|scripts/calc.py@{'e' * 40}|2027-01-05T09:00:00+08:00"
DONE = dict(checked_by="审查与治理", checked_at="2027-01-05T10:00:00+08:00")
HDR = ",".join(B.HEADER) + "\n"
FIRST = "2026-10-13-macro-c1-b1-r1"


def row(**kw):
    base = dict.fromkeys(B.HEADER, "")
    base.update(row_id=FIRST, classification_id="c1", domain="macro", framework_commit="b" * 40, draft_id="2026-10-13-macro",
                slug="gdp-q3", publish_date="2026-10-13", framework_version="v2.4",
                framework_sha256=SHA, observed_variable="GDP", unit="%", data_source="SRC:X",
                data_vintage="每季取到期核对日（SGT）最新发布的版本", window_start="2026-10-14", window_end="2026-12-31",
                branch_order="1", interval_low="", interval_low_closed="false", interval_high="5",
                interval_high_closed="false", trigger_condition="x < 5", registered_by="生产与发布",
                registered_at="2026-10-13T07:00:00+08:00", check_result="PENDING")
    base.update(kw)
    return base


def quarterly(**kw):
    q = dict(interval_low="NA", interval_low_closed="NA", interval_high="NA", interval_high_closed="NA",
             n_quarters="2", window_quarters="2026Q3;2026Q4", window_end="2027-01-31", lu_basis_date="2026-10-01",
             l_value="1", u_value="2", lu_evidence=LU, trigger_condition="连续 2 季低于 L")
    q.update(kw)
    return row(**q)


def hit(**kw):
    return row(**{**dict(check_result="HIT", actual_branch="是", actual_value="4", evidence=EVID, **DONE), **kw})


def miss(**kw):
    return row(**{**dict(check_result="MISS", actual_branch="否", actual_value="6", evidence=EVID, **DONE), **kw})


def rid(r, seq):
    r = dict(r); r["row_id"] = B.expected_row_id(r["draft_id"], r["classification_id"], r["branch_order"], seq); return r


def chain(*rows):
    """按出现顺序自动编 row_id。"""
    seq, out = {}, []
    for r in rows:
        k = B.branch_key(r); seq[k] = seq.get(k, 0) + 1
        out.append(rid(r, seq[k]))
    return out


def csv_of(*rows):
    return HDR + "".join(",".join(r[f] for f in B.HEADER) + "\n" for r in rows)


def sibling(r):
    """测试用：为单支组补一条同组的互补分支（每组至少 2 支），紧跟在登记行之后。"""
    s = dict(r, branch_order="2", corrects_row_id="", reason="")
    if B.is_interval(r) and r["interval_high"]:
        s.update(interval_low=r["interval_high"], interval_low_closed="true" if r["interval_high_closed"] == "false" else "false",
                 interval_high="", interval_high_closed="false")
        s["trigger_condition"] = B.canonical_trigger(s)
    elif B.is_quarterly(r):
        s["trigger_condition"] = "连续 2 季高于 U"
    else:
        s["trigger_condition"] = "其他情形"
    s["row_id"] = B.expected_row_id(s["draft_id"], s["classification_id"], "2", 1)
    return s


def with_sibling(rows):
    rows = list(rows)
    if rows and len({B.branch_key(r) for r in rows if B.group_key(r) == B.group_key(rows[0])}) == 1:
        rows.insert(1, sibling(rows[0]))
    return rows


def codes(*rows, manifest=None):
    return [c for _, c in B.parse(csv_of(*with_sibling(rows)), manifest)[1]]


def ccodes(*rows, manifest=None):
    return codes(*chain(*rows), manifest=manifest)


class Basics(unittest.TestCase):
    def test_header_only_ok(self):
        repo_file = Path(__file__).resolve().parents[1] / B.LEDGER_PATH
        self.assertEqual(B.parse(repo_file.read_text(encoding="utf-8"))[1], [])

    def test_bad_header(self):
        self.assertEqual(B.parse("a,b\n")[1], [(1, "E-BR-HEADER")])

    def test_interval_ok(self):
        self.assertEqual(codes(row()), [])

    def test_quarterly_ok(self):
        self.assertEqual(codes(quarterly()), [])

    def test_n_l_u_wq(self):
        self.assertIn("E-BR-N", codes(quarterly(n_quarters="0")))
        self.assertIn("E-BR-L-GT-U", codes(quarterly(l_value="3", u_value="2")))
        self.assertIn("E-BR-WQ-COUNT", codes(quarterly(window_quarters="2026Q4")))
        self.assertIn("E-BR-WQ-GAP", codes(quarterly(window_quarters="2026Q2;2026Q4")))
        self.assertIn("E-BR-WQ-AFTER-END", codes(quarterly(window_quarters="2026Q4;2027Q1", window_end="2026-12-31")))
        self.assertIn("E-BR-INTERVAL-NA", codes(quarterly(interval_low="")))
        self.assertIn("E-BR-LU-EVIDENCE", codes(quarterly(lu_evidence="")))
        self.assertIn("E-BR-LU-EVIDENCE-FORMAT", codes(quarterly(lu_evidence=LU.split("|")[0])))

    def test_sha_dates_domain_commit(self):
        self.assertIn("E-BR-SHA256", codes(row(framework_sha256="abc")))
        self.assertIn("E-BR-DATE:window_end", codes(row(window_end="2026-02-30")))
        self.assertIn("E-BR-DOMAIN", codes(row(domain="crypto")))
        self.assertIn("E-BR-COMMIT", codes(row(framework_commit="abc")))
        self.assertIn("E-BR-EMPTY:framework_commit", codes(row(framework_commit="")))

    def test_non_macro_na(self):
        ai = row(domain="ai", draft_id="2026-10-13-daily", unit="NA", data_vintage="NA",
                 interval_low="NA", interval_low_closed="NA", interval_high="NA", interval_high_closed="NA",
                 n_quarters="NA", window_quarters="NA", lu_basis_date="NA", l_value="NA", u_value="NA",
                 lu_evidence="NA", quarter_readings="NA", trigger_condition="发布一手公告")
        self.assertEqual(codes(rid(ai, 1)), [])
        self.assertIn("E-BR-QUARTERLY-ONLY:l_value", codes(row(l_value="1")))

    def test_row_id_rule(self):
        self.assertIn("E-BR-ROW-ID", codes(row(row_id="x")))
        self.assertIn("E-BR-ROW-ID", codes(row(), row()))

    def test_pending_cannot_fill(self):
        for f in ("actual_value", "evidence", "checked_by"):
            self.assertIn("E-BR-PENDING-FILLED", codes(row(**{f: "x"})), f)

    def test_error_source(self):
        gap = row(branch_order="2", interval_low="7", interval_low_closed="true", interval_high="",
                  interval_high_closed="false", trigger_condition="7 <= x")
        ok = row(check_result="NONE_HIT", actual_branch="否", actual_value="6", error_source="采集;框架", evidence=EVID, **DONE)
        self.assertEqual(ccodes(row(), gap, ok), [])
        self.assertIn("E-BR-ERROR-SOURCE", ccodes(row(), gap, dict(ok, error_source="采集;采集")))
        self.assertIn("E-BR-ERROR-SOURCE", ccodes(row(), hit(error_source="采集")))


class R2Registration(unittest.TestCase):
    """r2 BLOCKER 2：registered_at 完整时间戳、等于 publish_date、严格早于观测开始（window_start 至少为发布次日）。"""

    def test_R1_registered_on_window_end_day(self):  # 反例 R1
        self.assertIn("E-BR-REGISTERED-AFTER-START", codes(row(registered_at="2026-12-31T23:59:00+08:00")))

    def test_R2_registered_after_window_start(self):  # 反例 R2
        c = codes(row(registered_at="2026-10-20T07:00:00+08:00"))
        self.assertIn("E-BR-REGISTERED-AFTER-START", c)
        self.assertIn("E-BR-REGISTERED-DATE", c)

    def test_registered_date_equals_publish(self):
        self.assertIn("E-BR-REGISTERED-DATE", codes(row(registered_at="2026-10-12T07:00:00+08:00")))

    def test_window_start_after_publish(self):
        self.assertIn("E-BR-WINDOW-START", codes(row(window_start="2026-10-13")))

    def test_full_timestamp(self):
        for bad in ("2026-10-13 07:00", "2026-10-13T07:00:00Z", "2026-10-13T25:00:00+08:00", "2026-10-13T07:00+08:00"):
            self.assertIn("E-BR-TS:registered_at", codes(row(registered_at=bad)), bad)

    def test_lu_basis_and_vintage_not_future(self):
        self.assertIn("E-BR-LU-BASIS-FUTURE", codes(quarterly(lu_basis_date="2026-10-14")))
        fut = LU.replace("@2025-04-16", "@2026-10-14")
        self.assertIn("E-BR-LU-VINTAGE-FUTURE", codes(quarterly(lu_evidence=fut)))


class R1Corrections(unittest.TestCase):
    """r2 BLOCKER 1：更正行不能在结果出来后改写预测。"""

    def test_C1_correct_after_hit_change_interval_then_miss(self):  # 反例 C1 / C1'
        corr = row(corrects_row_id="2026-10-13-macro-c1-b1-r2", reason="改区间", interval_high="7",
                   trigger_condition="x < 7", registered_at="2027-01-06T07:00:00+08:00")
        c = ccodes(row(), hit(), corr, miss(interval_high="7", trigger_condition="x < 7",
                                            registered_at="2027-01-06T07:00:00+08:00"))
        self.assertTrue({"E-BR-CORRECTS-TARGET", "E-BR-CORRECTION-AFTER-START", "E-BR-REGISTERED-AFTER-START"} & set(c), c)

    def test_C1pp_registered_at_copied(self):  # 反例 C1''：沿用原 registered_at 的事后更正
        corr = row(corrects_row_id=FIRST, reason="改区间", interval_high="7", trigger_condition="x < 7")
        c = ccodes(row(), miss(), corr, hit(interval_high="7", trigger_condition="x < 7"))
        self.assertIn("E-BR-CORRECTION-TIME", c)
        self.assertIn("E-BR-CORRECTION-AFTER-START", c)

    def test_C2_move_window_end_after_expiry(self):  # 反例 C2
        corr = row(corrects_row_id=FIRST, reason="延长", window_end="2027-03-31",
                   registered_at="2027-01-02T07:00:00+08:00")
        c = ccodes(row(), corr)
        self.assertIn("E-BR-CORRECTION-AFTER-START", c)

    def test_C3_unknown_id(self):  # 反例 C3
        self.assertIn("E-BR-CORRECTS-TARGET", ccodes(row(), row(corrects_row_id="nope", reason="x",
                                                                 registered_at="2026-10-13T08:00:00+08:00")))

    def test_C4_other_branch(self):  # 反例 C4
        other = row(branch_order="2", corrects_row_id=FIRST, reason="x", registered_at="2026-10-13T08:00:00+08:00")
        self.assertIn("E-BR-CORRECTS-TARGET", ccodes(row(), row(branch_order="2"), other))

    def test_C5_correction_as_first_row(self):  # 反例 C5
        self.assertIn("E-BR-FIRST-ROW", codes(row(corrects_row_id=FIRST, reason="x")))

    def test_C6_points_to_reconciliation_row(self):  # 反例 C6：登记更正指向对账行
        du = row(check_result="DATA_UNAVAILABLE", evidence="", **DONE)
        corr = row(corrects_row_id="2026-10-13-macro-c1-b1-r2", reason="x", registered_at="2026-10-13T08:00:00+08:00")
        self.assertIn("E-BR-CORRECTS-TARGET", ccodes(row(), du, corr))

    def test_C7_conclusion_correction_needs_final_target(self):  # 反例 C7：没有最终结论时不能做结论更正
        self.assertIn("E-BR-CORRECTS-TARGET", ccodes(row(), hit(corrects_row_id=FIRST, reason="x")))

    def test_C8_sha_change_post_hoc(self):  # 反例 C8
        corr = row(corrects_row_id="2026-10-13-macro-c1-b1-r2", reason="改校验码", framework_sha256="f" * 64,
                   check_result="MISS", actual_branch="否", actual_value="6", evidence=EVID, **DONE)
        self.assertIn("E-BR-PREREG-CHANGED", ccodes(row(), hit(), corr))

    def test_C9_gate_first_row(self):  # 反例 C9：门禁以第一行为准
        r1, r2 = row(), sibling(row())
        kw = dict(reason="x", window_end="2027-03-31", registered_at="2026-10-13T08:00:00+08:00")
        c1 = rid(dict(r1, corrects_row_id=r1["row_id"], **kw), 2)
        c2 = rid(dict(r2, corrects_row_id=r2["row_id"], **kw), 2)
        rows, errs = B.parse(csv_of(r1, r2, c1, c2))
        self.assertEqual(errs, [])
        self.assertEqual(B.gate_count(rows), 2)

    def test_registered_at_frozen_on_reconciliation(self):
        self.assertIn("E-BR-PREREG-CHANGED", ccodes(row(), hit(registered_at="2026-10-13T08:00:00+08:00")))

    def test_ok_registration_correction_before_start(self):
        corr = row(corrects_row_id=FIRST, reason="短名登记错", slug="gdp-q3-fixed",
                   registered_at="2026-10-13T09:00:00+08:00")
        self.assertEqual(ccodes(row(), corr, hit(slug="gdp-q3-fixed", registered_at="2026-10-13T09:00:00+08:00")), [])

    def test_ok_conclusion_correction_and_count(self):
        corr = miss(corrects_row_id="2026-10-13-macro-c1-b1-r2", reason="对账取错数据")
        rows, errs = B.parse(csv_of(*with_sibling(chain(row(), hit(), corr))))
        self.assertEqual(errs, [])
        self.assertEqual(B.conclusion_changes(rows), {("2026-10-13-macro", "c1", "1"): 1})
        # 第二次结论更正必须指向当前最终结论（第 3 行），指向第 2 行失败
        bad = hit(corrects_row_id="2026-10-13-macro-c1-b1-r2", reason="再改")
        self.assertIn("E-BR-CORRECTS-TARGET", ccodes(row(), hit(), corr, bad))
        good = hit(corrects_row_id="2026-10-13-macro-c1-b1-r3", reason="再改")
        self.assertEqual(ccodes(row(), hit(), corr, good), [])

    def test_hit_then_miss_without_correction(self):
        self.assertIn("E-BR-SECOND-FINAL", ccodes(row(), hit(), miss()))

    def test_checked_after_end(self):
        late = row(check_result="DATA_UNAVAILABLE", checked_by="审查与治理", checked_at="2026-12-31T23:00:00+08:00")
        self.assertIn("E-BR-CHECKED-BEFORE-END", ccodes(row(), late))


class R3R4Quarterly(unittest.TestCase):
    def rd(self, readings, at="2027-02-01T10:00:00+08:00"):
        return quarterly(quarter_readings=readings, checked_by="审查与治理", checked_at=at)

    def test_r1_5b_only_pending(self):  # 反例 r1-5b
        for cr in ("TRIGGER_UNOBSERVABLE", "DATA_UNAVAILABLE", "HIT"):
            self.assertIn("E-BR-QUARTERLY-RESULT", ccodes(quarterly(), quarterly(check_result=cr, **DONE)), cr)

    def test_Q4_readings_in_first_row(self):  # 反例 Q4
        self.assertIn("E-BR-FIRST-ROW", codes(self.rd(QR1)))

    def test_Q1_rewrite_reading(self):  # 反例 Q1
        self.assertIn("E-BR-READINGS-REWRITE", ccodes(quarterly(), self.rd(QR1), self.rd(QR1.replace(":1.2@", ":9.9@"))))

    def test_Q2_drop_reading(self):  # 反例 Q2
        self.assertIn("E-BR-READINGS-REWRITE", ccodes(quarterly(), self.rd(QR2), self.rd(QR1)))

    def test_Q3_missing_sha(self):  # 反例 Q3
        self.assertIn("E-BR-READINGS-FORMAT", codes(self.rd("2026Q3:1.2@2026-10-20#" + RAWP)))

    def test_append_ok(self):
        self.assertEqual(ccodes(quarterly(), self.rd(QR1), self.rd(QR2)), [])

    def test_traversal_and_bad_raw(self):
        for p in ("raw/../../private/file.csv", "raw/2026-10-20/../x.csv", "raw/not-a-date/x.csv", "raw/2026-10-20/"):
            r = QR1.replace(RAWP, p)
            self.assertIn("E-BR-READING-RAW-FORMAT", ccodes(quarterly(), self.rd(r)), p)

    def test_manifest_binding(self):
        man = {RAWP: RSHA, "raw/2025-04-16/src/X.csv": "c" * 64}.get
        self.assertEqual(ccodes(quarterly(), self.rd(QR1), manifest=man), [])
        self.assertIn("E-BR-READING-RAW-MANIFEST", ccodes(quarterly(), self.rd(QR1.replace(RSHA, "9" * 64)), manifest=man))

    def test_vintage_window(self):
        self.assertIn("E-BR-READING-VINTAGE-EARLY", ccodes(quarterly(), self.rd(QR1.replace("@2026-10-20", "@2026-09-30"))))
        self.assertIn("E-BR-READING-VINTAGE-LATE", ccodes(quarterly(), self.rd(QR1, at="2026-10-19T10:00:00+08:00")))

    def test_readings_order(self):
        self.assertIn("E-BR-READINGS-QUARTERS", ccodes(quarterly(), self.rd(QR1.replace("2026Q3", "2026Q4").replace("@2026-10-20", "@2027-01-20"))))

    def test_quarterly_no_error_source(self):
        self.assertIn("E-BR-QUARTERLY-ERROR-SOURCE", codes(quarterly(error_source="框架")))


class R6Evidence(unittest.TestCase):
    def test_actual_value_numeric(self):
        self.assertIn("E-BR-ACTUAL-VALUE", ccodes(row(), hit(actual_value="")))
        self.assertIn("E-BR-ACTUAL-VALUE", ccodes(row(), hit(actual_value="约 4")))

    def test_evidence_structured(self):  # 反例：evidence="e"
        self.assertIn("E-BR-EVIDENCE", ccodes(row(), hit(evidence="e")))
        self.assertIn("E-BR-EVIDENCE-RAW-FORMAT", ccodes(row(), hit(evidence=EVID.replace(RAWP, "raw/bad"))))
        self.assertIn("E-BR-EVIDENCE-RAW-MANIFEST", ccodes(row(), hit(), manifest={}.get))

    def test_r1_6c_trigger_mismatch(self):  # 反例 r1-6c
        self.assertIn("E-BR-TRIGGER-MISMATCH", codes(row(trigger_condition="x > 100")))
        self.assertNotIn("E-BR-TRIGGER-MISMATCH",
                         codes(row(interval_low="1", interval_low_closed="true", trigger_condition="1 <= x < 5")))
        self.assertIn("E-BR-TRIGGER-MISMATCH", codes(row(interval_high="", trigger_condition="x")))


class R5Cli(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.run_git = lambda *a: subprocess.run(["git", "-C", str(self.d), *a], check=True, capture_output=True)
        self.run_git("init", "-q"); self.run_git("config", "user.email", "t@t"); self.run_git("config", "user.name", "t")
        (self.d / "ledger").mkdir(); (self.d / B.LEDGER_PATH).write_text(csv_of(*with_sibling([row()])), encoding="utf-8")
        self.run_git("add", "."); self.run_git("commit", "-qm", "a")
        self.script = Path(__file__).resolve().parents[1] / "scripts/check-branches.py"

    def cli(self, *a):
        return subprocess.run(["python3", str(self.script), "--repo", str(self.d), *a], capture_output=True, text=True)

    def test_not_append_only(self):
        (self.d / B.LEDGER_PATH).write_text(csv_of(*with_sibling([row(slug="changed")])), encoding="utf-8")
        self.run_git("commit", "-qam", "b")
        p = self.cli("--base", "HEAD~1")
        self.assertEqual(p.returncode, 1); self.assertIn("E-BR-NOT-APPEND-ONLY", p.stdout)

    def test_unreadable_base_fails(self):  # 反例：--base 0000…0001 返回 PASS
        p = self.cli("--base", "0000000000000000000000000000000000000001")
        self.assertEqual(p.returncode, 1); self.assertIn("E-BR-BASE-UNREADABLE", p.stdout)

    def test_base_without_file_ok(self):
        self.run_git("rm", "-q", B.LEDGER_PATH); self.run_git("commit", "-qm", "rm")
        (self.d / "ledger").mkdir(exist_ok=True)
        (self.d / B.LEDGER_PATH).write_text(csv_of(*with_sibling([row()])), encoding="utf-8")
        self.run_git("add", "."); self.run_git("commit", "-qm", "re")
        self.assertEqual(self.cli("--base", "HEAD~1").returncode, 0)



class R7Public(unittest.TestCase):
    def test_check_public_rejects_local_path_in_ledger(self):
        d = Path(tempfile.mkdtemp())
        g = lambda *a: subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True)  # noqa: E731
        g("init", "-q"); g("config", "user.email", "t@t"); g("config", "user.name", "t")
        (d / "review/ledger").mkdir(parents=True); (d / "review/ledger/.gitkeep").write_text("")
        (d / "ledger").mkdir()
        (d / B.LEDGER_PATH).write_text(csv_of(row(observed_variable="见 " + "/" + "workspace" + "/notes.md")), encoding="utf-8")
        g("add", "."); g("commit", "-qm", "a")
        script = Path(__file__).resolve().parents[1] / "scripts/check-public.py"
        p = subprocess.run(["python3", str(script)], cwd=d, capture_output=True, text=True)
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr); self.assertIn("E-PUBLIC-LOCAL-PATH", p.stdout)


class Groups(unittest.TestCase):
    """site38-r2 HIGH：一篇日报多个完成分类的条目，按 (draft_id, classification_id) 分组判定。"""

    def b(self, cid, order, **kw):
        r = row(classification_id=cid, branch_order=order, **kw)
        if order == "2":
            r.update(interval_low="5", interval_low_closed="true", interval_high="", interval_high_closed="false",
                     trigger_condition="5 <= x")
        return r

    def test_two_items_each_one_hit(self):
        H = dict(check_result="HIT", actual_branch="是", actual_value="4", evidence=EVID, **DONE)
        M = dict(check_result="MISS", actual_branch="否", actual_value="4", evidence=EVID, **DONE)
        rows = [self.b("c1", "1"), self.b("c1", "2"), self.b("c2", "1"), self.b("c2", "2"),
                self.b("c1", "1", **H), self.b("c1", "2", **M), self.b("c2", "1", **H), self.b("c2", "2", **M)]
        self.assertEqual(ccodes(*rows), [])

    def test_two_hits_in_one_group(self):
        rows = [self.b("c1", "1"), self.b("c1", "2"),
                hit(classification_id="c1", branch_order="1"), hit(classification_id="c1", branch_order="2")]
        self.assertIn("E-BR-GROUP-RESULT", ccodes(*rows))

    def test_none_hit_mixed_with_miss(self):
        nh = dict(check_result="NONE_HIT", actual_branch="否", error_source="框架")
        rows = [self.b("c1", "1"), self.b("c1", "2"), miss(branch_order="1", **nh), miss(branch_order="2")]
        self.assertIn("E-BR-GROUP-RESULT", ccodes(*rows))

    def test_all_miss_incomplete_result(self):
        rows = [self.b("c1", "1"), self.b("c1", "2"), miss(branch_order="1"), miss(branch_order="2")]
        self.assertIn("E-BR-GROUP-RESULT", ccodes(*rows))

    def test_row_id_includes_classification(self):
        self.assertIn("E-BR-ROW-ID", codes(row(classification_id="c2")))
        self.assertIn("E-BR-CLASSIFICATION-ID", codes(row(classification_id="X1")))
        self.assertIn("E-BR-EMPTY:classification_id", codes(row(classification_id="")))


class R3Review(unittest.TestCase):
    """r3 反例（data20-r3/counterexamples.txt）。"""

    def b2(self, **kw):
        return row(**{**dict(branch_order="2", interval_low="5", interval_low_closed="true", interval_high="",
                             interval_high_closed="false", trigger_condition="5 <= x"), **kw})

    def test_N1_correction_moves_window_start_before_itself(self):
        corr = row(corrects_row_id=FIRST, reason="x", window_start="2026-10-14", registered_at="2026-10-14T01:00:00+08:00")
        self.assertIn("E-BR-REGISTERED-AFTER-START", ccodes(row(), self.b2(), corr))

    def test_N2_branch_added_after_observation(self):
        rows = chain(row(), miss(), self.b2(), self.b2(check_result="HIT", actual_branch="是", actual_value="6",
                                                       evidence=EVID, **DONE))
        self.assertIn("E-BR-GROUP-LATE", codes(*rows))

    def test_N2_added_in_later_commit_before_any_result(self):
        # 文本上紧跟在登记行后，但组在更早的提交里已登记：由逐提交检查拦截（见 R5Cli.test_group_late_commit）
        rows = chain(row(), row(classification_id="c2", row_id="x"), self.b2())
        self.assertIn("E-BR-GROUP-LATE", codes(*rows))

    def test_N3_N4_single_branch_group(self):
        for r in (miss(), miss(check_result="NONE_HIT", error_source="框架")):
            errs = [c for _, c in B.parse(csv_of(*chain(row(), r)))[1]]
            self.assertIn("E-BR-GROUP-SIZE", errs)

    def test_N5_group_different_windows(self):
        self.assertIn("E-BR-GROUP-MISMATCH", ccodes(row(), self.b2(window_end="2027-03-31")))
        for f, v in (("observed_variable", "CPI"), ("unit", "pp"), ("data_source", "SRC:Y"), ("data_vintage", "首发值"),
                     ("window_start", "2026-10-15"), ("registered_at", "2026-10-14T07:00:00+08:00")):
            self.assertIn("E-BR-GROUP-MISMATCH" if f != "registered_at" else "E-BR-REGISTERED-DATE",
                          ccodes(row(), self.b2(**{f: v})), f)

    def warn(self, *rows):
        rows_, errs = B.parse(csv_of(*chain(*rows)))
        return errs, B.partition_warnings(rows_)

    def test_N6_overlap_is_warning(self):  # r4：不再拦登记，改为提示
        errs, w = self.warn(row(interval_high="6", trigger_condition="x < 6"), self.b2())
        self.assertEqual(errs, []); self.assertEqual(list(w.values()), ["W-BR-GROUP-OVERLAP"])

    def test_N7_gap_is_warning(self):
        errs, w = self.warn(row(), self.b2(interval_low_closed="false", trigger_condition="5 < x"))
        self.assertEqual(errs, []); self.assertEqual(list(w.values()), ["W-BR-GROUP-GAP"])
        self.assertEqual(self.warn(row(), self.b2())[1], {})

    def test_hit_outside_interval(self):  # r2-6：区间外宣称 HIT
        self.assertIn("E-BR-ACTUAL-MISMATCH", ccodes(row(), self.b2(), hit(actual_value="6")))
        self.assertIn("E-BR-ACTUAL-MISMATCH", ccodes(row(), self.b2(), miss(actual_value="4")))
        self.assertIn("E-BR-ACTUAL-MISMATCH", ccodes(row(), self.b2(), hit(actual_value="5")))  # 开端点

    def test_M3_readings_not_longer(self):
        rd = lambda r, at: quarterly(quarter_readings=r, checked_by="审查与治理", checked_at=at)  # noqa: E731
        self.assertIn("E-BR-READINGS-NOT-LONGER", ccodes(quarterly(), rd(QR1, "2027-02-01T10:00:00+08:00"),
                                                          rd(QR1, "2027-02-02T10:00:00+08:00")))

    def test_private_text(self):
        for v in ("见 /opt/private/x", "markjin-internal/framework.md", "file:x", "~/notes"):
            self.assertIn("E-BR-PRIVATE-TEXT:observed_variable", codes(row(observed_variable=v)), v)
        self.assertEqual(codes(row(unit="km/s")), [])

    def test_stats(self):
        rows, errs = B.parse(csv_of(*chain(row(), self.b2(), hit(), self.b2(check_result="MISS", actual_branch="否",
                                                                              actual_value="4", evidence=EVID, **DONE))))
        self.assertEqual(errs, [])
        st = B.hit_stats(rows)
        self.assertEqual((st["groups"], st["groups_judged"], st["groups_correct"], st["branches"]), (1, 1, 1, 2))


class R3Cli(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.g = lambda *a: subprocess.run(["git", "-C", str(self.d), *a], check=True, capture_output=True)  # noqa: E731
        self.g("init", "-q"); self.g("config", "user.email", "t@t"); self.g("config", "user.name", "t")
        (self.d / "ledger").mkdir()
        self.commit(HDR, "base")
        self.script = Path(__file__).resolve().parents[1] / "scripts/check-branches.py"

    def commit(self, text, msg):
        (self.d / B.LEDGER_PATH).write_text(text, encoding="utf-8"); self.g("add", "."); self.g("commit", "-qm", msg)

    def cli(self, *a):
        return subprocess.run(["python3", str(self.script), "--repo", str(self.d), *a], capture_output=True, text=True)

    def test_rewrite_inside_pr_caught_per_commit(self):  # H：同一 PR 内 A 新增、B 改写
        r1, r2 = row(), sibling(row())
        self.commit(csv_of(r1, r2), "A")
        self.commit(csv_of(dict(r1, interval_high="6", trigger_condition="x < 6"), dict(r2, interval_low="6",
                    trigger_condition="6 <= x")), "B")
        p = self.cli("--base", "HEAD~2")
        self.assertEqual(p.returncode, 1); self.assertIn("E-BR-NOT-APPEND-ONLY", p.stdout)

    def test_header_change_allowed_only_when_empty(self):
        self.commit("row_id,old\n", "old header")
        self.commit(HDR, "new header")
        self.assertEqual(self.cli("--base", "HEAD~2").returncode, 0)
        self.commit(csv_of(row(), sibling(row())), "rows")
        self.commit(csv_of(row(), sibling(row())).replace("row_id,", "rowid,", 1), "change header with rows")
        self.assertIn("E-BR-NOT-APPEND-ONLY", self.cli("--base", "HEAD~1").stdout)

    def test_group_late_commit(self):
        r1, r2 = row(), sibling(row())
        self.commit(csv_of(r1), "A")
        self.commit(csv_of(r1, r2), "B")
        p = self.cli("--base", "HEAD~2")
        self.assertIn("E-BR-GROUP-LATE", p.stdout)

    def test_push_time(self):
        self.commit(csv_of(row(), sibling(row())), "A")
        ok = self.cli("--base", "HEAD~1", "--now", "2026-10-13T09:00:00+08:00")
        self.assertEqual(ok.returncode, 0, ok.stdout)
        late = self.cli("--base", "HEAD~1", "--now", "2026-10-13T14:00:00+08:00")
        self.assertIn("E-BR-PUSH-SKEW", late.stdout)
        after = self.cli("--base", "HEAD~1", "--now", "2026-10-14T00:30:00+08:00")
        self.assertIn("E-BR-PUSH-AFTER-START", after.stdout)

    def commit_at(self, text, msg, when):
        import os
        (self.d / B.LEDGER_PATH).write_text(text, encoding="utf-8"); self.g("add", ".")
        subprocess.run(["git", "-C", str(self.d), "commit", "-qm", msg], check=True, capture_output=True,
                       env={**os.environ, "GIT_COMMITTER_DATE": when, "GIT_AUTHOR_DATE": when})

    def voids(self):
        r1, r2 = row(), sibling(row())
        v = lambda r: rid(dict(r, check_result="VOID", corrects_row_id=r["row_id"], reason="合并晚于观测开始"), 2)  # noqa: E731
        return r1, r2, v(r1), v(r2)

    def test_void_split_across_commits(self):
        r1, r2, v1, v2 = self.voids()
        self.commit_at(csv_of(r1, r2), "late merge", "2026-10-14T09:00:00+08:00")
        self.commit(csv_of(r1, r2, v1), "void b1")
        self.commit(csv_of(r1, r2, v1, v2), "void b2")
        self.assertIn("E-BR-VOID-SPLIT", self.cli("--base", "HEAD~2", "--main-ref", "HEAD").stdout)

    def test_non_fast_forward_push(self):  # MEDIUM 2
        self.commit(csv_of(row(), sibling(row())), "A")
        old = subprocess.run(["git", "-C", str(self.d), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        self.g("reset", "-q", "--hard", "HEAD~1")
        self.commit(csv_of(row(slug="other"), sibling(row(slug="other"))), "rewrite")
        p = self.cli("--base", old)
        self.assertEqual(p.returncode, 1); self.assertIn("E-BR-NOT-FAST-FORWARD", p.stdout)


class R4Review(unittest.TestCase):
    """r4 反例（data20-r4/counterexamples.txt）。"""

    def b2(self, **kw):
        return row(**{**dict(branch_order="2", interval_low="5", interval_low_closed="true", interval_high="",
                             interval_high_closed="false", trigger_condition="5 <= x"), **kw})

    def fin(self, r, res, v, **kw):
        return dict(r, **{**dict(check_result=res, actual_branch="是" if res in ("HIT", "MULTI_HIT") else ("" if res == "TRIGGER_UNOBSERVABLE" else "否"),
                                 actual_value=v, evidence=EVID, **DONE), **kw})

    def two(self, res1, v1, res2, v2, b1=None, b2=None, **kw2):
        b1 = b1 or row(); b2 = b2 or self.b2()
        return ccodes(b1, b2, self.fin(b1, res1, v1), self.fin(b2, res2, v2, **kw2))

    def test_Z1_none_hit_with_different_values(self):
        self.assertIn("E-BR-GROUP-OBSERVATION", self.two("NONE_HIT", "6", "NONE_HIT", "4"))
        # 同一取值也不行：6 落在第二支里，应是 MISS/HIT
        self.assertIn("E-BR-GROUP-RESULT", self.two("NONE_HIT", "6", "NONE_HIT", "6"))
        self.assertIn("E-BR-GROUP-OBSERVATION", self.two("MULTI_HIT", "4", "MULTI_HIT", "6"))

    def test_Z2_hit_and_miss_with_different_values(self):
        self.assertIn("E-BR-GROUP-OBSERVATION", self.two("HIT", "4", "MISS", "3"))
        self.assertIn("E-BR-GROUP-OBSERVATION",
                      self.two("HIT", "4", "MISS", "4", evidence=EVID.replace("09:00", "09:01")))
        self.assertEqual(self.two("HIT", "4", "MISS", "4"), [])

    def test_none_hit_and_multi_hit_possible(self):
        gap = self.b2(interval_low="7", trigger_condition="7 <= x")
        self.assertEqual(self.two("NONE_HIT", "6", "NONE_HIT", "6", b2=gap), [])
        b1 = row(interval_high="6", trigger_condition="x < 6")
        self.assertEqual(self.two("MULTI_HIT", "5.5", "MULTI_HIT", "5.5", b1=b1), [])
        self.assertIn("E-BR-GROUP-RESULT", self.two("HIT", "5.5", "MISS", "5.5", b1=b1))

    def test_Z3_decimal_long_and_endpoints(self):
        r = row(interval_high="1.000000000000000001", interval_high_closed="true")
        r["trigger_condition"] = B.canonical_trigger(r)
        self.assertIn("E-BR-ACTUAL-MISMATCH", B.check_row(self.fin(r, "HIT", "1.000000000000000002")))
        self.assertNotIn("E-BR-ACTUAL-MISMATCH", B.check_row(self.fin(r, "HIT", "1.000000000000000001")))
        self.assertNotIn("E-BR-ACTUAL-MISMATCH", B.check_row(self.fin(r, "MISS", "1.000000000000000002")))
        # 端点 5：x < 5 不含 5，5 <= x 含 5
        self.assertIn("E-BR-ACTUAL-MISMATCH", B.check_row(self.fin(row(), "HIT", "5")))
        self.assertEqual(self.two("MISS", "5", "HIT", "5"), [])
        self.assertIn("E-BR-GROUP-RESULT", self.two("HIT", "4.9999999999999999999", "MISS", "4.9999999999999999999",
                                                    b2=self.b2(interval_low="4.9999999999999999999",
                                                               trigger_condition="4.9999999999999999999 <= x")))

    def test_Z4_quarterly_private_unit(self):
        self.assertIn("E-BR-PRIVATE-TEXT:unit", B.check_row(quarterly(unit="/opt/private/x")))

    def test_Z5_quarterly_correction_without_reason(self):
        self.assertIn("E-BR-CORRECTION-REASON", B.check_row(quarterly(corrects_row_id=FIRST, reason="")))
        self.assertIn("E-BR-CORRECTION-REASON", B.check_row(quarterly(corrects_row_id=FIRST, reason="  ")))

    def test_Y1_units_and_paths(self):
        for u in ("/年", "亿元 /年", "bp /月", "x /5", "美元/桶", "%/年", "人/km2", "1/2", "/kg"):
            self.assertFalse(B.private_text("unit", u), u)
        for v in ("/年", "亿元 /年", "bp /月", "x /5", "https://example.org/series/X", "SRC:GDP/CPI", "见 / 年"):
            self.assertFalse(B.private_text("data_source", v), v)
        ws = "/work" + "space/a"
        for v in ("/opt/private/x", "a:/opt/private/x", "markjin-internal/f", "C:\\x", "~/a", "file:///x", ws,
                  "见 https://x.org 和 /srv/data"):
            self.assertTrue(B.private_text("data_source", v), v)
        for v in ("/opt/private/x", "a:/opt/private/x", ws, "file:///x"):
            self.assertTrue(B.private_text("unit", v), v)

    def void(self, **kw):
        return row(**{**dict(check_result="VOID", corrects_row_id=FIRST, reason="main 上合并晚于 window_start"), **kw})

    def void2(self, **kw):
        return self.b2(**{**dict(check_result="VOID", corrects_row_id="2026-10-13-macro-c1-b2-r1",
                                 reason="main 上合并晚于 window_start"), **kw})

    def test_void_whole_group(self):
        rs, errs = B.parse(csv_of(*chain(row(), self.b2(), self.void(), self.void2())))
        self.assertEqual(errs, [])
        # r6：VOID 只留痕，不决定排除；排除只看可信时间算出的晚合并组
        self.assertEqual(B.gate_count(rs), 2)
        g = {B.group_key(row())}
        self.assertEqual(B.gate_count(rs, excluded=g), 0)
        self.assertEqual(B.hit_stats(rs, g)["excluded_late_groups"], 1)
        self.assertEqual(B.complete_void_groups(rs), g)
        self.assertIn("E-BR-AFTER-VOID", ccodes(row(), self.b2(), self.void(), self.void2(), hit()))
        self.assertIn("E-BR-CORRECTION-REASON", ccodes(row(), self.b2(), self.void(reason=""), self.void2()))
        self.assertIn("E-BR-CORRECTS-TARGET", ccodes(row(), self.b2(), self.void(corrects_row_id="x"), self.void2()))
        self.assertIn("E-BR-VOID-FILLED", ccodes(row(), self.b2(), self.void(actual_value="4"), self.void2()))
        self.assertIn("E-BR-PREREG-CHANGED", ccodes(row(), self.b2(), self.void(unit="bp"), self.void2()))

    def test_void_checked_fields(self):  # r5 MEDIUM 2
        self.assertIn("E-BR-VOID-FILLED", ccodes(row(), self.b2(), self.void(checked_by="审查与治理"), self.void2()))
        self.assertIn("E-BR-VOID-FILLED", ccodes(row(), self.b2(), self.void(checked_at=DONE["checked_at"]), self.void2()))

    def test_V3_single_branch_void(self):  # 只作废一支：报错；门禁按整组排除
        c = ccodes(row(), self.b2(), self.void())
        self.assertIn("E-BR-VOID-PARTIAL", c)
        rs, _ = B.parse(csv_of(*chain(row(), self.b2(), self.void())))
        self.assertEqual(B.gate_count(rs), 2)          # r6 反例 V3：无效 VOID 不得改变统计
        self.assertEqual(B.complete_void_groups(rs), set())

    def test_void_revoked(self):
        v1 = rid(self.void(), 2)
        rev = self.void(check_result="VOID_REVOKED", corrects_row_id=v1["row_id"], reason="误作废")
        rows = chain(row(), self.b2(), self.void(), rev)
        rs, errs = B.parse(csv_of(*rows))
        self.assertEqual(errs, [])                      # 撤销后不再报 VOID-PARTIAL
        self.assertEqual(B.active_voids(rs), [])
        self.assertIn("E-BR-CORRECTION-REASON", ccodes(row(), self.b2(), self.void(), dict(rev, reason="")))
        self.assertIn("E-BR-CORRECTS-TARGET", ccodes(row(), self.b2(), self.void(), dict(rev, corrects_row_id=FIRST)))
        self.assertIn("E-BR-CORRECTS-TARGET", ccodes(row(), self.b2(), self.void(), rev, rev))
        self.assertIn("E-BR-VOID-FILLED", ccodes(row(), self.b2(), self.void(), dict(rev, checked_by="x")))
        # 撤销后可以继续正常对账
        self.assertEqual(ccodes(row(), self.b2(), self.void(), rev, hit(), self.fin(self.b2(), "MISS", "4")), [])

    def test_T1_trigger_unobservable_with_value(self):
        self.assertIn("E-BR-TU-VALUE", self.two("TRIGGER_UNOBSERVABLE", "4", "TRIGGER_UNOBSERVABLE", "4",
                                                 actual_branch=""))
        tu = lambda r: dict(r, check_result="TRIGGER_UNOBSERVABLE", actual_branch="", actual_value="", evidence=EVID, **DONE)  # noqa: E731
        self.assertEqual(ccodes(row(), self.b2(), tu(row()), tu(self.b2())), [])

    def test_paths_r5(self):
        for v in ("见/opt/private/x", "中文/opt/x", "https://x.org|/opt/private/x", "https://x.org,/srv/a"):
            self.assertTrue(B.private_text("data_source", v), v)
            self.assertTrue(B.private_text("unit", v), v)
        self.assertTrue(B.private_text("unit", "/data/private/report"))
        for root in ("opt", "home", "workspace", "Users", "var", "etc", "tmp", "root", "private", "mnt", "srv", "usr",
                     "Volumes", "Library"):
            for v in (f"见/{root}", f"详见/{root}。", f"见/{root} 下", f"见/{root}中", f"见/{root}/x"):
                self.assertTrue(B.private_text("data_source", v), v)
                self.assertTrue(B.private_text("unit", v), v)
        for v in ("见/optimal", "/年", "亿元 /年", "亿元/年", "人/km2", "美元/桶", "bp /月", "x /5"):
            self.assertFalse(B.private_text("unit", v), v)
            self.assertFalse(B.private_text("data_source", v), v)
        self.assertFalse(B.private_text("data_source", "https://example.org/series/X|SRC:X"))

class R6Trust(unittest.TestCase):
    """r6：可信合并时间 = 这组行首次进入 main 的那次 push 运行的 created_at（反例 B、C、D、E、V3、V7）。"""

    def setUp(self):
        import os
        self.os = os
        self.d = Path(tempfile.mkdtemp())
        self.g = lambda *a: subprocess.run(["git", "-C", str(self.d), *a], check=True, capture_output=True, text=True)  # noqa: E731
        self.g("init", "-q", "-b", "main"); self.g("config", "user.email", "t@t"); self.g("config", "user.name", "t")
        (self.d / "ledger").mkdir()
        self.commit(HDR, "base", "2026-10-01T00:00:00+08:00")
        self.script = Path(__file__).resolve().parents[1] / "scripts/check-branches.py"
        self.runs = []

    def commit(self, text, msg, when="2026-10-13T07:30:00+08:00"):
        (self.d / B.LEDGER_PATH).write_text(text, encoding="utf-8"); self.g("add", ".")
        subprocess.run(["git", "-C", str(self.d), "commit", "-qm", msg], check=True, capture_output=True,
                       env={**self.os.environ, "GIT_COMMITTER_DATE": when, "GIT_AUTHOR_DATE": when})
        return self.g("rev-parse", "HEAD").stdout.strip()

    def push(self, sha, created_at, run_id):
        self.runs.append({"id": run_id, "head_sha": sha, "created_at": created_at})

    def cli(self, runs=True, main_ref="HEAD"):
        a = ["--main-ref", main_ref, "--count-gate", "--stats"]
        if runs:
            f = self.d / "runs.json"; f.write_text(json.dumps(self.runs)); a += ["--push-runs", str(f)]
        return subprocess.run(["python3", str(self.script), "--repo", str(self.d), *a], capture_output=True, text=True)

    def grp(self):
        r1, r2 = row(), sibling(row())
        v = lambda r, reason: rid(dict(r, check_result="VOID", corrects_row_id=r["row_id"], reason=reason), 2)  # noqa: E731
        return r1, r2, v

    def test_C_old_commit_pushed_late(self):  # 旧提交（10-13）10-15 才推上 main：按 push 运行时间判晚合并
        r1, r2, v = self.grp()
        c = self.commit(csv_of(r1, r2), "old")
        self.push(c, "2026-10-15T01:00:00Z", 901)
        p = self.cli()
        # r8：时间相关只给警告、不让 main 一直红；晚合并组自动排除
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertIn("W-BR-LATE-UNHANDLED", p.stdout); self.assertIn("gate_count 0", p.stdout)
        (self.d / "x.txt").write_text("x"); self.g("add", "."); self.g("commit", "-qm", "unrelated")
        self.assertIn("W-BR-LATE-UNHANDLED", self.cli().stdout)
        # 整组 VOID 留痕（reason 写运行 ID）后恢复通过，组被自动排除
        c3 = self.commit(csv_of(r1, r2, v(r1, "晚合并 run:901"), v(r2, "晚合并 run:901")), "void", "2026-10-16T00:00:00+08:00")
        self.push(c3, "2026-10-16T01:00:00Z", 902)
        ok = self.cli()
        self.assertEqual(ok.returncode, 0, ok.stdout)
        self.assertIn("gate_count 0", ok.stdout); self.assertIn('"excluded_late_groups": 1', ok.stdout)

    def test_void_reason_must_cite_run(self):
        r1, r2, v = self.grp()
        c = self.commit(csv_of(r1, r2), "old"); self.push(c, "2026-10-15T01:00:00Z", 901)
        self.commit(csv_of(r1, r2, v(r1, "晚合并 run:900"), v(r2, "晚合并 run:900")), "void")
        self.assertIn("E-BR-VOID-UNVERIFIED", self.cli().stdout)

    def test_E_future_committer_date_pushed_in_time(self):  # 按时推送、提交时间伪造到未来：不能作废
        r1, r2, v = self.grp()
        c = self.commit(csv_of(r1, r2), "future", "2027-01-05T00:00:00+08:00")
        self.push(c, "2026-10-13T00:00:00Z", 801)
        ok = self.cli()
        self.assertEqual(ok.returncode, 0, ok.stdout); self.assertIn("gate_count 2", ok.stdout)
        self.commit(csv_of(r1, r2, v(r1, "x run:801"), v(r2, "x run:801")), "void", "2027-01-06T00:00:00+08:00")
        p = self.cli()
        self.assertIn("E-BR-VOID-UNVERIFIED", p.stdout); self.assertIn("gate_count INVALID", p.stdout)

    def test_D_V7_late_group_excluded_automatically(self):  # 晚合并组不靠作者 VOID，自动排除；结果已知后挑着作废无效
        r1, r2, v = self.grp()
        c = self.commit(csv_of(r1, r2), "late"); self.push(c, "2026-10-14T03:00:00Z", 701)
        rs, _ = B.parse(csv_of(r1, r2))
        import importlib.util
        spec = importlib.util.spec_from_file_location("cb", self.script); cb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cb)
        errs, warns, late, valid = cb.trust_check(str(self.d), rs, "HEAD", cb.load_runs(self._runs_file()))
        self.assertTrue(valid)
        self.assertEqual(late, {B.group_key(r1)})
        self.assertEqual(B.gate_count(rs, excluded=late), 0)
        # V7：按时合并的组在结果已知后（2027-06）作废 → 无效，统计不变
        d2 = R6Trust("test_C_old_commit_pushed_late"); d2.setUp()
        c = d2.commit(csv_of(r1, r2), "in time"); d2.push(c, "2026-10-13T00:00:00Z", 702)
        d2.commit(csv_of(r1, r2, v(r1, "x run:702"), v(r2, "x run:702")), "void", "2027-06-01T00:00:00+08:00")
        p = d2.cli()
        self.assertIn("E-BR-VOID-UNVERIFIED", p.stdout); self.assertIn("gate_count INVALID", p.stdout)

    def _runs_file(self):
        f = self.d / "runs.json"; f.write_text(json.dumps(self.runs)); return str(f)

    def test_B_invalid_void_then_revoked(self):  # 无效 VOID 不改变统计；撤销后恢复通过
        r1, r2, v = self.grp()
        c = self.commit(csv_of(r1, r2), "in time"); self.push(c, "2026-10-13T00:00:00Z", 601)
        v1 = v(r1, "x run:601")
        self.commit(csv_of(r1, r2, v1), "single void")
        self.assertIn("gate_count INVALID", self.cli().stdout)
        rev = rid(dict(r1, check_result="VOID_REVOKED", corrects_row_id=v1["row_id"], reason="误作废"), 3)
        self.commit(csv_of(r1, r2, v1, rev), "revoke")
        ok = self.cli()
        self.assertEqual(ok.returncode, 0, ok.stdout); self.assertIn("gate_count 2", ok.stdout)

    def test_strict_when_times_unavailable(self):
        r1, r2, _ = self.grp()
        c = self.commit(csv_of(r1, r2), "x")
        p = self.cli(runs=False)
        self.assertIn("W-BR-PUSH-TIME-UNAVAILABLE", p.stdout); self.assertIn("gate_count INVALID", p.stdout)
        (self.d / "bad.json").write_text("{")
        p = subprocess.run(["python3", str(self.script), "--repo", str(self.d), "--main-ref", "HEAD", "--count-gate",
                            "--push-runs", str(self.d / "bad.json")], capture_output=True, text=True)
        self.assertIn("W-BR-PUSH-TIME-UNAVAILABLE", p.stdout); self.assertIn("gate_count INVALID", p.stdout)
        self.push("f" * 40, "2026-10-13T00:00:00Z", 1)   # 有运行列表但找不到这次 push
        p = self.cli()
        self.assertIn("W-BR-PUSH-TIME-UNKNOWN", p.stdout); self.assertIn("gate_count INVALID", p.stdout)
        self.assertIsNotNone(c)

    def test_multi_commit_push_uses_descendant_run(self):
        r1, r2, _ = self.grp()
        self.commit(csv_of(r1, r2), "rows")
        (self.d / "x.txt").write_text("x"); self.g("add", "."); self.g("commit", "-qm", "later")
        head = self.g("rev-parse", "HEAD").stdout.strip()
        self.push(head, "2026-10-13T00:10:00Z", 501)
        # r8：只认 head_sha 恰为该提交的运行；一次推多个提交时判“时间未知”，计数 INVALID，不顺延
        p = self.cli()
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertIn("W-BR-PUSH-TIME-UNKNOWN", p.stdout); self.assertIn("gate_count INVALID", p.stdout)

    def test_not_on_main_yet(self):  # PR 阶段：组还没进 main，不做合并时间判定
        r1, r2, _ = self.grp()
        base = self.g("rev-parse", "HEAD").stdout.strip()
        self.push(base, "2026-10-01T00:00:00Z", 100)   # r9：须有运行记录，计数才有效
        self.commit(csv_of(r1, r2), "pr rows")
        p = self.cli(main_ref="HEAD~1")
        self.assertEqual(p.returncode, 0, p.stdout); self.assertIn("gate_count 2", p.stdout)
        self.assertNotIn("W-BR-PUSH-TIME-UNKNOWN", p.stdout)


class R7Review(R6Trust):
    """r7 反例：R1、R2、B2、R4、R5、run:<id> 精确匹配。"""

    def test_R1_first_run_missing_later_run_present(self):
        r1, r2, v = self.grp()
        c = self.commit(csv_of(r1, r2), "in time")   # 首次运行（10-13）已过期，只剩观测开始后的运行
        (self.d / "x.txt").write_text("x"); self.g("add", "."); self.g("commit", "-qm", "later")
        later = self.g("rev-parse", "HEAD").stdout.strip()
        self.push(later, "2026-10-15T01:00:00Z", 999)
        p = self.cli()
        self.assertNotIn("LATE-UNHANDLED", p.stdout); self.assertIn("gate_count INVALID", p.stdout)
        self.commit(csv_of(r1, r2, v(r1, "late run:999"), v(r2, "late run:999")), "void")
        p = self.cli()
        self.assertNotIn("gate_count 0", p.stdout); self.assertIn("gate_count INVALID", p.stdout)
        self.assertIsNotNone(c)

    def test_R2_empty_run_list(self):
        r1, r2, v = self.grp()
        self.commit(csv_of(r1, r2), "x")
        self.commit(csv_of(r1, r2, v(r1, "run:1"), v(r2, "run:1")), "void")
        p = self.cli()   # 空列表
        self.assertIn("gate_count INVALID", p.stdout); self.assertIn("stats INVALID", p.stdout)

    def test_B2_correction_pushed_after_start(self):  # 登记按时，观测开始后直推一条回填 registered_at 的登记更正
        r1, r2, _ = self.grp()
        c = self.commit(csv_of(r1, r2), "in time"); self.push(c, "2026-10-13T00:00:00Z", 1)
        corr = rid(dict(r1, corrects_row_id=r1["row_id"], reason="改条件", interval_high="4.5",
                        trigger_condition="x < 4.5", registered_at="2026-10-13T09:00:00+08:00"), 2)
        corr2 = rid(dict(r2, corrects_row_id=r2["row_id"], reason="改条件", interval_low="4.5",
                         trigger_condition="4.5 <= x", registered_at="2026-10-13T09:00:00+08:00"), 2)
        c2 = self.commit(csv_of(r1, r2, corr, corr2), "late corr"); self.push(c2, "2026-10-14T05:00:00Z", 2)
        p = self.cli()
        self.assertIn("W-BR-LATE-UNHANDLED", p.stdout); self.assertIn("gate_count 0", p.stdout)

    def test_R4_no_main_ref(self):
        r1, r2, _ = self.grp()
        c = self.commit(csv_of(r1, r2), "late"); self.push(c, "2026-10-15T00:00:00Z", 1)
        p = subprocess.run(["python3", str(self.script), "--repo", str(self.d), "--count-gate", "--stats"],
                           capture_output=True, text=True)
        self.assertIn("gate_count INVALID", p.stdout); self.assertIn("stats INVALID", p.stdout)

    def test_R5_bad_main_ref(self):
        p = self.cli(main_ref="no-such-ref")
        self.assertEqual(p.returncode, 1); self.assertIn("E-BR-MAIN-REF", p.stdout)

    def test_run_id_exact(self):
        r1, r2, v = self.grp()
        c = self.commit(csv_of(r1, r2), "old"); self.push(c, "2026-10-15T01:00:00Z", 901)
        self.commit(csv_of(r1, r2, v(r1, "晚合并 run:9010"), v(r2, "晚合并 run:9010")), "void")
        self.assertIn("E-BR-VOID-UNVERIFIED", self.cli().stdout)
        import importlib.util
        spec = importlib.util.spec_from_file_location("cb", self.script); cb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cb)
        self.assertEqual(cb.run_ids("x run:901。"), {"901"})
        self.assertEqual(cb.run_ids("x run:9010"), {"9010"})
        self.assertEqual(cb.run_ids("xrun:901"), set())


def cb_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("cb", Path(__file__).resolve().parents[1] / "scripts/check-branches.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


class R8VoidWarnOnly(R6Trust):
    """r8：自动排除和 VOID 相关的问题一律只警告，不改退出码，计数 INVALID（main 与 PR 一样）。"""

    def assert_warn(self, p, code):
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertRegex(p.stdout, r"warn line \S+: " + code)
        self.assertIn("gate_count INVALID", p.stdout); self.assertIn("stats INVALID", p.stdout)

    def test_void_unverified_main_is_warn(self):
        r1, r2, v = self.grp()
        c = self.commit(csv_of(r1, r2), "in time"); self.push(c, "2026-10-13T00:00:00Z", 11)
        self.commit(csv_of(r1, r2, v(r1, "x run:11"), v(r2, "x run:11")), "void")
        self.assert_warn(self.cli(), "E-BR-VOID-UNVERIFIED")

    def test_void_partial_is_warn(self):
        r1, r2, v = self.grp()
        c = self.commit(csv_of(r1, r2), "in time"); self.push(c, "2026-10-13T00:00:00Z", 12)
        self.commit(csv_of(r1, r2, v(r1, "x run:12")), "single void")
        self.assert_warn(self.cli(), "E-BR-VOID-PARTIAL")

    def test_void_split_and_after_void_on_pr_is_warn(self):
        r1, r2, v = self.grp()
        c = self.commit(csv_of(r1, r2), "late"); self.push(c, "2026-10-15T00:00:00Z", 13)
        v1, v2 = v(r1, "x run:13"), v(r2, "x run:13")
        self.commit(csv_of(r1, r2, v1), "void b1")
        self.commit(csv_of(r1, r2, v1, v2), "void b2")
        f = self.d / "runs.json"; f.write_text(json.dumps(self.runs))
        p = subprocess.run(["python3", str(self.script), "--repo", str(self.d), "--base", "HEAD~2", "--main-ref", "HEAD~2",
                            "--push-runs", str(f), "--now", "2026-10-15T09:00:00+08:00", "--count-gate", "--stats"],
                           capture_output=True, text=True)
        self.assert_warn(p, "E-BR-VOID-SPLIT")
        self.assertIn("E-BR-AFTER-VOID", cb_module().VOID_CODES)

    def test_void_filled_is_warn(self):
        r1, r2, v = self.grp()
        c = self.commit(csv_of(r1, r2), "late"); self.push(c, "2026-10-15T00:00:00Z", 14)
        self.commit(csv_of(r1, r2, dict(v(r1, "x run:14"), checked_by="审查与治理"), v(r2, "x run:14")), "void")
        self.assert_warn(self.cli(), "E-BR-VOID-FILLED")

    def test_non_void_errors_still_fail(self):
        self.commit(csv_of(row(trigger_condition="x > 100"), sibling(row())), "bad")
        self.assertEqual(self.cli().returncode, 1)

    def test_cli_void_prereg_changed_is_warn(self):   # 作废行改了事先登记字段：作废留痕写错，只警告、计数 INVALID
        r1, r2, v = self.grp()
        c = self.commit(csv_of(r1, r2), "late"); self.push(c, "2026-10-15T00:00:00Z", 15)
        self.commit(csv_of(r1, r2, dict(v(r1, "x run:15"), unit="pp"), v(r2, "x run:15")), "void")
        p = self.cli()
        self.assert_warn(p, "E-BR-PREREG-CHANGED")
        self.assertNotRegex(p.stdout, r"(?m)^line \d+: E-BR-PREREG-CHANGED$")

    def test_cli_void_row_id_error_still_fails(self):   # 作废行上的非作废类问题（row_id 不对）照常报错
        r1, r2, v = self.grp()
        c = self.commit(csv_of(r1, r2), "late"); self.push(c, "2026-10-15T00:00:00Z", 16)
        self.commit(csv_of(r1, r2, dict(v(r1, "x run:16"), row_id=r1["row_id"][:-1] + "9"), v(r2, "x run:16")), "void")
        p = self.cli()
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertRegex(p.stdout, r"(?m)^line \d+: E-BR-ROW-ID$")
        self.assertNotRegex(p.stdout, r"warn line \S+: E-BR-ROW-ID")
        self.assertIn("gate_count INVALID", p.stdout); self.assertIn("FAIL", p.stdout)


class R9Review(R6Trust):
    """r9：r8 审查的 MEDIUM 1、MEDIUM 2 与 LOW。"""

    def run_cli(self, *extra, env=None, runs=True, main_ref="HEAD~1"):
        import os
        a = ["--repo", str(self.d), "--main-ref", main_ref, "--count-gate", "--stats", *extra]
        if runs is not None:
            f = self.d / "runs.json"; f.write_text(json.dumps(self.runs)); a += ["--push-runs", str(f)]
        e = {k: v for k, v in os.environ.items() if k != "GITHUB_ACTIONS"}
        e.update(env or {})
        return subprocess.run(["python3", str(self.script), *a], capture_output=True, text=True, env=e)

    # MEDIUM 1：main 上还没有任何登记行、又没有运行记录时，PR 新增登记行不得得出有效计数
    def test_M1_empty_main_no_push_runs_arg(self):
        r1, r2, _ = self.grp()
        self.commit(csv_of(r1, r2), "pr rows")           # main（HEAD~1）只有表头
        p = self.run_cli(runs=None)                        # 未传 --push-runs
        self.assertIn("W-BR-PUSH-TIME-UNAVAILABLE", p.stdout)
        self.assertIn("gate_count INVALID", p.stdout); self.assertIn("stats INVALID", p.stdout)
        self.assertNotIn("gate_count 2", p.stdout)

    def test_M1_empty_main_empty_run_list(self):
        r1, r2, _ = self.grp()
        self.commit(csv_of(r1, r2), "pr rows")
        p = self.run_cli()                                 # 运行列表为空 []
        self.assertIn("W-BR-PUSH-TIME-UNAVAILABLE", p.stdout)
        self.assertIn("gate_count INVALID", p.stdout); self.assertIn("stats INVALID", p.stdout)

    def test_M1_trust_check_valid_false_without_runs(self):
        r1, r2, _ = self.grp()
        self.commit(csv_of(r1, r2), "pr rows")
        rs, _ = B.parse(csv_of(r1, r2))
        cb = cb_module()
        for runs in (None, []):
            _, warns, _, valid = cb.trust_check(str(self.d), rs, "HEAD~1", runs)
            self.assertFalse(valid, runs); self.assertIn((0, "W-BR-PUSH-TIME-UNAVAILABLE"), warns)

    # MEDIUM 2：作废行上的 E-BR-FIRST-ROW、E-BR-GROUP-LATE 不得降为警告
    def test_M2_all_void_first_rows_fail(self):
        r1, r2, _ = self.grp()
        v1 = dict(r1, check_result="VOID", corrects_row_id=r1["row_id"], reason="x run:21")
        v2 = dict(r2, check_result="VOID", corrects_row_id=r2["row_id"], reason="x run:21")
        c = self.commit(csv_of(v1, v2), "void-only group"); self.push(c, "2026-10-13T00:00:00Z", 21)
        p = self.run_cli(main_ref="HEAD")
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertRegex(p.stdout, r"(?m)^line \d+: E-BR-FIRST-ROW$")
        self.assertNotRegex(p.stdout, r"warn line \S+: E-BR-FIRST-ROW")
        self.assertIn("gate_count INVALID", p.stdout); self.assertIn("FAIL", p.stdout)

    def test_M2_group_late_on_void_line_fails(self):
        r1, r2, _ = self.grp()
        c = self.commit(csv_of(r1, r2), "in time"); self.push(c, "2026-10-13T00:00:00Z", 22)
        late3 = rid(dict(r1, branch_order="3", check_result="VOID", corrects_row_id=r1["row_id"], reason="x run:22"), 1)
        self.commit(csv_of(r1, r2, late3), "late branch as VOID")
        p = self.run_cli("--base", "HEAD~1", main_ref="HEAD~1")
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertRegex(p.stdout, r"(?m)^(commit \S+ )?line \d+: E-BR-GROUP-LATE$")
        self.assertNotRegex(p.stdout, r"warn line \S+: E-BR-GROUP-LATE")
        self.assertRegex(p.stdout, r"(?m)^line \d+: E-BR-FIRST-ROW$")

    def test_M2_downgrade_scope(self):
        cb = cb_module()
        for code in ("E-BR-FIRST-ROW", "E-BR-GROUP-LATE"):
            self.assertFalse(cb.downgradable(code, True)); self.assertFalse(cb.downgradable(code, False))
        for code in ("E-BR-ROW-ID", "E-BR-DUPLICATE", "E-BR-PRIVATE-TEXT:reason", "E-BR-REGISTERED-DATE"):
            self.assertFalse(cb.downgradable(code, True), code)   # 作废行上的其他问题照常报错
        for code in cb.VOID_CODES:
            self.assertTrue(cb.downgradable(code, False), code)
        self.assertTrue(cb.downgradable("E-BR-CORRECTS-TARGET", True))
        self.assertFalse(cb.downgradable("E-BR-CORRECTS-TARGET", False))

    # LOW：GitHub Actions 中输出 ::warning 与 ::notice；本机不输出
    def test_LOW_actions_annotations(self):
        r1, r2, _ = self.grp()
        c = self.commit(csv_of(r1, r2), "old"); self.push(c, "2026-10-15T01:00:00Z", 31)   # 晚合并
        p = self.run_cli(main_ref="HEAD", env={"GITHUB_ACTIONS": "true"})
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertIn("PASS", p.stdout)
        self.assertRegex(p.stdout, r"(?m)^::warning::ledger line \S+: W-BR-LATE-UNHANDLED$")
        self.assertRegex(p.stdout, r"(?m)^::notice::门禁数仅为预估.*人工核对登记 PR 的合并时间")
        local = self.run_cli(main_ref="HEAD")
        self.assertNotIn("::warning::", local.stdout); self.assertNotIn("::notice::", local.stdout)

    def test_LOW_early_exit_errors_annotated(self):   # r9 LOW：五种提前退出的错误在 Actions 中也输出 ::error::
        import os
        r1, r2, _ = self.grp()
        self.commit(csv_of(r1, r2), "rows")
        (self.d / B.LEDGER_PATH).unlink(); self.g("add", "-A"); self.g("commit", "-qm", "rm ledger")
        cases = {
            "E-BR-NOW": ["--ref", "HEAD~1", "--now", "2026-10-15 09:00"],
            "E-BR-GIT": ["--ref", "no-such-ref"],
            "E-BR-MISSING": ["--ref", "HEAD"],
            "E-BR-MAIN-REF": ["--ref", "HEAD~1", "--main-ref", "no-such-ref"],
            "E-BR-BASE-UNREADABLE": ["--ref", "HEAD~1", "--base", "no-such-ref"],
        }
        base_env = {k: v for k, v in os.environ.items() if k != "GITHUB_ACTIONS"}
        for code, args in cases.items():
            cmd = ["python3", str(self.script), "--repo", str(self.d), *args]
            gh = subprocess.run(cmd, capture_output=True, text=True, env={**base_env, "GITHUB_ACTIONS": "true"})
            self.assertEqual(gh.returncode, 1, (code, gh.stdout))
            self.assertRegex(gh.stdout, r"(?m)^" + code + r" ", code)
            self.assertRegex(gh.stdout, r"(?m)^::error::ledger " + code + r" ", code)
            local = subprocess.run(cmd, capture_output=True, text=True, env=base_env)
            self.assertEqual(local.returncode, 1, code)
            self.assertIn(code, local.stdout); self.assertNotIn("::error::", local.stdout)

    def test_LOW_actions_error_annotation(self):
        self.commit(csv_of(row(trigger_condition="x > 100"), sibling(row())), "bad")
        p = self.run_cli(main_ref="HEAD", env={"GITHUB_ACTIONS": "true"})
        self.assertEqual(p.returncode, 1); self.assertIn("::error::ledger line", p.stdout)
        self.assertIn("本次计数为 INVALID", p.stdout)


if __name__ == "__main__":
    unittest.main()
