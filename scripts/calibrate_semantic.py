import json
import random
from pathlib import Path
from typing import List, Dict

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None  # type: ignore
try:
    import numpy as np
except Exception:
    np = None  # type: ignore
try:
    from sklearn.metrics.pairwise import cosine_similarity  # type: ignore
except Exception:
    cosine_similarity = None  # type: ignore


def calibrate(queries: List[str], candidates: List[Dict], topk: int = 200) -> Dict:
    if SentenceTransformer is None or np is None or cosine_similarity is None:
        # Fallback heuristic if dependencies unavailable
        return {"threshold": 0.7, "p10": 0.0}
    model = SentenceTransformer('all-MiniLM-L6-v2')
    texts = [f"{c['repo_full_name']}\n{c.get('description','')}\n{' '.join(c.get('topics',[]))}\n{c.get('readme_head','')}" for c in candidates]
    emb_items = model.encode(texts, convert_to_numpy=True)
    precision_at_10 = []
    thresholds = np.linspace(0.5, 0.9, 9)
    best = {'threshold': 0.7, 'p10': 0.0}
    for q in queries:
        emb_q = model.encode([q], convert_to_numpy=True)
        sims = cosine_similarity(emb_items, emb_q)[...,0]
        # assume top-10 relevant are the top-10 by similarity as a proxy for pilot
        idx_sorted = np.argsort(-sims)
        top10 = set(idx_sorted[:10].tolist())
        for th in thresholds:
            kept = {i for i,s in enumerate(sims) if s >= th}
            if not kept:
                continue
            # proxy P@10: of the 10 highest sims, how many are above threshold
            p10 = len(top10 & kept) / 10.0
            if p10 > best['p10']:
                best = {'threshold': float(th), 'p10': float(p10)}
    return best


if __name__ == '__main__':
    # Minimal demo with synthetic candidates
    candidates = []
    for i in range(100):
        candidates.append({'repo_full_name': f'org/repo{i}', 'description': 'graph algorithms in python', 'topics': ['graph','python'], 'readme_head': 'Dijkstra and BFS'})
        candidates.append({'repo_full_name': f'org/repoX{i}', 'description': 'web app project', 'topics': ['web'], 'readme_head': 'Flask app'})
    queries = [
        'python graph shortest path',
        'graph traversal BFS DFS',
        'networkx graph algorithms'
    ]
    print(json.dumps(calibrate(queries, candidates), indent=2))
