"""
Scan NI-DAQ static digital outputs (USB-6343 layout) except ``port1/line0``.

Tests each line in isolation: connect, DOWN, UP, two toggles, disconnect.
Use with a scope on one BNC at a time to find which ``port``/``line`` toggles PFI *n*.

Default: all lines on port0 (0–15), port1 (1–7), port2 (0–7) — 31 channels, skipping
``port1/line0`` (PFI 0).

Run::

    python -m qt3utils.applications.qt3mirror.test_flipper_connection
    qt3test-flipper

Single line (legacy)::

    qt3test-flipper --port port1 --line 4
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from typing import Iterator, List, Optional, Sequence

from qt3utils.hardware.nidaq.digitaloutputs import FlipperMountController, FlipperMountError

DEFAULT_DEVICE = "Dev1"
DEFAULT_SETTLE_S = 0.5

# USB-6343: 16 lines on port0 (37-pin D), 8 per port on BNC port1/port2.
PORT0_LINE_COUNT = 16
PORT1_LINE_COUNT = 8
PORT2_LINE_COUNT = 8

EXCLUDE_PORT = "port1"
EXCLUDE_LINE = 0


@dataclass(frozen=True)
class LineTarget:
    port: str
    line: int

    @property
    def spec(self) -> str:
        return f"{self.port}/line{self.line}"


def iter_all_digital_lines(
    *,
    include_port0: bool = True,
    include_port1: bool = True,
    include_port2: bool = True,
    exclude_port: str = EXCLUDE_PORT,
    exclude_line: int = EXCLUDE_LINE,
) -> Iterator[LineTarget]:
    """Every static DO line in the USB-6343 layout, except one excluded (default port1/line0)."""
    exclude_port_n = exclude_port.strip().strip("/")

    def skip(port: str, line: int) -> bool:
        return port == exclude_port_n and line == exclude_line

    if include_port0:
        for line in range(PORT0_LINE_COUNT):
            port = "port0"
            if not skip(port, line):
                yield LineTarget(port, line)
    if include_port1:
        for line in range(PORT1_LINE_COUNT):
            port = "port1"
            if not skip(port, line):
                yield LineTarget(port, line)
    if include_port2:
        for line in range(PORT2_LINE_COUNT):
            port = "port2"
            if not skip(port, line):
                yield LineTarget(port, line)


def _step(name: str) -> None:
    print(f"\n--- {name} ---")


def _ok(msg: str) -> None:
    print(f"OK: {msg}")


@dataclass
class LineResult:
    target: LineTarget
    passed: bool
    error: Optional[str] = None


def test_single_line(
    device: str,
    target: LineTarget,
    settle_s: float,
    *,
    verbose: bool = True,
) -> LineResult:
    """Exercise one digital output line; return pass/fail without raising."""
    line_channel = target.spec
    label = f"{device}/{line_channel}"

    if verbose:
        _step(label)

    ctrl = FlipperMountController(device, line_channels=[line_channel])
    expected = f"{device}/{line_channel}"

    try:
        if ctrl.channel_string != expected:
            return LineResult(target, False, f"channel mismatch: {ctrl.channel_string!r}")

        ctrl.connect()
        if not ctrl.connected:
            return LineResult(target, False, "connect did not set connected")

        if len(ctrl.levels) != 1:
            return LineResult(target, False, f"expected 1 level, got {ctrl.levels!r}")

        def write_and_check(value: bool, step: str) -> Optional[str]:
            try:
                ctrl.write_levels([value])
            except FlipperMountError as exc:
                return f"{step}: {exc}"
            time.sleep(settle_s)
            if ctrl.levels[0] is not value:
                return f"{step}: wrote {value}, levels={ctrl.levels!r}"
            return None

        err = write_and_check(False, "DOWN")
        if err:
            return LineResult(target, False, err)

        err = write_and_check(True, "UP")
        if err:
            return LineResult(target, False, err)

        before = ctrl.levels[0]
        try:
            ctrl.toggle(0)
        except FlipperMountError as exc:
            return LineResult(target, False, f"toggle 1: {exc}")
        time.sleep(settle_s)
        after = ctrl.levels[0]
        if after is before:
            return LineResult(target, False, f"toggle 1: no change ({before} -> {after})")

        before = ctrl.levels[0]
        try:
            ctrl.toggle(0)
        except FlipperMountError as exc:
            return LineResult(target, False, f"toggle 2: {exc}")
        time.sleep(settle_s)
        after = ctrl.levels[0]
        if after is before:
            return LineResult(target, False, f"toggle 2: no change ({before} -> {after})")

        return LineResult(target, True)

    except FlipperMountError as exc:
        return LineResult(target, False, str(exc))
    except Exception as exc:
        return LineResult(target, False, f"{type(exc).__name__}: {exc}")
    finally:
        try:
            ctrl.close()
        except Exception:
            pass


def run_scan(
    device: str,
    targets: Sequence[LineTarget],
    settle_s: float,
    *,
    stop_on_first_fail: bool = False,
) -> int:
    """Test each line; print summary. Return 0 if all pass, else 1."""
    n = len(targets)
    print(f"Flipper DAQ scan -> {device}")
    print(f"Testing {n} digital output lines (excludes {EXCLUDE_PORT}/line{EXCLUDE_LINE}).")
    print("Scope one BNC at a time to match a passing line to a physical connector.\n")

    results: List[LineResult] = []
    for i, target in enumerate(targets, start=1):
        print(f"[{i}/{n}] {device}/{target.spec}", flush=True)
        result = test_single_line(device, target, settle_s, verbose=False)
        results.append(result)
        if result.passed:
            print("  PASS")
        else:
            print(f"  FAIL: {result.error}")
            if stop_on_first_fail:
                break

    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]

    print("\n=== Summary ===")
    print(f"Passed: {len(passed)}/{len(results)}")
    if passed:
        print("  " + ", ".join(r.target.spec for r in passed))
    if failed:
        print(f"Failed: {len(failed)}/{len(results)}")
        for r in failed:
            print(f"  {r.target.spec}: {r.error}")
        print(
            "\nDAQmx failures often mean the line is not a valid static DO "
            "(or is in use). Scope lines that passed to find your BNC."
        )
        return 1

    print("\n=== All lines passed (software); verify motion on scope per BNC ===")
    return 0


def run_single(
    device: str,
    port: str,
    line: int,
    settle_s: float,
) -> None:
    """Single-line test; exit 1 on failure (original behavior)."""
    target = LineTarget(port.strip().strip("/"), line)
    print(f"Flipper DAQ test -> {device}/{target.spec}")
    result = test_single_line(device, target, settle_s, verbose=True)
    if result.passed:
        print("\n=== All tests passed ===")
        return
    print(f"\nFAIL: {result.error}", file=sys.stderr)
    sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Test NI-DAQ digital outputs: scan all port0/port1/port2 lines "
            f"except {EXCLUDE_PORT}/line{EXCLUDE_LINE}, or one line with --port/--line."
        )
    )
    parser.add_argument(
        "--device",
        default=DEFAULT_DEVICE,
        help=f"NI-DAQmx device name (default {DEFAULT_DEVICE})",
    )
    parser.add_argument(
        "--port",
        default=None,
        help="Single-line mode: port (e.g. port1). Omit to scan all lines.",
    )
    parser.add_argument(
        "--line",
        type=int,
        default=None,
        help="Single-line mode: line 0–7 (port0: 0–15). Requires --port.",
    )
    parser.add_argument(
        "--settle",
        type=float,
        default=DEFAULT_SETTLE_S,
        help=f"Seconds after each command (default {DEFAULT_SETTLE_S})",
    )
    parser.add_argument(
        "--no-port0",
        action="store_true",
        help="Skip port0 (37-pin D connector); only test BNC port1/port2.",
    )
    parser.add_argument(
        "--stop-on-fail",
        action="store_true",
        help="Stop scan after the first failing line.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print channels that would be tested and exit.",
    )
    args = parser.parse_args(argv)

    if args.settle < 0:
        parser.error("--settle must be >= 0")

    device = args.device.strip()
    single_mode = args.port is not None or args.line is not None

    if single_mode:
        if args.port is None or args.line is None:
            parser.error("Single-line mode requires both --port and --line")
        port = args.port.strip().strip("/")
        line = args.line
        if port == "port0":
            if line < 0 or line >= PORT0_LINE_COUNT:
                parser.error(f"--line must be 0–{PORT0_LINE_COUNT - 1} for port0")
        else:
            if line < 0 or line > 7:
                parser.error("--line must be 0–7 for port1/port2")
        if port == EXCLUDE_PORT and line == EXCLUDE_LINE:
            parser.error(f"{EXCLUDE_PORT}/line{EXCLUDE_LINE} is excluded from scans")
        run_single(device, port, line, args.settle)
        return

    targets = list(
        iter_all_digital_lines(
            include_port0=not args.no_port0,
            include_port1=True,
            include_port2=True,
        )
    )

    if args.list:
        for t in targets:
            print(f"{device}/{t.spec}")
        print(f"\n{len(targets)} lines (excludes {device}/{EXCLUDE_PORT}/line{EXCLUDE_LINE})")
        return

    sys.exit(
        run_scan(
            device,
            targets,
            args.settle,
            stop_on_first_fail=args.stop_on_fail,
        )
    )


if __name__ == "__main__":
    main()
