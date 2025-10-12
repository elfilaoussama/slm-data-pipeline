import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
import argparse
from datetime import datetime

from prefect import flow, task, get_run_logger
from prefect.tasks import task_input_hash
from prefect.futures import PrefectFuture
import yaml
from dotenv import load_dotenv

# Local scripts (import-light to keep single-file entry simple)
from scripts.repo_discovery import discover_repos
from scripts.ingest_repo import ingest_repo
from scripts.security_scan import security_and_license_gate
from scripts.parse_extract import parse_and_extract
from scripts.normalize_dedup import normalize_and_dedup
from scripts.task_transformers import build_task_datasets
from scripts.validate_and_version import validate_and_version

CONFIG_PATH = Path(__file__).parent / "configs.yml"


def load_config(cfg_path: Path = CONFIG_PATH):
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@task(cache_key_fn=task_input_hash, retries=2, retry_delay_seconds=5)
def t_discover_repos(params: dict, cfg: dict) -> Path:
    return discover_repos(params, cfg)


@task(retries=2, retry_delay_seconds=5)
def t_ingest_repo(manifest_item: dict, cfg: dict) -> dict:
    return ingest_repo(manifest_item, cfg)


@task(retries=2, retry_delay_seconds=5)
def t_security_gate(snapshot_info: dict, cfg: dict) -> dict:
    return security_and_license_gate(snapshot_info, cfg)


@task(retries=2, retry_delay_seconds=5)
def t_parse_extract(gated_info: dict, cfg: dict) -> Path:
    return parse_and_extract(gated_info, cfg)


@task(retries=2, retry_delay_seconds=5)
def t_normalize_dedup(ast_dir: Path, cfg: dict) -> dict:
    return normalize_and_dedup(ast_dir, cfg)


@task(retries=2, retry_delay_seconds=5)
def t_task_transformers(norm_info: dict, cfg: dict) -> dict:
    return build_task_datasets(norm_info, cfg)

@task(retries=2, retry_delay_seconds=5)
def t_validate_and_version(final_info: dict, norm_info: dict, cfg: dict) -> str:
    final_dir = Path(cfg["paths"]["final_dir"])
    schemas_dir = Path(__file__).parent / "schemas"
    out = validate_and_version(final_dir, schemas_dir, cfg, stats_from_norm=norm_info)
    return str(out)

@flow(name="slm-pipeline")
def main(
    allowed_licenses: str = "MIT,Apache-2.0,BSD-3-Clause",
    languages: str = "python",
    min_stars: int = 100,
    max_repos: int = 5,
    semantic_query: str = "graph algorithms",
    semantic_topk: int = 200,
    semantic_threshold: float = 0.70,
    keyword_query: str = "graph algorithm python",
    min_function_loc: int = 5,
    max_function_loc: int = 400,
    dedup_shingle_size: int = 7,
    minhash_perms: int = 128,
    synthetic_bug_budget: float = 0.05,
    test_timeout: int = 600,
    worker_parallelism: int = 4,
    config_path: str | None = None,
    manifest_path: str | None = None,
):
    """
    Orchestrates the pilot pipeline: discovery -> ingest -> security -> extract -> dedup -> tasks.
    """
    logger = get_run_logger()
    cfg_file = Path(config_path) if config_path else CONFIG_PATH
    cfg = load_config(cfg_file)
    # Override cfg with CLI args
    cfg["allowed_licenses"] = [s.strip() for s in allowed_licenses.split(",") if s.strip()]
    cfg["languages"] = [s.strip() for s in languages.split(",") if s.strip()]
    cfg["min_stars"] = min_stars
    cfg["max_repos"] = max_repos
    cfg["semantic"]= cfg.get("semantic", {}) | {"topk": semantic_topk, "threshold": semantic_threshold}
    cfg["keywords"] = cfg.get("keywords", {}) | {"query": keyword_query}
    cfg["extract"] = cfg.get("extract", {}) | {
        "min_function_loc": min_function_loc,
        "max_function_loc": max_function_loc,
    }
    cfg["dedup"] = cfg.get("dedup", {}) | {
        "shingle_size": dedup_shingle_size,
        "minhash_permutations": minhash_perms,
    }
    cfg["debug"] = cfg.get("debug", {}) | {
        "test_timeout": test_timeout,
        "worker_parallelism": worker_parallelism,
        "synthetic_bug_budget": synthetic_bug_budget,
    }

    # Discovery: optionally use an existing manifest if provided
    if manifest_path:
        mp = Path(manifest_path)
        if not mp.is_absolute():
            mp = Path.cwd() / mp
        if not mp.exists():
            logger.warning(f"Provided manifest path not found: {mp}. Falling back to discovery.")
            mp = None
        else:
            logger.info(f"Using provided manifest: {mp}")
            manifest_path = mp

    if not manifest_path:
        logger.info("Starting repo discovery…")
        manifest_path = t_discover_repos.submit(
            {
                "semantic_query": semantic_query,
                "keyword_query": keyword_query,
            },
            cfg,
        ).result()

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    logger.info(f"Discovered {len(manifest)} repos; ingesting…")

    # Ingest -> Security gate -> Parse/Extract
    gated_results = []
    for item in manifest[: max_repos]:
        snapshot = t_ingest_repo.submit(item, cfg).result()
        if not isinstance(snapshot, dict) or snapshot.get("status") != "ok":
            logger.warning(f"Skipping repo due to ingest error: {snapshot.get('error') if isinstance(snapshot, dict) else 'unknown'}")
            continue
        gated = t_security_gate.submit(snapshot, cfg).result()
        if gated.get("status") == "ok":
            gated_results.append(gated)

    logger.info(f"{len(gated_results)} repos passed security/license gate; parsing…")

    ast_dirs = []
    for gated in gated_results:
        ast_dir = t_parse_extract.submit(gated, cfg).result()
        ast_dirs.append(ast_dir)

    if not ast_dirs:
        logger.warning("No AST dirs produced; exiting early.")
        return

    # Normalize and dedup across all AST dirs
    norm_info = t_normalize_dedup.submit(Path(cfg["paths"]["ast_dir"]), cfg).result()

    # Build final task datasets
    final_info = t_task_transformers.submit(norm_info, cfg).result()

    # Validate and version
    manifest_path = t_validate_and_version.submit(final_info, norm_info, cfg).result()

    logger.info("Pipeline complete.")
    logger.info(json.dumps({"final": final_info, "manifest": manifest_path}, indent=2))


if __name__ == "__main__":
    # Load environment variables from .env if present
    try:
        load_dotenv()
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Run the SLM pilot data pipeline")
    parser.add_argument("--allowed-licenses", type=str, default="MIT,Apache-2.0,BSD-3-Clause", help="Comma-separated allowlist of licenses")
    parser.add_argument("--languages", type=str, default="python", help="Comma-separated list of languages to include (pilot supports python)")
    parser.add_argument("--min-stars", type=int, default=100, help="Minimum GitHub/GitLab stars for discovery")
    parser.add_argument("--max-repos", type=int, default=5, help="Maximum repositories to process")
    parser.add_argument("--semantic-query", type=str, default="graph algorithms", help="Semantic discovery query text")
    parser.add_argument("--semantic-topk", type=int, default=200, help="Top-K repos to retrieve before thresholding")
    parser.add_argument("--semantic-threshold", type=float, default=0.70, help="Cosine similarity threshold for semantic filtering")
    parser.add_argument("--keyword-query", type=str, default="graph algorithm python", help="Keyword discovery fallback query")
    parser.add_argument("--min-function-loc", type=int, default=5, help="Minimum function LOC to extract")
    parser.add_argument("--max-function-loc", type=int, default=400, help="Maximum function LOC to extract")
    parser.add_argument("--dedup-shingle-size", type=int, default=7, help="Shingle size for near-dup detection")
    parser.add_argument("--minhash-perms", type=int, default=128, help="MinHash permutations for LSH")
    parser.add_argument("--synthetic-bug-budget", type=float, default=0.05, help="Proportion for synthetic bug generation (reserved)")
    parser.add_argument("--test-timeout", type=int, default=600, help="Timeout for running tests (reserved)")
    parser.add_argument("--worker-parallelism", type=int, default=4, help="Parallel workers for debugging step (reserved)")
    parser.add_argument("--config-path", type=str, default=None, help="Path to configs.yml override")
    parser.add_argument("--manifest-path", type=str, default=None, help="Path to an existing discovery manifest JSON to skip discovery")

    args = parser.parse_args()

    # Call the Prefect flow with parsed args
    main(
        allowed_licenses=args.allowed_licenses,
        languages=args.languages,
        min_stars=args.min_stars,
        max_repos=args.max_repos,
        semantic_query=args.semantic_query,
        semantic_topk=args.semantic_topk,
        semantic_threshold=args.semantic_threshold,
        keyword_query=args.keyword_query,
        min_function_loc=args.min_function_loc,
        max_function_loc=args.max_function_loc,
        dedup_shingle_size=args.dedup_shingle_size,
        minhash_perms=args.minhash_perms,
        synthetic_bug_budget=args.synthetic_bug_budget,
        test_timeout=args.test_timeout,
        worker_parallelism=args.worker_parallelism,
        config_path=args.config_path,
    manifest_path=args.manifest_path,
    )
