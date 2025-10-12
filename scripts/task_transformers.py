import json
import uuid
import difflib
from pathlib import Path
from typing import Dict


def _lang_from_path(p: str) -> str:
    if p.endswith('.py'):
        return 'python'
    return 'unknown'


def _maybe_black_format(code: str) -> tuple[str, str]:
    """Return (post_code, refactor_type). Uses Black if available; else a noop or minimal spacing tweak."""
    try:
        import black  # type: ignore

        mode = black.FileMode()
        formatted = black.format_file_contents(code, fast=True, mode=mode)
        if formatted != code:
            return formatted, 'formatting_black'
        # If Black results same, perform a tiny deterministic whitespace change then revert to stay idempotent
        # Keep identical to avoid introducing noise
        return code, 'formatting_black_noop'
    except Exception:
        # Minimal refactor: collapse double blank lines to single (idempotent with our normalizer)
        lines = code.splitlines()
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
        post = '\n'.join(out)
        return (post if post else code), 'formatting_minimal'


def _unified_diff(a: str, b: str, file_hint: str = 'code.py') -> str:
    a_lines = a.splitlines(keepends=True)
    b_lines = b.splitlines(keepends=True)
    diff = difflib.unified_diff(a_lines, b_lines, fromfile=f"a/{file_hint}", tofile=f"b/{file_hint}")
    return ''.join(diff)


def _inject_simple_bug(code: str) -> tuple[str, str]:
    """Make a tiny deterministic mutation for a synthetic bug. Returns (buggy_code, mutation_type)."""
    # Try a safe operator flip first
    replacements = [
        ('==', '!='),
        ('!=', '=='),
        ('>=', '>'),
        ('<=', '<'),
        (' True', ' False'),
        (' False', ' True'),
    ]
    for old, new in replacements:
        if old in code:
            return code.replace(old, new, 1), f"mutate_{old.strip()}_to_{new.strip()}"
    # As a last resort, append a no-op statement that might still be harmless
    return (code + "\n# FIXME: synthetic bug marker\n"), 'append_comment'


def build_task_datasets(norm_info: Dict, cfg: Dict) -> Dict:
    ast_dir = Path(cfg['paths'].get('ast_dir', 'data/processed/ast'))
    final_dir = Path(cfg['paths'].get('final_dir', 'data/final'))
    final_dir.mkdir(parents=True, exist_ok=True)

    kept_path = ast_dir / 'kept_records.jsonl'
    records = []
    if kept_path.exists():
        with open(kept_path, 'r', encoding='utf-8') as f:
            for line in f:
                records.append(json.loads(line))

    # Completion: create prefix->completion masks
    completion_out = final_dir / 'completion.jsonl'
    with open(completion_out, 'w', encoding='utf-8') as fo:
        for rec in records:
            code = rec['code_norm']
            lines = code.strip('\n').splitlines()
            for N in (1, 3, 10):
                if len(lines) > N:
                    prefix = '\n'.join(lines[:-N]) + '\n'
                    completion = '\n'.join(lines[-N:]) + '\n'
                    out = {
                        'id': str(uuid.uuid4()),
                        'task': 'completion',
                        'language': rec.get('language', _lang_from_path(rec['file_path'])),
                        'license': rec.get('provenance', {}).get('license_spdx'),
                        'provenance': rec.get('provenance'),
                        'input': {'prefix': prefix},
                        'output': {'completion': completion},
                        'metrics': {},
                        'synthetic': False,
                    }
                    fo.write(json.dumps(out) + '\n')

    # Documentation: use existing docstrings when present
    docs_out = final_dir / 'documentation.jsonl'
    with open(docs_out, 'w', encoding='utf-8') as fo:
        for rec in records:
            doc = rec.get('docstring')
            code = rec['code_norm']
            if doc and isinstance(doc, str) and doc.strip():
                out = {
                    'id': str(uuid.uuid4()),
                    'task': 'documentation',
                    'language': rec.get('language', _lang_from_path(rec['file_path'])),
                    'license': rec.get('provenance', {}).get('license_spdx'),
                    'provenance': rec.get('provenance'),
                    'code': code,
                    'docstring': doc,
                    'source': 'docstring',
                    'synthetic': False,
                }
                fo.write(json.dumps(out) + '\n')
            else:
                # Heuristic summary
                first_line = code.split('\n', 1)[0][:200]
                out = {
                    'id': str(uuid.uuid4()),
                    'task': 'documentation',
                    'language': rec.get('language', _lang_from_path(rec['file_path'])),
                    'license': rec.get('provenance', {}).get('license_spdx'),
                    'provenance': rec.get('provenance'),
                    'code': code,
                    'docstring': f"Function: {first_line}",
                    'source': 'heuristic',
                    'synthetic': True,
                }
                fo.write(json.dumps(out) + '\n')

    # Refactor: create pre/post with formatting-based changes when available
    refactor_out = final_dir / 'refactor.jsonl'
    with open(refactor_out, 'w', encoding='utf-8') as fo:
        for rec in records:
            pre = rec['code_norm']
            post, rf_type = _maybe_black_format(pre)
            diff = _unified_diff(pre, post, Path(rec['file_path']).name)
            out = {
                'id': str(uuid.uuid4()),
                'task': 'refactor',
                'language': rec.get('language', _lang_from_path(rec['file_path'])),
                'provenance': rec.get('provenance'),
                'pre': pre,
                'post': post,
                'diff': diff,
                'refactor_type': rf_type,
                'verified': False,
                'synthetic': True,
            }
            fo.write(json.dumps(out) + '\n')

    # Debugging: inject a small bug and pair with original as the fix
    dbg_out = final_dir / 'debugging.jsonl'
    with open(dbg_out, 'w', encoding='utf-8') as fo:
        for rec in records:
            fixed = rec['code_norm']
            buggy, mut_type = _inject_simple_bug(fixed)
            diff = _unified_diff(buggy, fixed, Path(rec['file_path']).name)
            prov = rec.get('provenance') or {}
            dbg_prov = {
                'pre_commit': prov.get('commit_sha') or 'synthetic',
                'post_commit': prov.get('commit_sha') or 'synthetic',
                'repo_full_name': prov.get('repo_full_name') or 'unknown'
            }
            out = {
                'id': str(uuid.uuid4()),
                'task': 'debugging',
                'language': rec.get('language', _lang_from_path(rec['file_path'])),
                'license': prov.get('license_spdx'),
                'provenance': dbg_prov,
                'pre_snippet': buggy,
                'post_snippet': fixed,
                'diff': diff,
                'failing_tests': [],
                'stack_trace': [],
                'synthetic': True,
            }
            fo.write(json.dumps(out) + '\n')

    return {
        'completion': str(completion_out),
        'documentation': str(docs_out),
        'refactor': str(refactor_out),
        'debugging': str(dbg_out),
    }
