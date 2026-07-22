"""Low-level TCP client for Single Quantum WebSQ (Atlas driver)."""

from __future__ import annotations

import json
import logging
import socket
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ETB = b"\x17"


def check_tcp(host: str, port: int, timeout: float = 3.0) -> bool:
    """Return True if a TCP connection to host:port succeeds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError as exc:
        logger.debug("TCP check failed %s:%s: %s", host, port, exc)
        return False


def websq_request(
    host: str,
    port: int,
    payload: Dict[str, Any],
    timeout: float = 5.0,
) -> List[Dict[str, Any]]:
    """
    Send one JSON request on the WebSQ control port; read until ETB.

    Returns a list of parsed JSON objects (usually one).
    """
    msg = (json.dumps(payload) + "\n").encode("utf-8")
    data = b""
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(msg)
        while ETB not in data:
            chunk = sock.recv(65536)
            if not chunk:
                break
            data += chunk

    replies: List[Dict[str, Any]] = []
    for part in data.split(ETB):
        part = part.strip()
        if not part:
            continue
        replies.append(json.loads(part.decode("utf-8")))
    return replies


def parse_counts_line(line: str, detector_index: int = 0) -> float:
    """
    Parse a counts stream line: unix_timestamp,ch1,ch2,...

    Returns the count for detector_index (0-based).
    """
    line = line.strip()
    if not line:
        raise ValueError("empty counts line")
    parts = line.split(",")
    if len(parts) < 2:
        raise ValueError(f"invalid counts line: {line!r}")
    counts = [float(x) for x in parts[1:]]
    if detector_index < 0 or detector_index >= len(counts):
        raise IndexError(
            f"detector_index {detector_index} out of range "
            f"(channel count {len(counts)})"
        )
    return counts[detector_index]


class CountsStream:
    """Persistent TCP reader for WebSQ port 12345 (newline-delimited counts)."""

    def __init__(
        self,
        host: str,
        port: int = 12345,
        connect_timeout: float = 10.0,
        read_timeout: float = 30.0,
    ) -> None:
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self._sock: Optional[socket.socket] = None
        self._buf = b""

    def connect(self) -> None:
        if self._sock is not None:
            return
        self._sock = socket.create_connection(
            (self.host, self.port),
            timeout=self.connect_timeout,
        )
        self._sock.settimeout(self.read_timeout)
        self._buf = b""
        logger.debug("CountsStream connected to %s:%s", self.host, self.port)

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError as exc:
                logger.debug("CountsStream close: %s", exc)
            self._sock = None
        self._buf = b""

    @property
    def connected(self) -> bool:
        return self._sock is not None

    def read_line(self) -> str:
        """Block until one complete line (without trailing newline) is received."""
        if self._sock is None:
            raise ConnectionError(
                f"CountsStream not connected to {self.host}:{self.port}"
            )
        while b"\n" not in self._buf:
            try:
                chunk = self._sock.recv(4096)
            except socket.timeout as exc:
                raise TimeoutError(
                    f"timeout waiting for counts line from {self.host}:{self.port}"
                ) from exc
            if not chunk:
                raise ConnectionError(
                    f"counts stream closed by {self.host}:{self.port}"
                )
            self._buf += chunk
        line_bytes, self._buf = self._buf.split(b"\n", 1)
        return line_bytes.decode("utf-8", errors="replace").strip()
