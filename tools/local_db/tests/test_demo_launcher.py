"""Regression coverage for launch readiness, repeat starts and window isolation."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import demo


class DemoLauncherTests(unittest.TestCase):
    def test_running_website_still_opens_browser_without_duplicate_server(self):
        with patch.object(demo, 'wait_for_backend') as ready, \
             patch.object(demo, 'demo_frontend_ready', return_value=True), \
             patch.object(demo, 'open_demo_browser') as browser, \
             patch.object(demo.subprocess, 'Popen') as launch:
            demo.start_frontend(Path('/unused'))
        ready.assert_called_once()
        browser.assert_called_once()
        launch.assert_not_called()

    def test_cold_start_opens_analytics_after_vite_starts(self):
        events = []
        process = Mock()
        process.poll.return_value = None
        process.wait.return_value = 0
        readiness = iter([False, False, True])

        def probe():
            ready = next(readiness)
            events.append(('ready', ready))
            return ready

        with patch.object(demo, 'wait_for_backend'), \
             patch.object(demo, 'demo_frontend_ready', side_effect=probe), \
             patch.object(demo, 'http_ready', return_value=False), \
             patch.object(demo.shutil, 'which', return_value='/example/node'), \
             patch.object(demo.time, 'sleep'), \
             patch.dict(demo.os.environ, {'BROWSER': 'none', 'BROWSER_ARGS': '--unrelated'}), \
             patch.object(demo.subprocess, 'Popen', return_value=process) as launch, \
             patch.object(demo, 'open_demo_browser', side_effect=lambda: events.append(('open', True))):
            demo.start_frontend(Path('/example/frontend'))
        argv = launch.call_args.args[0]
        env = launch.call_args.kwargs['env']
        self.assertEqual(argv[2], 'preview')
        self.assertEqual(argv[argv.index('--port') + 1], '5187')
        self.assertIn('--strictPort', argv)
        self.assertNotIn('--open', argv)
        self.assertEqual(env['VITE_API_BASE_URL'], 'http://127.0.0.1:8017')
        self.assertEqual(env['NODE_ENV'], 'production')
        self.assertNotIn('BROWSER', env)
        self.assertNotIn('BROWSER_ARGS', env)
        self.assertEqual(events, [('ready', False), ('ready', False), ('ready', True), ('open', True)])

    def test_backend_not_ready_never_opens_browser(self):
        with patch.object(demo, 'http_ready', return_value=False), \
             patch.object(demo.time, 'monotonic', side_effect=[0, 31]), \
             patch.object(demo, 'open_demo_browser') as browser, \
             patch.object(demo.subprocess, 'Popen') as launch:
            with self.assertRaisesRegex(SystemExit, '后端未能就绪'):
                demo.start_frontend(Path('/unused'))
        browser.assert_not_called()
        launch.assert_not_called()

    def test_backend_startup_is_waited_for(self):
        with patch.object(demo, 'http_ready', side_effect=[False, True]) as probe, \
             patch.object(demo.time, 'monotonic', return_value=0), \
             patch.object(demo.time, 'sleep') as sleep:
            demo.wait_for_backend()
        self.assertEqual(probe.call_count, 2)
        self.assertEqual(probe.call_args.args, (demo.BACKEND_READY_URL,))
        sleep.assert_called_once_with(0.5)

    def test_macos_open_failure_reports_the_manual_url(self):
        with patch.object(demo.sys, 'platform', 'darwin'), \
             patch.object(Path, 'is_file', return_value=True), \
             patch.object(demo.subprocess, 'Popen', side_effect=OSError('cannot launch')):
            with self.assertRaises(SystemExit) as failure:
                demo.open_demo_browser()
        self.assertIn(demo.DEMO_URL, str(failure.exception))
        self.assertIn('手动访问', str(failure.exception))

    def test_macos_requests_a_new_window_even_if_chrome_is_running(self):
        with patch.object(demo.sys, 'platform', 'darwin'), \
             patch.object(Path, 'is_file', return_value=True), \
             patch.object(demo.subprocess, 'Popen') as launch:
            launch.return_value.wait.return_value = 0
            demo.open_demo_browser()
        self.assertEqual(launch.call_args.args[0], [str(demo.CHROME), '--new-window', demo.DEMO_URL])
        launch.return_value.wait.assert_called_once_with(timeout=5)
        self.assertTrue(launch.call_args.kwargs['start_new_session'])

    def test_old_dev_server_is_not_mistaken_for_ready_demo(self):
        with patch.object(demo, 'wait_for_backend'), \
             patch.object(demo, 'demo_frontend_ready', return_value=False), \
             patch.object(demo, 'http_ready', return_value=True), \
             patch.object(demo, 'open_demo_browser') as browser, \
             patch.object(demo.subprocess, 'Popen') as launch:
            with self.assertRaisesRegex(SystemExit, '5187'):
                demo.start_frontend(Path('/unused'))
        browser.assert_not_called()
        launch.assert_not_called()

    def test_spa_html_fallback_is_not_a_successful_readiness_probe(self):
        opener = Mock()
        opener.open.return_value = io.BytesIO(b'<!doctype html><div id="app"></div>')
        with patch.object(demo.urllib.request, 'build_opener', return_value=opener):
            self.assertFalse(demo.demo_frontend_ready())
        opener.open.return_value = io.BytesIO(json.dumps({'application': 'biotech-local-demo'}).encode())
        with patch.object(demo.urllib.request, 'build_opener', return_value=opener):
            self.assertTrue(demo.demo_frontend_ready())

    def test_repeat_snapshot_preserves_unchanged_frontend(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'source'
            runtime = Path(directory) / 'runtime'
            (root / 'frontend').mkdir(parents=True)
            (runtime / 'frontend/node_modules').mkdir(parents=True)
            source = root / 'frontend/vite.config.ts'
            source.write_text('initial config')
            with patch.object(demo, 'ROOT', root), patch.object(demo, 'RUNTIME', runtime), \
                 patch.object(demo.subprocess, 'check_output', return_value=b'frontend/vite.config.ts\0'):
                target = demo.frontend_snapshot()
                destination = target / 'vite.config.ts'
                original = destination.stat().st_mtime_ns
                with patch.object(demo.shutil, 'copy2', wraps=demo.shutil.copy2) as copy:
                    demo.frontend_snapshot()
                    copy.assert_not_called()
                    self.assertEqual(destination.stat().st_mtime_ns, original)
                    source.write_text('updated config')
                    demo.frontend_snapshot()
                    copy.assert_called_once()
                self.assertEqual(destination.read_text(), 'updated config')

    def test_build_is_reused_until_frontend_content_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'frontend'
            (target / 'dist').mkdir(parents=True)
            source = target / 'index.html'
            source.write_text('original source')

            def build(*args, **kwargs):
                (target / 'dist/index.html').write_text('compiled page')

            with patch.object(demo, 'ROOT', root), \
                 patch.object(demo.subprocess, 'check_output', return_value=b'frontend/index.html\0'), \
                 patch.object(demo.shutil, 'which', return_value='/example/node'), \
                 patch.object(demo, 'run', side_effect=build) as build_command:
                demo.build_frontend(target)
                marker = target / 'dist' / demo.BUILD_MARKER
                initial = marker.read_bytes()
                demo.build_frontend(target)
                self.assertEqual(build_command.call_count, 1)
                self.assertEqual(marker.read_bytes(), initial)
                source.write_text('new source')
                demo.build_frontend(target)
                self.assertEqual(build_command.call_count, 2)
                self.assertNotEqual(marker.read_bytes(), initial)


if __name__ == '__main__':
    unittest.main()
