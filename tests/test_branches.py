import subprocess, tempfile, unittest
from pathlib import Path
import helpers  # noqa: F401
from markjin import branches as B

SHA = "a" * 64
RAWP = "raw/2026-10-20/fred/X.csv"
RSHA = "d" * 64
LU = "2025Q1:1.5@2025-04-16#raw/2025-04-16/fred/X.csv:" + "c" * 64 + "|https://fred.stlouisfed.org/series/X"
QR1 = f"2026Q3:1.2@2026-10-20#{RAWP}:{RSHA}"
QR2 = QR1 + f";2026Q4:1.3@2027-01-20#raw/2027-01-20/fred/X.csv:{RSHA}"
EVID = f"{RAWP}:{RSHA}|scripts/calc.py@{'e' * 40}|2027-01-05T09:00:00+08:00"
DONE = dict(checked_by="审查与治理", checked_at="2027-01-05T10:00:00+08:00")
HDR = ",".join(B.HEADER) + "\n"
FIRST = "2026-10-13-macro-c1-b1-r1"


def row(**kw):
    base = dict.fromkeys(B.HEADER, "")
    base.update(row_id=FIRST, classification_id="c1", domain="macro", framework_commit="b" * 40, draft_id="2026-10-13-macro",
                slug="gdp-q3", publish_date="2026-10-13", framework_version="v2.4",
                framework_sha256=SHA, observed_variable="GDP", unit="%", data_source="FRED:X",
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
        ok = row(check_result="NONE_HIT", actual_branch="否", actual_value="6", error_source="采集;框架", evidence=EVID, **DONE)
        self.assertEqual(ccodes(row(), ok), [])
        self.assertIn("E-BR-ERROR-SOURCE", ccodes(row(), dict(ok, error_source="采集;采集")))
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
        corr = miss(corrects_row_id="2026-10-13-macro-c1-b1-r2", reason="对账取错数据",
                    check_result="NONE_HIT", error_source="采集")
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
        man = {RAWP: RSHA, "raw/2025-04-16/fred/X.csv": "c" * 64}.get
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
        for f, v in (("observed_variable", "CPI"), ("unit", "pp"), ("data_source", "FRED:Y"), ("data_vintage", "首发值"),
                     ("window_start", "2026-10-15"), ("registered_at", "2026-10-14T07:00:00+08:00")):
            self.assertIn("E-BR-GROUP-MISMATCH" if f != "registered_at" else "E-BR-REGISTERED-DATE",
                          ccodes(row(), self.b2(**{f: v})), f)

    def test_N6_overlap(self):
        self.assertIn("E-BR-GROUP-OVERLAP", ccodes(row(interval_high="6", trigger_condition="x < 6"), self.b2()))

    def test_N7_gap(self):
        self.assertIn("E-BR-GROUP-GAP", ccodes(row(), self.b2(interval_low_closed="false", trigger_condition="5 < x")))
        self.assertEqual(ccodes(row(), self.b2()), [])

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


if __name__ == "__main__":
    unittest.main()
