"""Switch the red lights on Buzz quiz buzzers (Sony Buzz receiver, USB 054C:0002).

Windows only: writes the receiver's 8-byte HID output report through the Windows HID API,
so the browser needs no WebHID permission. Elsewhere (the online copy on Linux) every call
returns False and the game simply plays without lights.
"""

from __future__ import annotations

import sys
import threading

BUZZ_ID = "vid_054c&pid_0002"  # shows in Windows as "Logitech Buzz(tm) Controller V1"


class _NoLights:
    def set(self, on: list[bool]) -> bool:
        return False


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _hid = ctypes.WinDLL("hid")
    _setupapi = ctypes.WinDLL("setupapi")
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class _GUID(ctypes.Structure):
        _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                    ("Data4", ctypes.c_ubyte * 8)]

    class _IFACE(ctypes.Structure):  # SP_DEVICE_INTERFACE_DATA
        _fields_ = [("cbSize", wintypes.DWORD), ("InterfaceClassGuid", _GUID), ("Flags", wintypes.DWORD),
                    ("Reserved", ctypes.c_void_p)]

    _DIGCF = 0x02 | 0x10  # DIGCF_PRESENT | DIGCF_DEVICEINTERFACE
    _ACCESS = 0x80000000 | 0x40000000  # GENERIC_READ | GENERIC_WRITE
    _SHARE = 0x01 | 0x02  # FILE_SHARE_READ | FILE_SHARE_WRITE
    _OPEN_EXISTING = 3
    _INVALID = ctypes.c_void_p(-1).value

    _setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
    _setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(_GUID), wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD]
    _setupapi.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(_GUID),
                                                      wintypes.DWORD, ctypes.POINTER(_IFACE)]
    _setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_IFACE), ctypes.c_void_p,
                                                           wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    _setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
    _kernel32.CreateFileW.restype = ctypes.c_void_p
    _kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                      wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    _kernel32.WriteFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
                                    ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    _kernel32.CloseHandle.argtypes = [ctypes.c_void_p]

    def _hid_paths():
        guid = _GUID()
        _hid.HidD_GetHidGuid(ctypes.byref(guid))
        info = _setupapi.SetupDiGetClassDevsW(ctypes.byref(guid), None, None, _DIGCF)
        if info in (None, _INVALID):
            return
        try:
            i = 0
            while True:
                iface = _IFACE(cbSize=ctypes.sizeof(_IFACE))
                if not _setupapi.SetupDiEnumDeviceInterfaces(info, None, ctypes.byref(guid), i, ctypes.byref(iface)):
                    return
                i += 1
                need = wintypes.DWORD()
                _setupapi.SetupDiGetDeviceInterfaceDetailW(info, ctypes.byref(iface), None, 0, ctypes.byref(need), None)
                buf = ctypes.create_string_buffer(need.value)
                # cbSize of SP_DEVICE_INTERFACE_DETAIL_DATA_W: 8 on 64-bit Python, 6 on 32-bit.
                ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0] = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
                if _setupapi.SetupDiGetDeviceInterfaceDetailW(info, ctypes.byref(iface), buf, need, None, None):
                    yield ctypes.wstring_at(ctypes.addressof(buf) + 4)
        finally:
            _setupapi.SetupDiDestroyDeviceInfoList(info)

    class _WindowsLights:
        """One open handle to the receiver, reopened after an unplug. Thread safe."""

        def __init__(self) -> None:
            self._lock = threading.Lock()
            self._handle = None

        def _open(self):
            for path in _hid_paths():
                if BUZZ_ID in path.lower():
                    h = _kernel32.CreateFileW(path, _ACCESS, _SHARE, None, _OPEN_EXISTING, 0, None)
                    if h not in (None, _INVALID):
                        return h
            return None

        def set(self, on: list[bool]) -> bool:
            # Report id 0x00, then 0x00, one byte per handset (0xFF = on), then two zero bytes.
            data = bytes([0x00, 0x00] + [0xFF if v else 0x00 for v in on] + [0x00, 0x00])
            with self._lock:
                for _attempt in range(2):  # the second try reopens, e.g. after the receiver was replugged
                    if not self._handle:
                        self._handle = self._open()
                        if not self._handle:
                            return False
                    written = wintypes.DWORD()
                    buf = ctypes.create_string_buffer(data, len(data))
                    if _kernel32.WriteFile(self._handle, buf, len(data), ctypes.byref(written), None):
                        return True
                    _kernel32.CloseHandle(self._handle)
                    self._handle = None
                return False

    LIGHTS = _WindowsLights()
else:
    LIGHTS = _NoLights()


def set_lights(on: list[bool]) -> bool:
    """Switch the four buzzer lights. False when no receiver can be reached."""
    if len(on) != 4:
        raise ValueError("need exactly 4 values, one per handset")
    return LIGHTS.set([bool(v) for v in on])
