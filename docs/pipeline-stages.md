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

4) Parse & extract (`t_parse_extract` / `scripts/parse_extract.py`)
   - Extracts function-level units (Python via `ast`) into JSONL

5) Normalize & dedup (`t_normalize_dedup` / `scripts/normalize_dedup.py`)
   - Lightweight normalization; exact + LSH near-dup filtering
   - Emits `data/processed/ast/kept_records.jsonl` with retained units

6) Task transformers (`t_task_transformers` / `scripts/task_transformers.py`)
   - Builds task datasets: `completion.jsonl`, `documentation.jsonl`, `refactor.jsonl`, `debugging.jsonl`

7) Validate & version (`t_validate_and_version` / `scripts/validate_and_version.py`)
   - Validates JSONL against schemas; aggregates stats into `data/final/manifest.json`
