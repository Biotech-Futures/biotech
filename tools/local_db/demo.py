#!/usr/bin/env python3
"""Operate this workstation's isolated demo without resetting retained databases."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[2]
PREVIEW = ROOT / 'tmp/llm-preview-20261027-1zyclbhd'
RUNTIME = ROOT / 'tmp/demo-update-20261106'
STATE = RUNTIME / 'demo-state.json'
PROJECT = 'biotech-llm-preview-20261027'
DEMO_URL = 'http://127.0.0.1:5187/#/analytics'
FRONTEND_URL = 'http://127.0.0.1:5187/'
BACKEND_READY_URL = 'http://127.0.0.1:8017/api/v1/services/csrf/'
BUILD_MARKER = '__biotech_demo__.json'
CHROME = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {'database': 'biotech_llm_demo_20261106'}


def compose(database):
    env = os.environ.copy()
    env.update(BIOTECH_SOURCE_ROOT=str(ROOT), DEMO_RUNTIME_DIR=str(RUNTIME), DEMO_DB_NAME=database)
    args = ['docker', 'compose', '--project-name', PROJECT,
            '--env-file', str(PREVIEW / '.preview.env'), '-f', str(PREVIEW / 'compose.preview.yml'),
            '-f', str(ROOT / 'tools/local_db/compose.demo.yml')]
    return args, env


def tool(database, *args):
    command, env = compose(database)
    run(command + ['run', '--rm', '--no-deps', 'local-db-tool', *args], env=env)


def prepare(database):
    # CREATE DATABASE is issued only for a validated new local demo name.
    if not database.startswith('biotech_llm_demo_') or not database.replace('_', '').isalnum():
        raise SystemExit('Invalid local demo database name')
    command, env = compose(database)
    run(command + ['up', '-d', '--no-build', 'postgres'], env=env)
    found = subprocess.check_output(command + ['exec', '-T', 'postgres', 'psql', '-U', 'biotech_preview',
        '-d', 'postgres', '-tAc', f"SELECT 1 FROM pg_database WHERE datname='{database}'"], env=env, text=True).strip()
    if not found:
        run(command + ['exec', '-T', 'postgres', 'createdb', '-U', 'biotech_preview', database], env=env)
        tool(database, 'bootstrap')
    else:
        tool(database, 'verify')
    RUNTIME.mkdir(parents=True, exist_ok=True)
    (RUNTIME / 'files').mkdir(exist_ok=True)
    STATE.write_text(json.dumps({'database': database, 'source': str(ROOT),
        'base_ref': 'origin/feat/team2-us20-llm',
        'prepared_at': datetime.now(timezone.utc).isoformat()}, indent=2) + '\n')


def frontend_snapshot():
    target = RUNTIME / 'frontend'
    files = subprocess.check_output(['git', 'ls-files', '-z', '--', 'frontend'], cwd=ROOT).decode().split('\0')
    for name in filter(None, files):
        source = ROOT / name
        destination = RUNTIME / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Never touch unchanged files: rewriting tsconfig/vite.config under a
        # running dev server caused reload storms and startup blank screens.
        if not destination.exists() or source.read_bytes() != destination.read_bytes():
            shutil.copy2(source, destination)
    modules = target / 'node_modules'
    if not modules.exists():
        modules.symlink_to(PREVIEW / 'frontend/node_modules', target_is_directory=True)
    return target


def build_frontend(target):
    """Serve an actual build for presentations, without HMR or devtools."""
    files = subprocess.check_output(['git', 'ls-files', '-z', '--', 'frontend'], cwd=ROOT).decode().split('\0')
    digest = hashlib.sha256(b'biotech-local-preview-v1:api=127.0.0.1:8017')
    for name in sorted(filter(None, files)):
        digest.update(name.encode())
        digest.update((ROOT / name).read_bytes())
    fingerprint = digest.hexdigest()
    marker = target / 'dist' / BUILD_MARKER
    if marker.exists() and (target / 'dist/index.html').exists():
        try:
            if json.loads(marker.read_text()).get('fingerprint') == fingerprint:
                print('前端演示版本已准备好。', flush=True)
                return
        except (ValueError, OSError, AttributeError):
            pass
    node = shutil.which('node')
    if not node:
        raise SystemExit('未找到 Node.js 22，请使用 start-demo.command 启动。')
    print('正在准备前端演示版本（首次启动需要几秒钟）…', flush=True)
    env = os.environ.copy()
    env.update(VITE_API_BASE_URL='http://127.0.0.1:8017', NODE_ENV='production')
    run([node, str(target / 'node_modules/vite/bin/vite.js'), 'build'], cwd=target, env=env)
    marker.write_text(json.dumps({'application': 'biotech-local-demo', 'fingerprint': fingerprint}) + '\n')


def demo_frontend_ready():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(FRONTEND_URL + BUILD_MARKER, timeout=2) as response:
            return json.load(response).get('application') == 'biotech-local-demo'
    except (OSError, ValueError, AttributeError):
        return False


def http_ready(url):
    # Local readiness must not depend on the user's HTTP proxy settings.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url, timeout=2) as response:
            return response.status == 200
    except OSError:
        return False


def wait_for_backend(timeout=30):
    print('正在等待本地后端就绪…', flush=True)
    deadline = time.monotonic() + timeout
    while not http_ready(BACKEND_READY_URL):
        if time.monotonic() >= deadline:
            raise SystemExit('本地后端未能就绪。请检查 Docker Desktop 中的 BIOTech backend 服务，再重试。')
        time.sleep(0.5)


def open_demo_browser(url=DEMO_URL):
    print(f'Opening a separate Chrome window / 正在打开独立的 Chrome 窗口: {url}', flush=True)
    try:
        if sys.platform == 'darwin':
            if not CHROME.is_file():
                raise OSError('Google Chrome is not installed')
            # Chrome's process singleton forwards --new-window even when the
            # browser is already running. No global browser preference changes.
            browser = subprocess.Popen([str(CHROME), '--new-window', url],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       start_new_session=True)
            # An already-running Chrome acknowledges the forwarded command and
            # exits. Wait for that acknowledgement before the launcher exits.
            # A first Chrome process remains alive for the browser session.
            try:
                if browser.wait(timeout=5):
                    raise OSError('Chrome rejected the new-window request')
            except subprocess.TimeoutExpired:
                pass
        elif not webbrowser.open(url, new=1):
            raise OSError('No browser handler')
    except (OSError, subprocess.CalledProcessError):
        raise SystemExit(f'网站已就绪，但浏览器未能自动打开。请手动访问：{url}')


def start_frontend(target):
    wait_for_backend()
    if demo_frontend_ready():
        print('演示网站已在运行，正在复用现有服务。', flush=True)
        open_demo_browser()
        return
    if http_ready(FRONTEND_URL):
        raise SystemExit('5187 端口仍由旧版开发服务占用。请关闭旧版演示终端，再重新双击 start-demo.command。')
    node = shutil.which('node')
    if not node:
        raise SystemExit('未找到 Node.js 22，请使用 tools/local_db/start-demo.command 启动。')
    env = os.environ.copy()
    env['VITE_API_BASE_URL'] = 'http://127.0.0.1:8017'
    env['NODE_ENV'] = 'production'
    # Browser opening is handled explicitly after readiness, independent of
    # development-shell browser overrides.
    env.pop('BROWSER', None)
    env.pop('BROWSER_ARGS', None)
    print(f'正在启动前端：{DEMO_URL}\n演示期间请保持此终端窗口打开。', flush=True)
    process = subprocess.Popen([node, str(target / 'node_modules/vite/bin/vite.js'), 'preview',
                                '--host', '127.0.0.1', '--port', '5187', '--strictPort'],
                               cwd=target, env=env)
    try:
        deadline = time.monotonic() + 30
        while not demo_frontend_ready():
            if process.poll() is not None:
                raise SystemExit('前端启动失败，请查看上方错误信息。')
            if time.monotonic() >= deadline:
                raise SystemExit('前端启动超时，请查看上方错误信息。')
            time.sleep(0.3)
        open_demo_browser()
        result = process.wait()
        if result:
            raise SystemExit(f'演示前端异常退出（状态码 {result}）。请查看上方错误信息。')
    except KeyboardInterrupt:
        print('\n演示前端已停止。', flush=True)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['prepare', 'refresh', 'start', 'status', 'verify', 'gui', 'tool'])
    parser.add_argument('tool_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not (ROOT / 'backend/apps/assistant/knowledge.py').is_file():
        raise SystemExit('Select codex/demo-analytics-llm before starting this demo.')
    if not shutil.which('docker'):
        raise SystemExit('未找到 Docker。请安装并启动 Docker Desktop，再双击 start-demo.command。')
    if os.environ.get('DOCKER_HOST') and os.environ.get('DOCKER_CONTEXT'):
        raise SystemExit('Set only one of DOCKER_HOST and DOCKER_CONTEXT.')
    endpoint = os.environ.get('DOCKER_HOST') or subprocess.check_output(
        ['docker', 'context', 'inspect', '--format', '{{.Endpoints.docker.Host}}'], text=True).strip()
    if not endpoint.startswith(('unix://', 'npipe://')):
        raise SystemExit('Use a local Docker Desktop context for the synthetic demo.')
    RUNTIME.mkdir(parents=True, exist_ok=True)
    database = load_state()['database']
    if args.operation == 'refresh':
        database = 'biotech_llm_demo_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        prepare(database)
        command, env = compose(database)
        run(command + ['up', '-d', '--no-build', 'backend'], env=env)
        gui = subprocess.check_output(command + ['ps', '--status', 'running', '--quiet', 'local-db-gui'], env=env, text=True).strip()
        if gui:
            gui_env = os.environ.copy()
            gui_env['LOCAL_DB_GUI_SKIP_OPEN'] = '1'
            run(['sh', str(ROOT / 'tools/local_db/open_gui.command')], env=gui_env)
        print('New synthetic snapshot ready. Previous databases were retained. Reload the browser.')
    elif args.operation == 'prepare':
        prepare(database)
    elif args.operation in ('verify', 'status'):
        tool(database, args.operation)
    elif args.operation == 'tool':
        if not args.tool_args:
            raise SystemExit('Supply a generator command, for example: run status')
        tool(database, *args.tool_args)
    elif args.operation == 'gui':
        env = os.environ.copy()
        run(['sh', str(ROOT / 'tools/local_db/open_gui.command')], env=env)
        print('Demo generator: http://127.0.0.1:8766/')
    else:
        if not STATE.exists():
            prepare(database)
        command, env = compose(database)
        run(command + ['up', '-d', '--no-build', 'backend'], env=env)
        target = frontend_snapshot()
        build_frontend(target)
        start_frontend(target)


if __name__ == '__main__':
    main()
