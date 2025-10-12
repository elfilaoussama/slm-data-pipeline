import os
import io
import tarfile
import json
from pathlib import Path
from datetime import datetime
from typing import Dict

import hashlib
from git import Repo, exc as git_exc


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def ingest_repo(item: Dict, cfg: Dict) -> Dict:
    raw_dir = Path(cfg['paths'].get('raw_dir', 'data/raw'))
    raw_dir.mkdir(parents=True, exist_ok=True)
    repo_url = item['clone_url']
    default_branch = item.get('default_branch', 'main')

    # Clone shallow by default
    work_dir = raw_dir / f"{item['repo_full_name'].replace('/', '_')}"
    work_dir.mkdir(parents=True, exist_ok=True)

    repo_path = work_dir / 'repo'

    def _safe_clone():
        return Repo.clone_from(repo_url, repo_path, depth=1, branch=default_branch)

    repo = None
    try:
        if repo_path.exists():
            # If exists but not a valid repo (e.g., previous failed clone), clean it
            try:
                repo = Repo(repo_path)
            except Exception:
                # remove and reclone
                try:
                    for child in repo_path.rglob('*'):
                        try:
                            if child.is_file() or child.is_symlink():
                                child.unlink(missing_ok=True)
                        except Exception:
                            pass
                    # remove empty dirs
                    for child in sorted(repo_path.rglob('*'), reverse=True):
                        if child.is_dir():
                            try:
                                child.rmdir()
                            except Exception:
                                pass
                    repo_path.rmdir()
                except Exception:
                    pass
                repo_path.mkdir(parents=True, exist_ok=True)
                repo = _safe_clone()
        else:
            repo = _safe_clone()
    except git_exc.GitCommandError as e:
        return {
            'status': 'error',
            'error': f'git clone failed: {e}',
            'item': item,
        }

    if repo is None:
        # Attempt to open repo if clone path existed and was valid
        try:
            repo = Repo(repo_path)
        except Exception as e:
            return {
                'status': 'error',
                'error': f'invalid git repo at {repo_path}: {e}',
                'item': item,
            }
    sha = repo.head.commit.hexsha

    # Tar snapshot
    tar_name = f"{item['repo_full_name'].replace('/', '_')}-{sha[:12]}.tar.gz"
    tar_path = raw_dir / tar_name
    with tarfile.open(tar_path, 'w:gz') as tar:
        tar.add(repo_path, arcname=f"{item['repo_full_name'].replace('/', '_')}@{sha[:12]}")

    # Compute per-file hashes and provenance base
    file_hashes = {}
    for p in repo_path.rglob('*'):
        if p.is_file():
            try:
                file_hashes[str(p.relative_to(repo_path))] = _sha256_file(p)
            except Exception:
                continue

    provenance = {
        'repo_full_name': item['repo_full_name'],
        'source': item['source'],
        'clone_url': item['clone_url'],
        'default_branch': default_branch,
        'commit_sha': sha,
        'commit_date': datetime.utcfromtimestamp(repo.head.commit.committed_date).isoformat(),
        'license_spdx': item.get('license_hint'),
        'license_text': None,  # filled after ScanCode
        'scan_tool_versions': {},
        'scan_timestamp': None,
        'semantic_score': item.get('semantic_score'),
        'snapshot_tar': str(tar_path),
        'file_hashes': file_hashes,
    }

    prov_path = work_dir / 'provenance.json'
    prov_path.write_text(json.dumps(provenance, indent=2), encoding='utf-8')

    return {
        'status': 'ok',
        'work_dir': str(work_dir),
        'repo_path': str(repo_path),
        'tar_path': str(tar_path),
        'provenance_path': str(prov_path),
        'item': item,
    }
