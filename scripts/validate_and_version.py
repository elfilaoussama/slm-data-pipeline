import json
import hashlib
from pathlib import Path
from typing import Dict

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
    }

    for task, path in files.items():
        count = 0
        if not path.exists():
            manifest['counts'][task] = 0
            continue
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                rec = json.loads(line)
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
                count += 1
                lic = rec.get('license')
                lang = rec.get('language')
                if lic:
                    manifest['licenses'][lic] = manifest['licenses'].get(lic, 0) + 1
                if lang:
                    manifest['languages'][lang] = manifest['languages'].get(lang, 0) + 1
        manifest['counts'][task] = count

    if stats_from_norm and isinstance(stats_from_norm, dict):
        t = max(stats_from_norm.get('total', 0), 1)
        kept = stats_from_norm.get('near_unique', 0)
        manifest['duplication_rate_hint'] = 1.0 - (kept / t)

    manifest_path = final_dir / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest_path
