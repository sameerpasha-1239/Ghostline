import os
import json
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

class AppConfig(BaseModel):
    model_name: str = Field(default="phi3:mini", description="Ollama model to use for reasoning")
    ollama_url: str = Field(default="http://127.0.0.1:11434", description="Local Ollama daemon REST endpoint")
    capture_width: int = Field(default=900, description="Bounding box capture width in pixels")
    capture_height: int = Field(default=600, description="Bounding box capture height in pixels")
    hotkey: str = Field(default="alt+/", description="Global hotkey to trigger solve")
    indicator_mode: str = Field(default="both", description="Indicator mode: 'hud', 'tray', or 'both'")
    hud_opacity: float = Field(default=0.95, description="HUD opacity (0.5 to 1.0)")
    auto_copy_answer: bool = Field(default=False, description="Automatically copy answer to clipboard")
    save_history_locally: bool = Field(default=True, description="Save audit log of queries locally")
    caps_lock_indicator: bool = Field(default=False, description="Enable Caps Lock LED pulse indicator")
    caps_pulse_on_ms: int = Field(default=300, description="Caps Lock LED pulse ON duration in milliseconds")
    caps_pulse_off_ms: int = Field(default=250, description="Caps Lock LED pulse OFF duration between blinks in milliseconds")
    caps_sequence_cooldown_ms: int = Field(default=700, description="Caps Lock LED pulse sequence cooldown in milliseconds")
    show_hud_on_solve: bool = Field(default=True, description="Automatically display floating mini-HUD during solve")
    start_minimized: bool = Field(default=False, description="Start application minimized to system tray")
    answer_timeout_sec: int = Field(default=0, description="Auto-dismiss timeout for floating answer HUD in seconds (0 = keep open until dismissed)")
    
    # Floating HUD & Positioning
    hud_enabled: bool = Field(default=True, description="Enable floating transparent HUD overlay")
    hud_width: int = Field(default=380, description="HUD window width in pixels")
    hud_height: int = Field(default=300, description="HUD window height in pixels")
    hud_max_width: int = Field(default=520, description="HUD maximum width constraint in pixels")
    hud_max_height: int = Field(default=460, description="HUD maximum height constraint in pixels")
    hud_scroll_speed: int = Field(default=2, description="HUD mouse-wheel scrolling step multiplier")
    hud_pos_x: Optional[int] = Field(default=None, description="Persistent HUD X screen coordinate")
    hud_pos_y: Optional[int] = Field(default=None, description="Persistent HUD Y screen coordinate")
    hud_pinned: bool = Field(default=False, description="Pin HUD to persistent position")
    hud_always_on_top: bool = Field(default=True, description="Keep HUD above normal windows without stealing focus")
    exclude_from_capture: bool = Field(default=True, description="Exclude HUD from desktop screen captures via SetWindowDisplayAffinity")
    
    # Automatic Hover-to-Answer
    hover_to_answer_enabled: bool = Field(default=False, description="Enable automatic question detection on cursor hover")
    hover_delay_ms: int = Field(default=800, description="Stationary hover delay in milliseconds before triggering capture")
    hover_cooldown_sec: float = Field(default=3.0, description="Cooldown in seconds between consecutive hover solves")
    hover_movement_threshold_px: int = Field(default=15, description="Cursor movement jitter tolerance in pixels")
    is_hover_paused: bool = Field(default=False, description="Pause/resume state for automatic hover detection")


def get_app_dir() -> Path:
    app_data = os.environ.get("APPDATA")
    if app_data:
        path = Path(app_data) / "RubricLocal"
    else:
        path = Path.home() / ".rubric_local"
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_config_path() -> Path:
    # 1. Check for project-local config.json if present
    project_cfg = Path(__file__).resolve().parent.parent / "config.json"
    if project_cfg.exists():
        return project_cfg
    # 2. Check standard APPDATA path
    return get_app_dir() / "config.json"

def _sync_msix_appdata():
    """
    On Windows with Microsoft Store Python (MSIX), %APPDATA% reads and writes
    are isolated into %LOCALAPPDATA%\\Packages\\PythonSoftwareFoundation.*\\LocalCache\\Roaming.
    If the user modifies the unvirtualized %APPDATA%\\RubricLocal\\config.json directly,
    Store Python would otherwise read a stale LocalCache copy.
    This helper reads the real file via cmd.exe type and synchronizes LocalCache.
    """
    if os.name != "nt":
        return
    try:
        app_data = os.environ.get("APPDATA")
        if not app_data:
            return
        real_config = Path(app_data) / "RubricLocal" / "config.json"
        
        # Read the real file via cmd.exe to bypass MSIX file virtualization
        import subprocess
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 1)
        startupinfo.wShowWindow = 0  # SW_HIDE
        res = subprocess.run(
            ["cmd.exe", "/c", "type", str(real_config)],
            capture_output=True,
            text=True,
            timeout=1,
            creationflags=creationflags,
            startupinfo=startupinfo,
        )
        if res.returncode == 0 and res.stdout.strip():
            real_data = json.loads(res.stdout)
            cfg_path = get_config_path()
            # If cfg_path is not project-local, synchronize the virtualized copy
            if cfg_path != Path(__file__).resolve().parent.parent / "config.json":
                need_write = True
                if cfg_path.exists():
                    try:
                        with open(cfg_path, "r", encoding="utf-8") as f:
                            current = json.load(f)
                        if current == real_data:
                            need_write = False
                    except Exception:
                        pass
                if need_write:
                    cfg_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(cfg_path, "w", encoding="utf-8") as f:
                        json.dump(real_data, f, indent=2)
    except Exception:
        pass

def load_config(custom_path: Optional[Path] = None) -> AppConfig:
    if custom_path is None:
        _sync_msix_appdata()
        config_path = get_config_path()
    else:
        config_path = custom_path

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return AppConfig(**data)
        except Exception:
            pass
    config = AppConfig()
    save_config(config, custom_path=config_path)
    return config

def save_config(config: AppConfig, custom_path: Optional[Path] = None) -> None:
    config_path = custom_path or get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(), f, indent=2)

    # If running on Windows Store Python, also mirror to real APPDATA
    if os.name == "nt" and custom_path is None:
        try:
            app_data = os.environ.get("APPDATA")
            if app_data:
                real_config = Path(app_data) / "RubricLocal" / "config.json"
                if config_path != real_config:
                    import subprocess
                    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 1)
                    startupinfo.wShowWindow = 0  # SW_HIDE
                    subprocess.run(
                        ["cmd.exe", "/c", "copy", "/y", str(config_path), str(real_config)],
                        capture_output=True,
                        timeout=1,
                        creationflags=creationflags,
                        startupinfo=startupinfo,
                    )
        except Exception:
            pass

