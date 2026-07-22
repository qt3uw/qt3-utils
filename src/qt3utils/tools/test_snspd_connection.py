"""
Connectivity test for Single Quantum WebSQ (Atlas driver) over lab LAN.

Run before using qt3scan/qt3scope with signal_source: snspd::

    python -m qt3utils.tools.test_snspd_connection --host 10.0.0.50
    qt3test-snspd --host 10.0.0.50
"""

from __future__ import annotations

import argparse
import logging
import sys

from qt3utils.hardware.singlequantum.websq_client import (
    CountsStream,
    check_tcp,
    parse_counts_line,
    websq_request,
)
from qt3utils.hardware.singlequantum.websq_timed_counter import WebSqTimedCounter

logger = logging.getLogger(__name__)

DEFAULT_COUNTS_PORT = 12345
DEFAULT_CONTROL_PORT = 12000


def _step(name: str) -> None:
    print(f"\n--- {name} ---")


def _fail(msg: str, code: int = 1) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(code)


def _ok(msg: str) -> None:
    print(f"OK: {msg}")


def run_tests(
    host: str,
    detector_index: int,
    counts_port: int,
    control_port: int,
    n_lines: int,
    dwell: float | None,
    connect_timeout: float,
) -> None:
    print(f"WebSQ connectivity test -> {host}")
    print(
        "Prerequisite: Atlas on lab LAN with static IP; ports 12345/12000 open; "
        "detectors enabled in WebSQ if you expect non-zero counts."
    )

    _step("TCP port 12000 (control)")
    if not check_tcp(host, control_port, timeout=connect_timeout):
        _fail(f"cannot connect to {host}:{control_port}")
    _ok(f"TCP {host}:{control_port}")

    _step("TCP port 12345 (counts)")
    if not check_tcp(host, counts_port, timeout=connect_timeout):
        _fail(f"cannot connect to {host}:{counts_port}")
    _ok(f"TCP {host}:{counts_port}")

    _step("JSON pong")
    try:
        replies = websq_request(
            host, control_port, {"request": "pong"}, timeout=connect_timeout
        )
    except OSError as exc:
        _fail(f"pong request: {exc}")
    if not replies:
        _fail("pong returned no JSON")
    _ok(f"pong -> {replies}")

    _step("NumberOfDetectors")
    try:
        replies = websq_request(
            host,
            control_port,
            {"request": "NumberOfDetectors"},
            timeout=connect_timeout,
        )
    except OSError as exc:
        _fail(f"NumberOfDetectors: {exc}")
    _ok(f"NumberOfDetectors -> {replies}")

    _step("SoftwareVersion")
    try:
        replies = websq_request(
            host,
            control_port,
            {"request": "SoftwareVersion"},
            timeout=connect_timeout,
        )
    except OSError as exc:
        _fail(f"SoftwareVersion: {exc}")
    _ok(f"SoftwareVersion -> {replies}")

    _step(f"Counts stream ({n_lines} lines, detector {detector_index})")
    stream = CountsStream(
        host,
        port=counts_port,
        connect_timeout=connect_timeout,
        read_timeout=connect_timeout * 3,
    )
    try:
        stream.connect()
        for i in range(n_lines):
            line = stream.read_line()
            try:
                value = parse_counts_line(line, detector_index)
            except (ValueError, IndexError) as exc:
                print(f"  line {i}: parse error {exc}: {line[:120]!r}")
                continue
            print(f"  line {i}: ch{detector_index}={value}  ({line[:80]}...)")
    except (OSError, TimeoutError) as exc:
        _fail(f"counts stream: {exc}")
    finally:
        stream.close()
    _ok("counts stream")

    if dwell is not None:
        _step(f"Dwell integration ({dwell} s) via WebSqTimedCounter")
        counter = WebSqTimedCounter(
            host=host,
            counts_port=counts_port,
            control_port=control_port,
            detector_index=detector_index,
            connect_timeout=connect_timeout,
            read_timeout=connect_timeout * 3,
            auto_sync_period=True,
            auto_enable_detectors=False,
        )
        try:
            counter.start()
            counter.configure_sample_time(dwell)
            value = counter.sample_batch_counts()
            rate = value / dwell if dwell > 0 else 0.0
            print(f"  raw counts in {dwell}s: {value}")
            print(f"  rate (cts/s): {rate}")
        except (OSError, ConnectionError, TimeoutError) as exc:
            _fail(f"dwell read: {exc}")
        finally:
            counter.stop()
        _ok("dwell integration")

    print("\n=== All tests passed ===")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Test Ethernet connectivity to Single Quantum WebSQ (Atlas)."
    )
    parser.add_argument(
        "--host",
        required=True,
        help="Atlas driver static IP on lab LAN (Option B)",
    )
    parser.add_argument(
        "--detector-index",
        type=int,
        default=0,
        help="0-based detector channel (default 0)",
    )
    parser.add_argument(
        "--counts-port",
        type=int,
        default=DEFAULT_COUNTS_PORT,
    )
    parser.add_argument(
        "--control-port",
        type=int,
        default=DEFAULT_CONTROL_PORT,
    )
    parser.add_argument(
        "--lines",
        type=int,
        default=10,
        help="Number of counts lines to print (default 10)",
    )
    parser.add_argument(
        "--dwell",
        type=float,
        default=None,
        help="Optional dwell in seconds for one WebSqTimedCounter sample",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="TCP/connect timeout in seconds (default 5)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    run_tests(
        host=args.host,
        detector_index=args.detector_index,
        counts_port=args.counts_port,
        control_port=args.control_port,
        n_lines=args.lines,
        dwell=args.dwell,
        connect_timeout=args.timeout,
    )


if __name__ == "__main__":
    main()
