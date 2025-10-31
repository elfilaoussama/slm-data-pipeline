"""
Commit mining utilities for building debugging/refactor pairs from VCS history.

This module extracts lightweight commit diff records from a git repository using GitPython.
It focuses on Python files and modified diffs, returning unified diffs and metadata that
can later be transformed into training pairs.
"""

from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime

from git import Repo


def _safe_text(b: bytes) -> str:
    try:
        return b.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def mine_commit_pairs(
    repo_path: str,
    heuristics: Optional[Dict] = None,
    max_commits: int = 200,
    include_exts: Optional[List[str]] = None,
) -> List[Dict]:
    """
    Mine recent commit diffs and return lightweight records.

    Inputs:
    - repo_path: path to a local git repository (already cloned)
    - heuristics: reserved for future filters (e.g., keywords in messages)
    - max_commits: limit the number of commits to scan from HEAD
    - include_exts: file extensions to include (default: ['.py'])

    Output records:
    - {
        'repo': str,
        'commit': str,
        'parent': str,
        'author': str,
        'date': iso8601 str,
        'message': str,
        'file_path': str,
        'change_type': str,
        'diff': unified diff text,
      }
    """
    include_exts = include_exts or [".py"]
    repo = Repo(Path(repo_path))
    head = repo.head.commit
    records: List[Dict] = []

    commits = list(repo.iter_commits(head, max_count=max_commits))
    for commit in commits:
        if not commit.parents:
            continue
        parent = commit.parents[0]
        try:
            diffs = parent.diff(commit, create_patch=True)
        except Exception:
            continue
        for d in diffs:
            try:
                a_path = d.a_path or ""
                b_path = d.b_path or ""
                path = b_path or a_path
                if include_exts and not any(path.lower().endswith(ext) for ext in include_exts):
                    continue
                change = d.change_type  # 'A','M','D','R', etc.
                diff_txt = _safe_text(d.diff or b"")
                rec = {
                    "repo": str(Path(repo_path).resolve()),
                    "commit": commit.hexsha,
                    "parent": parent.hexsha,
                    "author": str(getattr(commit, "author", "") or ""),
                    "date": datetime.utcfromtimestamp(commit.committed_date).isoformat(),
                    "message": commit.message.strip() if commit.message else "",
                    "file_path": path,
                    "change_type": change,
                    "diff": diff_txt,
                }
                records.append(rec)
            except Exception:
                continue
    return records

