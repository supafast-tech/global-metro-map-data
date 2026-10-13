"""Checks of travel-times.json against the line topology. Run: python3 -m unittest discover -s scripts"""
import ast, json, os, re, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "build-travel-times.py")


def script_defs(*names):
    """The named top-level definitions of build-travel-times.py, without running the build."""
    tree = ast.parse(open(SCRIPT).read())
    keep = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name in names)
            or (isinstance(n, ast.Assign) and any(getattr(t, "id", None) in names for t in n.targets))]
    ns = {"re": re}
    exec(compile(ast.Module(body=keep, type_ignores=[]), SCRIPT, "exec"), ns)
    return ns


class LineTopology(unittest.TestCase):
    def setUp(self):
        self.ns = script_defs("LINE_FORKS", "seq", "line_pairs")
        subte = json.load(open(os.path.join(ROOT, "subte.json")))
        self.premetro = sorted(f["properties"]["id"] for f in subte["features"]
                               if f["geometry"]["type"] == "Point" and f["properties"]["id"].startswith("premetro"))

    def test_premetro_branch_hangs_off_pola(self):
        pairs = self.ns["line_pairs"]("premetro-E2", self.premetro)
        self.assertIn(("premetro-E2-12", "premetro-E2-17"), pairs)
        self.assertIn(("premetro-E2-17", "premetro-E2-18"), pairs)
        self.assertNotIn(("premetro-E2-16", "premetro-E2-17"), pairs)
        self.assertEqual(len(pairs), len(self.premetro) - 1)

    def test_no_edge_between_general_savio_and_ana_diaz(self):
        edges = json.load(open(os.path.join(ROOT, "travel-times.json")))["edges"]
        e2 = {tuple(sorted((e["from"], e["to"]))) for e in edges if e["line"] == "E2"}
        self.assertNotIn(("premetro-E2-16", "premetro-E2-17"), e2)
        want = {tuple(sorted(p)) for p in self.ns["line_pairs"]("premetro-E2", self.premetro)}
        self.assertEqual(e2, want)
        compare = json.load(open(os.path.join(ROOT, "travel-times-compare.json")))
        rows = [r for k in ("changed_over_1_min", "no_gtfs_time") for r in compare[k]]
        self.assertFalse([r for r in rows if {r["from"], r["to"]} == {"premetro-E2-16", "premetro-E2-17"}])


if __name__ == "__main__":
    unittest.main()
