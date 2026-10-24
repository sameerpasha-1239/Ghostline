# Rubric-Local

**100% Offline, Privacy-First On-Device AI Question Recognition & Solver Engine for Windows 11 & 10.**

Rubric-Local is a native Windows desktop application that captures on-screen multiple-choice questions, recognizes question structure with sub-second Windows Media OCR, performs local grounded reasoning via Ollama, and signals validated answers through a floating HUD, dynamic system tray badge, or keyboard Caps Lock pulses.

No cloud APIs. No telemetry. No accounts or subscriptions. Zero network requests leave your machine.

---

## Architecture Overview

```
 [ Screen Cursor ]
        │
        ▼ (Alt + /)
 [ DPI-Aware Win32 Capture ] (Captures 700x450px region around mouse)
        │
        ▼
 [ Windows Native OCR ] (Windows.Media.Ocr / win_ocr.exe ~35ms)
        │
        ▼
 [ Question Structure Parser ] (Distinguishes question text from options A-D/1-4)
        │
        ▼
 [ Local Ollama AI Engine ] (phi3:mini / qwen2.5 / llama3.2 on local GPU/CPU)
        │
        ▼
 [ Two-Pass Answer Validator ] (Rejects hallucinations, unlisted choices, ramblings)
        │
   ┌────┴─────────────────────────────┬───────────────────────────┐
   ▼                                  ▼                           ▼
[ Floating Glass HUD ]      [ Dynamic Tray Badge ]     [ Caps Lock Pulses ]
(Option + Full Reasoning)   (A/B/C/D/?/! glyphs)       (1=A, 2=B, 3=C, 4=D)
```

---

## User Interface

Rubric-Local features a restrained Windows minimalist dark design language (Zinc/Slate surfaces with subtle 1px dividers and a focused Sky Cyan accent):

```
┌──────────────────────┬────────────────────────────────────────────────────────────┐
│  ◈ RUBRIC-LOCAL      │  System Ready                                    [Alt + /] │
│                      ├────────────────────────────────────────────────────────────┤
│  ⚡ Dashboard        │  [ Offline Engine ]  [ Local Ollama ]  [ Win OCR ] [ HUD ] │
│  🎯 Answer & Capture │                                                            │
│  📜 History          │  ┌───────────────────────────────────────────────────────┐ │
│  ⚙️  Settings         │  │ ⚡ Solved (B)                                          │ │
│  🪄 Setup Wizard     │  │ Option B: Photosynthesis                              │ │
│  🩺 Diagnostics      │  │ Confidence: 97%  •  Total: 269ms                      │ │
│  ℹ️  About            │  └───────────────────────────────────────────────────────┘ │
│                      │  Recent Activity & Log Telemetry...                        │
│  ● Engine Ready      │                                                            │
└──────────────────────┴────────────────────────────────────────────────────────────┘
```

1. **Dashboard:** Readiness telemetry, one-click manual capture trigger, HUD toggles, and recent queries.
2. **Answer & Capture Monitor:** Step-by-step pipeline tracker (Capture -> OCR -> LLM -> Validation), prominent answer glyph, confidence score, timing breakdown, and copyable explanations.
3. **Question History:** Local searchable JSONL audit log with query filtering and telemetry inspection.
4. **Settings:** In-app selection of Ollama model, server endpoint, capture dimensions, indicator modes, and customizable Caps Lock pulse timing.
5. **Setup Wizard:** 5-step first-run onboarding with dependency verification, live Ollama probe, real model download progress, and benchmark inference.
6. **Diagnostics:** Live system telemetry (PID, GPU, paths, logs) and exportable Markdown report generator.
7. **About:** Privacy manifesto, zero-socket architecture verification, and keyboard shortcuts.

---

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **OS** | Windows 10 (64-bit, 20H2+) | Windows 11 (64-bit, 22H2+) |
| **RAM** | 8 GB | 16 GB+ |
| **GPU** | CPU Only (avx2) | NVIDIA RTX (4GB+ VRAM, e.g. RTX 3050/4050+) |
| **Storage** | 500 MB (app) + 2.5 GB (model) | 5 GB SSD free space |
| **Ollama** | v0.1.30+ | Latest from [ollama.com](https://ollama.com) |

---

## Quick Start (For Users)

### Option A: Portable Zero-Setup ZIP (Recommended)
1. Download `Rubric-Local-v1.0.0-win64-portable.zip` from [Releases](../../releases).
2. Extract the ZIP anywhere on your PC (e.g. `Downloads` or `Desktop`).
3. Ensure [Ollama](https://ollama.com) is installed and running (`ollama pull phi3:mini`).
4. Double-click `Run-Rubric-Local.bat`.

### Option B: Windows Installer
1. Download and run `install.bat` (or right-click `installer.ps1` -> *Run with PowerShell*).
2. It installs cleanly into `%LOCALAPPDATA%\Programs\Rubric-Local`, creates Start Menu and Desktop shortcuts, and registers an uninstaller in Windows Settings.

---

## Quick Start (For Developers)

```powershell
# 1. Clone repository
git clone https://github.com/your-username/rubric-local.git
cd rubric-local/rubric_local_app

# 2. Run automated setup & verification
.\setup.ps1

# 3. Launch in Developer Mode (interactive console)
.\run_dev.bat
```

To run the complete offline verification regression suite:
```powershell
python tests/run_all_tests.py
```

---

## Recommended Models by Hardware Tier

| Hardware Tier | Model | RAM/VRAM | Avg Latency | Reasoning Quality |
|---------------|-------|----------|-------------|-------------------|
| **Ultra-Light / CPU** | `qwen2.5:0.5b` | ~600 MB | ~150 ms | Fast factual MCQ |
| **Balanced (Recommended)** | `phi3:mini` (3.8B) | ~2.3 GB | ~280 ms | Exceptional math & logic |
| **High Accuracy** | `llama3.2:3b` | ~2.0 GB | ~290 ms | High vocabulary & science |
| **Pro / 8GB+ VRAM** | `qwen2.5:7b` | ~4.7 GB | ~600 ms | Complex domain knowledge |

Pull any model via terminal:
```bash
ollama pull phi3:mini
```

---

## Floating AI HUD Overlay

Rubric-Local includes a borderless, translucent dark floating HUD with subtle emerald green stealth accents (`#10b981` / `#064e3b` / `#0f1117`).

### Key Capabilities
- **Focus-Free Operation (`WS_EX_NOACTIVATE`):** Floating HUD stays above normal windows (`-topmost`) without stealing keyboard or window focus (`0x08000000`). Clicking controls or viewing answers never disrupts your active typing session or application.
- **Compact vs Expanded Modes:** Click `—` to collapse into a minimal pill indicator (title & badge), or `⤢` to expand to full reasoning and syntax-highlighted code.
- **Position Pinning (`📌` / `📍`):** Pin the HUD to lock it at fixed screen coordinates and prevent accidental drags. Position is saved persistently.
- **Syntax-Highlighted Code Blocks:** For programming questions, code blocks are rendered in a dedicated monospace container with syntax coloring (keywords in emerald green, strings in amber, comments in slate, types in sky blue), horizontal and vertical scrollbars, and a one-click **"💻 Copy Code"** button.
- **One-Click Answer Copying:** Click **"📋 Copy Answer"** to copy the formatted answer, badge, explanation, and code directly to your clipboard.
- **Dismiss & Auto-Dismiss:** Press `Esc` or click `×` to hide. Optionally configure an auto-dismiss timeout in Settings.

---

## Automatic Hover-to-Answer Engine

In addition to manual triggering via `Alt + /`, Rubric-Local features an autonomous hover-detection engine:

- **Stationary Detection:** Monitors cursor coordinates at 20Hz. When the mouse remains stationary within a configurable jitter radius (default: 15px) for longer than the hover delay (default: 800ms), screen capture and OCR are automatically initiated.
- **Duplicate-Question Filter (LRU Cache):** Uses normalized alphanumeric SHA-256 fingerprinting to prevent re-solving unchanged questions when the mouse hovers nearby. Cached questions are not re-submitted to the local LLM.
- **Smart Window Exclusion:** The cursor is ignored when resting over the floating HUD itself or the Rubric-Local application window, preventing self-capture loops.
- **Post-Solve Cooldown:** Enforces a configurable cooldown period (default: 3.0s) after each solve before another hover can trigger.
- **Pause/Resume Controls:** Toggle hover detection on the fly via the HUD (`⏸` / `▶`), system tray context menu, or Settings.

---

## Windows Screen-Capture Privacy Exclusion

Rubric-Local leverages the native Windows Window Display Affinity API (`SetWindowDisplayAffinity`) to prevent the floating HUD from being captured during screen recordings, screenshots, and meeting shares:

| API Affinity Level | Value | Target Platforms | Behavior |
|--------------------|-------|------------------|----------|
| `WDA_EXCLUDEFROMCAPTURE` | `0x00000011` | Windows 10 Version 2004+ (Build 19041+) and Windows 11 | Window is completely invisible in desktop captures (BitBlt, PrintWindow, ImageGrab, screen recorders). |
| `WDA_MONITOR` (Fallback) | `0x00000001` | Windows 10 (Build 10240+) and older | Window rendered only on its physical monitor; capture software sees black rect or passes through. |
| `WDA_NONE` | `0x00000000` | All Windows versions | Normal window display; included in all captures. |

> [!NOTE]
> Capture exclusion is an explicit privacy feature. While supported natively by Windows 10 (2004+) and Windows 11, hardware capture cards (HDMI passthrough) or specialized kernel-level capture drivers may bypass display affinity. Rubric-Local falls back gracefully on older Windows builds.

---

## Configuration Reference

All settings can be modified via the Settings tab in the application or by editing `%APPDATA%\RubricLocal\config.json`:

| Setting | Default | Description |
|---------|---------|-------------|
| `hud_enabled` | `true` | Enable or disable the floating HUD overlay |
| `hud_always_on_top` | `true` | Keep HUD above normal windows without stealing focus |
| `hud_pinned` | `false` | Pin HUD to fixed screen coordinates |
| `hud_opacity` | `0.92` | HUD translucency level (0.4 to 1.0) |
| `exclude_from_capture` | `true` | Apply `WDA_EXCLUDEFROMCAPTURE` privacy affinity |
| `answer_timeout_sec` | `0` | Auto-dismiss timer in seconds (0 = stay until dismissed) |
| `hover_to_answer_enabled` | `false` | Enable automatic hover question detection |
| `hover_delay_ms` | `800` | Stationary hover threshold before capture (ms) |
| `hover_cooldown_sec` | `3.0` | Cooldown period between automatic solves (s) |
| `hover_movement_threshold_px` | `15` | Cursor jitter movement tolerance (px) |
| `is_hover_paused` | `false` | Pause state for hover-to-answer |
| `caps_lock_indicator` | `false` | Enable hardware Caps Lock LED signaling |
| `hotkey` | `alt+/` | Global manual solve hotkey |

---

## Hotkeys & Controls

- `Alt + /` — Solve question under mouse cursor.
- `Hover mouse cursor for 800ms` — Automatically solve question under cursor (when Hover-to-Answer is enabled).
- `Escape` (on HUD) — Dismiss floating HUD overlay.
- `Double-click tray icon` — Show/restore Rubric-Local desktop window.
- `Right-click tray icon`:
  - **Open Rubric-Local** — Focus main window
  - **Solve Under Cursor (Alt+/)** — Trigger manual capture
  - **Show/Hide Mini HUD** — Toggle floating HUD visibility
  - **Pause/Resume Hover-to-Answer** — Toggle automatic hover detection
  - **Settings** — Open configuration screen
  - **Quit** — Terminate application cleanly

---

## Troubleshooting & FAQ

1. **HUD is not appearing on screen:**
   - Verify that **Enable Floating AI HUD Overlay** and **Show floating HUD automatically during solve** are checked in Settings.
   - If previously moved off-screen, click **Pin HUD** or reset `hud_pos_x`/`hud_pos_y` in `config.json`.
2. **Hover detection is not triggering:**
   - Ensure **Enable Automatic Hover-to-Answer** is checked in Settings.
   - Verify that hover detection is not paused (`⏸` symbol on HUD or status in Settings).
   - Keep the mouse cursor stationary over the question text for at least 800ms.
   - If the exact same question was recently solved, it is cached to prevent redundant inference. Move to a new question or press `Alt + /` to force re-solve.
3. **Capture exclusion status shows unsupported:**
   - `WDA_EXCLUDEFROMCAPTURE` requires Windows 10 Version 2004 (Build 19041) or higher. On older builds, `WDA_MONITOR` is used as fallback.
4. **Global hotkey `Alt + /` is not responding:**
   - If another application has already registered `Alt + /`, Rubric-Local will log a warning (Win32 Error 1409). You can solve questions via the tray menu, hover detection, or UI button.

---

## Privacy & Security Manifesto

1. **Zero Outbound Sockets:** Rubric-Local connects exclusively to `127.0.0.1:11434` (local Ollama loopback). No external HTTP, telemetry, or analytics requests are ever made.
2. **Local Data Storage:** All configuration and query history remain strictly on your device inside `%APPDATA%\RubricLocal`.
3. **No Continuous Screen Recording:** Rubric-Local captures an isolated frame around the cursor only when stationary hover conditions are met or `Alt + /` is pressed.
4. **Capture Exclusion:** Keeps AI reasoning private from screen-sharing tools.

---

## License

This project is licensed under the [MIT License](LICENSE).

