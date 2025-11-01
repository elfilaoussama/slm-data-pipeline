# Quickstart

This is the fastest way to run the SLM pilot pipeline end-to-end.

## Prereqs
- Python 3.10–3.12
- Docker (for security scans) available inside WSL2 or Linux
- Git (for cloning)

## Setup
```
python -m venv .venv
. .venv/bin/activate  # Windows PowerShell: wsl -e bash -lc "source .venv/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt
```

Optional: copy tokens
```
cp .env.example .env
# Edit .env and set GH_TOKENS=ghp_xxx,ghp_yyy and/or GL_TOKEN=glpat-xxx
```

## Run
Minimal run:
```
python pipeline.py --max-repos 1 --min-stars 0 --languages python --keyword-query "license:mit python"
```

WSL helper with logging:
```
scripts/run_wsl_with_logs.sh
```

## Outputs
- Final datasets: `data/final/{completion,documentation,refactor,debugging}.jsonl`
- Security reports: `.reports/security/`
- Manifest: `data/final/manifest.json`

## Next
- See [Pipeline stages](docs/pipeline-stages.md) for what each step does.
- See [Configuration](docs/configuration.md) to tune discovery, filters, and dedup.
- See [Security & licensing](docs/security-and-licensing.md) for gating and reports.

### Quality filters from CLI
No need to edit `configs.yml`—override per run:
```
# Disable all quality gates
python pipeline.py --no-quality

# Override thresholds
python pipeline.py --quality-min-loc 8 --quality-max-cyclomatic 10 --quality-max-nesting 4

# Drop synthetic docstrings
python pipeline.py --quality-disallow-synthetic-docs
```
