import subprocess, tempfile, unittest
from pathlib import Path
import helpers  # noqa: F401
from markjin import branches as B

SHA = "a" * 64
LU = "2025Q1:1.5@2025-04-16#raw/2025-04-16/fred/X.csv:" + "c" * 64 + "|https://fred.stlouisfed.org/series/X"
QR = "2026Q3:1.2@2026-10-20#raw/2026-10-20/fred/X.csv:" + "d" * 64
DONE = dict(checked_by="审查与治理", checked_at="2027-01-05T10:00:00+08:00")
HDR = ",".join(B.HEADER) + "\n"


def row(**kw):
    base = dict.fromkeys(B.HEADER, "")
    base.update(row_id="2026-10-13-macro-b1-r1", domain="macro", framework_commit="b" * 40, draft_id="2026-10-13-macro", slug="gdp-q3", publish_date="2026-10-13", framework_version="v2.4",
                framework_sha256=SHA, observed_variable="GDP", unit="%", data_source="FRED:X",
                data_vintage="每季取到期核对日（SGT）最新发布的版本", window_start="2026-10-13", window_end="2026-12-31",
                branch_order="1", interval_low="", interval_low_closed="false", interval_high="5",
                interval_high_closed="false", trigger_condition="x < 5", registered_by="生产与发布",
                registered_at="2026-10-13T07:00:00+08:00", check_result="PENDING")
    base.update(kw)
    return base


def quarterly(**kw):
    q = dict(interval_low="NA", interval_low_closed="NA", interval_high="NA", interval_high_closed="NA",
             n_quarters="2", window_quarters="2026Q3;2026Q4", lu_basis_date="2026-10-01", l_value="1",
             u_value="2", lu_evidence=LU)
    q.update(kw)
    return row(**q)


def rid(r, seq):
    r = dict(r); r["row_id"] = B.expected_row_id(r["draft_id"], r["branch_order"], seq); return r


def csv_of(*rows):
    return HDR + "".join(",".join(r[f] for f in B.HEADER) + "\n" for r in rows)


def codes(*rows):
    return [c for _, c in B.parse(csv_of(*rows))[1]]


class Branches(unittest.TestCase):
    def test_header_only_ok(self):
        repo_file = Path(__file__).resolve().parents[1] / B.LEDGER_PATH
        self.assertEqual(B.parse(repo_file.read_text(encoding="utf-8"))[1], [])

    def test_bad_header(self):
        self.assertEqual(B.parse("a,b\n")[1], [(1, "E-BR-HEADER")])

    def test_interval_ok(self):
        self.assertEqual(codes(row()), [])

    def test_quarterly_ok(self):
        self.assertEqual(codes(quarterly()), [])

    def test_n_ge_1(self):
        self.assertIn("E-BR-N", codes(quarterly(n_quarters="0")))

    def test_l_le_u(self):
        self.assertIn("E-BR-L-GT-U", codes(quarterly(l_value="3", u_value="2")))

    def test_window_quarters(self):
        self.assertIn("E-BR-WQ-COUNT", codes(quarterly(window_quarters="2026Q4")))
        self.assertIn("E-BR-WQ-GAP", codes(quarterly(window_quarters="2026Q2;2026Q4")))
        self.assertIn("E-BR-WQ-AFTER-END", codes(quarterly(window_quarters="2026Q4;2027Q1")))

    def test_quarterly_interval_must_be_na(self):
        self.assertIn("E-BR-INTERVAL-NA", codes(quarterly(interval_low="")))

    def test_lu_evidence_required(self):
        self.assertIn("E-BR-LU-EVIDENCE", codes(quarterly(lu_evidence="")))

    def test_sha_and_dates(self):
        self.assertIn("E-BR-SHA256", codes(row(framework_sha256="abc")))
        self.assertIn("E-BR-DATE:window_end", codes(row(window_end="2026-02-30")))
        self.assertIn("E-BR-TS:registered_at", codes(row(registered_at="2026-10-13 07:00")))

    def test_check_result_rules(self):
        self.assertIn("E-BR-CHECK-RESULT", codes(row(check_result="OK")))
        self.assertIn("E-BR-PENDING-FILLED", codes(row(actual_branch="是")))
        ok = row(check_result="NONE_HIT", actual_branch="否", error_source="采集;框架", checked_by="审查与治理",
                 checked_at="2027-01-05T10:00:00+08:00", evidence="raw/x sha")
        self.assertEqual(codes(row(), rid(ok, 2)), [])
        self.assertIn("E-BR-ERROR-SOURCE", codes(row(), rid(dict(ok, check_result="HIT", actual_branch="是"), 2)))
        self.assertIn("E-BR-ERROR-SOURCE", codes(row(), rid(dict(ok, error_source="采集;采集"), 2)))

    def test_prereg_unchanged_on_append(self):
        later = row(check_result="DATA_UNAVAILABLE", checked_by="审查与治理", checked_at="2027-01-05T10:00:00+08:00",
                    interval_high="6")
        self.assertIn("E-BR-PREREG-CHANGED", codes(row(), rid(later, 2)))

    def test_append_only(self):
        a = csv_of(row())
        self.assertTrue(B.append_only(a, a + csv_of(rid(row(branch_order="2"), 1))[len(HDR):]))
        self.assertFalse(B.append_only(a, csv_of(row(slug="other"))))

    def test_non_macro_na(self):
        ai = row(domain="ai", draft_id="2026-10-13-daily", unit="NA", data_vintage="NA",
                 interval_low="NA", interval_low_closed="NA", interval_high="NA", interval_high_closed="NA",
                 n_quarters="NA", window_quarters="NA", lu_basis_date="NA", l_value="NA", u_value="NA", lu_evidence="NA",
                 quarter_readings="NA", trigger_condition="发布一手公告")
        self.assertEqual(codes(rid(ai, 1)), [])
        self.assertIn("E-BR-DOMAIN", codes(row(domain="crypto")))
        self.assertIn("E-BR-QUARTERLY-ONLY:l_value", codes(row(l_value="1")))

    def test_framework_commit(self):
        self.assertIn("E-BR-COMMIT", codes(row(framework_commit="abc")))
        self.assertIn("E-BR-EMPTY:framework_commit", codes(row(framework_commit="")))

    def test_row_id_rule(self):
        self.assertIn("E-BR-ROW-ID", codes(row(row_id="x")))
        self.assertIn("E-BR-ROW-ID", codes(row(), row()))  # 第二行 row_id 仍为 r1

    def test_correction_ok(self):
        corr = rid(row(corrects_row_id="2026-10-13-macro-b1-r1", reason="上沿登记错", interval_high="6"), 2)
        self.assertEqual(codes(row(), corr), [])
        # 更正后的对账行以更正行为登记依据
        chk = rid(row(interval_high="6", check_result="DATA_UNAVAILABLE", checked_by="审查与治理",
                      checked_at="2027-01-05T10:00:00+08:00"), 3)
        self.assertEqual(codes(row(), corr, chk), [])

    def test_correction_must_point_to_existing(self):
        corr = rid(row(corrects_row_id="2026-10-13-macro-b1-r9", reason="x"), 2)
        self.assertIn("E-BR-CORRECTS-UNKNOWN", codes(row(), corr))
        other = rid(row(branch_order="2", corrects_row_id="2026-10-13-macro-b1-r1", reason="x"), 2)
        self.assertIn("E-BR-CORRECTS-UNKNOWN", codes(row(), rid(row(branch_order="2"), 1), other))

    def test_correction_needs_reason(self):
        corr = rid(row(corrects_row_id="2026-10-13-macro-b1-r1"), 2)
        self.assertIn("E-BR-CORRECTION-REASON", codes(row(), corr))
        self.assertIn("E-BR-CORRECTION-REASON", codes(row(reason="只有理由")))

    def test_first_row_rules(self):
        self.assertIn("E-BR-FIRST-ROW", codes(row(corrects_row_id="2026-10-13-macro-b1-r1", reason="x")))

    def test_gate_count_first_row_only(self):
        corr = rid(row(corrects_row_id="2026-10-13-macro-b1-r1", reason="x", window_end="2027-03-31"), 2)
        b2 = rid(row(branch_order="2", window_end="2027-03-31"), 1)
        rows, errs = B.parse(csv_of(row(), corr, b2))
        self.assertEqual(errs, [])
        self.assertEqual(B.gate_count(rows), 1)
        self.assertEqual(B.gate_count(rows, domain="ai"), 0)
        self.assertEqual(B.gate_count(rows, cutoff="2027-12-31"), 2)

    def test_registered_before_end(self):
        self.assertIn("E-BR-REGISTERED-AFTER-END", codes(row(registered_at="2027-01-01T07:00:00+08:00")))
        self.assertNotIn("E-BR-REGISTERED-AFTER-END", codes(row(registered_at="2026-12-31T07:00:00+08:00")))

    def test_first_row_must_be_pending(self):
        self.assertIn("E-BR-FIRST-ROW", codes(row(check_result="DATA_UNAVAILABLE", **DONE)))

    def test_checked_after_end(self):
        late = rid(row(check_result="DATA_UNAVAILABLE", checked_by="审查与治理", checked_at="2026-12-31T23:00:00+08:00"), 2)
        self.assertIn("E-BR-CHECKED-BEFORE-END", codes(row(), late))

    def test_one_final_per_branch(self):
        hit = rid(row(check_result="HIT", actual_branch="是", actual_value="4", evidence="e", **DONE), 2)
        miss = rid(row(check_result="MISS", actual_branch="否", actual_value="4", evidence="e", **DONE), 3)
        self.assertIn("E-BR-SECOND-FINAL", codes(row(), hit, miss))
        du = rid(row(check_result="DATA_UNAVAILABLE", **DONE), 2)
        self.assertEqual(codes(row(), du, rid(hit, 3)), [])
        corr = rid(row(corrects_row_id="2026-10-13-macro-b1-r2", reason="对账取错数据"), 3)
        self.assertEqual(codes(row(), hit, corr, rid(miss, 4)), [])

    def test_quarterly_results_limited(self):
        ok = rid(quarterly(check_result="TRIGGER_UNOBSERVABLE", evidence="e", **DONE), 2)
        self.assertEqual(codes(quarterly(), ok), [])
        self.assertIn("E-BR-QUARTERLY-RESULT", codes(quarterly(), rid(quarterly(check_result="HIT", actual_branch="是", evidence="e", **DONE), 2)))
        self.assertIn("E-BR-QUARTERLY-ERROR-SOURCE", codes(quarterly(), rid(dict(ok, error_source="框架"), 2)))

    def test_pending_cannot_fill(self):
        for f in ("actual_value", "evidence", "checked_by"):
            self.assertIn("E-BR-PENDING-FILLED", codes(row(**{f: "x"})), f)

    def test_readings_format(self):
        self.assertEqual(codes(quarterly(), rid(quarterly(quarter_readings=QR), 2)), [])
        for bad in ("2026Q3:1.2", "2026Q3:1.2@v1#raw/a:" + "d" * 64, "2026Q3:1.2@2026-10-20#raw/a:abc",
                    "2026Q3:1.2@2026-10-20#/tmp/a:" + "d" * 64):
            self.assertIn("E-BR-READINGS-FORMAT", codes(quarterly(quarter_readings=bad)), bad)
        self.assertIn("E-BR-READINGS-QUARTERS", codes(quarterly(quarter_readings=QR.replace("2026Q3", "2027Q1"))))
        self.assertIn("E-BR-LU-EVIDENCE-FORMAT", codes(quarterly(lu_evidence=LU.split("|")[0])))

    def test_cli_on_git(self):
        d = Path(tempfile.mkdtemp())
        run = lambda *a: subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True)
        run("init", "-q"); run("config", "user.email", "t@t"); run("config", "user.name", "t")
        (d / "ledger").mkdir(); (d / B.LEDGER_PATH).write_text(csv_of(row()), encoding="utf-8")
        run("add", "."); run("commit", "-qm", "a")
        (d / B.LEDGER_PATH).write_text(csv_of(row(slug="changed")), encoding="utf-8")
        run("commit", "-qam", "b")
        script = Path(__file__).resolve().parents[1] / "scripts/check-branches.py"
        p = subprocess.run(["python3", str(script), "--repo", str(d), "--base", "HEAD~1"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 1); self.assertIn("E-BR-NOT-APPEND-ONLY", p.stdout)


if __name__ == "__main__":
    unittest.main()
