# Ghostline

**100% Offline, Privacy-First On-Device AI Question Recognition & Reasoning Engine for Windows 10 & 11.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: Windows](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6.svg?logo=windows)](https://microsoft.com/windows)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?logo=python)](https://python.org)
[![Inference: Ollama](https://img.shields.io/badge/Inference-Ollama%20(Local)-white.svg?logo=ollama)](https://ollama.com)
[![Accuracy: 90.0%](https://img.shields.io/badge/Accuracy-90.0%25%20Verified-brightgreen.svg)](docs/ACCURACY.md)
[![Tests: 103 Passed](https://img.shields.io/badge/Tests-103%2F103%20Passed-success.svg)](tests/)

Ghostline (formerly Rubric-Local) is a native Windows desktop application that captures on-screen assessment questions, parses question structure in under 40 milliseconds using native Windows Media OCR, performs local grounded reasoning via Ollama, and signals validated answers through a floating HUD, dynamic system tray badge, or keyboard Caps Lock pulses.

Zero cloud APIs. Zero telemetry. No accounts, API keys, or subscriptions. All processing remains strictly on your machine.

---

## 1. Problem Statement & Intended Use

Standard cloud-based AI tools require transmitting full screen captures or text to remote servers, violating data privacy, incurring recurring API costs, introducing latency, and risking account telemetry leaks.

Ghostline solves this by running an entirely local, self-contained pipeline on Windows 10 and 11. It is designed for:
- **Research & Academic Study:** Instant local synthesis and verified explanations of complex technical concepts, theory questions, and mathematical formulas.
- **Offline Assessment Practice:** Practicing multiple-choice exams and technical programming challenges without internet access.
- **Privacy-Sensitive Workflows:** Analyzing on-screen documents and exercises in air-gapped or confidential enterprise environments where cloud transmission is strictly prohibited.

---

## 2. Features & Current Limitations

### Core Capabilities
- **Sub-Second Native OCR:** Bridges directly to native `Windows.Media.Ocr.OcrEngine` (UWP/WinRT APIs) via `win_ocr.exe`. Eliminates heavy Tesseract dependencies and executes in under 40ms without console window flash.
- **Grounded Local AI Inference:** Interfaces directly with local Ollama daemon (`127.0.0.1:11434`), supporting `phi3:mini` (3.8B, recommended default) and `qwen2.5:0.5b` (0.5B, low-VRAM fallback).
- **Deterministic Math AST Solver:** Parses arithmetic expressions (`25 * 4 - 30 / 2`, `17 % 5 + 2 * 3^2`) and linear equations (`3x + 15 = 42`) with 100% mathematical precision using restricted Python AST evaluation.
- **Two-Pass Hallucination Defense:** Validates LLM proposed options strictly against on-screen choices before signaling. Rejects ungrounded guesses and ramblings.
- **Floating Glass HUD Overlay:** Dark translucent glassmorphic HUD window (`WS_EX_TOPMOST`, `WS_EX_NOACTIVATE`) that never steals keyboard focus. Supports dragging, scrollable explanations, syntax-highlighted code, and one-click copying.
- **Dynamic System Tray Badges:** 32x32 pixel PIL icons dynamically rendering validated option glyphs (`A-D`, `1-9`, `T`/`F`, `Code`, `✓`, `?`, `!`).
- **Caps Lock Pulse Signaling:** Win32 keyboard pulse signaling with automatic atomic state restoration to preserve physical keyboard states.
- **Automated Verification:** 15 modular test suites with 103 unit and regression tests, plus an empirical 50-question evaluation benchmark measuring 90.0% overall accuracy.

### Current Limitations
- **Platform Specific:** Windows 10 (64-bit, 20H2+) and Windows 11 only (utilizes Win32 DPI hooks and Windows Media OCR). Linux and macOS are not supported.
- **Complex Multivariable Calculus:** Higher-order calculus problems where symbolic AST evaluation is not applicable rely on generative LLM reasoning.
- **Extreme Background Clutter:** Capturing heavily cluttered screen regions where question text collides with surrounding webpage ads or UI elements may require adjusting the capture position.

---

## 3. Visual Interface & Screenshots

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             GHOSTLINE INTERFACE                             │
├──────────────────────┬──────────────────────────────────────────────────────┤
│  ◈ GHOSTLINE         │  System Ready                              [Alt + /] │
│                      ├──────────────────────────────────────────────────────┤
│  ⚡ Dashboard        │  [ Offline Engine ] [ Local Ollama ] [ Win OCR ]     │
│  🎯 Answer & Capture │                                                      │
│  📜 History          │  ┌─────────────────────────────────────────────────┐ │
│  ⚙️  Settings         │  │ ⚡ Solved (B)                                    │ │
│  🩺 Diagnostics      │  │ Option B: Generational cyclic garbage collector │ │
│  ℹ️  About            │  │ Confidence: 98%  •  Total: 1.4s • Model: phi3    │ │
│                      │  └─────────────────────────────────────────────────┘ │
│  ● 100% Offline      │  Recent Activity & Step-by-Step Telemetry...         │
└──────────────────────┴──────────────────────────────────────────────────────┘
```

> _[Screenshot Placeholder: Ghostline Main Control Dashboard]_  
> `![Ghostline Dashboard](docs/assets/dashboard_placeholder.png)`

> _[Screenshot Placeholder: Floating Transparent Glass HUD with Syntax-Highlighted Python Code]_  
> `![Floating Glass HUD](docs/assets/hud_placeholder.png)`

> _[GIF Placeholder: Hover-to-Answer and Alt+/ Screen Solve Workflow]_  
> `![Solve Workflow Demo](docs/assets/workflow_demo_placeholder.gif)`

---

## 4. Architecture Overview & Data Flow

```
[ Screen Cursor ] ──(Alt + / or Hover)──▶ [ DPI-Aware Win32 Screen Capture ]
                                                        │
                                                        ▼ (700x450 RGB Bitmap)
                                          [ Native Windows.Media.Ocr Engine ]
                                                        │
                                                        ▼ (Words & Bounding Boxes)
                                          [ Structure & Option Separator ]
                                                        │
                         ┌──────────────────────────────┴──────────────────────────────┐
                         ▼                                                             ▼
              [ Deterministic Math AST ]                                    [ Type-Aware Prompt Builder ]
                         │                                                             │
                         │                                                             ▼
                         │                                              [ Local Ollama (127.0.0.1:11434) ]
                         │                                                             │
                         └──────────────────────────────┬──────────────────────────────┘
                                                        ▼
                                          [ Two-Pass Schema Validator ]
                                                        │
                        ┌───────────────────────────────┼───────────────────────────────┐
                        ▼                               ▼                               ▼
             [ Floating Glass HUD ]           [ System Tray Glyph ]          [ Caps Lock Pulses ]
             (Full formatted answer)          (Short option badge)           (1=A, 2=B, 3=C, 4=D)
```

For complete technical details, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## 5. Technology Stack & OS Compatibility

- **Language & Runtime:** Python 3.10, 3.11, or 3.12 (64-bit).
- **GUI Framework:** Custom Tkinter runtime with Win32 window attribute extensions (`ctypes`, `pywin32`).
- **OCR Engine:** C# standalone executable (`bin/win_ocr.exe`) compiled against native `Windows.Media.Ocr` (zero external DLLs).
- **Inference Runtime:** Local [Ollama](https://ollama.com) daemon.
- **Operating Systems:**
  - Windows 11 (64-bit, all builds) — *Fully Supported*
  - Windows 10 (64-bit, Version 20H2 or later) — *Fully Supported*
  - macOS / Linux — *Unsupported (native Win32/UWP dependencies)*

---

## 6. Prerequisites

1. **Operating System:** Windows 10 (20H2+) or Windows 11 (64-bit).
2. **Python:** Version 3.10 to 3.12 installed from [python.org](https://www.python.org/downloads/) (ensure *"Add python.exe to PATH"* is checked during installation).
3. **Ollama:** Download and install from [ollama.com](https://ollama.com).
4. **Local AI Model:** At least one locally runnable model pulled via Ollama (recommended: `phi3:mini`).
5. **Windows OCR Pack:** Windows native English OCR language component (installed by default on English Windows; verify in `Settings > Time & Language > Language`).

---

## 7. Exact Installation Steps (Windows)

### Step 1: Clone the Repository
Open PowerShell or Windows Terminal:
```powershell
git clone https://github.com/sameerpasha-1239/Ghostline.git
cd Ghostline/rubric_local_app
```

### Step 2: Create Virtual Environment & Install Dependencies
```powershell
# Create isolated virtual environment
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Upgrade pip and install pinned requirements
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Verify Native OCR Binary
Ghostline includes a pre-compiled `bin/win_ocr.exe`. Verify it executes:
```powershell
.\bin\win_ocr.exe --help
```
If the binary was deleted or blocked, recompile it from the provided C# source in 2 seconds using the built-in Windows .NET compiler:
```cmd
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /target:exe /out:bin\win_ocr.exe bin\src\WinOcr.cs
```

### Step 4: Install and Start Ollama
1. Download Ollama from [ollama.com/download/windows](https://ollama.com/download/windows) and run the installer.
2. In PowerShell, pull the recommended 3.8B model:
   ```powershell
   ollama pull phi3:mini
   ```
3. *(Optional for low-VRAM laptops)* Pull the 0.5B fallback model:
   ```powershell
   ollama pull qwen2.5:0.5b
   ```
4. Verify the model is installed locally:
   ```powershell
   ollama list
   ```

---

## 8. Launching the Application

### Method A: Launch with Terminal / Dev Output
```powershell
python -m rubric_local.app
```
or double-click `run_dev.bat`.

### Method B: Launch in Background / Quiet Mode
```powershell
pythonw -m rubric_local.app
```
or double-click `run.bat`.

### Method C: Headless Diagnostic CLI
```powershell
python -m rubric_local.cli diagnose
```

---

## 9. First-Run Setup & Usage Guide

1. **System Tray Initialization:** Upon launch, Ghostline places a dark status icon in your Windows notification tray. Left-click to open the dashboard; right-click for the context menu.
2. **Solving a Question:**
   - Move your mouse pointer over any multiple-choice or technical question on your screen.
   - Press **`Alt + /`** (or hover still for 800ms if hover-to-answer is enabled).
   - Ghostline captures the 700x450px region, parses options, runs local inference, and verifies the solution.
3. **Reading the Answer:**
   - **Floating HUD:** A translucent glass HUD appears near your cursor showing the validated option, direct answer, and complete reasoning.
   - **Code Blocks:** For programming questions, code is formatted with syntax highlighting and includes a *"Copy Code"* button.
   - **Tray Icon:** The tray icon displays the single option label (`A`, `B`, `1`, `2`, `T`, `F`, `Code`).
   - **Caps Lock:** If enabled, Caps Lock flashes in pulses (`1` pulse for A, `2` for B) and immediately reverts to its original physical state.
4. **Controlling the HUD:**
   - Press **`Ctrl + Shift + H`** to toggle HUD visibility.
   - Drag the HUD header to reposition.
   - Click `_` to minimize to a compact pill badge.
   - Click `✕` to dismiss.
5. **Reviewing Audit History:** Open the Main Window and navigate to the **History** tab to search and inspect all previous solves stored in `%APPDATA%\RubricLocal\history.jsonl`.

---

## 10. Configuration Reference

Settings are stored in `%APPDATA%\RubricLocal\config.json` and can be adjusted via the in-app Settings UI or edited directly:

| Key | Default | Valid Range / Options | Description |
|:---|:---:|:---:|:---|
| `ollama_model` | `"phi3:mini"` | Any installed Ollama model | Active inference model name |
| `ollama_base_url` | `"http://127.0.0.1:11434"` | Valid HTTP localhost URL | Local Ollama REST endpoint |
| `capture_hotkey` | `"Alt+/"` | Valid key combination string | Global screen capture shortcut |
| `hud_toggle_hotkey` | `"Ctrl+Shift+H"` | Valid key combination string | Global HUD visibility toggle shortcut |
| `capture_width` | `700` | `400` – `1600` | Width of captured screen region (pixels) |
| `capture_height` | `450` | `300` – `1200` | Height of captured screen region (pixels) |
| `hud_opacity` | `0.92` | `0.30` – `1.00` | Floating HUD glass translucency level |
| `hud_pinned` | `true` | `true` / `false` | Keep HUD above normal desktop windows |
| `enable_hover_answer` | `false` | `true` / `false` | Trigger capture automatically on cursor stillness |
| `hover_dwell_time_ms` | `800` | `300` – `3000` | Milliseconds of stillness required for hover trigger |
| `enable_caps_indicator` | `true` | `true` / `false` | Enable pulsed Caps Lock keyboard signaling |
| `caps_pulse_duration_ms` | `60` | `20` – `200` | Duration of each individual Caps Lock flash (ms) |
| `caps_pulse_gap_ms` | `100` | `30` – `300` | Gap between multiple Caps Lock flashes (ms) |

---

## 11. Troubleshooting

| Symptom | Cause | Resolution |
|:---|:---|:---|
| **Ollama Disconnected** | Ollama daemon is not running. | Run `ollama serve` in a terminal; verify `http://127.0.0.1:11434/api/tags` loads. |
| **Model Not Found** | Required model has not been downloaded. | Run `ollama pull phi3:mini`. |
| **Native OCR binary error** | `win_ocr.exe` missing or blocked by antivirus. | Compile `bin/src/WinOcr.cs` using Windows `csc.exe` (see Step 3 above). |
| **Hotkey does not trigger** | Another application claims `Alt + /`. | Change `capture_hotkey` to `Ctrl+Shift+F` in Settings. |
| **HUD off-screen** | Secondary monitor disconnected. | Press `Ctrl + Shift + H` or reset `hud_x` / `hud_y` to 100 in `config.json`. |
| **Caps Lock does not flash** | Signaling disabled or anti-cheat hook. | Ensure `enable_caps_indicator` is `true` in Settings; use HUD or tray instead. |

For advanced diagnostic steps, see [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

---

## 12. Accuracy Evaluation & Benchmark Results

Ghostline includes an automated local evaluation framework ([evaluation/evaluator.py](evaluation/evaluator.py)) running against 50 authored technical assessment questions across 7 categories:

### Measured Results (`phi3:mini`)

| Evaluation Set | Questions | Baseline Accuracy | Post-Improvement Accuracy | Net Gain | Average Latency |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Development Set** | 30 | 20 / 30 (66.7%) | **26 / 30 (86.7%)** | **+20.0%** | 3.47 s / query |
| **Held-Out Test Set** | 20 | 15 / 20 (75.0%) | **19 / 20 (95.0%)** | **+20.0%** | 2.39 s / query |
| **Combined Overall** | **50** | **35 / 50 (70.0%)** | **45 / 50 (90.0%)** | **+20.0%** | **2.93 s / query** |

### Per-Category Performance (Combined 50 Questions)
- **mcq_unlabelled:** 7 / 7 (**100.0%**)
- **true_false:** 5 / 5 (**100.0%**)
- **theory:** 7 / 7 (**100.0%**)
- **mcq_labelled:** 9 / 10 (**90.0%**)
- **numerical:** 6 / 7 (**85.7%**)
- **programming:** 6 / 7 (**85.7%**)
- **malformed_ocr:** 5 / 7 (**71.4%**)

To reproduce benchmarks locally:
```powershell
python evaluation/evaluator.py --dataset dev
python evaluation/evaluator.py --dataset heldout
```
Full methodology and error analysis are documented in [docs/ACCURACY.md](docs/ACCURACY.md).

---

## 13. Privacy, Security & Responsible Use

- **100% Offline Integrity:** Zero external API calls, tracking cookies, user telemetry, or remote analytics.
- **Ephemeral Screen Buffer:** Screen captures exist only in system RAM for the duration of OCR recognition and are purged immediately.
- **Local Isolation:** All configuration and history reside strictly inside `%APPDATA%\RubricLocal`.
- **Responsible Use Disclaimer:** Ghostline is intended solely for personal study, technical tutoring, and accessibility assistance. Users are responsible for adhering to all institutional academic integrity and testing platform policies.

For vulnerability reporting, see [SECURITY.md](SECURITY.md).

---

## 14. Testing & Development

Run all 103 automated tests across the 15 test suites:
```powershell
python tests/run_all_tests.py
```

Run specific test modules:
```powershell
python -m unittest tests.test_type_aware_presentation
python -m unittest tests.test_hover_and_hud
python -m unittest tests.test_caps_lock
```

---

## 15. Contributing & License

- Contributions are welcome! Please review [CONTRIBUTING.md](CONTRIBUTING.md) before submitting pull requests.
- Track verified changes in [CHANGELOG.md](CHANGELOG.md).
- Distributed under the **MIT License**. See [LICENSE](LICENSE) for full legal text.
- Target Release Repository: [https://github.com/sameerpasha-1239/Ghostline](https://github.com/sameerpasha-1239/Ghostline)
