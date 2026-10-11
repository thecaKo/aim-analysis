"""Drives rawinput_logger.run() on any OS with a fake user32, so the WM_INPUT
callback body (struct field names, formatting) is actually executed."""
import ctypes
import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from unittest import mock


class LoggerCallbackTests(unittest.TestCase):
    def test_wm_input_produces_a_line_with_motion_and_button(self):
        with mock.patch.object(sys, "platform", "win32"), \
                mock.patch.object(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE, create=True):
            sys.modules.pop("helix.capture.rawinput_logger", None)
            mod = importlib.import_module("helix.capture.rawinput_logger")

            captured = {}
            calls = {"n": 0}

            def register_class(ref):
                captured["wndproc"] = ref._obj.lpfnWndProc
                return 1

            def get_raw_input_data(lparam, flag, ref, size, hdr):
                raw = ref._obj
                raw.header.dwType = mod.RIM_TYPEMOUSE
                raw.mouse.usFlags = 0
                raw.mouse.lLastX, raw.mouse.lLastY = 7, -3
                raw.mouse.u.s.usButtonFlags = mod.BTN_LEFT_DOWN
                return 40

            def get_message(ref, *a):
                calls["n"] += 1
                if calls["n"] == 1:
                    captured["wndproc"](1, mod.WM_INPUT, 0, 0)
                    return 1
                return 0

            user32 = types.SimpleNamespace(
                RegisterClassW=register_class, CreateWindowExW=lambda *a: 1,
                RegisterRawInputDevices=lambda *a: 1, GetRawInputData=get_raw_input_data,
                GetRawInputBuffer=lambda *a: 0,
                GetMessageW=get_message, TranslateMessage=lambda r: 1,
                DispatchMessageW=lambda r: 0, DefWindowProcW=lambda *a: 0)
            kernel32 = types.SimpleNamespace(GetModuleHandleW=lambda n: 1)
            fake = types.SimpleNamespace(user32=user32, kernel32=kernel32)

            with tempfile.TemporaryDirectory() as d, \
                    mock.patch.object(ctypes, "windll", fake, create=True):
                path = os.path.join(d, "t.jsonl")
                mod.run(path)
                with open(path) as f:
                    rows = [json.loads(l) for l in f]
        sys.modules.pop("helix.capture.rawinput_logger", None)
        self.assertEqual(rows[0]["ev"], "clock_map")
        self.assertEqual(rows[1]["dx"], 7)
        self.assertEqual(rows[1]["dy"], -3)
        self.assertEqual(rows[1]["b"], 1)

    def test_buffered_mode_reads_a_batch_and_orders_records(self):
        with mock.patch.object(sys, "platform", "win32"), \
                mock.patch.object(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE, create=True):
            sys.modules.pop("helix.capture.rawinput_logger", None)
            mod = importlib.import_module("helix.capture.rawinput_logger")
            captured, calls = {}, {"buf": 0, "msg": 0}
            align = ctypes.sizeof(ctypes.c_void_p)
            rec_size = ctypes.sizeof(mod.RAWINPUT)
            stride = (rec_size + align - 1) // align * align

            def get_raw_input_buffer(buf, size_ref, hdr):
                calls["buf"] += 1
                if calls["buf"] > 1:
                    return 0
                addr = ctypes.addressof(buf)
                for i in range(5):
                    raw = mod.RAWINPUT.from_address(addr + i * stride)
                    raw.header.dwType = mod.RIM_TYPEMOUSE
                    raw.header.dwSize = rec_size
                    raw.mouse.usFlags = 0
                    raw.mouse.lLastX, raw.mouse.lLastY = i + 1, 0
                    raw.mouse.u.s.usButtonFlags = 0
                return 5

            def register_class(ref):
                captured["wndproc"] = ref._obj.lpfnWndProc
                return 1

            def get_message(ref, *a):
                calls["msg"] += 1
                if calls["msg"] == 1:
                    captured["wndproc"](1, mod.WM_INPUT, 0, 0)
                    return 1
                return 0

            user32 = types.SimpleNamespace(
                RegisterClassW=register_class, CreateWindowExW=lambda *a: 1,
                RegisterRawInputDevices=lambda *a: 1, GetRawInputBuffer=get_raw_input_buffer,
                GetRawInputData=lambda *a: 0,
                GetMessageW=get_message, TranslateMessage=lambda r: 1,
                DispatchMessageW=lambda r: 0, DefWindowProcW=lambda *a: 0)
            fake = types.SimpleNamespace(user32=user32,
                                         kernel32=types.SimpleNamespace(GetModuleHandleW=lambda n: 1))
            with tempfile.TemporaryDirectory() as d, \
                    mock.patch.object(ctypes, "windll", fake, create=True):
                path = os.path.join(d, "t.jsonl")
                mod.run(path, buffered=True)
                with open(path) as f:
                    rows = [json.loads(l) for l in f][1:]
        sys.modules.pop("helix.capture.rawinput_logger", None)
        self.assertEqual([r["dx"] for r in rows], [1, 2, 3, 4, 5])
        self.assertEqual(rows, sorted(rows, key=lambda r: r["t"]))

    def test_struct_layout_matches_windows_on_fixed_width_types(self):
        # usButtonFlags must be at offset 4 (union alignment), lLastX at 12, size 24.
        class Btn(ctypes.Structure):
            _fields_ = [("f", ctypes.c_uint16), ("d", ctypes.c_uint16)]

        class U(ctypes.Union):
            _fields_ = [("v", ctypes.c_uint32), ("s", Btn)]

        class R(ctypes.Structure):
            _fields_ = [("usFlags", ctypes.c_uint16), ("u", U), ("raw", ctypes.c_uint32),
                        ("x", ctypes.c_int32), ("y", ctypes.c_int32), ("e", ctypes.c_uint32)]
        self.assertEqual((R.u.offset, R.x.offset, ctypes.sizeof(R)), (4, 12, 24))


if __name__ == "__main__":
    unittest.main()
