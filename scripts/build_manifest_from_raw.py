import json
from pathlib import Path
from datetime import datetime
import argparse


def build_manifest(raw_dir: Path) -> list[dict]:
    items: list[dict] = []
    for child in sorted(raw_dir.iterdir()):
        if not child.is_dir():
            continue
        prov = child / "provenance.json"
        if not prov.exists():
            continue
        try:
            data = json.loads(prov.read_text(encoding="utf-8"))
        except Exception:
            continue
        item = {
            "source": data.get("source"),
            "repo_full_name": data.get("repo_full_name"),
            "clone_url": data.get("clone_url"),
            "default_branch": data.get("default_branch", "main"),
            "stars": None,
            "license_hint": data.get("license_spdx"),
            "url": None,
            "description": None,
            "topics": [],
            "readme_head": "",
            "semantic_score": data.get("semantic_score"),
            "fetch_timestamp": datetime.utcnow().isoformat(),
        }
        # Basic required fields guard
        if item["repo_full_name"] and item["clone_url"] and item["source"]:
            items.append(item)
    return items


def main():
    p = argparse.ArgumentParser(description="Build discovery manifest from existing raw repos")
    p.add_argument("--raw-dir", default="data/raw", help="Path to raw directory")
    p.add_argument("--out", default="manifests/from_raw_manifest.json", help="Output manifest path")
    args = p.parse_args()

    raw_dir = Path(args.raw_dir)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    items = build_manifest(raw_dir)
    out.write_text(json.dumps(items, indent=2), encoding="utf-8")
    print(f"Wrote {len(items)} entries to {out}")


if __name__ == "__main__":
    main()
