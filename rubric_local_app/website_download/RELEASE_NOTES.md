# Rubric-Local v1.0.0 — Official Release Notes

**Release Date:** October 2026  
**Build:** v1.0.0-win64 (Standalone & Portable)  
**Platform:** Windows 10 & Windows 11 (64-bit)

---

## Highlights

Rubric-Local v1.0.0 is the first public, production-grade release of the 100% offline, privacy-first AI question recognition and solver engine. Designed for zero-cloud autonomy, it delivers sub-second local OCR, hardware-accelerated local LLM inference, dynamic system tray badges, and physical keyboard Caps Lock indicators.

### 1. Zero-Crash Startup Architecture
- **Pre-GUI Mutex Guard:** Solved the instant startup crash/flash caused by secondary instances constructing Tkinter windows before mutex verification. Secondary instances immediately wake the primary instance via custom Win32 message filter and exit cleanly with code 0.
- **UIPI Message Filter:** Registered `WM_RUBRIC_WAKEUP` through `ChangeWindowMessageFilter` to guarantee wake-up message delivery across integrity levels.
- **Resilient Hotkey Registration:** If hotkey `Alt + /` encounters Windows conflict error 1409, the engine logs diagnostic guidance without killing the message pump.
- **Asynchronous Ollama Probing:** Decoupled local Ollama HTTP reachability checks to background daemon threads, reducing startup latency to <20ms.

### 2. Modern Minimalist Windows UI Redesign
- Redesigned with a restrained Zinc/Slate neutral aesthetic, subtle 1px dividers, and a focused Sky Cyan accent.
- **7 Comprehensive Views:**
  - `Dashboard`: Engine readiness status, metric cards, instant manual solve trigger, floating HUD docking toggle, and recent query preview.
  - `Answer & Capture Monitor`: Step-by-step pipeline tracker (Capture -> OCR -> LLM -> Verification), large validated answer badge, confidence percentage, latency diagnostics, and one-click copy buttons.
  - `History`: Dual-pane local question audit log with live substring search, choice breakdown, and JSONL export.
  - `Settings`: Model selection, Ollama endpoint URL, capture bounding boxes, HUD opacity, and Caps Lock pulse timing calibration.
  - `Setup Wizard`: 5-step interactive first-run wizard with live dependency checks, Ollama probe, real model streaming download progress, and benchmark verification test.
  - `Diagnostics`: Detailed system telemetry (PID, GPU VRAM, paths, live logs) and one-click sanitized report generator.
  - `About`: Offline manifesto, zero-socket architecture verification, and keyboard shortcuts.

### 3. Packaging & Distribution
- **Standalone Binary:** Fully bundled Windows 64-bit standalone package built with PyInstaller with clean native Win32 message loop support.
- **Portable ZIP:** Zero-setup distribution package with 1-click batch launcher (`Run-Rubric-Local.bat`).
- **Clean Installer / Uninstaller:** PowerShell installer script with Start Menu & Desktop shortcut creation and registered Windows Settings (Add/Remove Programs) uninstaller.

---

## System Requirements

- **Operating System:** Windows 10 (20H2+) or Windows 11 (64-bit)
- **Processor:** x86_64 Dual-Core or higher
- **RAM:** 8 GB minimum (16 GB recommended)
- **GPU (Optional):** NVIDIA GeForce (4 GB+ VRAM recommended for <300ms inference)
- **Local AI Daemon:** [Ollama](https://ollama.com) v0.1.30+ running locally

---

## Artifact Verification Hashes (SHA-256)

```text
3208569790a4e113dc0a8a56fb2347c9b4d4fd9fe45db95ac93ae87a83af6786  Rubric-Local-v1.0.0-win64-portable.zip
fa6ebb5ac611c3cdac9fe34f8d3b02b9319951a78135ce888377ab152bef9ffd  Rubric-Local.exe
```
