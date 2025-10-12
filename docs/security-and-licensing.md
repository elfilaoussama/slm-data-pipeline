# Security & licensing

This pipeline prioritizes legal compliance and basic security hygiene.

- License gating:
  - Primary detection via ScanCode (Docker). If unavailable or inconclusive, fall back to ingestion hint (e.g., GitHub license field) to avoid false negatives.
  - Allowlist is configured via `configs.yml: allowed_licenses`.
- Secret detection:
  - Gitleaks scan; if any findings, the snapshot tar is copied to `.quarantine/` and the repo is excluded.
- Static analysis:
  - Semgrep (generic rules) and Bandit (Python). Findings are recorded in `.reports/security/`.

Artifacts:
- `.reports/security/*_{scancode,semgrep,bandit,gitleaks}.json`
- `data/raw/<repo>/provenance.json` includes license and scan metadata

Operational notes:
- Docker must be available within the runtime (WSL2 is recommended on Windows).
- Network failures or missing images generate stub outputs; the gate still enforces the allowlist.
