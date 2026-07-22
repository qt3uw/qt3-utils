"""
Cross-process lock for NI-DAQ piezo analog outputs shared by qt3scan and qt3move.

qt3scan acquires with blocking while using ScanController piezo motion.
qt3move tries non-blocking acquire before manual piezo moves so active scans keep the lock.
"""
from __future__ import annotations

import os
import sys
import tempfile

_MUTEX_NAME = "Local\\QT3Utils_PiezoDAQ"
_UNIX_LOCK_BASENAME = "qt3utils_piezo_daq.lock"

_win_mutex_handle = None
_scanner_unix_fp = None
_manual_stack: list = []


def _win_mutex() -> int:
    global _win_mutex_handle
    if _win_mutex_handle is None:
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
        if not handle:
            raise OSError("CreateMutexW failed for piezo DAQ lock")
        _win_mutex_handle = handle
    return _win_mutex_handle


def acquire_scanner(blocking: bool = True) -> bool:
    """
    Acquire the piezo DAQ lock for qt3scan. Use release_scanner() in a finally block.
    """
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        WAIT_OBJECT_0 = 0
        INFINITE = 0xFFFFFFFF
        ms = INFINITE if blocking else 0
        r = kernel32.WaitForSingleObject(_win_mutex(), ms)
        return r == WAIT_OBJECT_0

    global _scanner_unix_fp
    import fcntl

    path = os.path.join(tempfile.gettempdir(), _UNIX_LOCK_BASENAME)
    _scanner_unix_fp = open(path, "a+")
    try:
        flags = fcntl.LOCK_EX
        if not blocking:
            flags |= fcntl.LOCK_NB
        fcntl.flock(_scanner_unix_fp.fileno(), flags)
    except BlockingIOError:
        _scanner_unix_fp.close()
        _scanner_unix_fp = None
        return False
    return True


def release_scanner() -> None:
    """Release the lock after qt3scan finishes a piezo/counter operation."""
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.kernel32.ReleaseMutex(_win_mutex())
        return

    global _scanner_unix_fp
    if _scanner_unix_fp is None:
        return
    import fcntl

    try:
        fcntl.flock(_scanner_unix_fp.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        _scanner_unix_fp.close()
    except OSError:
        pass
    _scanner_unix_fp = None


def try_acquire_manual_move() -> bool:
    """
    Non-blocking acquire for qt3move manual piezo moves. Pair with release_manual_move().
    """
    if sys.platform == "win32":
        return acquire_scanner(blocking=False)

    import fcntl

    path = os.path.join(tempfile.gettempdir(), _UNIX_LOCK_BASENAME)
    fp = open(path, "a+")
    try:
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fp.close()
        return False
    _manual_stack.append(fp)
    return True


def release_manual_move() -> None:
    """Release after a qt3move manual piezo move."""
    if sys.platform == "win32":
        release_scanner()
        return

    import fcntl

    if not _manual_stack:
        return
    fp = _manual_stack.pop()
    try:
        fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        fp.close()
    except OSError:
        pass
