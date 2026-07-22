"""Tkinter control panel for Newport-style TTL flipper mounts on NI-DAQ digital outputs."""
from __future__ import annotations

import argparse
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Dict, List, Optional

from qt3utils.applications.qt3mirror.config import (
    N_FLIPPERS,
    FlipperPreset,
    Qt3MirrorConfig,
    load_flipper_config,
)
from qt3utils.hardware.nidaq.digitaloutputs import FlipperMountController, FlipperMountError

DAQ_DEVICE = "Dev1"
# Minimum delay after each DAQ command before the UI accepts another (debounce / move time).
SETTLE_MS_AFTER_COMMAND = 500


class FlipperMirrorApp:
    def __init__(self, root: tk.Tk, app_config: Qt3MirrorConfig) -> None:
        self.root = root
        self._app_cfg = app_config
        root.title("Qt3 Mirror — Flipper DAQ")
        root.resizable(False, False)
        self._controller: Optional[FlipperMountController] = None
        self._n_lines: int = N_FLIPPERS
        self._busy = False

        self._status_var = tk.StringVar(value="Disconnected.")
        self._flipper_state_vars: List[tk.StringVar] = []

        self._build()
        root.protocol("WM_DELETE_WINDOW", self._on_quit)

    def _build(self) -> None:
        pad = {"padx": 8, "pady": 4}
        outer = ttk.Frame(self.root, padding="10")
        outer.grid(row=0, column=0, sticky="nsew")

        conn = ttk.LabelFrame(outer, text="DAQ connection", padding="8")
        conn.grid(row=0, column=0, sticky="ew", **pad)

        btn_row = ttk.Frame(conn)
        btn_row.grid(row=0, column=0, sticky="ew")
        self._connect_btn = ttk.Button(btn_row, text="Connect", command=self._connect)
        self._connect_btn.pack(side=tk.LEFT, padx=(0, 6))
        self._disconnect_btn = ttk.Button(
            btn_row, text="Disconnect", command=self._disconnect, state=tk.DISABLED
        )
        self._disconnect_btn.pack(side=tk.LEFT, padx=(0, 6))
        self._sync_btn = ttk.Button(
            btn_row,
            text="Initialize (sync to UP)",
            command=self._sync_all_up,
            state=tk.DISABLED,
        )
        self._sync_btn.pack(side=tk.LEFT)

        ctrl = ttk.LabelFrame(
            outer, text="Flippers (open-loop — no position readback)", padding="8"
        )
        ctrl.grid(row=1, column=0, sticky="ew", **pad)

        bulk = ttk.Frame(ctrl)
        bulk.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        self._all_up_btn = ttk.Button(
            bulk, text="All up", command=self._all_up, state=tk.DISABLED
        )
        self._all_up_btn.pack(side=tk.LEFT, padx=(0, 6))
        self._all_down_btn = ttk.Button(
            bulk, text="All down", command=self._all_down, state=tk.DISABLED
        )
        self._all_down_btn.pack(side=tk.LEFT)

        self._toggle_btns: List[ttk.Button] = []
        for i in range(N_FLIPPERS):
            sv = tk.StringVar(value="—")
            self._flipper_state_vars.append(sv)
            row = 1 + i
            name = self._app_cfg.flipper_names[i]
            ttk.Label(ctrl, text=name).grid(row=row, column=0, sticky="w", pady=2)
            ttk.Label(ctrl, textvariable=sv, width=14).grid(
                row=row, column=1, sticky="w", padx=(8, 8), pady=2
            )
            b = ttk.Button(
                ctrl,
                text="Toggle",
                command=lambda idx=i: self._toggle(idx),
                state=tk.DISABLED,
            )
            b.grid(row=row, column=2, sticky="e", pady=2)
            self._toggle_btns.append(b)

        presets = ttk.LabelFrame(outer, text="Presets", padding="8")
        presets.grid(row=2, column=0, sticky="ew", **pad)
        self._preset_btns: List[ttk.Button] = []
        for pr in self._app_cfg.presets:
            b = ttk.Button(
                presets,
                text=pr.label,
                command=lambda p=pr: self._apply_preset(p),
                state=tk.DISABLED,
            )
            b.pack(anchor="w", pady=2)
            self._preset_btns.append(b)

        status = ttk.Label(outer, textvariable=self._status_var, wraplength=420)
        status.grid(row=3, column=0, sticky="ew", **pad)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._update_widget_states()

    def _update_widget_states(self) -> None:
        c = self._controller is not None and self._controller.connected
        busy = self._busy
        self._connect_btn.configure(state=tk.DISABLED if busy or c else tk.NORMAL)
        self._disconnect_btn.configure(state=tk.DISABLED if busy or not c else tk.NORMAL)
        bulk_state = tk.DISABLED if busy or not c else tk.NORMAL
        self._sync_btn.configure(state=bulk_state)
        self._all_up_btn.configure(state=bulk_state)
        self._all_down_btn.configure(state=bulk_state)
        for i, b in enumerate(self._toggle_btns):
            if busy or not c or i >= self._n_lines:
                b.configure(state=tk.DISABLED)
            else:
                b.configure(state=tk.NORMAL)
        for b in self._preset_btns:
            b.configure(state=bulk_state)

    def _refresh_flipper_labels(self) -> None:
        if not self._controller or not self._controller.connected:
            for sv in self._flipper_state_vars:
                sv.set("—")
            return
        levels = self._controller.levels
        for i, sv in enumerate(self._flipper_state_vars):
            if i >= self._n_lines:
                sv.set("n/a")
            elif i < len(levels):
                sv.set("UP (high)" if levels[i] else "DOWN (low)")
            else:
                sv.set("—")

    def _refresh_status(self) -> None:
        if self._controller and self._controller.connected:
            self._status_var.set(f"Connected: {self._controller.channel_string}")
        else:
            self._status_var.set("Disconnected.")

    def _connect(self) -> None:
        if self._busy:
            return

        self._set_busy(True)

        def work() -> None:
            err: Optional[BaseException] = None
            ctrl: Optional[FlipperMountController] = None
            try:
                ctrl = FlipperMountController(
                    DAQ_DEVICE,
                    line_channels=self._app_cfg.flipper_lines,
                )
                ctrl.connect()
            except FlipperMountError as e:
                err = e
            except Exception as e:
                err = e

            def apply() -> None:
                self._set_busy(False)
                if err is not None:
                    messagebox.showerror("Flipper DAQ", str(err))
                    self._controller = None
                else:
                    self._controller = ctrl
                    self._n_lines = N_FLIPPERS
                self._refresh_flipper_labels()
                self._refresh_status()
                self._update_widget_states()

            self.root.after(0, apply)

        threading.Thread(target=work, daemon=True).start()

    def _disconnect(self) -> None:
        if self._controller is not None:
            try:
                self._controller.close()
            except Exception:
                pass
            self._controller = None
        self._refresh_flipper_labels()
        self._refresh_status()
        self._update_widget_states()

    def _on_quit(self) -> None:
        self._disconnect()
        self.root.destroy()

    def _daq_call(self, op: Callable[[], None]) -> None:
        if self._busy or self._controller is None:
            return
        self._set_busy(True)

        def work() -> None:
            err: Optional[BaseException] = None
            try:
                op()
            except FlipperMountError as e:
                err = e
            except Exception as e:
                err = e
            time.sleep(SETTLE_MS_AFTER_COMMAND / 1000.0)

            def finish() -> None:
                self._refresh_flipper_labels()
                self._set_busy(False)
                if err is not None:
                    messagebox.showerror("Flipper DAQ", str(err))
                self._update_widget_states()

            self.root.after(0, finish)

        threading.Thread(target=work, daemon=True).start()

    def _sync_all_up(self) -> None:
        if self._controller is None:
            return
        low = self._app_cfg.sync_pulse_low_ms
        high = self._app_cfg.sync_pulse_high_ms
        self._daq_call(lambda: self._controller.sync_all_up(low, high))

    def _all_up(self) -> None:
        if self._controller is None:
            return
        self._daq_call(self._controller.all_up)

    def _all_down(self) -> None:
        if self._controller is None:
            return
        self._daq_call(self._controller.all_down)

    def _toggle(self, index: int) -> None:
        if self._controller is None:
            return
        self._daq_call(lambda: self._controller.toggle(index))

    def _apply_preset(self, preset: FlipperPreset) -> None:
        if self._controller is None:
            return
        updates: Dict[int, bool] = preset.targets_dict()
        self._daq_call(lambda: self._controller.apply_partial(updates))


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Qt3 Mirror — flipper DAQ control (tkinter).")
    p.add_argument(
        "--config",
        metavar="PATH",
        help="YAML flipper config (default: bundled qt3mirror_base.yaml)",
    )
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = _parse_args(argv)
    try:
        cfg = load_flipper_config(args.config)
    except Exception as e:
        print(f"qt3mirror: failed to load config: {e}", file=sys.stderr)
        sys.exit(1)

    root = tk.Tk()
    btn_font = ("Segoe UI", 9) if sys.platform == "win32" else ("TkDefaultFont", 9)
    root.option_add("*TButton*Font", btn_font)
    root.option_add("*TLabel*Font", btn_font)
    FlipperMirrorApp(root, cfg)
    root.mainloop()


if __name__ == "__main__":
    main()
