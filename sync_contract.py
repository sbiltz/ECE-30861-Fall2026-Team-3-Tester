"""Regenerate the optional JSON compatibility copy after updating canonical YAML."""
import json
from suite import ROOT, SPEC, json_schema

if __name__ == '__main__':
    (ROOT/'shared-openapi.json').write_text(json.dumps(json_schema(SPEC), indent=2)+'\n', encoding='utf-8')
    print('Generated shared-openapi.json from shared-openapi.yaml', SPEC['info']['version'])
