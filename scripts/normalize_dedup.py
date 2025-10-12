import json
import hashlib
from pathlib import Path
from typing import Dict, List

from blake3 import blake3
from datasketch import MinHash, MinHashLSH


def _normalize_python(code: str) -> str:
    # Minimal normalization: strip trailing spaces and trim blank lines
    lines = [ln.rstrip() for ln in code.splitlines()]
    # Collapse multiple blank lines
    out = []
    blank = 0
    for ln in lines:
        if ln.strip() == '':
            blank += 1
            if blank > 1:
                continue
        else:
            blank = 0
        out.append(ln)
    norm = '\n'.join(out).strip() + '\n'
    return norm


def _hash_text(text: str) -> str:
    return blake3(text.encode('utf-8')).hexdigest()


def _shingles(tokens: List[str], k: int) -> List[str]:
    return [' '.join(tokens[i:i+k]) for i in range(max(0, len(tokens)-k+1))]


def normalize_and_dedup(ast_dir: Path, cfg: Dict) -> Dict:
    ast_dir = Path(ast_dir)
    items = []
    for p in ast_dir.glob('*_functions.jsonl'):
        with open(p, 'r', encoding='utf-8') as f:
            for line in f:
                rec = json.loads(line)
                if rec.get('language') == 'python':
                    rec['code_norm'] = _normalize_python(rec['code'])
                else:
                    rec['code_norm'] = rec['code']
                rec['exact_hash'] = _hash_text(rec['code_norm'])
                items.append(rec)

    # Exact dedup
    seen = {}
    uniq = []
    for rec in items:
        h = rec['exact_hash']
        if h in seen:
            continue
        seen[h] = True
        uniq.append(rec)

    # Near dedup using MinHash LSH
    shingle_k = int(cfg.get('dedup', {}).get('shingle_size', 7))
    perms = int(cfg.get('dedup', {}).get('minhash_permutations', 128))
    lsh_threshold = float(cfg.get('dedup', {}).get('lsh_threshold', 0.85))

    lsh = MinHashLSH(threshold=lsh_threshold, num_perm=perms)
    mh_list = []
    for idx, rec in enumerate(uniq):
        tokens = rec['code_norm'].split()
        shingles = _shingles(tokens, shingle_k)
        m = MinHash(num_perm=perms)
        for s in shingles:
            m.update(s.encode('utf-8'))
        mh_list.append(m)
        lsh.insert(str(idx), m)

    # Filter near duplicates by keeping first in each LSH bucket cluster
    kept = []
    dropped = set()
    for i, m in enumerate(mh_list):
        if i in dropped:
            continue
        neighbors = lsh.query(m)
        for n in neighbors:
            j = int(n)
            if j != i:
                dropped.add(j)
        kept.append(uniq[i])

    out = {
        'total': len(items),
        'exact_unique': len(uniq),
        'near_unique': len(kept),
        'kept_records_path': str(ast_dir / 'kept_records.jsonl')
    }

    with open(ast_dir / 'kept_records.jsonl', 'w', encoding='utf-8') as f:
        for rec in kept:
            f.write(json.dumps(rec) + '\n')

    return out
