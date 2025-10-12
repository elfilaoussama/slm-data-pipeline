# Data schemas

Schemas live in `schemas/`. The validator checks all final JSONL shards.

- `completion.schema.json`
- `documentation.schema.json`
- `refactor.schema.json`
- `debugging.schema.json`
- `provenance.schema.json` (nested)

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
