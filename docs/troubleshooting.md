# Troubleshooting

[Back to Pipeline stages](pipeline-stages.md) · [Quickstart](../QUICKSTART.md) · [Security & licensing](security-and-licensing.md)

- Docker not found or images fail to pull
  - Run under WSL2; verify `docker ps` works; pre-pull images if needed
- Discovery returns zero repos
  - Add tokens in `.env`; broaden `--keyword-query`; lower `--min-stars`
- License gate blocks all repos
  - Expand `--allowed-licenses` to include permissive licenses you accept
- Large outputs / slow runs
  - Start with `--max-repos 1`; use specific queries (e.g., `license:mit fastapi`)
- Validation errors
  - Check `schemas/` and the offending record line; open an issue with a minimal repro

More:
- Flow overview: [Pipeline stages](pipeline-stages.md)
- Config reference: [Configuration](configuration.md)
