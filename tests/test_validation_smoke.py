import json
from pathlib import Path

from scripts.validate_and_version import validate_and_version


def test_sample_outputs_validate(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[1]
    final_dir = tmp_path / "final"
    final_dir.mkdir(parents=True, exist_ok=True)

    # Copy sample outputs into tmp final dir
    sample = repo_root / "sample_outputs"
    for name in ("completion.jsonl", "documentation.jsonl", "refactor.jsonl", "debugging.jsonl"):
        (final_dir / name).write_text((sample / name).read_text(encoding="utf-8"), encoding="utf-8")

    schemas_dir = repo_root / "schemas"
    out = validate_and_version(final_dir, schemas_dir, cfg={}, stats_from_norm={"total": 10, "near_unique": 7})
    assert out.exists(), "manifest.json should be written"
    data = json.loads(out.read_text(encoding="utf-8"))
    assert set(data["counts"].keys()) == {"completion", "documentation", "refactor", "debugging"}
    assert data["duplication_rate_hint"] is not None
