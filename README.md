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

## Outputs
- Manifests: `manifests/discovered_repos.json`
- Repo snapshots: `data/raw/`
- AST/function records: `data/processed/ast/*_functions.jsonl`
- Final datasets: `data/final/completion.jsonl`, `data/final/documentation.jsonl`, `data/final/refactor.jsonl`, `data/final/debugging.jsonl`
- Security reports: `.reports/security/`
- Validation summary: `data/final/manifest.json`

## Docs
- QUICKSTART: `QUICKSTART.md`
- Pipeline stages: `docs/pipeline-stages.md`
- Configuration/CLI: `docs/configuration.md`
- Security & licensing: `docs/security-and-licensing.md`
- Schemas: `docs/data-schemas.md`
- Troubleshooting: `docs/troubleshooting.md`

## License Policy
Exclude copyleft (GPL/LGPL/AGPL) by default. The pipeline gates licenses and stores `license_spdx` text in provenance; do not publish shards with disallowed licenses.
