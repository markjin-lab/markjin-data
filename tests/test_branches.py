import subprocess, tempfile, unittest
from pathlib import Path
import helpers  # noqa: F401
from markjin import branches as B

SHA = "a" * 64
HDR = ",".join(B.HEADER) + "\n"


def row(**kw):
    base = dict.fromkeys(B.HEADER, "")
    base.update(draft_id="2026-10-13-macro", slug="gdp-q3", publish_date="2026-10-13", framework_version="v2.4",
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
             u_value="2", lu_evidence="2025Q1:1@v#raw/x:" + SHA)
    q.update(kw)
    return row(**q)


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
        self.assertEqual(codes(row(), ok), [])
        self.assertIn("E-BR-ERROR-SOURCE", codes(row(), dict(ok, check_result="HIT", actual_branch="是")))
        self.assertIn("E-BR-ERROR-SOURCE", codes(row(), dict(ok, error_source="采集;采集")))

    def test_prereg_unchanged_on_append(self):
        later = row(check_result="DATA_UNAVAILABLE", checked_by="审查与治理", checked_at="2027-01-05T10:00:00+08:00",
                    interval_high="6")
        self.assertIn("E-BR-PREREG-CHANGED", codes(row(), later))

    def test_append_only(self):
        a = csv_of(row())
        self.assertTrue(B.append_only(a, a + csv_of(row(branch_order="2"))[len(HDR):]))
        self.assertFalse(B.append_only(a, csv_of(row(slug="other"))))

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
