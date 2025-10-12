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
/mnt/e/PROJECTS/arkx/code_data_pipline/run_wsl_with_logs.sh
```

## Outputs
- Final datasets: `data/final/{completion,documentation,refactor,debugging}.jsonl`
- Security reports: `.reports/security/`
- Manifest: `data/final/manifest.json`

## Next
- See `docs/pipeline-stages.md` for what each step does.
- See `docs/configuration.md` to tune discovery, filters, and dedup.
