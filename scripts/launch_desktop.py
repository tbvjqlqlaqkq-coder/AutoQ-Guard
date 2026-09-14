import argparse
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.runtime/desktop'
WORK = Path.home() / 'Documents/Codex/2026-09-08/cmd-x20/work'
HIDDEN = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

def listening(port):
    try:
        with socket.create_connection(('127.0.0.1', port), 1):
            return True
    except OSError:
        return False

def wait(url):
    for _ in range(180):
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError('Startup timeout: ' + url)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--admin', action='store_true')
    p.add_argument('--no-open', action='store_true')
    args = p.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    tokenfile = STATE / 'integration-token.txt'
    if not tokenfile.exists():
        tokenfile.write_text(secrets.token_urlsafe(32), encoding='utf-8')
    env = os.environ.copy()
    env.update(AUTOQ_INTEGRATION_TOKEN=tokenfile.read_text().strip(),
               AUTOQ_N8N_INTEGRATION='true', AUTOQ_DEFAULT_PROFILE='automotive',
               N8N_PORT='5678', N8N_HOST='127.0.0.1', N8N_LISTEN_ADDRESS='127.0.0.1',
               N8N_DIAGNOSTICS_ENABLED='false', N8N_BLOCK_ENV_ACCESS_IN_NODE='false')
    def spawn(command, name):
        with (STATE / (name + '.log')).open('ab') as log:
            subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=HIDDEN)
    if not listening(8880):
        base = next((ROOT / 'results' / name / 'current' for name in
                     ['public_candidate_trial', 'public_enterprise_integration', 'enterprise_pipeline']
                     if (ROOT / 'results' / name / 'current/03_database/automotive_quality.db').exists()), None)
        if base is None:
            raise RuntimeError('Integrated database missing.')
        spawn([sys.executable, str(ROOT / 'src/enterprise_dashboard.py'), '--port', '8880', '--no-browser',
               '--database', str(base / '03_database/automotive_quality.db'),
               '--summary', str(base / 'pipeline_summary.json'),
               '--model-result', str(ROOT / 'results/purged_ml/model_comparison.json')], 'autoq')
    wait('http://127.0.0.1:8880/')
    with urllib.request.urlopen('http://127.0.0.1:8880/') as response:
        if 'n8nStart' not in response.read().decode('utf-8'):
            raise RuntimeError('Port 8880 contains an older dashboard.')
    error = None
    try:
        if not listening(5678):
            entry = ROOT / '.runtime/n8n/node_modules/n8n/bin/n8n'
            if not entry.exists():
                entry = WORK / 'n8n-runtime/node_modules/n8n/bin/n8n'
            node = Path(shutil.which('node') or 'C:/Program Files/nodejs/node.exe')
            data = WORK / 'n8n-data-clean'
            env['N8N_USER_FOLDER'] = str(data if data.exists() else ROOT / '.runtime/n8n-data')
            for command in [['import:workflow', '--input=' + str(ROOT / 'n8n/autoq-guard-optional-integration.json')],
                            ['publish:workflow', '--id=autoqGuardMesErpDemo']]:
                with (STATE / 'n8n-setup.log').open('ab') as log:
                    subprocess.run([str(node), str(entry)] + command, cwd=ROOT, env=env,
                                   stdout=log, stderr=log, timeout=300, check=True, creationflags=HIDDEN)
            spawn([str(node), str(entry), 'start'], 'n8n')
        wait('http://127.0.0.1:5678/healthz/readiness')
    except Exception as exc:
        error = str(exc)
    url = 'http://127.0.0.1:8880/' + ('?view=admin' if args.admin else '')
    if not args.no_open:
        webbrowser.open(url)
    print('Dashboard: ' + url)
    print('n8n: ' + (error or 'http://127.0.0.1:5678/ READY'))
    return 1 if error else 0

if __name__ == '__main__':
    raise SystemExit(main())
