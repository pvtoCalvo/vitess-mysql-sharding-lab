"""Valida configuración localmente contra el CRD fijado, sin necesitar Kubernetes."""
import hashlib
import json
from pathlib import Path
import yaml
from jsonschema import Draft7Validator

ROOT = Path(__file__).resolve().parent
versions = json.loads((ROOT / 'versions.json').read_text())
operator = ROOT / 'k8s/operator.yaml'
assert hashlib.sha256(operator.read_bytes()).hexdigest() == versions['operator_sha256']
docs = list(yaml.safe_load_all(operator.read_text()))
crd = next(d for d in docs if d['kind'] == 'CustomResourceDefinition' and d['metadata']['name'] == 'vitessclusters.planetscale.com')
schema = next(v['schema']['openAPIV3Schema'] for v in crd['spec']['versions'] if v['name'] == 'v2')
validator = Draft7Validator(schema)
operator_deployment = next(d for d in docs if d['kind'] == 'Deployment')
container = operator_deployment['spec']['template']['spec']['containers'][0]
assert container['image'] == 'planetscale/vitess-operator:' + versions['operator']
assert next(e['value'] for e in container['env'] if e['name'] == 'WATCH_NAMESPACE') == 'default,vitess-lab'

for filename in ('01-initial.yaml', '02-customer.yaml', '03-reshard.yaml', '04-final.yaml'):
    documents = list(yaml.safe_load_all((ROOT / 'k8s' / filename).read_text()))
    cluster = documents[0]
    validator.validate(cluster)
    assert cluster['metadata']['namespace'] == 'vitess-lab'
    spec = cluster['spec']
    assert spec['vtadmin']['readOnly'] is True
    for component in ('vtctld', 'vtgate', 'vttablet', 'vtbackup', 'vtorc'):
        assert spec['images'][component] == 'vitess/lite:' + versions['vitess']
    parts = {k['name']: [p['equal']['parts'] for p in k['partitionings']] for k in spec['keyspaces']}
    assert parts['commerce'] == [1]
    if filename == '01-initial.yaml': assert 'customer' not in parts
    elif filename == '02-customer.yaml': assert parts['customer'] == [1]
    elif filename == '03-reshard.yaml': assert parts['customer'] == [1, 2]
    else: assert parts['customer'] == [2]
    print(f'{filename}: CRD y topología correctos')

v = json.loads((ROOT / 'schema/customer-sharded.json').read_text())
s = json.loads((ROOT / 'schema/commerce-sequences.json').read_text())
assert v['sharded'] is True and not s.get('sharded', False)
for name, table in v['tables'].items():
    assert table['column_vindexes'] == [{'column': 'customer_id', 'name': 'hash'}]
    sequence_ks, sequence = table['auto_increment']['sequence'].split('.')
    assert sequence_ks == 'commerce' and s['tables'][sequence]['type'] == 'sequence'
assert (ROOT / 'schema/sequences.sql').read_text().count("COMMENT 'vitess_sequence'") == 2
print('VSchema, secuencias, versiones y checksum correctos')
