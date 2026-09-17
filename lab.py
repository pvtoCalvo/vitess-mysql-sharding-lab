#!/usr/bin/env python3
"""Laboratorio Vitess 24. Python 3.10+, kubectl y un perfil Minikube dedicado."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTEXT = 'vitess-lab'
NAMESPACE = 'vitess-lab'
WORKFLOWS = {'move': ('MoveTables', 'commerce2customer'),
             'reshard': ('Reshard', 'customer2shards')}


def run(args, *, capture=False, input_text=None, timeout=900):
    """Sin shell: ni SQL ni argumentos pasan por expansión de comandos."""
    result = subprocess.run(args, input=input_text, text=True, check=True,
                            stdout=subprocess.PIPE if capture else None,
                            timeout=timeout)
    return result.stdout.strip() if capture else ''


def kubectl(*args, **kwargs):
    return run(['kubectl', '--context', CONTEXT, '-n', NAMESPACE, *args], **kwargs)


def object_name(kind, component):
    selector = f'planetscale.com/cluster=example,planetscale.com/component={component}'
    if kind == 'service' and component == 'vtgate':
        selector += ',!planetscale.com/cell'
    data = json.loads(kubectl('get', kind, '-l', selector, '-o', 'json', capture=True))
    items = data['items']
    if kind == 'pod':
        items = [p for p in items if not p['metadata'].get('deletionTimestamp') and
                 any(c.get('type') == 'Ready' and c.get('status') == 'True'
                     for c in p.get('status', {}).get('conditions', []))]
    if len(items) != 1:
        raise RuntimeError(f'Se esperaba un {kind} {component} listo; encontrados: {len(items)}. Ejecuta status.')
    return items[0]['metadata']['name']


def vt(*args, capture=False):
    return kubectl('exec', object_name('pod', 'vtctld'), '-c', 'vtctld', '--',
                   'vtctldclient', '--server', 'localhost:15999', *args, capture=capture)


def mysql(sql, database='commerce', capture=False):
    # El cliente y vtctldclient proceden de la misma imagen fijada que el servidor.
    return kubectl('exec', '-i', object_name('pod', 'vtctld'), '-c', 'vtctld', '--',
                   'mysql', '--protocol=TCP', '-h', object_name('service', 'vtgate'),
                   '-P', '3306', '-u', 'user', '--batch', '--skip-column-names',
                   database, input_text=sql, capture=capture)


def apply(filename):
    kubectl('apply', '-f', str(ROOT / 'k8s' / filename))


def apply_schema(filename, keyspace):
    vt('ApplySchema', '--sql', (ROOT / 'schema' / filename).read_text(), keyspace)


def apply_vschema(filename, keyspace):
    vt('ApplyVSchema', '--vschema', (ROOT / 'schema' / filename).read_text(), keyspace)


def wait_primary(keyspace, shard, timeout=600):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            data = json.loads(vt('GetShard', f'{keyspace}/{shard}', capture=True))
            alias = data.get('primary_alias', data.get('primaryAlias'))
            if alias:
                tablet = f"{alias['cell']}-{int(alias['uid']):010d}"
                vt('PingTablet', tablet, capture=True)
                print(f'Primary listo: {keyspace}/{shard} ({tablet})')
                return
        except (RuntimeError, subprocess.CalledProcessError, ValueError):
            pass
        time.sleep(5)
    raise RuntimeError(f'Tiempo agotado esperando primary de {keyspace}/{shard}. Ejecuta status.')


def wf(phase, *args, capture=False):
    command, name = WORKFLOWS[phase]
    return vt(command, '--target-keyspace', 'customer', '--workflow', name, *args, capture=capture)


def validate_vdiff(report, workflow):
    """Contrato de salida JSON de VDiff show UUID --verbose en v24.0.3."""
    if not isinstance(report, dict):
        raise ValueError('VDiff no devuelve un objeto JSON.')
    if report.get('Workflow') != workflow or report.get('Keyspace') != 'customer':
        raise ValueError('VDiff pertenece a otro workflow/keyspace.')
    if report.get('State') != 'completed' or report.get('HasMismatch') is not False:
        raise ValueError('VDiff no completado o con diferencias.')
    rows = report.get('RowsCompared')
    if isinstance(rows, bool) or not isinstance(rows, int) or rows <= 0:
        raise ValueError('VDiff no ha comparado filas; este laboratorio requiere datos.')
    if report.get('Errors'):
        raise ValueError('VDiff contiene errores.')
    for shard in report.get('ShardSummaries', {}).values():
        if shard.get('State') != 'completed' or shard.get('LastError'):
            raise ValueError('Un shard no ha completado VDiff correctamente.')
    return rows


def check(phase):
    # UUID propio evita validar por accidente un VDiff antiguo con `show last`.
    import uuid
    diff_id = str(uuid.uuid4())
    name = WORKFLOWS[phase][1]
    args = ('VDiff', '--target-keyspace', 'customer', '--workflow', name)
    vt(*args, 'create', diff_id, '--wait', '--wait-update-interval', '5s')
    report = json.loads(vt(*args, 'show', diff_id, '--verbose', '--format', 'json', capture=True))
    rows = validate_vdiff(report, name)
    print(f'VDiff {diff_id}: {rows} filas comparadas, sin diferencias.')


def switch(phase):
    check(phase)
    wf(phase, 'switchtraffic', '--tablet-types', 'replica', '--dry-run')
    wf(phase, 'switchtraffic', '--tablet-types', 'replica')
    wf(phase, 'switchtraffic', '--tablet-types', 'primary', '--dry-run')
    wf(phase, 'switchtraffic', '--tablet-types', 'primary')
    wf(phase, 'status')


def bootstrap():
    architecture = run(['docker', 'info', '--format', '{{.Architecture}}'], capture=True)
    if architecture not in ('x86_64', 'amd64'):
        raise RuntimeError('Las imágenes fijadas requieren Docker linux/amd64. Usa una máquina o VM amd64.')
    versions = json.loads((ROOT / 'versions.json').read_text())
    run(['minikube', 'start', '-p', CONTEXT, '--driver=docker',
         '--kubernetes-version', versions['kubernetes'], '--cpus=4',
         '--memory=11000', '--disk-size=50g'], timeout=1200)
    kubectl('apply', '-f', str(ROOT / 'k8s' / 'namespace.yaml'))
    # Los CRD grandes exceden el límite de anotaciones de client-side apply.
    run(['kubectl', '--context', CONTEXT, 'apply', '--server-side',
         '-f', str(ROOT / 'k8s' / 'operator.yaml')])
    for crd in ('vitessclusters', 'vitesscells', 'vitesskeyspaces', 'vitessshards'):
        kubectl('wait', '--for=condition=Established', f'crd/{crd}.planetscale.com', '--timeout=120s')
    run(['kubectl', '--context', CONTEXT, '-n', 'default', 'rollout', 'status',
         'deployment/vitess-operator', '--timeout=180s'])
    apply('01-initial.yaml')
    wait_primary('commerce', '-')
    print('Clúster creado. Siguiente paso: python3 lab.py init')


def initialize():
    apply_schema('commerce.sql', 'commerce')
    apply_vschema('commerce-initial.json', 'commerce')
    mysql((ROOT / 'schema' / 'seed.sql').read_text())
    verify('commerce')


def prepare_move():
    apply('02-customer.yaml')
    wait_primary('customer', '-')


def prepare_reshard():
    # Con la carga de escritura detenida durante esta transición del esquema.
    apply_schema('sequences.sql', 'commerce')
    for table, column, sequence in [('customer', 'customer_id', 'customer_seq'),
                                    ('corder', 'order_id', 'order_seq')]:
        next_id = int(mysql(f'SELECT COALESCE(MAX({column}),0)+1 FROM {table};', 'customer', True))
        mysql(f'INSERT INTO {sequence}(id,next_id,cache) VALUES(0,{next_id},100) '
              f'ON DUPLICATE KEY UPDATE next_id=GREATEST(next_id,{next_id});')
    apply_vschema('commerce-sequences.json', 'commerce')
    apply_schema('customer-sharded.sql', 'customer')
    apply_vschema('customer-sharded.json', 'customer')
    apply('03-reshard.yaml')
    for shard in ('-80', '80-'):
        wait_primary('customer', shard)


def verify(database='customer'):
    # Comprueba el conjunto de datos determinista, no solo un COUNT(*) global.
    for table, column, expected in [('customer', 'customer_id', 20), ('corder', 'order_id', 40)]:
        actual = mysql(f'SELECT {column} FROM {table} WHERE {column} <= {expected} ORDER BY {column};', database, True)
        if [int(x) for x in actual.splitlines()] != list(range(1, expected + 1)):
            raise RuntimeError(f'Faltan filas o hay duplicados en {database}.{table}')
    print(f'{database}: comprobadas las 20 filas de clientes y 40 de pedidos del seed.')


def forward():
    processes = []
    try:
        for component, ports in [('vtgate', ['15306:3306']), ('vtadmin', ['14000:15000', '14001:15001'])]:
            service = object_name('service', component)
            processes.append(subprocess.Popen(['kubectl', '--context', CONTEXT, '-n', NAMESPACE,
                                              'port-forward', '--address', '127.0.0.1',
                                              f'service/{service}', *ports]))
        print('VTAdmin: http://127.0.0.1:14000 | MySQL: 127.0.0.1:15306. Ctrl-C para cerrar.')
        while all(p.poll() is None for p in processes):
            time.sleep(1)
        raise RuntimeError('Un port-forward terminó; vuelve a ejecutar forward.')
    except KeyboardInterrupt:
        pass
    finally:
        for p in processes:
            if p.poll() is None:
                p.terminate()
        for p in processes:
            p.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = ['up', 'init', 'status', 'forward', 'verify', 'distribution', 'sequence-check', 'sql', 'vt', 'down']
    commands += [f'{phase}-{action}' for phase in WORKFLOWS for action in
                 ('prepare', 'create', 'check', 'switch', 'reverse', 'complete')]
    parser.add_argument('command', choices=commands)
    parser.add_argument('args', nargs=argparse.REMAINDER)
    opts = parser.parse_args()
    command = opts.command
    if command == 'up': bootstrap()
    elif command == 'init': initialize()
    elif command == 'status':
        kubectl('get', 'pods,svc,pvc')
        vt('GetTablets')
    elif command == 'forward': forward()
    elif command == 'verify': verify()
    elif command == 'distribution':
        for table, column, total in [('customer', 'customer_id', 20), ('corder', 'order_id', 40)]:
            counts = [int(mysql(f'SELECT COUNT(*) FROM {table} WHERE {column}<={total};',
                                f'customer:{shard}', True)) for shard in ('-80', '80-')]
            if sum(counts) != total or min(counts) <= 0:
                raise RuntimeError(f'Distribución inesperada: {table}: {counts}')
            print(f'{table}: -80={counts[0]}, 80-={counts[1]}, total={sum(counts)}')
    elif command == 'sequence-check':
        customer_id = int(mysql("INSERT INTO customer(email) VALUES ('secuencia@example.test'); SELECT LAST_INSERT_ID();", capture=True))
        order_id = int(mysql(f"INSERT INTO corder(customer_id,sku,price) VALUES ({customer_id},'SKU-01',3000); SELECT LAST_INSERT_ID();", capture=True))
        if customer_id <= 20 or order_id <= 40:
            raise RuntimeError('IDs de secuencia inesperados.')
        print(f'Secuencias comprobadas: customer_id={customer_id}, order_id={order_id}. Filas de prueba conservadas.')
    elif command == 'sql': mysql(sys.stdin.read(), opts.args[0] if opts.args else 'customer')
    elif command == 'vt': vt(*opts.args)
    elif command == 'down':
        if opts.args != ['--confirm-destroy']:
            parser.error('down --confirm-destroy elimina exclusivamente el perfil vitess-lab y sus datos.')
        run(['minikube', 'delete', '-p', CONTEXT])
    elif command == 'move-prepare': prepare_move()
    elif command == 'reshard-prepare': prepare_reshard()
    elif command == 'move-create':
        wf('move', 'create', '--source-keyspace', 'commerce', '--tables', 'customer,corder')
    elif command == 'reshard-create':
        wf('reshard', 'create', '--source-shards=-', '--target-shards=-80,80-')
    else:
        phase, action = command.split('-')
        if action == 'check': check(phase)
        elif action == 'switch': switch(phase)
        elif action == 'reverse': wf(phase, 'reversetraffic', '--tablet-types', 'primary,replica')
        elif action == 'complete':
            if opts.args != ['--confirm-complete']:
                parser.error('complete --confirm-complete retira el origen y cierra la ventana de reversión.')
            verify()
            wf(phase, 'complete')
            if phase == 'reshard': apply('04-final.yaml')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, subprocess.SubprocessError, OSError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
