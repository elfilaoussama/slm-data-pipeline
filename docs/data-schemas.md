# Data schemas

[Back to Pipeline stages](pipeline-stages.md) · [Quickstart](../QUICKSTART.md) · [Configuration](configuration.md)

JSONL outputs live in `data/final/`:

- `completion.jsonl`
- `documentation.jsonl`
- `refactor.jsonl`
- `debugging.jsonl`

Schemas live in [`schemas/`](../schemas/):

- [completion.schema.json](../schemas/completion.schema.json)
- [documentation.schema.json](../schemas/documentation.schema.json)
- [refactor.schema.json](../schemas/refactor.schema.json)
- [debugging.schema.json](../schemas/debugging.schema.json)
- [provenance.schema.json](../schemas/provenance.schema.json) (nested)

Validate manually (example):
```
python - << 'PY'
from jsonschema import Draft7Validator
import json, sys
sch = json.load(open('schemas/completion.schema.json'))
for i,l in enumerate(open('data/final/completion.jsonl','r',encoding='utf-8')):
    Draft7Validator(sch).validate(json.loads(l))
print('ok')
PY
```

See [Pipeline stages](pipeline-stages.md) for where each file is produced and [scripts/validate_and_version.py](../scripts/validate_and_version.py) for validation.
