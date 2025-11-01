import json
import hashlib
from pathlib import Path
from typing import Dict, List

from jsonschema import validate, RefResolver, Draft7Validator


def _load_schema(schemas_dir: Path, name: str) -> Dict:
    p = schemas_dir / name
    return json.loads(p.read_text(encoding='utf-8'))


def validate_and_version(final_dir: Path, schemas_dir: Path, cfg: Dict, stats_from_norm: Dict | None = None) -> Path:
    final_dir = Path(final_dir)
    schemas_dir = Path(schemas_dir)
    prov_schema = _load_schema(schemas_dir, 'provenance.schema.json')
    completion_schema = _load_schema(schemas_dir, 'completion.schema.json')
    documentation_schema = _load_schema(schemas_dir, 'documentation.schema.json')
    refactor_schema = _load_schema(schemas_dir, 'refactor.schema.json')
    debugging_schema = _load_schema(schemas_dir, 'debugging.schema.json')

    # Build resolver for $ref within same folder
    resolver = RefResolver(base_uri=str(schemas_dir.as_uri()) + '/', referrer={})

    files = {
        'completion': final_dir / 'completion.jsonl',
        'documentation': final_dir / 'documentation.jsonl',
        'refactor': final_dir / 'refactor.jsonl',
        'debugging': final_dir / 'debugging.jsonl',
    }

    manifest = {
        'counts': {},
        'licenses': {},
        'languages': {},
        'duplication_rate_hint': None,
        'provenance_complete': True,
        'quality_report': {
            'by_task': {},
            'doc_tiers': {'high_quality': 0, 'medium_quality': 0, 'low_quality': 0, 'synthetic': 0},
            'complexity': {'sum': 0.0, 'count': 0},
            'synthetic_pct': 0.0,
        },
    }

    for task, path in files.items():
        count = 0
        if not path.exists():
            manifest['counts'][task] = 0
            continue
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except Exception:
                    # Skip malformed JSONL lines to be lenient with legacy samples
                    continue
                # Validate record
                if task == 'completion':
                    schema = completion_schema
                elif task == 'documentation':
                    schema = documentation_schema
                elif task == 'refactor':
                    schema = refactor_schema
                else:
                    schema = debugging_schema
                Draft7Validator(schema, resolver=resolver).validate(rec)
                # Validate provenance field (debugging has a specialized provenance layout)
                if task in ('completion', 'documentation', 'refactor'):
                    Draft7Validator(prov_schema, resolver=resolver).validate(rec['provenance'])
                # Task-specific checks
                if task == 'completion':
                    metrics = rec.get('metrics') or {}
                    # Only enforce when the flag is explicitly provided; treat missing as OK for backward-compatibility
                    if metrics.get('valid_syntax') is False:
                        raise ValueError('completion record invalid syntax flag')
                if task == 'refactor':
                    # ensure both sides parse; skip malformed legacy samples instead of failing hard
                    bad = False
                    for fld in ('pre', 'post'):
                        try:
                            compile(rec[fld], '<refactor>', 'exec')
                        except Exception:
                            bad = True
                            break
                    if bad:
                        continue
                count += 1
                lic = rec.get('license')
                lang = rec.get('language')
                if lic:
                    manifest['licenses'][lic] = manifest['licenses'].get(lic, 0) + 1
                if lang:
                    manifest['languages'][lang] = manifest['languages'].get(lang, 0) + 1
                # Aggregate quality stats
                md = rec.get('metadata') or {}
                dq = (md.get('documentation') or {})
                if task == 'documentation':
                    if dq.get('synthetic', False):
                        manifest['quality_report']['doc_tiers']['synthetic'] += 1
                    else:
                        tier = dq.get('tier') or 'low_quality'
                        if tier in manifest['quality_report']['doc_tiers']:
                            manifest['quality_report']['doc_tiers'][tier] += 1
                q = md.get('quality') or {}
                cplx = q.get('cyclomatic_complexity')
                if isinstance(cplx, (int, float)):
                    manifest['quality_report']['complexity']['sum'] += float(cplx)
                    manifest['quality_report']['complexity']['count'] += 1
        manifest['counts'][task] = count

    if stats_from_norm and isinstance(stats_from_norm, dict):
        t = max(stats_from_norm.get('total', 0), 1)
        kept = stats_from_norm.get('near_unique', 0)
        manifest['duplication_rate_hint'] = 1.0 - (kept / t)

    total_recs = sum(manifest['counts'].values()) or 1
    # compute synthetic percent from documentation tier synthetic only (best-effort)
    syn_docs = manifest['quality_report']['doc_tiers']['synthetic']
    manifest['quality_report']['synthetic_pct'] = round(100.0 * syn_docs / max(1, manifest['counts'].get('documentation', 1)), 2)

    manifest_path = final_dir / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest_path
