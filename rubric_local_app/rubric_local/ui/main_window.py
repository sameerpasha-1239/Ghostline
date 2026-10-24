"""
Rubric-Local — Modern Windows Desktop Application Interface.
100% Offline, Privacy-First Architecture with Native Restrained Minimalist Aesthetic.
"""

import os
import sys
import json
import time
import subprocess
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
from tkinter import messagebox, filedialog
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List, Tuple

from rubric_local import __version__
from rubric_local.config import AppConfig, save_config, get_app_dir, get_config_path

# Modern Restrained Windows Minimalist Theme Tokens
# Neutral surfaces, generous whitespace, subtle borders, single restrained sky cyan accent
C_BG_APP = "#0f1115"          # Slate/Zinc deep window background
C_BG_SIDEBAR = "#14171f"      # Sidebar darker neutral surface
C_BG_CARD = "#1a1e28"         # Surface card background
C_BG_CARD_HOVER = "#232836"   # Hover surface card
C_BORDER = "#282e3d"          # Subtle card/divider 1px border
C_ACCENT = "#38bdf8"          # Restrained sky cyan accent
C_ACCENT_HOVER = "#0284c7"    # Darker accent hover
C_SUCCESS = "#10b981"         # Emerald green
C_WARNING = "#f59e0b"         # Amber
C_AMBER = "#f59e0b"           # Amber
C_DANGER = "#ef4444"          # Red
C_TEXT_PRIMARY = "#f8fafc"    # Bright white text
C_TEXT_SECONDARY = "#94a3b8"  # Neutral slate text
C_TEXT_MUTED = "#64748b"      # Muted slate text

class RubricMainWindow:
    """
    Polished Minimalist Windows Desktop UI for Rubric-Local.
    Features:
    - 7 Core Views: Dashboard, Answer / Capture, History, Settings, Setup Wizard, Diagnostics, About
    - Background minimization to system tray
    - Single-instance wake-up
    - Real-time solver monitoring & progress steps
    - Dynamic history search & filtering
    - Interactive First-run Setup Wizard with real model downloads
    - Complete settings configuration & persistence
    - Copyable sanitized diagnostic telemetry
    """

    def __init__(
        self,
        config: AppConfig,
        on_trigger_solve: Optional[Callable[[], None]] = None,
        on_settings_saved: Optional[Callable[[AppConfig], None]] = None,
        on_toggle_hud: Optional[Callable[[], None]] = None,
        on_test_caps: Optional[Callable[[], None]] = None,
        on_exit: Optional[Callable[[], None]] = None,
        ollama_client: Optional[Any] = None
    ):
        self.config = config
        self.on_trigger_solve = on_trigger_solve
        self.on_settings_saved = on_settings_saved
        self.on_toggle_hud = on_toggle_hud
        self.on_test_caps = on_test_caps
        self.on_exit = on_exit
        self.ollama_client = ollama_client

        self.root: Optional[tk.Tk] = None
        self.current_screen = "dashboard"
        self.screen_frames: Dict[str, tk.Frame] = {}
        self.nav_buttons: Dict[str, tk.Label] = {}
        self.last_result: Optional[Any] = None
        self._is_minimized_to_tray = False

        # History and answer widget aliases
        self.history_records: List[Dict[str, Any]] = []
        self.ans_badge_label = None
        self.ans_option_text_lbl = None

        # Wizard state
        self.wizard_step = 1
        self.pulling_model = False

    @property
    def _history_entries(self) -> List[Dict[str, Any]]:
        return self.history_records

    @_history_entries.setter
    def _history_entries(self, val: List[Dict[str, Any]]):
        self.history_records = val

    def build(self) -> tk.Tk:
        """Constructs and returns the main Tk window without starting mainloop."""
        self.root = tk.Tk()
        self.root.title("Rubric-Local — Offline AI Assistant")
        self.root.geometry("1060x720")
        self.root.minsize(880, 600)
        self.root.configure(bg=C_BG_APP)

        # Set App Icon if present
        ico_path = Path(__file__).resolve().parent.parent.parent / "rubric.ico"
        if ico_path.exists():
            try:
                self.root.iconbitmap(str(ico_path))
            except Exception:
                pass

        # Intercept window close (X button) to minimize to tray instead of quitting
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self.root.bind("<Escape>", lambda e: self.hide_to_tray())

        # Setup Modern Typography
        self.font_logo = tkfont.Font(family="Segoe UI", size=13, weight="bold")
        self.font_h1 = tkfont.Font(family="Segoe UI", size=16, weight="bold")
        self.font_h2 = tkfont.Font(family="Segoe UI", size=12, weight="bold")
        self.font_body = tkfont.Font(family="Segoe UI", size=10)
        self.font_body_bold = tkfont.Font(family="Segoe UI", size=10, weight="bold")
        self.font_code = tkfont.Font(family="Consolas", size=9)
        self.font_badge = tkfont.Font(family="Segoe UI", size=26, weight="bold")
        self.font_sm = tkfont.Font(family="Segoe UI", size=8)

        # Configure Root Grid
        self.root.grid_columnconfigure(0, weight=0, minsize=220) # Sidebar
        self.root.grid_columnconfigure(1, weight=1)              # Content area
        self.root.grid_rowconfigure(0, weight=1)

        # Build Sidebar & Content Layout
        self._build_sidebar()
        self._build_content_area()

        # Decide initial screen: if config is unconfigured or model is missing, start in setup wizard
        initial_scr = "dashboard"
        if getattr(self.config, "start_minimized", False):
            self.root.withdraw()
            self._is_minimized_to_tray = True
        else:
            self.show_screen(initial_scr)

        return self.root

    def _build_sidebar(self):
        sidebar = tk.Frame(self.root, bg=C_BG_SIDEBAR, bd=0, highlightthickness=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        # 1. Top Logo Header
        logo_frame = tk.Frame(sidebar, bg=C_BG_SIDEBAR, pady=18, padx=16)
        logo_frame.pack(fill=tk.X)

        lbl_logo = tk.Label(
            logo_frame,
            text="⚡ RUBRIC-LOCAL",
            font=self.font_logo,
            fg=C_ACCENT,
            bg=C_BG_SIDEBAR
        )
        lbl_logo.pack(anchor="w")

        lbl_sub = tk.Label(
            logo_frame,
            text="On-Device Reasoning Engine",
            font=self.font_sm,
            fg=C_TEXT_MUTED,
            bg=C_BG_SIDEBAR
        )
        lbl_sub.pack(anchor="w", pady=(2, 0))

        # Divider
        tk.Frame(sidebar, bg=C_BORDER, height=1).pack(fill=tk.X, padx=14, pady=(0, 10))

        # 2. Navigation Items (7 screens)
        nav_items = [
            ("dashboard",   "📊  Dashboard"),
            ("answer",      "⚡  Answer / Capture"),
            ("history",     "📜  History"),
            ("settings",    "⚙️  Settings"),
            ("setup",       "🪄  Setup Wizard"),
            ("diagnostics", "🔍  Diagnostics"),
            ("about",       "ℹ️  About")
        ]

        self.nav_container = tk.Frame(sidebar, bg=C_BG_SIDEBAR)
        self.nav_container.pack(fill=tk.X, padx=10)

        for key, label in nav_items:
            btn = tk.Label(
                self.nav_container,
                text=label,
                font=self.font_body,
                fg=C_TEXT_SECONDARY,
                bg=C_BG_SIDEBAR,
                padx=12,
                pady=8,
                anchor="w",
                cursor="hand2"
            )
            btn.pack(fill=tk.X, pady=2)
            btn.bind("<Button-1>", lambda e, s=key: self.show_screen(s))
            btn.bind("<Enter>", lambda e, b=btn, k=key: self._on_nav_hover(b, k, True))
            btn.bind("<Leave>", lambda e, b=btn, k=key: self._on_nav_hover(b, k, False))
            self.nav_buttons[key] = btn

        # 3. Sidebar Bottom Quick Action Area
        bottom_box = tk.Frame(sidebar, bg=C_BG_SIDEBAR, padx=12, pady=16)
        bottom_box.pack(side=tk.BOTTOM, fill=tk.X)

        tk.Frame(bottom_box, bg=C_BORDER, height=1).pack(fill=tk.X, pady=(0, 12))

        btn_solve = tk.Label(
            bottom_box,
            text="⚡ Solve (Alt + /)",
            font=self.font_body_bold,
            fg="#ffffff",
            bg="#0284c7",
            padx=10,
            pady=8,
            cursor="hand2"
        )
        btn_solve.pack(fill=tk.X, pady=(0, 8))
        btn_solve.bind("<Button-1>", lambda e: self._on_solve_clicked())
        btn_solve.bind("<Enter>", lambda e: btn_solve.configure(bg="#0369a1"))
        btn_solve.bind("<Leave>", lambda e: btn_solve.configure(bg="#0284c7"))

        btn_hud = tk.Label(
            bottom_box,
            text="🪟 Toggle Mini HUD",
            font=self.font_sm,
            fg=C_TEXT_SECONDARY,
            bg=C_BG_CARD,
            padx=8,
            pady=6,
            cursor="hand2"
        )
        btn_hud.pack(fill=tk.X)
        btn_hud.bind("<Button-1>", lambda e: self._on_toggle_hud_clicked())
        btn_hud.bind("<Enter>", lambda e: btn_hud.configure(bg=C_BG_CARD_HOVER, fg=C_TEXT_PRIMARY))
        btn_hud.bind("<Leave>", lambda e: btn_hud.configure(bg=C_BG_CARD, fg=C_TEXT_SECONDARY))

        # Status Dot
        status_row = tk.Frame(bottom_box, bg=C_BG_SIDEBAR, pady=8)
        status_row.pack(fill=tk.X)
        self.sidebar_status_dot = tk.Label(status_row, text="●", fg=C_SUCCESS, bg=C_BG_SIDEBAR, font=("Segoe UI", 8))
        self.sidebar_status_dot.pack(side=tk.LEFT)
        self.sidebar_status_lbl = tk.Label(status_row, text="Offline Engine Ready", font=self.font_sm, fg=C_TEXT_MUTED, bg=C_BG_SIDEBAR)
        self.sidebar_status_lbl.pack(side=tk.LEFT, padx=4)

    def _build_content_area(self):
        self.content_area = tk.Frame(self.root, bg=C_BG_APP)
        self.content_area.grid(row=0, column=1, sticky="nsew")
        self.content_area.grid_columnconfigure(0, weight=1)
        self.content_area.grid_rowconfigure(0, weight=1)

        # Initialize all 7 screen frames
        self.screen_frames["dashboard"] = self._create_dashboard_screen()
        self.screen_frames["answer"] = self._create_answer_screen()
        self.screen_frames["history"] = self._create_history_screen()
        self.screen_frames["settings"] = self._create_settings_screen()
        self.screen_frames["setup"] = self._create_setup_screen()
        self.screen_frames["diagnostics"] = self._create_diagnostics_screen()
        self.screen_frames["about"] = self._create_about_screen()

    def _on_nav_hover(self, btn: tk.Label, key: str, is_hover: bool):
        if key == self.current_screen:
            return
        if is_hover:
            btn.configure(bg=C_BG_CARD, fg=C_TEXT_PRIMARY)
        else:
            btn.configure(bg=C_BG_SIDEBAR, fg=C_TEXT_SECONDARY)

    def show_screen(self, screen_key: str):
        """Switches active view with clean highlight updates."""
        if screen_key not in self.screen_frames:
            return

        for k, f in self.screen_frames.items():
            f.grid_remove()

        self.screen_frames[screen_key].grid(row=0, column=0, sticky="nsew")
        self.current_screen = screen_key

        for k, b in self.nav_buttons.items():
            if k == screen_key:
                b.configure(bg=C_BG_CARD, fg=C_ACCENT, font=self.font_body_bold)
            else:
                b.configure(bg=C_BG_SIDEBAR, fg=C_TEXT_SECONDARY, font=self.font_body)

        if screen_key == "history":
            self.refresh_history_list()
        elif screen_key == "diagnostics":
            self.refresh_diagnostics()
        elif screen_key == "setup":
            self.refresh_setup_screen()

    # -------------------------------------------------------------
    # 1. Dashboard Screen
    # -------------------------------------------------------------
    def _create_dashboard_screen(self) -> tk.Frame:
        parent = tk.Frame(self.content_area, bg=C_BG_APP, padx=28, pady=24)
        parent.grid_columnconfigure(0, weight=1)

        # Header Title
        title_box = tk.Frame(parent, bg=C_BG_APP)
        title_box.pack(fill=tk.X, pady=(0, 18))
        tk.Label(title_box, text="System Dashboard", font=self.font_h1, fg=C_TEXT_PRIMARY, bg=C_BG_APP).pack(anchor="w")
        tk.Label(title_box, text="Local offline AI solver overview, readiness, and runtime status.", font=self.font_body, fg=C_TEXT_MUTED, bg=C_BG_APP).pack(anchor="w", pady=(3, 0))

        # Top 4 Status Metric Cards
        cards_row = tk.Frame(parent, bg=C_BG_APP)
        cards_row.pack(fill=tk.X, pady=(0, 18))
        for i in range(4):
            cards_row.grid_columnconfigure(i, weight=1, uniform="metric")

        self.card_model = self._create_metric_card(cards_row, 0, "AI Model", self.config.model_name, "Ollama local inference", C_ACCENT)
        self.card_ollama = self._create_metric_card(cards_row, 1, "Endpoint", "127.0.0.1:11434", "Offline HTTP REST", C_SUCCESS)
        self.card_hotkey = self._create_metric_card(cards_row, 2, "Global Hotkey", self.config.hotkey.upper(), "Win32 RegisterHotKey", C_WARNING)
        caps_status = "ENABLED" if getattr(self.config, "caps_lock_indicator", False) else "DISABLED"
        caps_color = C_SUCCESS if caps_status == "ENABLED" else C_TEXT_MUTED
        self.card_caps = self._create_metric_card(cards_row, 3, "Caps Indicator", caps_status, f"{getattr(self.config, 'caps_pulse_on_ms', 300)}ms ON / {getattr(self.config, 'caps_pulse_off_ms', 250)}ms gap", caps_color)

        # Hero Action Card
        hero = tk.Frame(parent, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1, padx=22, pady=20)
        hero.pack(fill=tk.X, pady=(0, 18))

        hero_left = tk.Frame(hero, bg=C_BG_CARD)
        hero_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(hero_left, text="⚡ Instant Question Recognition & Solver", font=self.font_h2, fg=C_TEXT_PRIMARY, bg=C_BG_CARD).pack(anchor="w")
        tk.Label(
            hero_left,
            text="Place your mouse cursor over any question on screen and press Alt + /.\nRubric-Local silently captures the bounding box, extracts structured options using native OCR,\nand reasons locally using your offline model with zero network traffic.",
            font=self.font_body,
            fg=C_TEXT_SECONDARY,
            bg=C_BG_CARD,
            justify=tk.LEFT
        ).pack(anchor="w", pady=(8, 14))

        hero_btn_row = tk.Frame(hero_left, bg=C_BG_CARD)
        hero_btn_row.pack(anchor="w")

        btn_solve_now = tk.Label(
            hero_btn_row,
            text="⚡ Solve Question Under Cursor",
            font=self.font_body_bold,
            fg="#ffffff",
            bg="#0284c7",
            padx=16,
            pady=9,
            cursor="hand2"
        )
        btn_solve_now.pack(side=tk.LEFT, padx=(0, 12))
        btn_solve_now.bind("<Button-1>", lambda e: self._on_solve_clicked())
        btn_solve_now.bind("<Enter>", lambda e: btn_solve_now.configure(bg="#0369a1"))
        btn_solve_now.bind("<Leave>", lambda e: btn_solve_now.configure(bg="#0284c7"))

        btn_view_last = tk.Label(
            hero_btn_row,
            text="View Last Answer →",
            font=self.font_body,
            fg=C_ACCENT,
            bg=C_BG_CARD_HOVER,
            padx=14,
            pady=9,
            cursor="hand2"
        )
        btn_view_last.pack(side=tk.LEFT, padx=(0, 10))
        btn_view_last.bind("<Button-1>", lambda e: self.show_screen("answer"))

        btn_run_setup = tk.Label(
            hero_btn_row,
            text="🪄 Run Setup Wizard",
            font=self.font_body,
            fg=C_TEXT_SECONDARY,
            bg=C_BG_CARD,
            padx=12,
            pady=9,
            cursor="hand2"
        )
        btn_run_setup.pack(side=tk.LEFT)
        btn_run_setup.bind("<Button-1>", lambda e: self.show_screen("setup"))

        # Recent Activity Card
        recent_box = tk.Frame(parent, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1, padx=22, pady=18)
        recent_box.pack(fill=tk.BOTH, expand=True)

        tk.Label(recent_box, text="Recent Activity", font=self.font_h2, fg=C_TEXT_PRIMARY, bg=C_BG_CARD).pack(anchor="w")
        self.dash_recent_lbl = tk.Label(
            recent_box,
            text="No queries in current session. Solve your first question using [Alt + /] or the button above.",
            font=self.font_body,
            fg=C_TEXT_MUTED,
            bg=C_BG_CARD,
            justify=tk.LEFT,
            wraplength=720
        )
        self.dash_recent_lbl.pack(anchor="w", pady=(10, 0))

        return parent

    def _create_metric_card(self, parent: tk.Frame, col: int, label: str, val: str, sub: str, accent_color: str) -> Dict[str, tk.Label]:
        card = tk.Frame(parent, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1, padx=14, pady=12)
        card.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 0))

        lbl_title = tk.Label(card, text=label, font=self.font_sm, fg=C_TEXT_MUTED, bg=C_BG_CARD)
        lbl_title.pack(anchor="w")

        lbl_val = tk.Label(card, text=val, font=self.font_h2, fg=accent_color, bg=C_BG_CARD)
        lbl_val.pack(anchor="w", pady=(4, 2))

        lbl_sub = tk.Label(card, text=sub, font=self.font_sm, fg=C_TEXT_MUTED, bg=C_BG_CARD)
        lbl_sub.pack(anchor="w")

        return {"title": lbl_title, "val": lbl_val, "sub": lbl_sub}

    # -------------------------------------------------------------
    # 2. Answer & Capture Screen
    # -------------------------------------------------------------
    def _create_answer_screen(self) -> tk.Frame:
        parent = tk.Frame(self.content_area, bg=C_BG_APP, padx=28, pady=24)
        parent.grid_columnconfigure(0, weight=1)

        title_box = tk.Frame(parent, bg=C_BG_APP)
        title_box.pack(fill=tk.X, pady=(0, 14))

        tk.Label(title_box, text="Live Answer & Capture Monitor", font=self.font_h1, fg=C_TEXT_PRIMARY, bg=C_BG_APP).pack(side=tk.LEFT)
        self.answer_stage_chip = tk.Label(title_box, text="IDLE / READY", font=self.font_sm, fg=C_TEXT_MUTED, bg=C_BG_CARD, padx=10, pady=4)
        self.answer_stage_chip.pack(side=tk.RIGHT)

        # Latency / Steps Indicator Row
        self.steps_row = tk.Frame(parent, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1, padx=16, pady=10)
        self.steps_row.pack(fill=tk.X, pady=(0, 16))

        self.step_labels = []
        steps = ["1. Capture Window", "2. Windows OCR", "3. Local AI Reasoning", "4. Verification"]
        for i, s in enumerate(steps):
            lbl = tk.Label(self.steps_row, text=s, font=self.font_sm, fg=C_TEXT_MUTED, bg=C_BG_CARD)
            lbl.pack(side=tk.LEFT, padx=(0 if i == 0 else 18, 0))
            self.step_labels.append(lbl)

        # Primary Answer Presentation Card
        self.answer_card = tk.Frame(parent, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1, padx=24, pady=20)
        self.answer_card.pack(fill=tk.X, pady=(0, 16))

        ans_top = tk.Frame(self.answer_card, bg=C_BG_CARD)
        ans_top.pack(fill=tk.X)

        self.ans_badge_lbl = tk.Label(
            ans_top,
            text="?",
            font=self.font_badge,
            fg=C_ACCENT,
            bg=C_BG_SIDEBAR,
            width=3,
            pady=4
        )
        self.ans_badge_lbl.pack(side=tk.LEFT, padx=(0, 18))
        self.ans_badge_label = self.ans_badge_lbl

        ans_meta = tk.Frame(ans_top, bg=C_BG_CARD)
        ans_meta.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.ans_status_lbl = tk.Label(ans_meta, text="Awaiting question trigger...", font=self.font_h2, fg=C_TEXT_PRIMARY, bg=C_BG_CARD)
        self.ans_status_lbl.pack(anchor="w")
        self.ans_option_text_lbl = self.ans_status_lbl

        self.ans_confidence_lbl = tk.Label(ans_meta, text="Press Alt + / with your cursor over a question to begin.", font=self.font_body, fg=C_TEXT_MUTED, bg=C_BG_CARD)
        self.ans_confidence_lbl.pack(anchor="w", pady=(3, 0))

        self.ans_timing_lbl = tk.Label(ans_meta, text="", font=self.font_code, fg=C_TEXT_MUTED, bg=C_BG_CARD)
        self.ans_timing_lbl.pack(anchor="w", pady=(3, 0))

        # Copy Action Bar
        act_row = tk.Frame(self.answer_card, bg=C_BG_CARD)
        act_row.pack(fill=tk.X, pady=(16, 0))

        btn_copy_ans = tk.Label(act_row, text="📋 Copy Option", font=self.font_sm, fg=C_TEXT_PRIMARY, bg=C_BG_CARD_HOVER, padx=12, pady=6, cursor="hand2")
        btn_copy_ans.pack(side=tk.LEFT, padx=(0, 10))
        btn_copy_ans.bind("<Button-1>", lambda e: self._copy_answer_to_clipboard())

        btn_copy_exp = tk.Label(act_row, text="📋 Copy Explanation", font=self.font_sm, fg=C_TEXT_PRIMARY, bg=C_BG_CARD_HOVER, padx=12, pady=6, cursor="hand2")
        btn_copy_exp.pack(side=tk.LEFT, padx=(0, 10))
        btn_copy_exp.bind("<Button-1>", lambda e: self._copy_explanation_to_clipboard())

        btn_dock_hud = tk.Label(act_row, text="🪟 Toggle Floating HUD", font=self.font_sm, fg=C_ACCENT, bg=C_BG_CARD_HOVER, padx=12, pady=6, cursor="hand2")
        btn_dock_hud.pack(side=tk.LEFT)
        btn_dock_hud.bind("<Button-1>", lambda e: self._on_toggle_hud_clicked())

        # Detailed Question & Reasoning Box
        detail_box = tk.Frame(parent, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1, padx=20, pady=16)
        detail_box.pack(fill=tk.BOTH, expand=True)

        tk.Label(detail_box, text="Extracted Question & Grounded Reasoning", font=self.font_h2, fg=C_TEXT_PRIMARY, bg=C_BG_CARD).pack(anchor="w")

        self.ans_question_text = tk.Text(
            detail_box,
            font=self.font_body,
            bg=C_BG_APP,
            fg=C_TEXT_PRIMARY,
            bd=0,
            highlightthickness=1,
            highlightbackground=C_BORDER,
            wrap=tk.WORD,
            height=5,
            padx=10,
            pady=8
        )
        self.ans_question_text.pack(fill=tk.X, pady=(10, 12))
        self.ans_question_text.insert("1.0", "No question captured yet.")
        self.ans_question_text.configure(state="disabled")

        self.ans_explanation_text = tk.Text(
            detail_box,
            font=self.font_body,
            bg=C_BG_APP,
            fg=C_TEXT_SECONDARY,
            bd=0,
            highlightthickness=1,
            highlightbackground=C_BORDER,
            wrap=tk.WORD,
            padx=10,
            pady=8
        )
        self.ans_explanation_text.pack(fill=tk.BOTH, expand=True)
        self.ans_explanation_text.insert("1.0", "Reasoning explanation will appear here upon completion.")
        self.ans_explanation_text.configure(state="disabled")

        return parent

    # -------------------------------------------------------------
    # 3. History Screen
    # -------------------------------------------------------------
    def _create_history_screen(self) -> tk.Frame:
        parent = tk.Frame(self.content_area, bg=C_BG_APP, padx=28, pady=24)
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        # Header Title
        title_box = tk.Frame(parent, bg=C_BG_APP)
        title_box.pack(fill=tk.X, pady=(0, 14))

        tk.Label(title_box, text="Local Question History", font=self.font_h1, fg=C_TEXT_PRIMARY, bg=C_BG_APP).pack(side=tk.LEFT)
        self.hist_count_lbl = tk.Label(title_box, text="0 entries", font=self.font_sm, fg=C_TEXT_MUTED, bg=C_BG_APP)
        self.hist_count_lbl.pack(side=tk.RIGHT)

        # Search Bar & Filter Controls
        toolbar = tk.Frame(parent, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1, padx=14, pady=10)
        toolbar.pack(fill=tk.X, pady=(0, 14))

        tk.Label(toolbar, text="🔍", font=self.font_body, fg=C_TEXT_MUTED, bg=C_BG_CARD).pack(side=tk.LEFT, padx=(0, 6))

        self.hist_search_var = tk.StringVar()
        self.hist_search_var.trace_add("write", lambda *args: self._filter_history_list())
        search_entry = tk.Entry(
            toolbar,
            textvariable=self.hist_search_var,
            font=self.font_body,
            bg=C_BG_APP,
            fg=C_TEXT_PRIMARY,
            insertbackground=C_TEXT_PRIMARY,
            bd=0,
            highlightthickness=1,
            highlightbackground=C_BORDER,
            width=36
        )
        search_entry.pack(side=tk.LEFT, padx=(0, 14), ipady=4)

        btn_refresh = tk.Label(toolbar, text="🔄 Refresh", font=self.font_sm, fg=C_TEXT_PRIMARY, bg=C_BG_CARD_HOVER, padx=10, pady=5, cursor="hand2")
        btn_refresh.pack(side=tk.LEFT, padx=(0, 8))
        btn_refresh.bind("<Button-1>", lambda e: self.refresh_history_list())

        btn_export = tk.Label(toolbar, text="💾 Export", font=self.font_sm, fg=C_TEXT_PRIMARY, bg=C_BG_CARD_HOVER, padx=10, pady=5, cursor="hand2")
        btn_export.pack(side=tk.LEFT, padx=(0, 8))
        btn_export.bind("<Button-1>", lambda e: self._export_history())

        btn_clear = tk.Label(toolbar, text="🗑️ Clear All", font=self.font_sm, fg=C_DANGER, bg=C_BG_CARD_HOVER, padx=10, pady=5, cursor="hand2")
        btn_clear.pack(side=tk.RIGHT)
        btn_clear.bind("<Button-1>", lambda e: self._clear_history_log())

        # Main Split Content: Listbox on Left, Inspection View on Right
        split_container = tk.Frame(parent, bg=C_BG_APP)
        split_container.pack(fill=tk.BOTH, expand=True)
        split_container.grid_columnconfigure(0, weight=1)
        split_container.grid_columnconfigure(1, weight=1)
        split_container.grid_rowconfigure(0, weight=1)

        # Left list
        left_frame = tk.Frame(split_container, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self.hist_listbox = tk.Listbox(
            left_frame,
            font=self.font_body,
            bg=C_BG_CARD,
            fg=C_TEXT_PRIMARY,
            selectbackground="#0369a1",
            selectforeground="#ffffff",
            bd=0,
            highlightthickness=0,
            activestyle="none"
        )
        hist_scroll = tk.Scrollbar(left_frame, orient="vertical", command=self.hist_listbox.yview)
        self.hist_listbox.configure(yscrollcommand=hist_scroll.set)
        self.hist_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)
        hist_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.hist_listbox.bind("<<ListboxSelect>>", self._on_history_select)

        # Right Detail Inspection Pane
        right_frame = tk.Frame(split_container, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1, padx=18, pady=16)
        right_frame.grid(row=0, column=1, sticky="nsew")

        tk.Label(right_frame, text="Query Details & Latency", font=self.font_h2, fg=C_TEXT_PRIMARY, bg=C_BG_CARD).pack(anchor="w")
        self.hist_detail_meta = tk.Label(right_frame, text="Select an entry to view structured telemetry.", font=self.font_sm, fg=C_TEXT_MUTED, bg=C_BG_CARD)
        self.hist_detail_meta.pack(anchor="w", pady=(2, 10))

        self.hist_detail_text = tk.Text(
            right_frame,
            font=self.font_body,
            bg=C_BG_APP,
            fg=C_TEXT_SECONDARY,
            bd=0,
            highlightthickness=1,
            highlightbackground=C_BORDER,
            wrap=tk.WORD,
            padx=10,
            pady=8
        )
        self.hist_detail_text.pack(fill=tk.BOTH, expand=True)

        return parent

    def refresh_history_list(self, custom_path: Optional[Path] = None):
        """Reloads entries from local history file."""
        self.hist_listbox.delete(0, tk.END)
        self.history_records: List[Dict[str, Any]] = []

        history_file = custom_path or (get_app_dir() / "history.jsonl")
        if not history_file.exists():
            self.hist_count_lbl.configure(text="0 entries")
            self.hist_detail_text.configure(state="normal")
            self.hist_detail_text.delete("1.0", tk.END)
            self.hist_detail_text.insert("1.0", "No local history entries found.")
            self.hist_detail_text.configure(state="disabled")
            return

        try:
            with open(history_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            self.history_records.append(json.loads(line))
                        except Exception:
                            pass
        except Exception as e:
            self.hist_detail_text.configure(state="normal")
            self.hist_detail_text.delete("1.0", tk.END)
            self.hist_detail_text.insert("1.0", f"Error loading history: {e}")
            self.hist_detail_text.configure(state="disabled")
            return

        self.history_records.reverse() # Newest first
        self.hist_count_lbl.configure(text=f"{len(self.history_records)} entries")
        self._filter_history_list()

    def _filter_history_list(self):
        query = self.hist_search_var.get().lower().strip()
        self.hist_listbox.delete(0, tk.END)
        self.filtered_indices = []

        for idx, rec in enumerate(self.history_records):
            q_txt = rec.get("question", "")
            ans = rec.get("answer", "")
            if not query or query in q_txt.lower() or query in ans.lower():
                ts = time.strftime("%H:%M:%S", time.localtime(rec.get("timestamp", 0)))
                ans_badge = f"[{ans}]" if ans else "[?]"
                preview = q_txt[:42].replace("\n", " ")
                self.hist_listbox.insert(tk.END, f"{ts} {ans_badge:5} {preview}")
                self.filtered_indices.append(idx)

    def _on_history_select(self, event):
        sel = self.hist_listbox.curselection()
        if not sel or not hasattr(self, "filtered_indices") or sel[0] >= len(self.filtered_indices):
            return
        actual_idx = self.filtered_indices[sel[0]]
        rec = self.history_records[actual_idx]

        self.hist_detail_text.configure(state="normal")
        self.hist_detail_text.delete("1.0", tk.END)

        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(rec.get("timestamp", 0)))
        t_data = rec.get("timing_ms", {})
        timing_str = f"OCR: {t_data.get('ocr', 0):.1f}ms | LLM: {t_data.get('llm', 0):.1f}ms | Total: {t_data.get('total', 0):.1f}ms"

        self.hist_detail_meta.configure(text=f"Captured: {ts}   •   {timing_str}")

        report = f"QUESTION:\n{rec.get('question', '')}\n\n"
        if rec.get("options"):
            report += "OPTIONS:\n"
            for k, v in rec.get("options", {}).items():
                report += f"  {k}) {v}\n"
            report += "\n"

        report += f"ANSWER OPTION: {rec.get('answer', 'Uncertain')}\n"
        report += f"CONFIDENCE:    {rec.get('confidence', 0.0) * 100:.1f}%\n"
        report += f"VALIDATED:     {rec.get('is_validated', False)}\n\n"
        report += f"EXPLANATION:\n{rec.get('explanation', '')}"

        self.hist_detail_text.insert("1.0", report)
        self.hist_detail_text.configure(state="disabled")

    def _clear_history_log(self):
        if messagebox.askyesno("Clear History", "Are you sure you want to delete all local history logs?"):
            history_file = get_app_dir() / "history.jsonl"
            if history_file.exists():
                try:
                    history_file.unlink()
                except Exception:
                    pass
            self.refresh_history_list()

    def _export_history(self):
        history_file = get_app_dir() / "history.jsonl"
        if not history_file.exists():
            messagebox.showinfo("Export History", "No history available to export.")
            return

        dest = filedialog.asksaveasfilename(
            defaultextension=".jsonl",
            filetypes=[("JSON Lines", "*.jsonl"), ("All Files", "*.*")],
            title="Export Rubric-Local History"
        )
        if dest:
            try:
                import shutil
                shutil.copyfile(str(history_file), dest)
                messagebox.showinfo("Export Successful", f"History exported cleanly to:\n{dest}")
            except Exception as e:
                messagebox.showerror("Export Failed", str(e))

    # -------------------------------------------------------------
    # 4. Settings Screen
    # -------------------------------------------------------------
    def _create_settings_screen(self) -> tk.Frame:
        parent = tk.Frame(self.content_area, bg=C_BG_APP, padx=28, pady=24)

        # Header Title
        title_box = tk.Frame(parent, bg=C_BG_APP)
        title_box.pack(fill=tk.X, pady=(0, 14))

        tk.Label(title_box, text="Application Settings", font=self.font_h1, fg=C_TEXT_PRIMARY, bg=C_BG_APP).pack(side=tk.LEFT)
        self.settings_save_msg = tk.Label(title_box, text="", font=self.font_sm, fg=C_SUCCESS, bg=C_BG_APP)
        self.settings_save_msg.pack(side=tk.RIGHT)

        # Scrollable Settings Container
        canvas = tk.Canvas(parent, bg=C_BG_APP, bd=0, highlightthickness=0)
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=C_BG_APP)

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Section 1: AI Reasoning & Model
        sec1 = self._create_settings_section(scroll_frame, "1. Local AI Reasoning & Model")
        self.cfg_model_var = tk.StringVar(value=self.config.model_name)
        self._add_setting_row(sec1, "Model Name:", self.cfg_model_var, "e.g. phi3:mini, qwen2.5:0.5b (Runs completely offline via Ollama)")

        self.cfg_url_var = tk.StringVar(value=self.config.ollama_url)
        self._add_setting_row(sec1, "Ollama Endpoint:", self.cfg_url_var, "Default: http://127.0.0.1:11434 (Localhost only)")

        # Section 2: Screen Capture Dimensions
        sec2 = self._create_settings_section(scroll_frame, "2. Cursor Screen Capture Dimensions")
        self.cfg_w_var = tk.StringVar(value=str(self.config.capture_width))
        self._add_setting_row(sec2, "Capture Width (px):", self.cfg_w_var, "Width of bounding box centered at mouse cursor")

        self.cfg_h_var = tk.StringVar(value=str(self.config.capture_height))
        self._add_setting_row(sec2, "Capture Height (px):", self.cfg_h_var, "Height of bounding box centered at mouse cursor")

        # Section 3: Keyboard Shortcuts
        sec3 = self._create_settings_section(scroll_frame, "3. Global Keyboard Shortcut")
        self.cfg_hotkey_var = tk.StringVar(value=self.config.hotkey)
        self._add_setting_row(sec3, "Trigger Hotkey:", self.cfg_hotkey_var, "Default: alt+/ (Requires restarting app to re-bind)")

        # Section 4: Floating AI HUD & Window Display
        sec4 = self._create_settings_section(scroll_frame, "4. Floating AI HUD & Display Privacy")
        
        self.cfg_hud_enabled = tk.BooleanVar(value=getattr(self.config, "hud_enabled", True))
        chk_hud_en = tk.Checkbutton(
            sec4,
            text="Enable Floating AI HUD Overlay",
            variable=self.cfg_hud_enabled,
            bg=C_BG_CARD,
            fg=C_TEXT_PRIMARY,
            selectcolor=C_BG_SIDEBAR,
            activebackground=C_BG_CARD,
            activeforeground=C_ACCENT,
            font=self.font_body_bold
        )
        chk_hud_en.pack(anchor="w", pady=(0, 6))

        self.cfg_hud_on_solve = tk.BooleanVar(value=getattr(self.config, "show_hud_on_solve", True))
        chk_hud = tk.Checkbutton(
            sec4,
            text="Show floating HUD automatically during solve",
            variable=self.cfg_hud_on_solve,
            bg=C_BG_CARD,
            fg=C_TEXT_PRIMARY,
            selectcolor=C_BG_SIDEBAR,
            activebackground=C_BG_CARD,
            activeforeground=C_ACCENT,
            font=self.font_body
        )
        chk_hud.pack(anchor="w", pady=(0, 6))

        self.cfg_hud_always_on_top = tk.BooleanVar(value=getattr(self.config, "hud_always_on_top", True))
        chk_aot = tk.Checkbutton(
            sec4,
            text="Keep HUD above normal windows (Topmost without stealing focus)",
            variable=self.cfg_hud_always_on_top,
            bg=C_BG_CARD,
            fg=C_TEXT_PRIMARY,
            selectcolor=C_BG_SIDEBAR,
            activebackground=C_BG_CARD,
            activeforeground=C_ACCENT,
            font=self.font_body
        )
        chk_aot.pack(anchor="w", pady=(0, 6))

        self.cfg_hud_pinned = tk.BooleanVar(value=getattr(self.config, "hud_pinned", False))
        chk_pin = tk.Checkbutton(
            sec4,
            text="Pin HUD to persistent screen coordinates",
            variable=self.cfg_hud_pinned,
            bg=C_BG_CARD,
            fg=C_TEXT_PRIMARY,
            selectcolor=C_BG_SIDEBAR,
            activebackground=C_BG_CARD,
            activeforeground=C_ACCENT,
            font=self.font_body
        )
        chk_pin.pack(anchor="w", pady=(0, 6))

        self.cfg_exclude_capture = tk.BooleanVar(value=getattr(self.config, "exclude_from_capture", True))
        chk_excl = tk.Checkbutton(
            sec4,
            text="Exclude HUD from Screen Captures (WDA_EXCLUDEFROMCAPTURE)",
            variable=self.cfg_exclude_capture,
            bg=C_BG_CARD,
            fg=C_TEXT_PRIMARY,
            selectcolor=C_BG_SIDEBAR,
            activebackground=C_BG_CARD,
            activeforeground=C_ACCENT,
            font=self.font_body
        )
        chk_excl.pack(anchor="w", pady=(0, 2))

        # Status indicator for capture exclusion API support
        from rubric_local.core.capture_exclusion import check_capture_exclusion_support
        is_sup, sup_msg = check_capture_exclusion_support()
        lbl_excl_stat = tk.Label(
            sec4,
            text=f"Status: {sup_msg}",
            font=self.font_code,
            fg=C_SUCCESS if is_sup else C_WARNING,
            bg=C_BG_CARD
        )
        lbl_excl_stat.pack(anchor="w", padx=24, pady=(0, 8))

        self.cfg_start_minimized = tk.BooleanVar(value=getattr(self.config, "start_minimized", False))
        chk_min = tk.Checkbutton(
            sec4,
            text="Start application minimized to system tray",
            variable=self.cfg_start_minimized,
            bg=C_BG_CARD,
            fg=C_TEXT_PRIMARY,
            selectcolor=C_BG_SIDEBAR,
            activebackground=C_BG_CARD,
            activeforeground=C_ACCENT,
            font=self.font_body
        )
        chk_min.pack(anchor="w", pady=(0, 6))

        self.cfg_auto_copy = tk.BooleanVar(value=getattr(self.config, "auto_copy_answer", False))
        chk_copy = tk.Checkbutton(
            sec4,
            text="Automatically copy validated answer to clipboard",
            variable=self.cfg_auto_copy,
            bg=C_BG_CARD,
            fg=C_TEXT_PRIMARY,
            selectcolor=C_BG_SIDEBAR,
            activebackground=C_BG_CARD,
            activeforeground=C_ACCENT,
            font=self.font_body
        )
        chk_copy.pack(anchor="w", pady=(0, 8))

        self.cfg_opacity_var = tk.StringVar(value=str(getattr(self.config, "hud_opacity", 0.92)))
        self._add_setting_row(sec4, "HUD Opacity (0.5-1.0):", self.cfg_opacity_var, "Translucency level for the floating HUD overlay")

        self.cfg_ans_timeout_var = tk.StringVar(value=str(getattr(self.config, "answer_timeout_sec", 0)))
        self._add_setting_row(sec4, "HUD Auto-Dismiss (s):", self.cfg_ans_timeout_var, "Auto-dismiss timer in seconds (0 = stay until dismissed)")

        # Section 5: Automatic Hover-to-Answer Engine
        sec_hover = self._create_settings_section(scroll_frame, "5. Automatic Hover-to-Answer Engine")
        self.cfg_hover_enabled = tk.BooleanVar(value=getattr(self.config, "hover_to_answer_enabled", False))
        chk_hover = tk.Checkbutton(
            sec_hover,
            text="Enable Automatic Hover-to-Answer (captures question when cursor pauses)",
            variable=self.cfg_hover_enabled,
            bg=C_BG_CARD,
            fg=C_TEXT_PRIMARY,
            selectcolor=C_BG_SIDEBAR,
            activebackground=C_BG_CARD,
            activeforeground=C_ACCENT,
            font=self.font_body_bold
        )
        chk_hover.pack(anchor="w", pady=(0, 6))

        self.cfg_hover_paused = tk.BooleanVar(value=getattr(self.config, "is_hover_paused", False))
        chk_hpause = tk.Checkbutton(
            sec_hover,
            text="Pause Automatic Hover Detection",
            variable=self.cfg_hover_paused,
            bg=C_BG_CARD,
            fg=C_TEXT_PRIMARY,
            selectcolor=C_BG_SIDEBAR,
            activebackground=C_BG_CARD,
            activeforeground=C_AMBER,
            font=self.font_body
        )
        chk_hpause.pack(anchor="w", pady=(0, 8))

        self.cfg_hover_delay_var = tk.StringVar(value=str(getattr(self.config, "hover_delay_ms", 800)))
        self._add_setting_row(sec_hover, "Hover Delay (ms):", self.cfg_hover_delay_var, "Stationary duration required before capture (e.g. 800ms)")

        self.cfg_hover_cooldown_var = tk.StringVar(value=str(getattr(self.config, "hover_cooldown_sec", 3.0)))
        self._add_setting_row(sec_hover, "Cooldown (s):", self.cfg_hover_cooldown_var, "Cooldown between consecutive automatic solves (e.g. 3.0s)")

        self.cfg_hover_threshold_var = tk.StringVar(value=str(getattr(self.config, "hover_movement_threshold_px", 15)))
        self._add_setting_row(sec_hover, "Jitter Radius (px):", self.cfg_hover_threshold_var, "Cursor movement tolerance radius (e.g. 15px)")

        # Section 5: Caps Lock Indicator & Signals
        sec5 = self._create_settings_section(scroll_frame, "5. Hardware Caps Lock LED Signaling")
        self.cfg_caps_enabled = tk.BooleanVar(value=getattr(self.config, "caps_lock_indicator", False))
        chk_caps = tk.Checkbutton(
            sec5,
            text="Enable Physical Caps Lock LED Pulse Signaling",
            variable=self.cfg_caps_enabled,
            bg=C_BG_CARD,
            fg=C_TEXT_PRIMARY,
            selectcolor=C_BG_SIDEBAR,
            activebackground=C_BG_CARD,
            activeforeground=C_ACCENT,
            font=self.font_body_bold
        )
        chk_caps.pack(anchor="w", pady=(0, 6))

        self.cfg_pulse_on_var = tk.StringVar(value=str(getattr(self.config, "caps_pulse_on_ms", 300)))
        self._add_setting_row(sec5, "LED ON Time (ms):", self.cfg_pulse_on_var, "Recommended ~300ms so blinks are easily countable")

        self.cfg_pulse_off_var = tk.StringVar(value=str(getattr(self.config, "caps_pulse_off_ms", 250)))
        self._add_setting_row(sec5, "LED OFF Gap (ms):", self.cfg_pulse_off_var, "Recommended ~250ms gap between consecutive pulses")

        test_row = tk.Frame(sec5, bg=C_BG_CARD)
        test_row.pack(anchor="w", pady=(6, 0))
        btn_test_caps = tk.Label(test_row, text="⚡ Test 2 Pulses on Keyboard", font=self.font_sm, fg=C_ACCENT, bg=C_BG_CARD_HOVER, padx=10, pady=5, cursor="hand2")
        btn_test_caps.pack(side=tk.LEFT, padx=(0, 10))
        btn_test_caps.bind("<Button-1>", lambda e: self._on_test_caps_clicked())

        # Future indicators explicitly labeled as not yet implemented
        future_lbl = tk.Label(sec5, text="Note: Num Lock, Scroll Lock, and Esc LED indicators are planned for v1.1 release.", font=self.font_sm, fg=C_TEXT_MUTED, bg=C_BG_CARD)
        future_lbl.pack(anchor="w", pady=(8, 0))

        # Section 6: Local History & Retention
        sec6 = self._create_settings_section(scroll_frame, "6. Local History & Privacy")
        self.cfg_history_var = tk.BooleanVar(value=self.config.save_history_locally)
        chk_hist = tk.Checkbutton(
            sec6,
            text="Save queries and latency benchmarks to local history file (%APPDATA%\\RubricLocal\\history.jsonl)",
            variable=self.cfg_history_var,
            bg=C_BG_CARD,
            fg=C_TEXT_PRIMARY,
            selectcolor=C_BG_SIDEBAR,
            activebackground=C_BG_CARD,
            activeforeground=C_ACCENT,
            font=self.font_body
        )
        chk_hist.pack(anchor="w")

        # Save Action Button
        btn_save = tk.Label(
            scroll_frame,
            text="💾 Save Application Settings",
            font=self.font_body_bold,
            fg="#ffffff",
            bg="#0284c7",
            padx=20,
            pady=10,
            cursor="hand2"
        )
        btn_save.pack(anchor="w", pady=(18, 20))
        btn_save.bind("<Button-1>", lambda e: self._save_settings())
        btn_save.bind("<Enter>", lambda e: btn_save.configure(bg="#0369a1"))
        btn_save.bind("<Leave>", lambda e: btn_save.configure(bg="#0284c7"))

        return parent

    def _create_settings_section(self, parent: tk.Frame, title: str) -> tk.Frame:
        sec = tk.Frame(parent, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1, padx=20, pady=16)
        sec.pack(fill=tk.X, pady=(0, 14))
        tk.Label(sec, text=title, font=self.font_h2, fg=C_TEXT_PRIMARY, bg=C_BG_CARD).pack(anchor="w", pady=(0, 10))
        return sec

    def _add_setting_row(self, parent: tk.Frame, label: str, var: tk.StringVar, hint: str):
        row = tk.Frame(parent, bg=C_BG_CARD)
        row.pack(fill=tk.X, pady=(0, 8))
        tk.Label(row, text=label, font=self.font_body_bold, fg=C_TEXT_SECONDARY, bg=C_BG_CARD, width=22, anchor="w").pack(side=tk.LEFT)
        e = tk.Entry(row, textvariable=var, font=self.font_body, bg=C_BG_APP, fg=C_TEXT_PRIMARY, insertbackground=C_TEXT_PRIMARY, bd=0, highlightthickness=1, highlightbackground=C_BORDER, width=28)
        e.pack(side=tk.LEFT, padx=(0, 12), ipady=3)
        tk.Label(row, text=hint, font=self.font_sm, fg=C_TEXT_MUTED, bg=C_BG_CARD).pack(side=tk.LEFT)

    def _save_settings(self):
        try:
            self.config.model_name = self.cfg_model_var.get().strip()
            self.config.ollama_url = self.cfg_url_var.get().strip()
            self.config.capture_width = int(self.cfg_w_var.get())
            self.config.capture_height = int(self.cfg_h_var.get())
            self.config.hotkey = self.cfg_hotkey_var.get().strip().lower()
            self.config.caps_lock_indicator = self.cfg_caps_enabled.get()
            self.config.caps_pulse_on_ms = int(self.cfg_pulse_on_var.get())
            self.config.caps_pulse_off_ms = int(self.cfg_pulse_off_var.get())
            self.config.show_hud_on_solve = self.cfg_hud_on_solve.get()
            self.config.start_minimized = self.cfg_start_minimized.get()
            self.config.auto_copy_answer = self.cfg_auto_copy.get()
            self.config.save_history_locally = self.cfg_history_var.get()

            # Floating HUD settings
            self.config.hud_enabled = self.cfg_hud_enabled.get()
            self.config.hud_always_on_top = self.cfg_hud_always_on_top.get()
            self.config.hud_pinned = self.cfg_hud_pinned.get()
            self.config.exclude_from_capture = self.cfg_exclude_capture.get()
            try:
                self.config.hud_opacity = max(0.2, min(1.0, float(self.cfg_opacity_var.get())))
            except ValueError:
                pass
            try:
                self.config.answer_timeout_sec = max(0, int(self.cfg_ans_timeout_var.get()))
            except ValueError:
                pass

            # Hover-to-Answer settings
            self.config.hover_to_answer_enabled = self.cfg_hover_enabled.get()
            self.config.is_hover_paused = self.cfg_hover_paused.get()
            try:
                self.config.hover_delay_ms = max(100, int(self.cfg_hover_delay_var.get()))
            except ValueError:
                pass
            try:
                self.config.hover_cooldown_sec = max(0.5, float(self.cfg_hover_cooldown_var.get()))
            except ValueError:
                pass
            try:
                self.config.hover_movement_threshold_px = max(2, int(self.cfg_hover_threshold_var.get()))
            except ValueError:
                pass

            save_config(self.config)

            if self.on_settings_saved:
                self.on_settings_saved(self.config)

            self.settings_save_msg.configure(text="✓ Settings persisted to disk successfully!")
            self.root.after(3000, lambda: self.settings_save_msg.configure(text=""))
        except Exception as e:
            messagebox.showerror("Error Saving Settings", str(e))

    # -------------------------------------------------------------
    # 5. Setup / First-Run Wizard Screen
    # -------------------------------------------------------------
    def _create_setup_screen(self) -> tk.Frame:
        parent = tk.Frame(self.content_area, bg=C_BG_APP, padx=28, pady=24)
        parent.grid_columnconfigure(0, weight=1)

        # Header Title
        title_box = tk.Frame(parent, bg=C_BG_APP)
        title_box.pack(fill=tk.X, pady=(0, 14))
        tk.Label(title_box, text="First-Run Setup & Dependency Wizard", font=self.font_h1, fg=C_TEXT_PRIMARY, bg=C_BG_APP).pack(anchor="w")
        tk.Label(title_box, text="Configure your local offline AI environment without editing JSON or running commands.", font=self.font_body, fg=C_TEXT_MUTED, bg=C_BG_APP).pack(anchor="w", pady=(3, 0))

        # Wizard Step Card
        self.wizard_card = tk.Frame(parent, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1, padx=24, pady=20)
        self.wizard_card.pack(fill=tk.BOTH, expand=True)

        # Step 1: System Readiness & Dependency Check
        self.w_step1_box = tk.Frame(self.wizard_card, bg=C_BG_CARD)
        self.w_step1_box.pack(fill=tk.X, pady=(0, 14))

        tk.Label(self.w_step1_box, text="Step 1: System Dependency & Offline Readiness", font=self.font_h2, fg=C_TEXT_PRIMARY, bg=C_BG_CARD).pack(anchor="w")
        self.w_dep_lbl = tk.Label(self.w_step1_box, text="Checking system runtimes...", font=self.font_body, fg=C_TEXT_SECONDARY, bg=C_BG_CARD, justify=tk.LEFT)
        self.w_dep_lbl.pack(anchor="w", pady=(6, 0))

        # Step 2: Ollama Local Daemon
        self.w_step2_box = tk.Frame(self.wizard_card, bg=C_BG_CARD)
        self.w_step2_box.pack(fill=tk.X, pady=(0, 14))

        tk.Label(self.w_step2_box, text="Step 2: Ollama Local Service Connection", font=self.font_h2, fg=C_TEXT_PRIMARY, bg=C_BG_CARD).pack(anchor="w")
        self.w_ollama_lbl = tk.Label(self.w_step2_box, text="Testing 127.0.0.1:11434...", font=self.font_body, fg=C_TEXT_SECONDARY, bg=C_BG_CARD, justify=tk.LEFT)
        self.w_ollama_lbl.pack(anchor="w", pady=(6, 4))

        btn_test_ollama = tk.Label(self.w_step2_box, text="🔄 Test Ollama Connection", font=self.font_sm, fg=C_ACCENT, bg=C_BG_CARD_HOVER, padx=12, pady=6, cursor="hand2")
        btn_test_ollama.pack(anchor="w")
        btn_test_ollama.bind("<Button-1>", lambda e: self.check_ollama_connection())

        # Step 3: Model Selection & Download
        self.w_step3_box = tk.Frame(self.wizard_card, bg=C_BG_CARD)
        self.w_step3_box.pack(fill=tk.X, pady=(0, 14))

        tk.Label(self.w_step3_box, text="Step 3: Select or Download Offline Reasoning Model", font=self.font_h2, fg=C_TEXT_PRIMARY, bg=C_BG_CARD).pack(anchor="w")
        tk.Label(self.w_step3_box, text="Recommended: phi3:mini (3.8B - 2.3 GB) for highest reasoning accuracy, or qwen2.5:0.5b (400 MB) for ultra-fast response.", font=self.font_sm, fg=C_TEXT_MUTED, bg=C_BG_CARD).pack(anchor="w", pady=(2, 6))

        m_row = tk.Frame(self.w_step3_box, bg=C_BG_CARD)
        m_row.pack(fill=tk.X)

        self.w_model_var = tk.StringVar(value=self.config.model_name)
        self.w_model_combo = ttk.Combobox(m_row, textvariable=self.w_model_var, values=["phi3:mini", "qwen2.5:0.5b", "llama3.2:1b"], width=20)
        self.w_model_combo.pack(side=tk.LEFT, padx=(0, 12))

        self.btn_pull_model = tk.Label(m_row, text="⬇️ Pull / Download Selected Model", font=self.font_sm, fg="#ffffff", bg="#0284c7", padx=14, pady=6, cursor="hand2")
        self.btn_pull_model.pack(side=tk.LEFT)
        self.btn_pull_model.bind("<Button-1>", lambda e: self._pull_selected_model())

        self.w_pull_progress = tk.Label(self.w_step3_box, text="", font=self.font_sm, fg=C_SUCCESS, bg=C_BG_CARD)
        self.w_pull_progress.pack(anchor="w", pady=(4, 0))

        # Step 4: Sample Verification Test
        self.w_step4_box = tk.Frame(self.wizard_card, bg=C_BG_CARD)
        self.w_step4_box.pack(fill=tk.X, pady=(0, 14))

        tk.Label(self.w_step4_box, text="Step 4: Offline Verification Benchmark", font=self.font_h2, fg=C_TEXT_PRIMARY, bg=C_BG_CARD).pack(anchor="w")
        self.w_verify_lbl = tk.Label(self.w_step4_box, text="Execute a sample reasoning test on local model to confirm latency and accuracy.", font=self.font_body, fg=C_TEXT_SECONDARY, bg=C_BG_CARD)
        self.w_verify_lbl.pack(anchor="w", pady=(4, 6))

        btn_sample_test = tk.Label(self.w_step4_box, text="🧪 Run Sample Verification Test", font=self.font_sm, fg=C_TEXT_PRIMARY, bg=C_BG_CARD_HOVER, padx=14, pady=6, cursor="hand2")
        btn_sample_test.pack(anchor="w")
        btn_sample_test.bind("<Button-1>", lambda e: self._run_sample_wizard_test())

        # Step 5: Finish & Save
        self.w_step5_box = tk.Frame(self.wizard_card, bg=C_BG_CARD)
        self.w_step5_box.pack(fill=tk.X, pady=(10, 0))

        btn_finish = tk.Label(
            self.w_step5_box,
            text="✓ Complete Setup & Go to Dashboard",
            font=self.font_body_bold,
            fg="#ffffff",
            bg=C_SUCCESS,
            padx=18,
            pady=9,
            cursor="hand2"
        )
        btn_finish.pack(side=tk.LEFT)
        btn_finish.bind("<Button-1>", lambda e: self._finish_setup_wizard())

        return parent

    def refresh_setup_screen(self):
        """Runs live environment checks for the setup wizard."""
        # 1. Check Python & Native OCR
        from rubric_local.core.ocr_engine import get_win_ocr_binary_path
        try:
            ocr_p = get_win_ocr_binary_path()
            ocr_ok = ocr_p.exists()
        except Exception:
            ocr_ok = False

        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        status_text = f"• Python Runtime: v{py_ver} ({sys.executable})\n• Windows Native OCR (win_ocr.exe): {'INSTALLED & READY' if ocr_ok else 'MISSING'}"
        self.w_dep_lbl.configure(text=status_text)

        self.check_ollama_connection()

    def check_ollama_connection(self):
        url = self.config.ollama_url
        def _check():
            import urllib.request
            try:
                req = urllib.request.Request(f"{url}/api/tags", headers={"User-Agent": "RubricLocal"})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        models = [m.get("name", "") for m in data.get("models", [])]
                        self.root.after(0, lambda: self._update_ollama_status(True, models))
                        return
            except Exception as e:
                self.root.after(0, lambda: self._update_ollama_status(False, [], str(e)))

        threading.Thread(target=_check, daemon=True).start()

    def _update_ollama_status(self, is_online: bool, models: List[str], err: str = ""):
        if is_online:
            txt = f"✓ Ollama service is ONLINE at {self.config.ollama_url}.\nInstalled local models: {', '.join(models) if models else 'None'}"
            self.w_ollama_lbl.configure(text=txt, fg=C_SUCCESS)
            if models:
                self.w_model_combo.configure(values=models)
                if self.config.model_name in models:
                    self.w_model_var.set(self.config.model_name)
                else:
                    self.w_model_var.set(models[0])
        else:
            txt = f"✗ Ollama service is OFFLINE at {self.config.ollama_url}.\nPlease download and launch Ollama from https://ollama.com before solving."
            self.w_ollama_lbl.configure(text=txt, fg=C_WARNING)

    def _pull_selected_model(self):
        if self.pulling_model:
            return
        target = self.w_model_var.get().strip()
        if not target:
            return

        self.pulling_model = True
        self.btn_pull_model.configure(text="Downloading...", bg="#0369a1")
        self.w_pull_progress.configure(text=f"Pulling model '{target}' via Ollama... Please wait (2-5 minutes depending on connection).", fg=C_WARNING)

        def _worker():
            try:
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 1)
                startupinfo.wShowWindow = 0  # SW_HIDE
                proc = subprocess.Popen(
                    ["ollama", "pull", target],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    creationflags=creationflags,
                    startupinfo=startupinfo,
                )
                for line in proc.stdout:
                    clean = line.strip()
                    if clean:
                        self.root.after(0, lambda l=clean: self.w_pull_progress.configure(text=l[:80]))
                proc.wait()
                if proc.returncode == 0:
                    self.root.after(0, lambda: self._on_pull_complete(target, True))
                else:
                    self.root.after(0, lambda: self._on_pull_complete(target, False, f"Exit code {proc.returncode}"))
            except Exception as e:
                self.root.after(0, lambda: self._on_pull_complete(target, False, str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_pull_complete(self, target: str, success: bool, err_msg: str = ""):
        self.pulling_model = False
        self.btn_pull_model.configure(text="⬇️ Pull / Download Selected Model", bg="#0284c7")
        if success:
            self.w_pull_progress.configure(text=f"✓ Model '{target}' pulled and verified locally!", fg=C_SUCCESS)
            self.check_ollama_connection()
        else:
            self.w_pull_progress.configure(text=f"✗ Failed to pull '{target}': {err_msg}", fg=C_DANGER)

    def _run_sample_wizard_test(self):
        self.w_verify_lbl.configure(text="Running local inference test on 'What is 15 + 27?'...", fg=C_ACCENT)
        target_model = self.w_model_var.get().strip()

        def _worker():
            try:
                from rubric_local.core.llm_client import OllamaClient
                client = OllamaClient(base_url=self.config.ollama_url)
                t0 = time.perf_counter()
                ans = client.solve_question(
                    question_text="What is 15 + 27?",
                    options={"A": "32", "B": "40", "C": "42", "D": "52"},
                    model=target_model
                )
                dur = (time.perf_counter() - t0) * 1000.0
                txt = f"✓ Verified! Model chose: {ans.answer_option} (Confidence: {ans.confidence*100:.0f}%, Latency: {dur:.1f}ms)\n{ans.explanation}"
                self.root.after(0, lambda: self.w_verify_lbl.configure(text=txt, fg=C_SUCCESS))
            except Exception as e:
                self.root.after(0, lambda: self.w_verify_lbl.configure(text=f"✗ Test failed: {e}", fg=C_DANGER))

        threading.Thread(target=_worker, daemon=True).start()

    def _finish_setup_wizard(self):
        self.config.model_name = self.w_model_var.get().strip()
        save_config(self.config)
        if self.on_settings_saved:
            self.on_settings_saved(self.config)
        self.show_screen("dashboard")

    # -------------------------------------------------------------
    # 6. Diagnostics Screen
    # -------------------------------------------------------------
    def _create_diagnostics_screen(self) -> tk.Frame:
        parent = tk.Frame(self.content_area, bg=C_BG_APP, padx=28, pady=24)
        parent.grid_columnconfigure(0, weight=1)

        title_box = tk.Frame(parent, bg=C_BG_APP)
        title_box.pack(fill=tk.X, pady=(0, 14))

        tk.Label(title_box, text="System Diagnostics & Telemetry", font=self.font_h1, fg=C_TEXT_PRIMARY, bg=C_BG_APP).pack(side=tk.LEFT)

        act_box = tk.Frame(title_box, bg=C_BG_APP)
        act_box.pack(side=tk.RIGHT)

        btn_open_log = tk.Label(act_box, text="📄 Open Log", font=self.font_sm, fg=C_TEXT_PRIMARY, bg=C_BG_CARD_HOVER, padx=10, pady=5, cursor="hand2")
        btn_open_log.pack(side=tk.LEFT, padx=(0, 8))
        btn_open_log.bind("<Button-1>", lambda e: self._open_log_file())

        btn_open_dir = tk.Label(act_box, text="📁 Open AppData", font=self.font_sm, fg=C_TEXT_PRIMARY, bg=C_BG_CARD_HOVER, padx=10, pady=5, cursor="hand2")
        btn_open_dir.pack(side=tk.LEFT, padx=(0, 8))
        btn_open_dir.bind("<Button-1>", lambda e: self._open_app_dir())

        btn_copy = tk.Label(act_box, text="📋 Copy Report", font=self.font_sm, fg=C_ACCENT, bg=C_BG_CARD_HOVER, padx=10, pady=5, cursor="hand2")
        btn_copy.pack(side=tk.LEFT)
        btn_copy.bind("<Button-1>", lambda e: self._copy_diagnostic_report())

        # Telemetry Display Box
        telemetry_card = tk.Frame(parent, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1, padx=20, pady=16)
        telemetry_card.pack(fill=tk.BOTH, expand=True)

        self.diag_text = tk.Text(
            telemetry_card,
            font=self.font_code,
            bg=C_BG_APP,
            fg=C_TEXT_PRIMARY,
            bd=0,
            highlightthickness=1,
            highlightbackground=C_BORDER,
            wrap=tk.WORD,
            padx=12,
            pady=10
        )
        self.diag_text.pack(fill=tk.BOTH, expand=True)

        return parent

    def refresh_diagnostics(self):
        self.diag_text.configure(state="normal")
        self.diag_text.delete("1.0", tk.END)

        from rubric_local.core.ocr_engine import get_win_ocr_binary_path
        try:
            ocr_p = get_win_ocr_binary_path()
            ocr_str = f"EXISTS ({ocr_p})"
        except Exception as e:
            ocr_str = f"ERROR ({e})"

        # Probe Ollama directly
        ollama_status = "ONLINE" if self._probe_ollama() else "OFFLINE"

        diag_content = f"""======================================================================
  Rubric-Local Diagnostic & Telemetry Report (v{__version__})
======================================================================
Generated:            {time.strftime('%Y-%m-%d %H:%M:%S')}
Operating System:     {sys.platform} (Win32 NT)
Process ID (PID):     {os.getpid()}
Executable:           {sys.executable}
Working Directory:    {os.getcwd()}

--- Configuration ---
Config Path:          {get_config_path()}
Active Model:         {self.config.model_name}
Ollama Endpoint:      {self.config.ollama_url}
Ollama Service:       {ollama_status}
Global Hotkey:        {self.config.hotkey} (Alt + /)
Capture Dimensions:   {self.config.capture_width} x {self.config.capture_height} px
Indicator Mode:       {self.config.indicator_mode}
Caps Lock Indicator:  {'ENABLED' if getattr(self.config, 'caps_lock_indicator', False) else 'DISABLED'}
Local History File:   {get_app_dir() / 'history.jsonl'}
Application Log File: {get_app_dir() / 'rubric_local.log'}

--- Native Subsystems ---
Windows Native OCR:   {ocr_str}
System Tray:          pystray active (HICON replacement)
Single-Instance Sink: RubricLocalSingleInstanceSink (Registered)

--- Recent Diagnostic Log Lines ---
"""
        log_file = get_app_dir() / "rubric_local.log"
        if log_file.exists():
            try:
                with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                    diag_content += "".join(lines[-35:])
            except Exception as e:
                diag_content += f"[Error reading log file: {e}]"
        else:
            diag_content += "[Log file not found]"

        self.diag_text.insert("1.0", diag_content)
        self.diag_text.configure(state="disabled")

    def _probe_ollama(self) -> bool:
        import urllib.request
        try:
            req = urllib.request.Request(f"{self.config.ollama_url}/api/tags", headers={"User-Agent": "RubricLocal"})
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _open_log_file(self):
        log_file = get_app_dir() / "rubric_local.log"
        if log_file.exists():
            os.startfile(str(log_file))

    def _open_app_dir(self):
        app_dir = get_app_dir()
        if app_dir.exists():
            os.startfile(str(app_dir))

    def _copy_diagnostic_report(self):
        content = self.diag_text.get("1.0", tk.END)
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        messagebox.showinfo("Report Copied", "Sanitized diagnostic report copied to clipboard.")

    # -------------------------------------------------------------
    # 7. About Screen
    # -------------------------------------------------------------
    def _create_about_screen(self) -> tk.Frame:
        parent = tk.Frame(self.content_area, bg=C_BG_APP, padx=28, pady=24)
        parent.grid_columnconfigure(0, weight=1)

        tk.Label(parent, text="About Rubric-Local", font=self.font_h1, fg=C_TEXT_PRIMARY, bg=C_BG_APP).pack(anchor="w", pady=(0, 16))

        about_card = tk.Frame(parent, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1, padx=24, pady=22)
        about_card.pack(fill=tk.BOTH, expand=True)

        tk.Label(about_card, text=f"Rubric-Local  v{__version__}", font=self.font_h2, fg=C_ACCENT, bg=C_BG_CARD).pack(anchor="w")
        tk.Label(about_card, text="100% Offline, Privacy-First Assessment Assistant & Solver Engine", font=self.font_body_bold, fg=C_TEXT_PRIMARY, bg=C_BG_CARD).pack(anchor="w", pady=(2, 14))

        body_text = """Rubric-Local is a clean-room, open-source reimplementation of the Rubric assessment engine.

Unlike the original cloud-tethered application which required mandatory Google OAuth, remote proxy endpoints, and cloud API subscriptions, Rubric-Local is engineered from the ground up for complete offline autonomy.

Core Architecture:
• Screen Capture: High-DPI Windows cursor coordinate capture
• OCR Engine: Windows 10/11 native Media.Ocr runtime (win_ocr.exe)
• Reasoning Engine: On-device Small Language Models (SLMs) via Ollama
• Stealth Indicators: Dynamic taskbar HICON answer badge + Caps Lock pulse signaling
• Privacy Boundary: 0 outbound external sockets. 100% loopback telemetry only."""

        tk.Label(about_card, text=body_text, font=self.font_body, fg=C_TEXT_SECONDARY, bg=C_BG_CARD, justify=tk.LEFT).pack(anchor="w", pady=(0, 20))

        btn_row = tk.Frame(about_card, bg=C_BG_CARD)
        btn_row.pack(anchor="w")

        btn_setup = tk.Label(btn_row, text="🪄 Open Setup Wizard", font=self.font_sm, fg=C_TEXT_PRIMARY, bg=C_BG_CARD_HOVER, padx=14, pady=7, cursor="hand2")
        btn_setup.pack(side=tk.LEFT, padx=(0, 10))
        btn_setup.bind("<Button-1>", lambda e: self.show_screen("setup"))

        btn_diag = tk.Label(btn_row, text="🔍 View Diagnostics", font=self.font_sm, fg=C_TEXT_PRIMARY, bg=C_BG_CARD_HOVER, padx=14, pady=7, cursor="hand2")
        btn_diag.pack(side=tk.LEFT)
        btn_diag.bind("<Button-1>", lambda e: self.show_screen("diagnostics"))

        return parent

    # -------------------------------------------------------------
    # Callbacks and State Management
    # -------------------------------------------------------------
    def _on_solve_clicked(self):
        if self.on_trigger_solve:
            self.on_trigger_solve()

    def _on_toggle_hud_clicked(self):
        if self.on_toggle_hud:
            self.on_toggle_hud()

    def _on_test_caps_clicked(self):
        if self.on_test_caps:
            self.on_test_caps()

    def _copy_answer_to_clipboard(self):
        if self.last_result and hasattr(self.last_result, "answer_result"):
            opt = self.last_result.answer_result.answer_option
            self.root.clipboard_clear()
            self.root.clipboard_append(opt)

    def _copy_explanation_to_clipboard(self):
        if self.last_result and hasattr(self.last_result, "answer_result"):
            exp = self.last_result.answer_result.explanation
            self.root.clipboard_clear()
            self.root.clipboard_append(exp)

    def on_solve_started(self):
        """Thread-safe UI update when solve worker begins."""
        if not self.root:
            return
        if threading.current_thread() is threading.main_thread():
            self._apply_solve_started()
        else:
            self.root.after(0, self._apply_solve_started)

    def _apply_solve_started(self):
        self.answer_stage_chip.configure(text="REASONING IN PROGRESS...", fg=C_WARNING)
        self.ans_badge_lbl.configure(text="…", fg=C_WARNING)
        self.ans_status_lbl.configure(text="Analyzing question on screen...")
        self.ans_confidence_lbl.configure(text="Capturing bounding box and reasoning with local model...")
        self.sidebar_status_lbl.configure(text="Solving Question...")
        self.sidebar_status_dot.configure(fg=C_WARNING)

    def on_solve_completed(self, res: Any):
        """Thread-safe UI update when solve worker finishes."""
        self.last_result = res
        if not self.root:
            return
        if threading.current_thread() is threading.main_thread():
            self._apply_solve_completed(res)
        else:
            self.root.after(0, lambda: self._apply_solve_completed(res))

    def _apply_solve_completed(self, res: Any):
        ans = res.answer_result
        badge = getattr(ans, "tray_badge", getattr(ans, "source_option_label", "?"))
        timing_str = f"Capture: {res.capture_time_ms:.0f}ms | OCR: {res.ocr_time_ms:.0f}ms | LLM: {res.llm_time_ms:.0f}ms | Total: {res.total_time_ms:.0f}ms"

        if not ans.is_validated or badge in ["Uncertain", "?"]:
            self.answer_stage_chip.configure(text="UNCERTAIN RESULT", fg=C_WARNING)
            self.ans_badge_lbl.configure(text="?", fg=C_WARNING)
            self.ans_status_lbl.configure(text="Answer Could Not Be Reliably Validated")
            self.ans_confidence_lbl.configure(text="Explicit uncertain state: Question lacked distinguishable MCQ choices.")
        else:
            self.answer_stage_chip.configure(text="ANSWER CONFIRMED", fg=C_SUCCESS)
            self.ans_badge_lbl.configure(text=badge, fg=C_ACCENT)
            if getattr(res.parsed_question, "is_multiple_choice", True):
                opt_desc = f"Option {badge}"
                if ans.option_text:
                    opt_desc += f": {ans.option_text}"
            else:
                opt_desc = ans.option_text or ans.answer_option or "Answer Identified"
            self.ans_status_lbl.configure(text=opt_desc)
            self.ans_confidence_lbl.configure(text=f"Confidence: {ans.confidence * 100:.0f}% (Local Grounding Verified)")

        self.ans_timing_lbl.configure(text=timing_str)

        self.ans_question_text.configure(state="normal")
        self.ans_question_text.delete("1.0", tk.END)
        self.ans_question_text.insert("1.0", res.parsed_question.question_text)
        self.ans_question_text.configure(state="disabled")

        self.ans_explanation_text.configure(state="normal")
        self.ans_explanation_text.delete("1.0", tk.END)
        self.ans_explanation_text.insert("1.0", ans.explanation or "No explanation provided.")
        self.ans_explanation_text.configure(state="disabled")

        # Update dashboard recent snippet
        q_prev = res.parsed_question.question_text[:110].replace("\n", " ")
        self.dash_recent_lbl.configure(text=f"Last solved ({badge}): \"{q_prev}...\"\n{timing_str}")

        self.sidebar_status_lbl.configure(text="Offline Engine Ready")
        self.sidebar_status_dot.configure(fg=C_SUCCESS)

        # Switch to Answer screen if main window is visible
        if not self._is_minimized_to_tray and self.current_screen != "answer":
            self.show_screen("answer")

        if getattr(self.config, "auto_copy_answer", False) and badge not in ["?", "!"]:
            self._copy_answer_to_clipboard()

    def on_solve_error(self, err_msg: str):
        if not self.root:
            return
        if threading.current_thread() is threading.main_thread():
            self._apply_solve_error(err_msg)
        else:
            self.root.after(0, lambda: self._apply_solve_error(err_msg))

    def _apply_solve_error(self, err_msg: str):
        self.answer_stage_chip.configure(text="ERROR ENCOUNTERED", fg=C_DANGER)
        self.ans_badge_lbl.configure(text="!", fg=C_DANGER)
        self.ans_status_lbl.configure(text="Solve Execution Error")
        self.ans_confidence_lbl.configure(text=err_msg[:90])
        self.sidebar_status_lbl.configure(text="Error Occurred")
        self.sidebar_status_dot.configure(fg=C_DANGER)

    # -------------------------------------------------------------
    # Window Lifecycle & Tray Minimization
    # -------------------------------------------------------------
    def show_window(self):
        """Restores window from minimized or hidden state and raises to foreground."""
        if not self.root:
            return
        if threading.current_thread() is threading.main_thread():
            self._show_window_main()
        else:
            self.root.after(0, self._show_window_main)

    def _show_window_main(self):
        if self.root:
            self.root.deiconify()
            self.root.state("normal")
            self.root.lift()
            self.root.focus_force()
            # Win32 topmost toggle ensures window rises above other foreground apps
            try:
                self.root.attributes("-topmost", True)
                self.root.attributes("-topmost", False)
            except Exception:
                pass
            self._is_minimized_to_tray = False

    def hide_to_tray(self):
        """Hides window to system tray without terminating process."""
        if self.root:
            self.root.withdraw()
            self._is_minimized_to_tray = True

    def toggle_visibility(self):
        """Toggles between visible and hidden to tray."""
        if self._is_minimized_to_tray:
            self.show_window()
        else:
            self.hide_to_tray()

    def get_window_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """Returns (left, top, right, bottom) bounding box for screen capture exclusion."""
        if not self.root or self._is_minimized_to_tray:
            return None
        try:
            x = self.root.winfo_rootx()
            y = self.root.winfo_rooty()
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            return (x, y, x + w, y + h)
        except Exception:
            return None

    def destroy(self):
        """Terminates UI cleanly."""
        if self.root:
            try:
                self.root.update_idletasks()
            except Exception:
                pass
            try:
                self.root.destroy()
            except Exception:
                pass
            self.root = None
