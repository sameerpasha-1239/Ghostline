import win32gui
import win32con
import win32api
import winerror
import ctypes

user32 = ctypes.windll.user32
WM_RUBRIC_WAKEUP = win32gui.RegisterWindowMessage("RubricLocalWakeUpMsg")

# Register sink window class
wc = win32gui.WNDCLASS()
wc.lpszClassName = "RubricLocalSingleInstanceSink"
def wndproc(hwnd, msg, wparam, lparam):
    if msg == WM_RUBRIC_WAKEUP:
        print("[Sink] Received WM_RUBRIC_WAKEUP directly!")
        return 0
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
wc.lpfnWndProc = wndproc

try:
    win32gui.RegisterClass(wc)
except Exception as e:
    print(f"RegisterClass note: {e}")

sink_hwnd = win32gui.CreateWindow(
    "RubricLocalSingleInstanceSink", "RubricLocalSinkWindow",
    0, 0, 0, 0, 0, 0, 0, 0, None
)
print(f"Created sink window: {sink_hwnd}")

# Now test finding it from another check
found_hwnd = win32gui.FindWindow("RubricLocalSingleInstanceSink", None)
print(f"Found sink window: {found_hwnd}")

assert found_hwnd == sink_hwnd, "FindWindow failed to find sink window!"
print("SUCCESS: Sink window pattern verified!")

win32gui.DestroyWindow(sink_hwnd)
win32gui.UnregisterClass("RubricLocalSingleInstanceSink", None)
