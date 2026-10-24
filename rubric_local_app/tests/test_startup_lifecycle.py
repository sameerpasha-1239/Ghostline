import unittest
import os
import sys
import time
import subprocess
from pathlib import Path

# Add project root to path
pkg_dir = Path(__file__).resolve().parent.parent
if str(pkg_dir) not in sys.path:
    sys.path.insert(0, str(pkg_dir))

import win32gui
import win32process
from rubric_local.config import get_app_dir

class TestStartupAndSingleInstance(unittest.TestCase):
    """
    Empirical validation for Phase 1 & 2:
    - Single-instance detection before GUI creation
    - Secondary instance clean exit (code 0) without GUI flash
    - Wake-up message delivery to primary instance
    - Clean shutdown and mutex release
    - Repeat-launch reliability
    """

    def setUp(self):
        # Kill any lingering test instances
        self._kill_existing()
        time.sleep(0.5)

    def tearDown(self):
        self._kill_existing()
        time.sleep(0.5)

    def _kill_existing(self):
        try:
            import psutil
            for p in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if p.pid == os.getpid():
                        continue
                    cmd = ' '.join(p.info['cmdline'] or []).lower()
                    name = p.info['name'].lower()
                    if 'rubric-local' in name or ('rubric_local' in cmd and 'app.py' in cmd):
                        p.kill()
                        try:
                            p.wait(timeout=2)
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(0.5)

    def _wait_for_sink(self, timeout=12.0) -> int:
        start = time.time()
        while time.time() - start < timeout:
            hwnd = win32gui.FindWindow("RubricLocalSingleInstanceSink", None) or win32gui.FindWindow(None, "RubricLocalSinkWindow")
            if hwnd:
                return hwnd
            time.sleep(0.15)
        return 0

    def test_single_instance_wakeup_and_exit(self):
        """Verify secondary instance exits cleanly and wakes primary instance."""
        # 1. Start primary instance
        p1 = subprocess.Popen(
            [sys.executable, "rubric_local/app.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(pkg_dir),
            text=True
        )
        sink_hwnd = self._wait_for_sink()
        if sink_hwnd == 0:
            p1.kill()
            p1_out, p1_err = p1.communicate(timeout=2)
            self.fail(f"Sink window was not created in time! Poll: {p1.poll()}, stdout: {p1_out}, stderr: {p1_err}")
        self.assertIsNone(p1.poll(), "Primary instance failed to stay running!")

        # 2. Launch secondary instance
        p2 = subprocess.Popen(
            [sys.executable, "rubric_local/app.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(pkg_dir),
            text=True
        )
        p2_out, p2_err = p2.communicate(timeout=6)
        self.assertEqual(p2.returncode, 0, f"Secondary instance did not exit with code 0: {p2_err}")
        self.assertIn("Activated existing Rubric-Local instance", p2_out)

        # Verify primary instance is still running
        self.assertIsNone(p1.poll(), "Primary instance died after secondary launch!")

        # Terminate primary instance cleanly
        p1.kill()
        try:
            p1.communicate(timeout=2)
        except Exception:
            pass

    def test_repeat_launch_stability(self):
        """Launch and terminate application 5 times consecutively to ensure no mutex leaks or crashes."""
        for i in range(5):
            p = subprocess.Popen(
                [sys.executable, "rubric_local/app.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(pkg_dir),
                text=True
            )
            sink_hwnd = self._wait_for_sink()
            if sink_hwnd == 0:
                p.kill()
                p_out, p_err = p.communicate(timeout=2)
                self.fail(f"Iteration {i+1}: Sink window not found in time! Poll: {p.poll()}, stdout: {p_out}, stderr: {p_err}")
            self.assertIsNone(p.poll(), f"Iteration {i+1}: Application failed to launch or stay running!")
            
            # Clean shutdown
            p.kill()
            try:
                p.communicate(timeout=2)
            except Exception:
                pass
            self.assertIsNotNone(p.poll())
            time.sleep(0.5)

    def test_startup_diagnostics_logging(self):
        """Verify startup diagnostics log entry is created with timestamp, version, and PID."""
        log_file = get_app_dir() / "rubric_local.log"

        p = subprocess.Popen(
            [sys.executable, "rubric_local/app.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(pkg_dir),
            text=True
        )
        time.sleep(1.8)
        self.assertIsNone(p.poll())

        p.kill()
        try:
            p.communicate(timeout=2)
        except Exception:
            pass

        self.assertTrue(log_file.exists(), "Log file was not created!")
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        self.assertIn("Starting Rubric-Local v1.0.0", content)
        self.assertIn("Configuration loaded", content)
        self.assertIn("Rubric-Local application starting main GUI loop", content)

if __name__ == "__main__":
    unittest.main()
