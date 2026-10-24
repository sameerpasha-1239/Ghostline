import os
import sys
import ctypes
import logging
from typing import Tuple, Dict, Any, Optional
from PIL import Image, ImageGrab

# Enable Per-Monitor DPI Awareness to ensure GetCursorPos and GetSystemMetrics match physical pixels
try:
    # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
    ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
except Exception:
    try:
        # PROCESS_PER_MONITOR_DPI_AWARE = 2
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def inspect_capture_environment() -> Dict[str, Any]:
    """
    Inspects the active window environment before capture:
    - Foreground window HWND, title, and class
    - Fullscreen detection
    - Windows Display Affinity (WDA_MONITOR / WDA_EXCLUDEFROMCAPTURE)
    """
    diag: Dict[str, Any] = {
        "hwnd": 0,
        "title": "",
        "class_name": "",
        "is_fullscreen": False,
        "display_affinity": 0,
        "is_capture_protected": False,
    }
    if sys.platform != "win32":
        return diag

    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return diag

        diag["hwnd"] = hwnd
        title_buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title_buf, 512)
        diag["title"] = title_buf.value

        class_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buf, 256)
        diag["class_name"] = class_buf.value

        # Fullscreen check
        rect = (ctypes.c_long * 4)()
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            left, top, right, bottom = rect[0], rect[1], rect[2], rect[3]
            sw = user32.GetSystemMetrics(0)
            sh = user32.GetSystemMetrics(1)
            if left <= 0 and top <= 0 and right >= sw and bottom >= sh:
                diag["is_fullscreen"] = True

        # Check SetWindowDisplayAffinity
        affinity = ctypes.c_uint32(0)
        if hasattr(user32, "GetWindowDisplayAffinity"):
            if user32.GetWindowDisplayAffinity(hwnd, ctypes.byref(affinity)):
                diag["display_affinity"] = affinity.value
                # 0x01 = WDA_MONITOR, 0x11 = WDA_EXCLUDEFROMCAPTURE
                if affinity.value > 0:
                    diag["is_capture_protected"] = True
                    logging.warning(
                        "[Capture Diagnostic] Target window HWND %s has Display Affinity %d (Screen Capture Protected)",
                        hwnd, affinity.value
                    )
    except Exception as e:
        diag["error"] = str(e)

    return diag

def get_cursor_position() -> Tuple[int, int]:
    """
    Returns the current mouse cursor (x, y) coordinates on the screen.
    Includes graceful fallback to screen center if running in headless/service sessions.
    """
    pt = POINT()
    try:
        if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
            return (pt.x, pt.y)
    except Exception:
        pass

    # Fallback to primary monitor center
    try:
        sw = ctypes.windll.user32.GetSystemMetrics(0)
        sh = ctypes.windll.user32.GetSystemMetrics(1)
        return (sw // 2, sh // 2)
    except Exception:
        return (960, 540)

def capture_screen_around_cursor(
    width: int = 900, 
    height: int = 600, 
    offset_y_ratio: float = 0.2
) -> Tuple[Image.Image, Tuple[int, int, int, int]]:
    """
    Captures the screen region around the current cursor position.
    
    Args:
        width: Desired capture box width.
        height: Desired capture box height.
        offset_y_ratio: Places the cursor at 20% from the top of the box.
    
    Returns:
        Tuple of (PIL Image, (left, top, right, bottom))
    """
    screenshot, bbox, _ = capture_screen_around_cursor_with_diagnostics(
        width=width, height=height, offset_y_ratio=offset_y_ratio
    )
    return screenshot, bbox

def capture_screen_around_cursor_with_diagnostics(
    width: int = 900,
    height: int = 600,
    offset_y_ratio: float = 0.2
) -> Tuple[Image.Image, Tuple[int, int, int, int], Dict[str, Any]]:
    """
    Captures the screen region around the current cursor position and returns
    diagnostic telemetry (window affinity, blank frame detection, DPI scaling).
    """
    diag = inspect_capture_environment()
    cx, cy = get_cursor_position()
    diag["cursor"] = (cx, cy)
    
    # Calculate bounding box
    left = int(cx - (width / 2))
    top = int(cy - (height * offset_y_ratio))
    right = left + width
    bottom = top + height
    
    # Get virtual screen metrics across multi-monitor setups
    try:
        v_left = ctypes.windll.user32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
        v_top = ctypes.windll.user32.GetSystemMetrics(77)    # SM_YVIRTUALSCREEN
        v_width = ctypes.windll.user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
        v_height = ctypes.windll.user32.GetSystemMetrics(79) # SM_CYVIRTUALSCREEN
        if v_width <= 0:
            v_width = 1920
        if v_height <= 0:
            v_height = 1080
    except Exception:
        v_left, v_top, v_width, v_height = 0, 0, 1920, 1080
        
    v_right = v_left + v_width
    v_bottom = v_top + v_height
    
    # Clamp to display bounds
    left = max(v_left, min(left, v_right - width))
    top = max(v_top, min(top, v_bottom - height))
    right = left + width
    bottom = top + height
    
    bbox = (left, top, right, bottom)
    diag["bbox"] = bbox
    
    try:
        screenshot = ImageGrab.grab(bbox=bbox, all_screens=True)
        diag["grab_method"] = "all_screens"
    except Exception:
        try:
            screenshot = ImageGrab.grab(bbox=bbox)
            diag["grab_method"] = "primary_only"
        except Exception:
            # Fallback for headless / non-interactive test sessions
            screenshot = Image.new("RGB", (right - left, bottom - top), (255, 255, 255))
            diag["grab_method"] = "synthetic_fallback"

    # Blank frame / zero-variance detection
    try:
        gray = screenshot.convert("L")
        extrema = gray.getextrema()
        diag["pixel_extrema"] = extrema
        if extrema[0] == extrema[1]:
            diag["is_blank_frame"] = True
            logging.warning(
                "[Capture Diagnostic] Captured image is completely uniform (all pixels=%d). "
                "Possible cause: DRM, anti-cheat display affinity, or minimized target.",
                extrema[0]
            )
        else:
            diag["is_blank_frame"] = False
    except Exception:
        diag["is_blank_frame"] = False
        
    return screenshot, bbox, diag
