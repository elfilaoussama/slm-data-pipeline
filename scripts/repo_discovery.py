import os
import re
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

import requests
import hashlib
import numpy as np
from github import Github
import gitlab
# Load .env early so GH_TOKENS / GL_TOKEN are available even when running this module directly
try:
    from dotenv import load_dotenv, find_dotenv  # type: ignore
    # Prefer a discovered .env (searches from CWD upward); fall back to slm-pipeline/.env
    dotenv_path = find_dotenv(usecwd=True)
    if dotenv_path:
        load_dotenv(dotenv_path=dotenv_path)
    else:
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except Exception:
    # If python-dotenv isn't available or load fails, continue; callers may have loaded env already
    pass
try:
    from sentence_transformers import SentenceTransformer  # optional
except Exception:
    SentenceTransformer = None

CACHE_DIR = Path('.cache')
CACHE_DIR.mkdir(parents=True, exist_ok=True)
EMB_CACHE = CACHE_DIR / 'embeddings'
EMB_CACHE.mkdir(parents=True, exist_ok=True)


def _get_github_client():
    tokens = os.getenv('GH_TOKENS', '')
    token_list = [t.strip() for t in tokens.split(',') if t.strip()]
    if token_list:
        # Use first token; rotation can be added later
        return Github(token_list[0], per_page=50)
    return Github(per_page=50)


def _get_gitlab_client():
    gl_token = os.getenv('GL_TOKEN')
    if gl_token:
        return gitlab.Gitlab('https://gitlab.com', private_token=gl_token)
    return gitlab.Gitlab('https://gitlab.com')


def _load_model(model_name: str):
    try:
        if SentenceTransformer is None:
            return None
        return SentenceTransformer(model_name)
    except Exception:
        return None


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _embed_texts(model, texts: List[str]):
    if not model:
        return None
    embs = []
    for t in texts:
        h = _text_hash(t)
        fp = EMB_CACHE / f"{h}.npy"
        if fp.exists():
            try:
                embs.append(np.load(fp))
                continue
            except Exception:
                pass
        e = model.encode([t], convert_to_numpy=True, show_progress_bar=False)[0]
        try:
            np.save(fp, e)
        except Exception:
            pass
        embs.append(e)
    return np.vstack(embs)


def _readme_head(text: str, n_chars: int = 2000) -> str:
    return text[:n_chars] if text else ''


def _gh_search(keyword_query: str, min_stars: int, language_filters: List[str], max_items: int = 100) -> List[Dict]:
    """Search GitHub with proper OR semantics for languages and paginate until max_items."""
    gh = _get_github_client()
    qualifiers = []
    if min_stars:
        qualifiers.append(f"stars:>={min_stars}")
    base_q = f"{keyword_query} " + ' '.join(qualifiers)
    langs = language_filters or []
    # GitHub search does not support multiple language: qualifiers as OR; run per-language if provided
    language_queries = langs if langs else [None]
    seen = set()
    out: List[Dict] = []
    try:
        for lang in language_queries:
            q = base_q if not lang else f"{base_q} language:{lang}"
            # sort by stars to get most relevant first
            pl = gh.search_repositories(query=q, sort="stars", order="desc")
            count = 0
            for repo in pl:  # iterate paginated list
                key = ("github", repo.full_name)
                if key in seen:
                    continue
                seen.add(key)
                try:
                    license_hint = repo.license.spdx_id if getattr(repo, 'license', None) else None
                except Exception:
                    license_hint = None
                try:
                    topics = repo.get_topics()  # may require preview header; handled by PyGithub internally
                except Exception:
                    topics = []
                out.append({
                    'source': 'github',
                    'repo_full_name': repo.full_name,
                    'clone_url': repo.clone_url,
                    'default_branch': getattr(repo, 'default_branch', None) or 'main',
                    'stars': getattr(repo, 'stargazers_count', 0) or 0,
                    'license_hint': license_hint,
                    'url': repo.html_url,
                    'description': repo.description or '',
                    'topics': topics or [],
                })
                count += 1
                if len(out) >= max_items:
                    return out
                # Light pacing to be gentle on API if unauthenticated
                if count % 50 == 0:
                    time.sleep(0.5)
    except Exception:
        # Swallow to keep discovery resilient; downstream will continue with what we have
        pass
    return out


def _gl_search(keyword_query: str, min_stars: int, language_filters: List[str], max_items: int = 100) -> List[Dict]:
    """Search GitLab public projects; use iterator pagination and try languages endpoint when filtering."""
    gl = _get_gitlab_client()
    out: List[Dict] = []
    seen = set()
    try:
        # iterator=True to paginate lazily
        projects = gl.projects.list(search=keyword_query, visibility='public', per_page=50, iterator=True)
        for proj in projects:
            try:
                key = ("gitlab", proj.path_with_namespace)
                if key in seen:
                    continue
                star_count = getattr(proj, 'star_count', 0) or 0
                if min_stars and star_count < min_stars:
                    continue
                # Language filter: prefer API endpoint; fallback to heuristic on topics/description
                lang_ok = True
                if language_filters:
                    try:
                        langs_map = proj.languages()  # {'Python': 87.0, ...}
                        langs_keys = {k.lower() for k in (langs_map or {}).keys()}
                        lang_ok = any(l.lower() in langs_keys for l in language_filters)
                    except Exception:
                        topics = getattr(proj, 'tag_list', []) or []
                        hay = (proj.description or '') + ' ' + ' '.join(topics)
                        lang_ok = any(l.lower() in hay.lower() for l in language_filters)
                if not lang_ok:
                    continue

                license_hint = None
                try:
                    lic = getattr(proj, 'license', None)
                    if isinstance(lic, dict):
                        license_hint = lic.get('spdx_id') or lic.get('key') or lic.get('name')
                    else:
                        license_hint = lic
                except Exception:
                    license_hint = None

                out.append({
                    'source': 'gitlab',
                    'repo_full_name': proj.path_with_namespace,
                    'clone_url': proj.http_url_to_repo,
                    'default_branch': getattr(proj, 'default_branch', None) or 'main',
                    'stars': star_count,
                    'license_hint': license_hint,
                    'url': proj.web_url,
                    'description': proj.description or '',
                    'topics': getattr(proj, 'tag_list', []) or [],
                })
                seen.add(key)
                if len(out) >= max_items:
                    break
            except Exception:
                continue
    except Exception:
        pass
    return out


def _fetch_readme_preview(item: Dict) -> str:
    """Try several common README names, cache locally to avoid repeated fetches."""
    cache_p = CACHE_DIR / f"readme_{item['source'].lower()}_{item['repo_full_name'].replace('/', '_')}.txt"
    if cache_p.exists():
        try:
            return cache_p.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            pass
    text = ''
    names = ["README.md", "README.rst", "README", "readme.md", "Readme.md"]
    base = None
    if item['source'] == 'github':
        base = f"https://raw.githubusercontent.com/{item['repo_full_name']}/{item['default_branch']}"
    else:
        base = f"https://gitlab.com/{item['repo_full_name']}/-/raw/{item['default_branch']}"
    for nm in names:
        try:
            resp = requests.get(f"{base}/{nm}", timeout=10)
            if resp.status_code == 200 and resp.text:
                text = resp.text
                break
        except Exception:
            continue
    try:
        cache_p.parent.mkdir(parents=True, exist_ok=True)
        cache_p.write_text(text, encoding='utf-8')
    except Exception:
        pass
    return text


def discover_repos(params: Dict, cfg: Dict) -> Path:
    out_dir = Path(cfg['paths'].get('manifests_dir', 'manifests'))
    out_dir.mkdir(parents=True, exist_ok=True)
    semantic_cfg = cfg.get('semantic', {})
    languages = cfg.get('languages', ['python'])
    min_stars = int(cfg.get('min_stars', 0))
    max_repos = int(cfg.get('max_repos', 50))

    keyword_query = params.get('keyword_query') or cfg.get('keywords', {}).get('query', '')
    items: List[Dict] = []
    # Pull from both sources and deduplicate by (source, repo_full_name)
    max_per_source = int(semantic_cfg.get('topk', 200))
    gh_items = _gh_search(keyword_query, min_stars, languages, max_items=max_per_source)
    gl_items = _gl_search(keyword_query, min_stars, languages, max_items=max_per_source)
    seen_pairs = set()
    for it in gh_items + gl_items:
        key = (it['source'], it['repo_full_name'])
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        items.append(it)

    # Build corpus texts for semantic ranking
    texts = []
    for it in items:
        readme = _readme_head(_fetch_readme_preview(it), 2000)
        it['readme_head'] = readme
        texts.append(f"{it['repo_full_name']}\n{it.get('description','')}\n{' '.join(it.get('topics',[]))}\n{readme}")

    model_name = semantic_cfg.get('model', 'all-MiniLM-L6-v2')
    model = _load_model(model_name)
    semantic_query = params.get('semantic_query', '')
    threshold = float(semantic_cfg.get('threshold', 0.7))

    scores = []
    if model and semantic_query and items:
        emb_items = _embed_texts(model, texts)
        emb_query = _embed_texts(model, [semantic_query])
        if emb_items is not None and emb_query is not None:
            # cosine via numpy
            a = emb_items
            b = emb_query[0]
            b = b / (np.linalg.norm(b) + 1e-8)
            a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-8)
            sims = a_norm @ b
            scores = sims.tolist()
    # If scores empty, fallback rank by stars
    for idx, it in enumerate(items):
        it['semantic_score'] = float(scores[idx]) if scores else None
        it['fetch_timestamp'] = datetime.utcnow().isoformat()
    if scores:
        filtered = [it for it in items if it['semantic_score'] is not None and it['semantic_score'] >= threshold]
        filtered.sort(key=lambda x: x['semantic_score'], reverse=True)
    else:
        filtered = sorted(items, key=lambda x: x.get('stars', 0), reverse=True)
    filtered = filtered[:max_repos]

    out_path = out_dir / 'discovered_repos.json'
    out_path.write_text(json.dumps(filtered, indent=2), encoding='utf-8')
    return out_path
