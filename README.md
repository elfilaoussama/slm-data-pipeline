# SLM Pipeline (Pilot)

Lean, repo-centric pipeline to produce license-compliant training datasets for SLM tasks: completion, documentation, refactor, debugging.

## Quickstart

See QUICKSTART.md for a copy-pasteable guide. Highlights:

1) Create and activate a Python 3.11+ environment, then install deps:

```
pip install -r requirements.txt
```

2) Optional: copy `.env.example` to `.env` and set `GH_TOKENS`, `GL_TOKEN`.

3) Run the Prefect flow:

```
python pipeline.py
```

Windows quick run script is available: `reproduce.ps1`.

## Project flow
End-to-end stages, each linked to its implementation and docs:

1. Discover → [scripts/repo_discovery.py](scripts/repo_discovery.py)
2. Ingest/clone → [scripts/ingest_repo.py](scripts/ingest_repo.py)
3. Security & license gate → [scripts/security_scan.py](scripts/security_scan.py) · See [Security & licensing](docs/security-and-licensing.md)
4. Parse & extract → [scripts/parse_extract.py](scripts/parse_extract.py)
5. Normalize & dedup → [scripts/normalize_dedup.py](scripts/normalize_dedup.py)
6. Task datasets → [scripts/task_transformers.py](scripts/task_transformers.py)
7. Validate & version → [scripts/validate_and_version.py](scripts/validate_and_version.py)

See the detailed walkthrough in [Pipeline stages](docs/pipeline-stages.md).

## Outputs
- Manifests: `manifests/discovered_repos.json`
- Repo snapshots: `data/raw/`
- AST/function records: `data/processed/ast/*_functions.jsonl`
- Final datasets: `data/final/completion.jsonl`, `data/final/documentation.jsonl`, `data/final/refactor.jsonl`, `data/final/debugging.jsonl`
- Security reports: `.reports/security/`
- Validation summary: `data/final/manifest.json`

## Quality filters via CLI
You can control the function-level quality gate without editing `configs.yml`:

```
# Disable quality filtering entirely (keep all extracted functions before dedup)
python pipeline.py --no-quality

# Tighten thresholds
python pipeline.py \
	--quality-min-loc 8 \
	--quality-max-cyclomatic 10 \
	--quality-max-nesting 4

# Drop synthetic docstrings fabricated during extraction
python pipeline.py --quality-disallow-synthetic-docs
```

These flags override `quality_filters` in `configs.yml` for the current run only.

## Docs
- [Quickstart](QUICKSTART.md)
- [Pipeline stages](docs/pipeline-stages.md)
- [Configuration and CLI](docs/configuration.md)
- [Security & licensing](docs/security-and-licensing.md)
- [Data schemas](docs/data-schemas.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Running in WSL](docs/running-in-wsl.md)

## License Policy
Exclude copyleft (GPL/LGPL/AGPL) by default. The pipeline gates licenses and stores `license_spdx` text in provenance; do not publish shards with disallowed licenses.
