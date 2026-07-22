"""NI-DAQ digital output control for edge-triggered flipper mounts (e.g. Newport 889x)."""
from __future__ import annotations

import threading
import time
from typing import List, Mapping, Optional, Sequence, Union

import nidaqmx
import numpy as np
from nidaqmx.stream_writers import DigitalMultiChannelWriter, DigitalSingleChannelWriter

_DoWriter = Union[DigitalSingleChannelWriter, DigitalMultiChannelWriter]


class FlipperMountError(Exception):
    """Raised when flipper DAQ operations fail."""


def _resolve_line_spec(device_name: str, line: str) -> str:
    """Build a full physical channel string for ``add_do_chan``."""
    line = line.strip().strip("/")
    if not line:
        raise ValueError("empty digital line spec")
    if line.startswith(f"{device_name}/"):
        return line
    return f"{device_name}/{line}"


def _add_do_channels(task: nidaqmx.Task, resolved: Sequence[str]) -> None:
    """Add one DO channel per line (range syntax breaks per-line list writes)."""
    for spec in resolved:
        task.do_channels.add_do_chan(spec)


def _make_do_writer(task: nidaqmx.Task, n_lines: int) -> _DoWriter:
    if n_lines == 1:
        return DigitalSingleChannelWriter(task.out_stream, auto_start=True)
    return DigitalMultiChannelWriter(task.out_stream, auto_start=True)


def _write_do_levels(writer: _DoWriter, n_lines: int, levels: Sequence[bool]) -> None:
    lst = [bool(x) for x in levels]
    data = np.array(lst, dtype=bool)
    if n_lines == 1:
        writer.write_one_sample_one_line(data[0])
    else:
        # One boolean per channel, in channel add order.
        writer.write_one_sample_one_line(data)


class FlipperMountController:
    """
    Software-timed static digital output for TTL flipper inputs (rising/falling edges).

    **NI USB-6343 (BNC):** front-panel digital / PFI BNCs appear in NI-DAQmx as
    ``port1/line0``–``line7`` (PFI 0–7) and ``port2/line0``–``line7`` (PFI 8–15).
    ``port0`` lines live on the 37-pin D connector. Timed waveform DO is often
    restricted to port0 on X Series, but **static** writes used here are valid on
    port1/port2 for TTL-style control—match each flipper's ``line`` in YAML to the
    connector you wired.

    **Construction:** either a contiguous port range (legacy), or an explicit ordered
    list of lines (e.g. four ``port2/line0``…``line3`` entries for BNC DIO). Write
    order matches the order of ``line_channels``.
    """

    def __init__(
        self,
        device_name: str = "Dev1",
        port: str = "port0",
        line_start: int = 0,
        n_lines: int = 4,
        line_channels: Optional[Sequence[str]] = None,
    ) -> None:
        self._device_name = device_name
        self._task: Optional[nidaqmx.Task] = None
        self._writer: Optional[_DoWriter] = None
        self._lock = threading.Lock()

        if line_channels is not None:
            specs = list(line_channels)
            if len(specs) < 1:
                raise ValueError("line_channels must be non-empty")
            resolved = [_resolve_line_spec(device_name, s) for s in specs]
            self._resolved_channels = resolved
            self._n = len(resolved)
            self._port = ""
            self._line_start = 0
        else:
            if n_lines < 1:
                raise ValueError("n_lines must be at least 1")
            self._port = port
            self._line_start = line_start
            self._n = n_lines
            last = line_start + n_lines - 1
            self._resolved_channels = [
                f"{device_name}/{port}/line{i}" for i in range(line_start, last + 1)
            ]

        self._channel_string = ",".join(self._resolved_channels)
        self._levels: List[bool] = [False] * self._n

    @property
    def channel_string(self) -> str:
        return self._channel_string

    @property
    def connected(self) -> bool:
        return self._task is not None

    @property
    def levels(self) -> List[bool]:
        """Copy of last commanded line levels (True = high, UP for typical TTL flipper inputs)."""
        with self._lock:
            return list(self._levels)

    def _write_do(self, levels: Sequence[bool]) -> None:
        if self._task is None or self._writer is None:
            raise FlipperMountError("Not connected")
        _write_do_levels(self._writer, self._n, levels)

    def connect(self) -> None:
        with self._lock:
            if self._task is not None:
                return
            task = None
            try:
                task = nidaqmx.Task()
                _add_do_channels(task, self._resolved_channels)
                writer = _make_do_writer(task, self._n)
                levels = [True] * self._n
                _write_do_levels(writer, self._n, levels)
                self._task = task
                self._writer = writer
                self._levels = levels
                task = None
            except Exception as e:
                if task is not None:
                    try:
                        task.close()
                    except Exception:
                        pass
                raise FlipperMountError(
                    f"Failed to connect to {self._channel_string}: {e}"
                ) from e

    def close(self) -> None:
        with self._lock:
            if self._task is None:
                return
            t = self._task
            self._task = None
            self._writer = None
            try:
                t.stop()
            except Exception:
                pass
            try:
                t.close()
            except Exception:
                pass

    def write_levels(self, levels: Sequence[bool]) -> None:
        if len(levels) != self._n:
            raise ValueError(f"expected {self._n} booleans, got {len(levels)}")
        lst = [bool(x) for x in levels]
        with self._lock:
            if self._task is None:
                raise FlipperMountError("Not connected")
            try:
                self._write_do(lst)
                self._levels = lst
            except Exception as e:
                raise FlipperMountError(f"write failed: {e}") from e

    def apply_partial(self, updates: Mapping[int, bool]) -> None:
        """
        Set only the listed line indices to the given levels; all other lines
        keep their last commanded values (no edges on unchanged lines).
        """
        if not updates:
            return
        with self._lock:
            if self._task is None:
                raise FlipperMountError("Not connected")
            new = list(self._levels)
            for i, v in updates.items():
                if i < 0 or i >= self._n:
                    raise IndexError(f"flipper index out of range: {i}")
                new[i] = bool(v)
            try:
                self._write_do(new)
                self._levels = new
            except Exception as e:
                raise FlipperMountError(f"apply_partial failed: {e}") from e

    def toggle(self, index: int) -> None:
        if index < 0 or index >= self._n:
            raise IndexError(f"flipper index out of range: {index}")
        with self._lock:
            if self._task is None:
                raise FlipperMountError("Not connected")
            new = list(self._levels)
            new[index] = not new[index]
            try:
                self._write_do(new)
                self._levels = new
            except Exception as e:
                raise FlipperMountError(f"toggle failed: {e}") from e

    def all_up(self) -> None:
        self.write_levels([True] * self._n)

    def all_down(self) -> None:
        self.write_levels([False] * self._n)

    def sync_all_up(self, pulse_low_ms: float = 15.0, pulse_high_ms: float = 15.0) -> None:
        """
        For each line, pulse that line low then high while holding other lines
        at their current commanded values, ending with all lines high.

        Ensures each line sees a rising edge even if it was already high.
        """
        low_s = pulse_low_ms / 1000.0
        high_s = pulse_high_ms / 1000.0
        with self._lock:
            if self._task is None:
                raise FlipperMountError("Not connected")
            try:
                for i in range(self._n):
                    bits = list(self._levels)
                    bits[i] = False
                    self._write_do(bits)
                    self._levels = bits
                    time.sleep(low_s)
                    bits = list(self._levels)
                    bits[i] = True
                    self._write_do(bits)
                    self._levels = bits
                    time.sleep(high_s)
            except Exception as e:
                raise FlipperMountError(f"sync_all_up failed: {e}") from e
