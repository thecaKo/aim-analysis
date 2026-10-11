"""Raw Input mouse logger (Windows only, stdlib only).

Reads the mouse through WM_INPUT with RIDEV_INPUTSINK, so it works while
KovaaK's has focus. It only observes the OS input stream: no injection, no
game-process access. Output is JSONL:

  {"ev":"clock_map","perf0":<s>,"epoch0":<s>}
  {"ev":"m","t":<ms since perf0>,"dx":int,"dy":int,"b":<button flags>}

Stop with Ctrl+C.   python -m helix.capture.rawinput_logger out.jsonl
"""
import ctypes
import json
import sys
import time
from ctypes import wintypes

WM_INPUT = 0x00FF
RIDEV_INPUTSINK = 0x00000100
RID_INPUT = 0x10000003
RIM_TYPEMOUSE = 0
MOUSE_MOVE_ABSOLUTE = 0x01

# Left/right/middle down+up flag bits of RAWMOUSE.usButtonFlags.
BTN_LEFT_DOWN, BTN_LEFT_UP = 0x0001, 0x0002

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [("usUsagePage", wintypes.USHORT), ("usUsage", wintypes.USHORT),
                ("dwFlags", wintypes.DWORD), ("hwndTarget", wintypes.HWND)]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [("dwType", wintypes.DWORD), ("dwSize", wintypes.DWORD),
                ("hDevice", wintypes.HANDLE), ("wParam", wintypes.WPARAM)]


class RAWMOUSE(ctypes.Structure):
    _fields_ = [("usFlags", wintypes.USHORT), ("usButtonFlags", wintypes.USHORT),
                ("usButtonData", wintypes.USHORT), ("ulRawButtons", wintypes.ULONG),
                ("lLastX", wintypes.LONG), ("lLastY", wintypes.LONG),
                ("ulExtraInformation", wintypes.ULONG)]


class RAWINPUT(ctypes.Structure):
    _fields_ = [("header", RAWINPUTHEADER), ("mouse", RAWMOUSE)]


class WNDCLASS(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HANDLE),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HANDLE),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


def run(path):
    if sys.platform != "win32":
        raise SystemExit("rawinput_logger only runs on Windows")
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.DefWindowProcW.restype = LRESULT
    user32.GetRawInputData.argtypes = [wintypes.HANDLE, wintypes.UINT, ctypes.c_void_p,
                                       ctypes.POINTER(wintypes.UINT), wintypes.UINT]

    perf0 = time.perf_counter()
    out = open(path, "a", encoding="utf-8", buffering=1 << 16)
    out.write(json.dumps({"ev": "clock_map", "perf0": perf0, "epoch0": time.time()}) + "\n")
    count = [0]

    def wndproc(hwnd, msg, wparam, lparam):
        if msg == WM_INPUT:
            now = time.perf_counter()
            size = wintypes.UINT(ctypes.sizeof(RAWINPUT))
            raw = RAWINPUT()
            got = user32.GetRawInputData(lparam, RID_INPUT, ctypes.byref(raw), ctypes.byref(size),
                                         ctypes.sizeof(RAWINPUTHEADER))
            if got != 0xFFFFFFFF and raw.header.dwType == RIM_TYPEMOUSE \
                    and not raw.mouse.usFlags & MOUSE_MOVE_ABSOLUTE:
                m = raw.mouse
                out.write('{"ev":"m","t":%.3f,"dx":%d,"dy":%d,"b":%d}\n'
                          % ((now - perf0) * 1000.0, m.lLastX, m.lLastY, m.usButtonFlags))
                count[0] += 1
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    proc = WNDPROC(wndproc)  # keep a reference alive
    hinst = kernel32.GetModuleHandleW(None)
    cls = WNDCLASS()
    cls.lpfnWndProc, cls.hInstance, cls.lpszClassName = proc, hinst, "HelixRawInput"
    user32.RegisterClassW(ctypes.byref(cls))
    HWND_MESSAGE = wintypes.HWND(-3)
    hwnd = user32.CreateWindowExW(0, cls.lpszClassName, "helix", 0, 0, 0, 0, 0, HWND_MESSAGE, None, hinst, None)
    dev = RAWINPUTDEVICE(0x01, 0x02, RIDEV_INPUTSINK, hwnd)
    if not user32.RegisterRawInputDevices(ctypes.byref(dev), 1, ctypes.sizeof(dev)):
        raise SystemExit("RegisterRawInputDevices failed")

    print("Logging to %s - Ctrl+C to stop" % path)
    msg = wintypes.MSG()
    try:
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    except KeyboardInterrupt:
        pass
    finally:
        out.close()
        print("%d events written" % count[0])


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "data/trace.jsonl")
