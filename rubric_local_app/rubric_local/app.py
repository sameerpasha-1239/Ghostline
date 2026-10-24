import os
import sys
from pathlib import Path

# Add parent directory to sys.path if run directly
pkg_dir = Path(__file__).resolve().parent.parent
if str(pkg_dir) not in sys.path:
    sys.path.insert(0, str(pkg_dir))

import time
import json
import threading
from typing import Optional

import ctypes
from ctypes import wintypes
import win32con
import win32gui
import win32api
import win32event
import winerror
import pywintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
user32.PostThreadMessageW.restype = wintypes.BOOL


import logging
from rubric_local.config import load_config, save_config, get_app_dir, get_config_path
from rubric_local.core.pipeline import RubricPipeline, DuplicateQuestionError
from rubric_local.core.pipeline_tracer import PipelineTracer
from rubric_local.core.hover_detector import HoverDetector
from rubric_local.core.llm_client import OllamaClient, AnswerResult
from rubric_local.ui.presentation import (
    build_answer_presentation,
    PresentedAnswer,
    TYPE_MCQ,
    TYPE_UNCERTAIN,
    TYPE_ERROR
)
from rubric_local.ui.main_window import RubricMainWindow
from rubric_local.ui.hud_overlay import RubricHudOverlay
from rubric_local.ui.tray_indicator import TrayIndicator
from rubric_local.ui.caps_indicator import CapsLockIndicator

from rubric_local import __version__

# Register custom Win32 messages for single-instance activation and IPC solve triggers
WM_RUBRIC_WAKEUP = win32gui.RegisterWindowMessage("RubricLocalWakeUpMsg")
WM_RUBRIC_SOLVE = win32gui.RegisterWindowMessage("RubricLocalSolveMsg")
SINGLE_INSTANCE_SINK_CLASS = "RubricLocalSingleInstanceSink"

def setup_file_logging():
    try:
        log_file = get_app_dir() / "rubric_local.log"
        handlers = [
            logging.FileHandler(str(log_file), encoding="utf-8", mode="a")
        ]
        if sys.stdout is not None:
            handlers.append(logging.StreamHandler(sys.stdout))
        logging.basicConfig(
            handlers=handlers,
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            force=True
        )
    except Exception:
        pass

class RubricApp:
    def __init__(self, mutex=None):
        self._mutex = mutex
        setup_file_logging()
        self.sink_hwnd: Optional[int] = None
        self.is_running = True
        self.is_solving = False
        self.hotkey_thread: Optional[threading.Thread] = None
        self.hotkey_hwnd: Optional[int] = None
        self.hotkey_thread_id: Optional[int] = None
        self.hotkey_registered: bool = False
        self.main_window: Optional[RubricMainWindow] = None

        # Set up single-instance sink window on main thread immediately
        self._setup_sink_window()

        self.config = load_config()
        logging.info("Configuration loaded: Model=%s, Endpoint=%s, Hotkey=%s, CapsLock=%s, Hover=%s",
                     self.config.model_name, self.config.ollama_url, self.config.hotkey,
                     getattr(self.config, "caps_lock_indicator", False),
                     getattr(self.config, "hover_to_answer_enabled", False))
        self.ollama = OllamaClient(
            base_url=self.config.ollama_url,
            default_model=self.config.model_name
        )
        self.pipeline = RubricPipeline(
            ollama_client=self.ollama,
            model_name=self.config.model_name
        )

        # Build Main Window
        self.main_window = RubricMainWindow(
            config=self.config,
            on_trigger_solve=self.trigger_solve,
            on_settings_saved=self.on_settings_saved,
            on_toggle_hud=self.toggle_hud,
            on_test_caps=self.test_caps_lock,
            on_exit=self.shutdown,
            ollama_client=self.ollama
        )
        root = self.main_window.build()

        # Build floating HUD attached as Toplevel (initially hidden)
        self.hud = RubricHudOverlay(
            on_close=self.on_hud_close,
            on_toggle_pause=self.toggle_hover_pause,
            on_position_changed=self.on_hud_position_changed,
            on_retry=lambda: self.trigger_solve(is_auto_hover=False),
            opacity=getattr(self.config, "hud_opacity", 0.95),
            width=getattr(self.config, "hud_width", 380),
            height=getattr(self.config, "hud_height", 300),
            max_width=getattr(self.config, "hud_max_width", 520),
            max_height=getattr(self.config, "hud_max_height", 460),
            scroll_speed=getattr(self.config, "hud_scroll_speed", 2),
            pos_x=getattr(self.config, "hud_pos_x", None),
            pos_y=getattr(self.config, "hud_pos_y", None),
            is_pinned=getattr(self.config, "hud_pinned", False),
            always_on_top=getattr(self.config, "hud_always_on_top", True),
            exclude_from_capture=getattr(self.config, "exclude_from_capture", True),
            is_paused=getattr(self.config, "is_hover_paused", False)
        )
        self.hud.launch(parent=root, start_visible=False)

        # Build Automatic Hover-to-Answer Engine
        self.hover_detector = HoverDetector(
            on_trigger=lambda: self.trigger_solve(is_auto_hover=True),
            is_solving_fn=lambda: self.is_solving,
            get_excluded_rects=self.get_excluded_window_rects,
            enabled=getattr(self.config, "hover_to_answer_enabled", False),
            hover_delay_ms=getattr(self.config, "hover_delay_ms", 800),
            cooldown_sec=getattr(self.config, "hover_cooldown_sec", 3.0),
            movement_threshold_px=getattr(self.config, "hover_movement_threshold_px", 15),
            is_paused=getattr(self.config, "is_hover_paused", False)
        )

        # Build Tray Indicator with full navigation menu
        self.tray = TrayIndicator(
            on_trigger=self.trigger_solve,
            on_open_main=self.main_window.show_window,
            on_toggle_hud=self.toggle_hud,
            on_open_settings=self.open_settings,
            on_exit=self.shutdown,
            on_toggle_pause=self.toggle_hover_pause
        )

        # Initialize Caps Lock Indicator with configured timing
        self.caps_indicator = CapsLockIndicator(
            enabled=getattr(self.config, "caps_lock_indicator", False),
            pulse_on_ms=getattr(self.config, "caps_pulse_on_ms", 300),
            pulse_off_ms=getattr(self.config, "caps_pulse_off_ms", 250),
            sequence_cooldown_ms=getattr(self.config, "caps_sequence_cooldown_ms", 700)
        )

    def _setup_sink_window(self):
        """Creates hidden Win32 sink window on main thread for instant single-instance wakeup and solve IPC."""
        wc = win32gui.WNDCLASS()
        wc.lpszClassName = SINGLE_INSTANCE_SINK_CLASS

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == WM_RUBRIC_WAKEUP:
                logging.info("[Diagnostic %s] Received WM_RUBRIC_WAKEUP in sink wndproc. Restoring main window.", time.strftime("%H:%M:%S"))
                if hasattr(self, "main_window") and self.main_window:
                    self.main_window.show_window()
                return 0
            elif msg == WM_RUBRIC_SOLVE:
                logging.info("[Diagnostic %s] Received WM_RUBRIC_SOLVE in sink wndproc. Triggering solve.", time.strftime("%H:%M:%S"))
                self.trigger_solve()
                return 0
            return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

        wc.lpfnWndProc = wndproc

        try:
            win32gui.RegisterClass(wc)
        except pywintypes.error as e:
            if e.winerror != 1410:
                logging.warning(f"Sink window class registration note: {e}")

        try:
            self.sink_hwnd = win32gui.CreateWindow(
                wc.lpszClassName, "RubricLocalSinkWindow", 0, 0, 0, 0, 0, 0, 0, 0, None
            )
            try:
                user32.ChangeWindowMessageFilter(WM_RUBRIC_WAKEUP, 1)  # MSGFLT_ADD
                user32.ChangeWindowMessageFilter(WM_RUBRIC_SOLVE, 1)   # MSGFLT_ADD
            except Exception:
                pass
            logging.info("Single-instance sink window created on main thread: HWND %s", self.sink_hwnd)
        except Exception as e:
            logging.exception(f"Failed to create sink window: {e}")
            self.sink_hwnd = None

    def toggle_hud(self):
        """Toggles floating mini-HUD visibility on demand."""
        self.hud.toggle_visibility()

    def open_settings(self):
        """Restores main window and switches to Settings screen."""
        self.main_window.show_window()
        self.main_window.show_screen("settings")

    def test_caps_lock(self):
        """Triggers a 2-pulse test signal on keyboard LED with hardware verification."""
        logging.info("[*] Manual Caps Lock test triggered from Settings/UI.")
        orig = self.caps_indicator.enabled
        self.caps_indicator.enabled = True
        try:
            # First verify toggle ability
            toggled = self.caps_indicator.test_toggle()
            logging.info("[*] Caps Lock hardware toggle verification result: %s", toggled)
            self.caps_indicator.pulse("B")
        finally:
            self.caps_indicator.enabled = orig

    def get_excluded_window_rects(self):
        """Returns bounding boxes of active Rubric-Local windows to avoid self-capture in hover detection."""
        rects = []
        if hasattr(self, "hud") and self.hud and getattr(self.hud, "is_visible", False):
            r = self.hud.get_window_rect()
            if r:
                rects.append(r)
        if hasattr(self, "main_window") and self.main_window:
            r = self.main_window.get_window_rect()
            if r:
                rects.append(r)
        return rects

    def toggle_hover_pause(self) -> bool:
        """Toggles hover-to-answer pause state across hover detector, HUD, tray, and config."""
        if not hasattr(self, "hover_detector"):
            return False
        paused = self.hover_detector.toggle_pause()
        self.config.is_hover_paused = paused
        if hasattr(self, "hud") and self.hud:
            self.hud.is_paused = paused
            if hasattr(self.hud, "btn_pause") and self.hud.btn_pause:
                from rubric_local.ui.hud_overlay import C_EMERALD, C_AMBER
                self.hud.btn_pause.config(
                    text="⏸" if not paused else "▶",
                    fg=C_EMERALD if not paused else C_AMBER
                )
        save_config(self.config)
        logging.info("[RubricApp] Hover detection toggled: paused=%s", paused)
        return paused

    def on_hud_position_changed(self, x: int, y: int):
        """Persists HUD position when moved."""
        self.config.hud_pos_x = x
        self.config.hud_pos_y = y
        if getattr(self.config, "hud_pinned", False):
            save_config(self.config)

    def on_settings_saved(self, new_config):
        """Called when user saves settings from the UI."""
        self.config = new_config
        self.caps_indicator.enabled = new_config.caps_lock_indicator
        self.caps_indicator.pulse_on_sec = max(0.04, new_config.caps_pulse_on_ms / 1000.0)
        self.caps_indicator.pulse_off_sec = max(0.04, new_config.caps_pulse_off_ms / 1000.0)
        self.pipeline.model_name = new_config.model_name
        self.ollama.default_model = new_config.model_name
        self.ollama.base_url = new_config.ollama_url

        if hasattr(self, "hover_detector"):
            self.hover_detector.update_config(
                enabled=new_config.hover_to_answer_enabled,
                hover_delay_ms=new_config.hover_delay_ms,
                cooldown_sec=new_config.hover_cooldown_sec,
                movement_threshold_px=new_config.hover_movement_threshold_px
            )
            if new_config.is_hover_paused != self.hover_detector.is_paused:
                if new_config.is_hover_paused:
                    self.hover_detector.pause()
                else:
                    self.hover_detector.resume()

        if hasattr(self, "hud") and self.hud and self.hud.root:
            try:
                self.hud.opacity = new_config.hud_opacity
                self.hud.root.attributes("-alpha", new_config.hud_opacity)
                self.hud.always_on_top = new_config.hud_always_on_top
                self.hud.root.attributes("-topmost", new_config.hud_always_on_top)
                self.hud.is_pinned = new_config.hud_pinned
                self.hud.exclude_from_capture = new_config.exclude_from_capture
                if self.hud.hwnd:
                    from rubric_local.core.capture_exclusion import set_capture_exclusion
                    set_capture_exclusion(self.hud.hwnd, new_config.exclude_from_capture)
            except Exception as e:
                logging.warning("[HUD] Settings application warning: %s", e)
        logging.info("Settings updated and reloaded in active runtime.")


    def start(self):
        config_path = get_config_path()
        config_exists = config_path.exists()
        caps_enabled = getattr(self.config, "caps_lock_indicator", False)

        print("=" * 60)
        print("  Rubric-Local: On-Device Question Recognition & Solver Engine")
        print("=" * 60)
        print(f"[*] Version: {__version__}")
        print(f"[*] Process: PID={os.getpid()}, Executable={sys.executable}")
        print(f"[*] Config File: {config_path} (Exists: {config_exists})")
        print(f"[*] Caps Lock Indicator: {'ENABLED' if caps_enabled else 'DISABLED'}")
        print(f"[*] Indicator Mode: {self.config.indicator_mode}")
        print(f"[*] Local Model: {self.config.model_name}")
        print(f"[*] Ollama Endpoint: {self.config.ollama_url}")
        print(f"[*] Trigger Hotkey: {self.config.hotkey}")
        print(f"[*] Hover-to-Answer: {'ENABLED' if getattr(self.config, 'hover_to_answer_enabled', False) else 'DISABLED'}")

        logging.info("Starting runtime subsystems (PID=%d, Hotkey=%s, Model=%s)...",
                     os.getpid(), self.config.hotkey, self.config.model_name)

        # 1. Start Hotkey Listener & Single-Instance Sink immediately
        self.hotkey_thread = threading.Thread(target=self._hotkey_listener_loop, daemon=True)
        self.hotkey_thread.start()

        # 2. Start Tray Indicator immediately
        self.tray.start()

        # 3. Start Automatic Hover-to-Answer Engine
        if hasattr(self, "hover_detector"):
            self.hover_detector.start()

        # 4. Check Ollama daemon asynchronously so startup is instant (<20ms)
        def _async_check_ollama():
            try:
                if not self.ollama.is_available():
                    logging.warning("Ollama daemon is not responding at %s", self.config.ollama_url)
                    print(f"[!] Note: Ollama is not responding at {self.config.ollama_url}. Please ensure Ollama is running.")
                else:
                    logging.info("Local Ollama service confirmed reachable at %s", self.config.ollama_url)
            except Exception as e:
                logging.warning("Async Ollama check warning: %s", e)

        threading.Thread(target=_async_check_ollama, daemon=True).start()

        # 5. Run Main Window Tkinter loop on main thread
        logging.info("Rubric-Local application starting main GUI loop.")
        try:
            if self.main_window.root:
                self.main_window.root.mainloop()
        except KeyboardInterrupt:
            self.shutdown()
        except Exception as e:
            logging.exception(f"Unhandled exception in UI mainloop: {e}")
            self.shutdown()

    def trigger_solve(self, is_auto_hover: bool = False):
        """Called when hotkey is pressed, hover occurs, or triggered via tray or IPC."""
        logging.info("[Diagnostic %s] trigger_solve invoked (PID=%d, Thread=%s, is_solving=%s, is_auto_hover=%s)",
                     time.strftime("%H:%M:%S"), os.getpid(), threading.get_ident(), self.is_solving, is_auto_hover)
        if self.is_solving:
            logging.info("[Diagnostic %s] Solve already in progress; ignoring overlapping trigger.", time.strftime("%H:%M:%S"))
            return
        
        thread = threading.Thread(target=self._solve_worker, args=(is_auto_hover,), daemon=True)
        thread.start()

    def _solve_worker(self, is_auto_hover: bool = False):
        self.is_solving = True
        t_start = time.time()
        tracer = PipelineTracer()
        tracer.start_trace()
        logging.info("[Diagnostic %s] _solve_worker started (PID=%d, Thread=%s, is_auto_hover=%s)",
                     time.strftime("%H:%M:%S"), os.getpid(), threading.get_ident(), is_auto_hover)
        solve_id = self.hud.start_solve() if hasattr(self.hud, "start_solve") else 0
        show_hud = getattr(self.config, "hud_enabled", True) and getattr(self.config, "show_hud_on_solve", True)
        if show_hud:
            self.hud.timeout_sec = getattr(self.config, "answer_timeout_sec", 0)
            self.hud.show()
            self.hud.set_state("capturing", solve_id=solve_id)
        self.main_window.on_solve_started()

        self.tray.update_badge(
            badge="",
            status="thinking",
            tooltip="Rubric-Local — Thinking…"
        )

        def on_stream(token: str):
            if show_hud:
                self.hud.append_stream_token(token, solve_id=solve_id)

        def on_progress(stage: str):
            if show_hud:
                self.hud.set_state(stage, solve_id=solve_id)

        try:
            dup_check = self.hover_detector.question_cache.contains if (is_auto_hover and hasattr(self, "hover_detector")) else None
            res = self.pipeline.process_from_cursor(
                capture_width=self.config.capture_width,
                capture_height=self.config.capture_height,
                stream_callback=on_stream,
                progress_callback=on_progress,
                is_duplicate_fn=dup_check,
                tracer=tracer
            )

            # Update cache and notify hover detector of completed solve
            if hasattr(self, "hover_detector"):
                self.hover_detector.notify_solve_completed()
                if res.parsed_question and res.parsed_question.question_text:
                    self.hover_detector.question_cache.add(res.parsed_question.question_text)

            # Update Main Window with full result
            self.main_window.on_solve_completed(res)

            # Build centralized type-aware presentation
            presentation = build_answer_presentation(res.parsed_question, res.answer_result)

            badge = presentation.badge
            is_mcq = (presentation.question_type == TYPE_MCQ)
            is_valid = presentation.is_validated

            logging.info("[Diagnostic %s] Solve completed in %.1fms: type=%s, badge=%s, is_validated=%s",
                         time.strftime("%H:%M:%S"), (time.time() - t_start) * 1000.0,
                         presentation.question_type, badge, is_valid)

            rec_hud = tracer.begin_stage("HUD Update")
            if not is_valid or presentation.question_type in [TYPE_UNCERTAIN, TYPE_ERROR]:
                if show_hud:
                    self.hud.timeout_sec = getattr(self.config, "answer_timeout_sec", 0)
                    self.hud.set_state("error", presentation=presentation, solve_id=solve_id)
                self.tray.update_badge(
                    badge="?",
                    status="error",
                    is_validated=False,
                    is_multiple_choice=is_mcq,
                    tooltip=f"Rubric-Local — {presentation.headline}"
                )
                tracer.end_stage(rec_hud, success=False, details={"state": "uncertain", "error": presentation.explanation})
                print(f"[*] [Solve Worker] Answer uncertain/unvalidated: triggering indicator for '?' (Caps Lock enabled: {self.caps_indicator.enabled})")
                self.caps_indicator.pulse("?")
            else:
                if show_hud:
                    self.hud.timeout_sec = getattr(self.config, "answer_timeout_sec", 0)
                    self.hud.set_state("answer", presentation=presentation, solve_id=solve_id)
                self.tray.update_badge(
                    badge=badge,
                    status="normal",
                    is_validated=True,
                    is_multiple_choice=is_mcq,
                    tooltip=f"Rubric-Local — {presentation.headline}"
                )
                tracer.end_stage(rec_hud, success=True, details={"badge": badge, "type": presentation.question_type})
                print(f"[*] [Solve Worker] Answer validated: triggering indicator for '{badge}' (Caps Lock enabled: {self.caps_indicator.enabled})")
                self.caps_indicator.pulse(badge)

            # Auto-copy answer if enabled
            if getattr(self.config, "auto_copy_answer", False):
                try:
                    if hasattr(self, "hud") and self.hud:
                        self.hud.copy_answer_to_clipboard()
                except Exception:
                    pass

            # Save local history with complete diagnostics
            if self.config.save_history_locally:
                self._save_history_entry(res)

        except DuplicateQuestionError as dup:
            logging.info("[Diagnostic %s] Duplicate question ignored in auto-hover: %s", time.strftime("%H:%M:%S"), dup)
            if hasattr(self, "hover_detector"):
                self.hover_detector.notify_solve_completed()

        except Exception as ex:
            if hasattr(self, "hover_detector"):
                self.hover_detector.notify_solve_completed()
            err_msg = str(ex)
            logging.exception(f"Error during solve worker execution: {err_msg}")
            self.main_window.on_solve_error(err_msg)
            err_ans = AnswerResult(
                answer_option="!",
                proposed_option="!",
                validation_status="error",
                is_validated=False,
                error=err_msg,
                tray_badge="!"
            )
            err_presentation = build_answer_presentation(None, err_ans)
            if show_hud:
                self.hud.timeout_sec = getattr(self.config, "answer_timeout_sec", 0)
                self.hud.set_state("error", presentation=err_presentation, solve_id=solve_id)
            self.tray.update_badge(
                badge="!",
                status="error",
                tooltip="Rubric-Local — Error (!)"
            )
            print(f"[*] [Solve Worker] Solve error: triggering indicator for '!' (Caps Lock enabled: {self.caps_indicator.enabled})")
            self.caps_indicator.pulse("!")

        finally:
            self.is_solving = False
            logging.info("\n" + tracer.get_summary_report())
            logging.info("[Diagnostic %s] Solve worker finished. is_solving reset to False.", time.strftime("%H:%M:%S"))

    def _save_history_entry(self, res):
        try:
            history_file = get_app_dir() / "history.jsonl"
            entry = {
                "timestamp": time.time(),
                "cursor_pos": res.cursor_pos,
                "question": res.parsed_question.question_text,
                "options": res.parsed_question.options,
                "proposed_answer": res.answer_result.proposed_option,
                "answer": res.answer_result.answer_option,
                "is_validated": res.answer_result.is_validated,
                "confidence": res.answer_result.confidence,
                "explanation": res.answer_result.explanation,
                "code_snippet": getattr(res.answer_result, "code_snippet", None),
                "code_language": getattr(res.answer_result, "code_language", ""),
                "question_type": getattr(res.answer_result, "question_type", "mcq"),
                "direct_answer": getattr(res.answer_result, "direct_answer", ""),
                "timing_ms": {
                    "capture": res.capture_time_ms,
                    "ocr": res.ocr_time_ms,
                    "llm": res.llm_time_ms,
                    "total": res.total_time_ms
                }
            }
            with open(history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass


    def _hotkey_listener_loop(self):
        """Win32 RegisterHotKey loop and single-instance activation message sink."""
        HOTKEY_ID = 1001
        # Alt + / (VK_OEM_2 is '/')
        MOD_ALT = win32con.MOD_ALT
        MOD_NOREPEAT = 0x4000
        VK_SLASH = 0xBF  # VK_OEM_2

        self.hotkey_thread_id = kernel32.GetCurrentThreadId()

        # Create hidden window for message pump and single-instance activation
        wc = win32gui.WNDCLASS()
        wc.lpszClassName = SINGLE_INSTANCE_SINK_CLASS

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == WM_RUBRIC_WAKEUP:
                logging.info("Received WM_RUBRIC_WAKEUP in sink window procedure. Restoring main window.")
                if hasattr(self, "main_window") and self.main_window:
                    self.main_window.show_window()
                return 0
            return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

        wc.lpfnWndProc = wndproc

        try:
            win32gui.RegisterClass(wc)
        except pywintypes.error as e:
            # 1410: Class already exists across re-runs in same process
            if e.winerror != 1410:
                logging.warning(f"Sink window class registration note: {e}")

        hwnd = None
        try:
            hwnd = win32gui.CreateWindow(
                wc.lpszClassName, "RubricLocalSinkWindow", 0, 0, 0, 0, 0, 0, 0, 0, None
            )
            self.hotkey_hwnd = hwnd

            # Enable UIPI message filter so non-elevated or background instances can signal
            try:
                user32.ChangeWindowMessageFilter(WM_RUBRIC_WAKEUP, 1)  # MSGFLT_ADD
                user32.ChangeWindowMessageFilter(WM_RUBRIC_SOLVE, 1)   # MSGFLT_ADD
            except Exception:
                pass

            if not user32.RegisterHotKey(hwnd, HOTKEY_ID, MOD_ALT | MOD_NOREPEAT, VK_SLASH):
                err = ctypes.GetLastError()
                if err == 1409:
                    logging.warning("Global hotkey Alt+/ already registered by another application (Error 1409).")
                    print("[!] Note: Global hotkey Alt+/ is in use by another application. Trigger solve via system tray or UI.")
                else:
                    logging.warning(f"Failed to register global hotkey Alt+/ (Win32 Error: {err}).")
                    print(f"[!] Note: Win32 hotkey registration error: {err}. Trigger solve via system tray or UI.")
                # Resilient behavior: DO NOT return! Continue running message pump for single-instance wake-up.
            else:
                self.hotkey_registered = True
                logging.info("Global hotkey registered successfully: Alt + /")
                print("[*] Global hotkey registered successfully: Alt + /")

            while self.is_running:
                ret, msg = win32gui.GetMessage(0, 0, 0)
                if ret == 0:  # WM_QUIT
                    break
                msg_hwnd, msg_id, wparam, lparam, msg_time, pt = msg
                if msg_id == win32con.WM_HOTKEY and wparam == HOTKEY_ID:
                    logging.info("[Diagnostic %s] WM_HOTKEY Alt+/ received in hotkey thread. Calling trigger_solve.", time.strftime("%H:%M:%S"))
                    self.trigger_solve()
                elif msg_id == WM_RUBRIC_WAKEUP:
                    logging.info("[Diagnostic %s] Received WM_RUBRIC_WAKEUP in hotkey loop. Restoring main window.", time.strftime("%H:%M:%S"))
                    if hasattr(self, "main_window") and self.main_window:
                        self.main_window.show_window()
                elif msg_id == WM_RUBRIC_SOLVE:
                    logging.info("[Diagnostic %s] Received WM_RUBRIC_SOLVE in hotkey loop. Triggering solve.", time.strftime("%H:%M:%S"))
                    self.trigger_solve()
                win32gui.TranslateMessage(msg)
                win32gui.DispatchMessage(msg)
        except Exception as e:
            logging.exception(f"Hotkey/Sink message loop error: {e}")
        finally:
            if hwnd and self.hotkey_registered:
                try:
                    user32.UnregisterHotKey(hwnd, HOTKEY_ID)
                except Exception:
                    pass
                self.hotkey_registered = False
            if hwnd:
                try:
                    win32gui.DestroyWindow(hwnd)
                except Exception:
                    pass
            self.hotkey_hwnd = None

    def on_hud_close(self):
        self.hud.set_state("ready")
        self.tray.update_badge("", "ready", tooltip="Rubric-Local: Ready (Alt+/)")

    def shutdown(self):
        logging.info("Shutting down Rubric-Local application...")
        self.is_running = False
        if hasattr(self, "caps_indicator"):
            try:
                self.caps_indicator.restore_safety_state()
            except Exception:
                pass
        if self.hotkey_hwnd and self.hotkey_registered:
            try:
                user32.UnregisterHotKey(self.hotkey_hwnd, 1001)
                self.hotkey_registered = False
            except Exception:
                pass
        if self.hotkey_thread_id:
            try:
                user32.PostThreadMessageW(self.hotkey_thread_id, win32con.WM_QUIT, 0, 0)
            except Exception:
                pass
        if hasattr(self, "hover_detector"):
            try:
                self.hover_detector.stop()
            except Exception:
                pass
        if hasattr(self, "tray"):
            try:
                self.tray.stop()
            except Exception:
                pass
        if hasattr(self, "hud"):
            try:
                self.hud.destroy()
            except Exception:
                pass
        if hasattr(self, "main_window"):
            try:
                self.main_window.destroy()
            except Exception:
                pass
        if hasattr(self, "sink_hwnd") and self.sink_hwnd:
            try:
                win32gui.DestroyWindow(self.sink_hwnd)
            except Exception:
                pass
            self.sink_hwnd = None
        if hasattr(self, "_mutex") and self._mutex:
            try:
                win32api.CloseHandle(self._mutex)
            except Exception:
                pass
            self._mutex = None
        sys.exit(0)

def main():
    setup_file_logging()
    logging.info("=" * 65)
    logging.info("Starting Rubric-Local v%s (PID=%d)", __version__, os.getpid())
    logging.info("Python Executable: %s", sys.executable)
    logging.info("Working Directory: %s", os.getcwd())

    # 1. Single-Instance Check BEFORE any GUI creation
    mutex_name = "Local\\RubricLocalSingleInstanceMutex"
    mutex = win32event.CreateMutex(None, False, mutex_name)
    last_err = win32api.GetLastError()
    if last_err == winerror.ERROR_ALREADY_EXISTS:
        is_solve_trigger = any(arg in sys.argv for arg in ["--solve", "-s", "/solve"])
        target_msg = WM_RUBRIC_SOLVE if is_solve_trigger else WM_RUBRIC_WAKEUP
        msg_name = "WM_RUBRIC_SOLVE" if is_solve_trigger else "WM_RUBRIC_WAKEUP"
        logging.info("[Diagnostic %s] Existing Rubric-Local instance detected via Mutex (PID=%d). Sending %s to primary instance.",
                     time.strftime("%H:%M:%S"), os.getpid(), msg_name)
        sink_hwnd = win32gui.FindWindow(SINGLE_INSTANCE_SINK_CLASS, None)
        if sink_hwnd:
            logging.info("[Diagnostic %s] Found active sink window (HWND %s). Posting %s.",
                         time.strftime("%H:%M:%S"), sink_hwnd, msg_name)
            win32gui.PostMessage(sink_hwnd, target_msg, 0, 0)
            if not is_solve_trigger:
                try:
                    win32gui.SetForegroundWindow(sink_hwnd)
                except Exception:
                    pass
            print(f"[*] Activated existing Rubric-Local instance (sent {msg_name}). Exiting secondary process (PID={os.getpid()}).")
            sys.exit(0)
        else:
            logging.warning("[Diagnostic %s] Mutex was held but sink window not found (possible orphaned process). Attempting broadcast %s.",
                            time.strftime("%H:%M:%S"), msg_name)
            win32gui.PostMessage(win32con.HWND_BROADCAST, target_msg, 0, 0)
            sys.exit(0)

    # 2. Main Application Lifecycle
    try:
        app = RubricApp(mutex=mutex)
        app.start()
    except Exception as ex:
        logging.exception("Fatal unhandled exception in Rubric-Local startup: %s", ex)
        try:
            ctypes.windll.user32.MessageBoxW(
                0,
                f"Rubric-Local encountered a critical startup error:\n\n{ex}\n\nPlease check the diagnostic log at:\n{get_app_dir() / 'rubric_local.log'}",
                "Rubric-Local Startup Error",
                0x10  # MB_ICONERROR
            )
        except Exception:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
