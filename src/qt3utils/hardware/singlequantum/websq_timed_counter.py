"""
WebSQ timed counter for qt3scan / qt3scope.

Reads photon counts from Single Quantum Atlas driver port 12345 and optionally
syncs integration time via JSON on port 12000. Implements the same method names
as NidaqTimedRateCounter / NidaqTimedAnalogMean.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from qt3utils.hardware.singlequantum.websq_client import (
    CountsStream,
    parse_counts_line,
    websq_request,
)

logger = logging.getLogger(__name__)


class WebSqTimedCounter:
    """
  Timed batch acquisition from WebSQ over Ethernet.

  Attributes
  ----------
  host : str
      Atlas driver IP on the lab LAN.
  counts_port : int
      TCP port for counts stream (default 12345).
  control_port : int
      TCP port for JSON control (default 12000).
  detector_index : int
      0-based detector channel to read from each line.
  sample_time_in_seconds : float
      Integration window; synced to WebSQ when auto_sync_period is True.
  """

    def __init__(
        self,
        host: str = "192.168.1.1",
        counts_port: int = 12345,
        control_port: int = 12000,
        detector_index: int = 0,
        connect_timeout: float = 10.0,
        read_timeout: float = 30.0,
        auto_sync_period: bool = True,
        auto_enable_detectors: bool = False,
    ) -> None:
        self.host = host
        self.counts_port = counts_port
        self.control_port = control_port
        self.detector_index = detector_index
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.auto_sync_period = auto_sync_period
        self.auto_enable_detectors = auto_enable_detectors

        self.sample_time_in_seconds = 1.0
        self.running = False
        self.read_lock = False
        self._stream: Optional[CountsStream] = None

    def configure(self, config_dict: dict) -> None:
        self.host = config_dict.get("host", self.host)
        self.counts_port = int(config_dict.get("counts_port", self.counts_port))
        self.control_port = int(config_dict.get("control_port", self.control_port))
        self.detector_index = int(
            config_dict.get("detector_index", self.detector_index)
        )
        self.connect_timeout = float(
            config_dict.get("connect_timeout", self.connect_timeout)
        )
        self.read_timeout = float(config_dict.get("read_timeout", self.read_timeout))
        self.auto_sync_period = bool(
            config_dict.get("auto_sync_period", self.auto_sync_period)
        )
        self.auto_enable_detectors = bool(
            config_dict.get("auto_enable_detectors", self.auto_enable_detectors)
        )
        self.sample_time_in_seconds = float(
            config_dict.get("sample_time_in_seconds", self.sample_time_in_seconds)
        )

    def _sync_measurement_period(self) -> None:
        period_ms = max(1, int(round(self.sample_time_in_seconds * 1000)))
        payload = {
            "command": "SetMeasurementPeriod",
            "value": period_ms,
            "label": "InptMeasurementPeriod",
        }
        try:
            replies = websq_request(
                self.host,
                self.control_port,
                payload,
                timeout=self.connect_timeout,
            )
            logger.debug(
                "SetMeasurementPeriod %s ms -> %s", period_ms, replies
            )
        except OSError as exc:
            raise ConnectionError(
                f"failed SetMeasurementPeriod on {self.host}:{self.control_port}: {exc}"
            ) from exc

    def _enable_detectors(self) -> None:
        payload = {
            "command": "DetectorEnable",
            "label": "DetectorEnable",
            "value": True,
        }
        try:
            replies = websq_request(
                self.host,
                self.control_port,
                payload,
                timeout=self.connect_timeout,
            )
            logger.info("DetectorEnable on %s -> %s", self.host, replies)
        except OSError as exc:
            raise ConnectionError(
                f"failed DetectorEnable on {self.host}:{self.control_port}: {exc}"
            ) from exc

    def start(self) -> None:
        if self.running:
            self.stop()
        self._stream = CountsStream(
            self.host,
            port=self.counts_port,
            connect_timeout=self.connect_timeout,
            read_timeout=self.read_timeout,
        )
        try:
            self._stream.connect()
        except OSError as exc:
            self._stream = None
            raise ConnectionError(
                f"cannot connect counts stream to {self.host}:{self.counts_port}: {exc}"
            ) from exc

        if self.auto_enable_detectors:
            self._enable_detectors()
        if self.auto_sync_period:
            self._sync_measurement_period()

        self.running = True

    def stop(self) -> None:
        if self.running:
            while self.read_lock:
                time.sleep(0.05)
        if self._stream is not None:
            self._stream.close()
            self._stream = None
        self.running = False

    def configure_sample_time(self, sample_time: float) -> None:
        self.sample_time_in_seconds = sample_time
        if self.running and self.auto_sync_period:
            self._sync_measurement_period()

    def _read_one_count(self) -> float:
        if not self.running or self._stream is None:
            return 0.0
        try:
            self.read_lock = True
            line = self._stream.read_line()
            return parse_counts_line(line, self.detector_index)
        finally:
            self.read_lock = False

    def sample_batch_counts(self) -> float:
        if not self.running:
            return 0.0
        return self._read_one_count()

    def sample_nbatches_counts(
        self, n_batches: int = 1, sum_counts: bool = True
    ) -> np.ndarray:
        totals: list[float] = []
        for _ in range(n_batches):
            totals.append(self._read_one_count())
        arr = np.asarray(totals, dtype=np.float64)
        if sum_counts:
            return np.array([float(np.sum(arr))], dtype=np.float64)
        return arr
