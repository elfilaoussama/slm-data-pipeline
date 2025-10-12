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
