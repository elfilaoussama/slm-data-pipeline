import os
import ast
import json
from pathlib import Path
from typing import Dict, List

# Tree-sitter optional; pilot uses Python's ast for Python only.


def _list_source_files(repo_path: Path, languages: List[str]) -> List[Path]:
    exts = []
    if 'python' in languages:
        exts += ['.py']
    if 'javascript' in languages:
        exts += ['.js', '.jsx', '.ts', '.tsx']
    files = [p for p in repo_path.rglob('*') if p.suffix.lower() in exts]
    return files


def _extract_python_functions(path: Path, min_loc: int, max_loc: int):
    text = path.read_text(encoding='utf-8', errors='ignore')
    try:
        tree = ast.parse(text)
    except Exception:
        return []
    results = []
    lines = text.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno
            end = getattr(node, 'end_lineno', None) or start
            loc = end - start + 1
            if loc < min_loc or loc > max_loc:
                continue
            snippet = '\n'.join(lines[start-1:end])
            docstring = ast.get_docstring(node)
            results.append({
                'language': 'python',
                'file_path': str(path),
                'start_line': start,
                'end_line': end,
                'loc': loc,
                'code': snippet,
                'docstring': docstring,
            })
    return results


def parse_and_extract(gated_info: Dict, cfg: Dict) -> Path:
    repo_path = Path(gated_info['repo_path'])
    prov = json.loads(Path(gated_info['provenance_path']).read_text(encoding='utf-8'))
    ast_dir = Path(cfg['paths'].get('ast_dir', 'data/processed/ast'))
    ast_dir.mkdir(parents=True, exist_ok=True)

    languages = cfg.get('languages', ['python'])
    min_loc = int(cfg.get('extract', {}).get('min_function_loc', 5))
    max_loc = int(cfg.get('extract', {}).get('max_function_loc', 400))

    outputs = []
    for p in _list_source_files(repo_path, languages):
        if p.suffix.lower() == '.py':
            outputs.extend(_extract_python_functions(p, min_loc, max_loc))
        # Additional languages via tree-sitter can be added here

    # attach provenance
    for rec in outputs:
        rec['provenance'] = {
            'repo_full_name': prov.get('repo_full_name'),
            'source': prov.get('source'),
            'clone_url': prov.get('clone_url'),
            'default_branch': prov.get('default_branch'),
            'commit_sha': prov.get('commit_sha'),
            'commit_date': prov.get('commit_date'),
            'file_path': str(Path(rec['file_path']).relative_to(repo_path)),
            'lines': [rec['start_line'], rec['end_line']],
            'license_spdx': prov.get('license_spdx'),
            'license_text': prov.get('license_text'),
            'scan_tool_versions': prov.get('scan_tool_versions'),
            'scan_timestamp': prov.get('scan_timestamp'),
            'semantic_score': prov.get('semantic_score'),
        }

    out_path = ast_dir / f"{prov.get('repo_full_name').replace('/', '_')}_{prov.get('commit_sha')[:12]}_functions.jsonl"
    with open(out_path, 'w', encoding='utf-8') as f:
        for rec in outputs:
            f.write(json.dumps(rec) + "\n")
    return out_path
