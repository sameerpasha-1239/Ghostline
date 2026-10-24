# Contributing to Rubric-Local

Thank you for your interest in contributing to **Rubric-Local**! We welcome bug reports, documentation improvements, model prompts optimizations, and platform stability enhancements.

---

## Philosophy & Guiding Principles

1. **100% Offline Autonomy:** Under no circumstances may code introduce remote API calls, analytics, telemetry, or external network dependencies. The only permissible network socket is loopback (`127.0.0.1`) to the local Ollama daemon.
2. **Handle Hygiene & Thread Safety:** All Win32 resources (HWNDs, mutexes, hooks) must be cleanly unregistered and closed. Long-running or blocking work (HTTP calls, subprocesses, model downloads) must never block the main Tkinter thread.
3. **Restrained Minimalism:** UI additions must respect the minimalist design tokens (Zinc/Slate surfaces, subtle 1px borders, restrained Sky Cyan accent). Avoid visual clutter.

---

## Development Environment Setup

1. **Prerequisites:**
   - Windows 10 or 11 (64-bit)
   - Python 3.10 or 3.11
   - [Ollama](https://ollama.com) installed and serving locally

2. **Clone and Install:**
   ```powershell
   git clone https://github.com/your-username/rubric-local.git
   cd rubric-local/rubric_local_app
   python -m pip install -r requirements.txt
   ```

3. **Verify Setup:**
   Run the full verification suite before making changes:
   ```powershell
   python tests/run_all_tests.py
   ```

4. **Launch Application in Dev Mode:**
   ```powershell
   .\run_dev.bat
   ```

---

## Testing & Quality Assurance

All pull requests must pass the complete automated test suite without regressions:

```powershell
# Run all 51 automated tests across 11 test suites
python tests/run_all_tests.py

# Run specific suite
python -m unittest tests.test_desktop_ui
python -m unittest tests.test_startup_lifecycle
python -m unittest tests.test_hotkey
```

### Writing New Tests
- Place tests under `tests/test_<feature>.py`.
- Ensure tests cleanly release all Win32 mutexes, sockets, and window handles in `tearDown()`.
- Never leave orphaned background processes running.

---

## Pull Request Guidelines

1. **Create a Topic Branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. **Keep Commits Focused:**
   Write clear, concise commit messages following standard conventions:
   `fix(startup): resolve race condition in mutex acquisition`
3. **Document Changes:**
   Update relevant sections of `README.md` if changing user-facing settings, flags, or shortcuts.
4. **Submit PR:**
   Provide a detailed description of the problem solved, testing methodology, and any relevant logs.
