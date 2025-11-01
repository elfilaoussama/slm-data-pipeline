from pathlib import Path
import json

from scripts.normalize_dedup import _normalize_python, normalize_and_dedup


def test_normalize_python_collapse_blank_lines():
    src = "def f():\n\n\n    return 1\n\n\n"
    norm = _normalize_python(src)
    assert "\n\n\n" not in norm
    assert norm.endswith("\n")


def test_dedup_keeps_first(tmp_path: Path):
    ast_dir = tmp_path
    # Two identical records and one different
    rec1 = {"language": "python", "code": "def f():\n    return 1\n", "file_path": "repo/a.py", "start_line": 1, "end_line": 2}
    rec2 = {"language": "python", "code": "def f():\n    return 1\n", "file_path": "repo/b.py", "start_line": 1, "end_line": 2}
    rec3 = {"language": "python", "code": "def g():\n    return 2\n", "file_path": "repo/c.py", "start_line": 1, "end_line": 2}

    fp = ast_dir / "dummyrepo_aaaa1111_functions.jsonl"
    with open(fp, "w", encoding="utf-8") as f:
        for r in (rec1, rec2, rec3):
            f.write(json.dumps(r) + "\n")

    out = normalize_and_dedup(ast_dir, cfg={"dedup": {"shingle_size": 2, "minhash_permutations": 64, "lsh_threshold": 0.9}})
    assert out["total"] == 3
    assert out["exact_unique"] == 2  # rec1 and rec2 collapse
    kept_path = ast_dir / "kept_records.jsonl"
    assert kept_path.exists()
    kept = kept_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(kept) in (1, 2)  # near-dup may drop one more depending on LSH
