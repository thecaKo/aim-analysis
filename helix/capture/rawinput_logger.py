"""Raw Input mouse logger (Windows only, stdlib only).

Reads the mouse through WM_INPUT with RIDEV_INPUTSINK, so it works while
KovaaK's has focus. It only observes the OS input stream: no injection, no
game-process access. Output is JSONL:

  {"ev":"clock_map","perf0":<s>,"epoch0":<s>}
  {"ev":"m","t":<ms since perf0>,"dx":int,"dy":int,"b":<button flags>}

Stop with Ctrl+C.
  python -m helix.capture.rawinput_logger data\\run.jsonl
  python -m helix.capture.rawinput_logger --send 192.168.0.10:8765 --name A_rapido_01
(--send streams to helix.capture.receiver on another machine; --out also keeps a local file.)
"""
import argparse
import ctypes
import json
import sys
import time

if sys.platform != "win32":
    raise SystemExit("rawinput_logger only runs on native Windows (not Linux, macOS or WSL): "
                     "it reads the Windows Raw Input API. Run it from PowerShell/CMD with Windows Python.")

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


class _RAWMOUSE_BUTTONS(ctypes.Structure):
    _fields_ = [("usButtonFlags", wintypes.USHORT), ("usButtonData", wintypes.USHORT)]


class _RAWMOUSE_UNION(ctypes.Union):
    _fields_ = [("ulButtons", wintypes.ULONG), ("s", _RAWMOUSE_BUTTONS)]


class RAWMOUSE(ctypes.Structure):
    # The button union is 4-byte aligned, so usButtonFlags sits at offset 4 (not 2).
    _fields_ = [("usFlags", wintypes.USHORT), ("u", _RAWMOUSE_UNION),
                ("ulRawButtons", wintypes.ULONG),
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


def run(path=None, send=None, name=None):
    if sys.platform != "win32":
        raise SystemExit("rawinput_logger only runs on Windows")
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.DefWindowProcW.restype = LRESULT
    user32.GetRawInputData.argtypes = [wintypes.HANDLE, wintypes.UINT, ctypes.c_void_p,
                                       ctypes.POINTER(wintypes.UINT), wintypes.UINT]

    perf0 = time.perf_counter()
    sender = None
    if send:
        from .netsink import Sender
        host, _, port = send.rpartition(":")
        try:
            sender = Sender(host, int(port), name)
        except OSError as e:
            raise SystemExit("cannot connect to receiver %s: %s" % (send, e))
    out = open(path, "a", encoding="utf-8", buffering=1 << 16) if path else None
    header = json.dumps({"ev": "clock_map", "perf0": perf0, "epoch0": time.time()})
    if out:
        out.write(header + "\n")
    if sender:
        sender.send(header)
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
                line = '{"ev":"m","t":%.3f,"dx":%d,"dy":%d,"b":%d}' \
                       % ((now - perf0) * 1000.0, m.lLastX, m.lLastY, m.usButtonFlags)
                if out:
                    out.write(line + "\n")
                if sender:
                    sender.send(line)
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

    print("Logging%s%s - Ctrl+C to stop" % (" to " + path if path else "", " and streaming to " + send if send else ""))
    msg = wintypes.MSG()
    try:
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    except KeyboardInterrupt:
        pass
    finally:
        if out:
            out.close()
        if sender:
            sender.close()
        print("%d events written" % count[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", help="local JSONL file (optional if --send is used)")
    ap.add_argument("--send", metavar="HOST:PORT", help="stream to a helix receiver")
    ap.add_argument("--name", help="run name used by the receiver for the file")
    a = ap.parse_args()
    if not a.out and not a.send:
        ap.error("give a local file and/or --send")
    run(a.out, a.send, a.name)


if __name__ == "__main__":
    main()
