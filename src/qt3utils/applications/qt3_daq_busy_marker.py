"""Cross-process marker: qt3santec holds the DAQ during sweeps; qt3power skips reads while present."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

BUSY_MARKER_PATH = Path(tempfile.gettempdir()) / "qt3santec_daq_busy"


def santec_daq_busy() -> bool:
    """True if qt3santec (or a stale crash) has claimed exclusive DAQ use for scanning."""
    return BUSY_MARKER_PATH.is_file()


def _marker_payload() -> Dict[str, Any]:
    return {
        "pid": os.getpid(),
        "started": datetime.now(timezone.utc).isoformat(),
    }


def mark_santec_daq_busy() -> None:
    """Create the busy marker (call when a Santec sweep thread begins DAQ use)."""
    try:
        BUSY_MARKER_PATH.write_text(
            json.dumps(_marker_payload(), indent=0),
            encoding="utf-8",
        )
    except OSError:
        pass


def clear_santec_daq_busy() -> None:
    """Remove the busy marker (call in sweep thread finally)."""
    try:
        BUSY_MARKER_PATH.unlink(missing_ok=True)
    except OSError:
        pass
