# Configuration

[Back to Pipeline stages](pipeline-stages.md) · [Quickstart](../QUICKSTART.md) · [Security & licensing](security-and-licensing.md)

Edit `configs.yml` to control discovery, extraction, deduplication, security, and quality filters.

Key sections and related CLI overrides:
- semantic, keywords → discovery
  - CLI: `--semantic-query`, `--semantic-topk`, `--semantic-threshold`, `--keyword-query`
- extract → function size bounds
  - CLI: `--min-function-loc`, `--max-function-loc`
- quality_filters → function quality gating
  - Toggle and thresholds; CLI: `--no-quality`, `--quality-min-loc`, `--quality-max-loc`, `--quality-max-cyclomatic`, `--quality-max-nesting`, `--quality-allow-synthetic-docs|--quality-disallow-synthetic-docs`
- dedup → near-duplicate detection
  - CLI: `--dedup-shingle-size`, `--minhash-perms`
- security → license/compliance and scanners
  - CLI: `--skip-security`

See the full flow in [Pipeline stages](pipeline-stages.md) and [schemas](data-schemas.md) for output formats.
# Configuration and CLI

Config file: `configs.yml`. Override most values using CLI flags in `pipeline.py`.

Key options:
- allowed_licenses: list of SPDX identifiers to allow
- languages: default `python`
- min_stars, max_repos: discovery sizing
- semantic: model name, topk, threshold (optional embeddings)
- paths: controls output dirs and reports/quarantine
- dedup: shingle_size, minhash_permutations, lsh_threshold
- extract: min/max function LOC

Examples:
```
python pipeline.py \
  --allowed-licenses "MIT,Apache-2.0,BSD-3-Clause" \
  --languages python \
  --min-stars 50 \
  --max-repos 3 \
  --keyword-query "license:mit python"
```

`.env` variables (optional):
- GH_TOKENS: comma-separated GitHub tokens
- GL_TOKEN: GitLab token

WSL helper supports env overrides:
- KEYWORD_QUERY, MAX_REPOS, MIN_STARS, LANGUAGES, ALLOWED_LICENSES
