# Pipeline stages

Overview of the single-file Prefect flow in `pipeline.py`.

1) Discovery (`t_discover_repos` / `scripts/repo_discovery.py`)
   - Searches GitHub/GitLab using keyword query and optional semantic score
   - Produces `manifests/discovered_repos.json`

2) Ingest (`t_ingest_repo` / `scripts/ingest_repo.py`)
   - Shallow clone, snapshot to tar.gz, compute per-file hashes
   - Writes `data/raw/<repo>/provenance.json`

3) Security & license gate (`t_security_gate` / `scripts/security_scan.py`)
   - Runs Dockerized scans: ScanCode, Semgrep, Bandit, Gitleaks
   - Enforces allowlist licenses and quarantines on secrets
   - Writes `.reports/security/*` and updates provenance

## Pipeline stages

[Quickstart](../QUICKSTART.md) · [Configuration](configuration.md) · [Security & licensing](security-and-licensing.md) · [Schemas](data-schemas.md) · [Troubleshooting](troubleshooting.md)

High-level flow:

Discover → Ingest → Security/License Gate → Parse/Extract → Normalize/Dedup → Task Datasets → Validate/Version

1) Discover
- Code: [scripts/repo_discovery.py](../scripts/repo_discovery.py)
- Inputs: `configs.yml` (semantic, keywords), CLI `--semantic-query`, `--keyword-query`
- Outputs: `[manifests]/discovered_repos.json`

2) Ingest/Clone
- Code: [scripts/ingest_repo.py](../scripts/ingest_repo.py)
- Inputs: manifest item
- Outputs: `data/raw/<repo>/` snapshot + provenance

3) Security & License Gate
- Code: [scripts/security_scan.py](../scripts/security_scan.py)
- Config: `security.*` in `configs.yml`, CLI `--skip-security`
- Outputs: `.reports/security/*`, quarantine decisions
- Docs: [Security & licensing](security-and-licensing.md)

4) Parse & extract
- Code: [scripts/parse_extract.py](../scripts/parse_extract.py)
- Adds quality metrics and documentation metadata via [scripts/quality.py](../scripts/quality.py)
- Config: `extract.*` (LOC bounds)
- Outputs: `data/processed/ast/*_functions.jsonl`
   - Extracts function-level units (Python via `ast`) into JSONL

5) Normalize & dedup
- Code: [scripts/normalize_dedup.py](../scripts/normalize_dedup.py)
- Config: `dedup.*`, `quality_filters.*` (gates); CLI overrides: `--no-quality`, `--quality-...`
- Outputs: `kept_records.jsonl`, stats
   - Lightweight normalization; exact + LSH near-dup filtering
   - Emits `data/processed/ast/kept_records.jsonl` with retained units

6) Task transformers (`t_task_transformers` / `scripts/task_transformers.py`)
   - Builds task datasets: `completion.jsonl`, `documentation.jsonl`, `refactor.jsonl`, `debugging.jsonl`

6) Build task datasets
- Code: [scripts/task_transformers.py](../scripts/task_transformers.py)
- Outputs: `data/final/{completion,documentation,refactor,debugging}.jsonl`

7) Validate & version
- Code: [scripts/validate_and_version.py](../scripts/validate_and_version.py)
- Schemas: [docs/schemas](data-schemas.md)
- Outputs: `data/final/manifest.json`

Navigation: [README](../README.md) · [Configuration](configuration.md) · [Security](security-and-licensing.md)
   - Validates JSONL against schemas; aggregates stats into `data/final/manifest.json`
