import tkinter as tk
from tkinter import messagebox
import time
from typing import Dict, Optional, Tuple

import nidaqmx

from qt3utils.applications.qt3_daq_busy_marker import santec_daq_busy

_STALE_LOCK_TOOLTIP = (
    "Only use this when qt3santec is not scanning but the busy marker was left behind "
    "(e.g. after a crash or force-close). Do not enable during an active Santec sweep—"
    "both apps may touch the same DAQ channels and cause errors."
)


def _attach_tooltip(widget: tk.Widget, text: str) -> None:
    """Show text in a borderless Toplevel while the pointer is over widget."""
    tip_window: Dict[str, Optional[tk.Toplevel]] = {"w": None}

    def on_enter(_event: object) -> None:
        if tip_window["w"] is not None:
            return
        x = widget.winfo_rootx() + 20
        y = widget.winfo_rooty() + widget.winfo_height() + 2
        tw = tk.Toplevel(widget)
        tip_window["w"] = tw
        tw.wm_overrideredirect(True)
        tw.attributes("-topmost", True)
        tw.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(
            tw,
            text=text,
            justify="left",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=4,
            font=("Arial", 9),
        )
        lbl.pack()

    def on_leave(_event: object) -> None:
        tw = tip_window["w"]
        tip_window["w"] = None
        if tw is not None:
            tw.destroy()

    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)


class PhotodetectorController:
    """Minimal controller for reading voltage from two photodetectors via NI DAQ."""

    def __init__(
        self,
        device_name: str = "Dev1",
        channel1: str = "ai2",
        channel2: str = "ai0",
        min_voltage: float = -10.0,
        max_voltage: float = 10.0,
    ) -> None:
        """
        Initialize photodetector controller.

        Args:
            device_name: NI DAQ device name (e.g., 'Dev1').
            channel1: Analog input channel for first detector (PDA50B2).
            channel2: Analog input channel for second detector (PDA100A2).
            min_voltage: Minimum expected voltage.
            max_voltage: Maximum expected voltage.
        """
        self.device_name = device_name
        self.channel1 = channel1
        self.channel2 = channel2
        self.min_voltage = min_voltage
        self.max_voltage = max_voltage

    def read_both_detectors(self) -> Tuple[float, float]:
        """
        Read voltage from both detectors simultaneously.

        Returns:
            (voltage1, voltage2) in volts.

        Raises:
            RuntimeError: If there is an error talking to the DAQ.
        """
        try:
            with nidaqmx.Task() as task:
                task.ai_channels.add_ai_voltage_chan(
                    f"{self.device_name}/{self.channel1}",
                    min_val=self.min_voltage,
                    max_val=self.max_voltage,
                )
                task.ai_channels.add_ai_voltage_chan(
                    f"{self.device_name}/{self.channel2}",
                    min_val=self.min_voltage,
                    max_val=self.max_voltage,
                )
                data = task.read(number_of_samples_per_channel=1)

            if isinstance(data, (list, tuple)) and len(data) >= 2:
                v1_raw = data[0]
                v2_raw = data[1]
                v1 = float(v1_raw[0] if hasattr(v1_raw, "__getitem__") else v1_raw)
                v2 = float(v2_raw[0] if hasattr(v2_raw, "__getitem__") else v2_raw)
                return v1, v2

            raise RuntimeError(f"Unexpected data format from DAQ: {type(data)}")
        except Exception as e:
            raise RuntimeError(f"Error reading detectors: {e}")


class PowerMonitorApp:
    """
    Simple GUI that shows power in MW for two photodetectors read via NI DAQ.

    The conversion is based on a fixed calibration:
        power_MW = voltage_V / 7.0
    assuming the photodetector gain is fixed and never changed.
    """

    VOLT_TO_MW_FACTOR = 7.0  # V : MW (e.g., 0.7 V -> 0.1 MW)

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("QT3 Power Monitor")
        self.root.minsize(500, 250)

        self.detector_ctrl: Optional[PhotodetectorController] = None
        self.running = False
        self.update_interval_ms = 200  # ~5 Hz polling
        self.var_ignore_santec_lock = tk.BooleanVar(value=False)

        self._build_gui()

    def _build_gui(self) -> None:
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # DAQ configuration
        cfg_frame = tk.LabelFrame(main_frame, text="DAQ Configuration")
        cfg_frame.pack(fill="x", pady=5)

        tk.Label(cfg_frame, text="DAQ Device:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.ent_device = tk.Entry(cfg_frame, width=12)
        self.ent_device.grid(row=0, column=1, padx=5, pady=5)
        self.ent_device.insert(0, "Dev1")

        tk.Label(cfg_frame, text="PDA50B2 Channel:").grid(row=0, column=2, sticky="e", padx=5, pady=5)
        self.ent_ch1 = tk.Entry(cfg_frame, width=10)
        self.ent_ch1.grid(row=0, column=3, padx=5, pady=5)
        self.ent_ch1.insert(0, "ai2")

        tk.Label(cfg_frame, text="PDA100A2 Channel:").grid(row=0, column=4, sticky="e", padx=5, pady=5)
        self.ent_ch2 = tk.Entry(cfg_frame, width=10)
        self.ent_ch2.grid(row=0, column=5, padx=5, pady=5)
        self.ent_ch2.insert(0, "ai0")

        self.btn_init = tk.Button(
            cfg_frame,
            text="Initialize DAQ",
            command=self.init_daq,
            bg="#dddddd",
        )
        self.btn_init.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="w")

        self.lbl_status = tk.Label(cfg_frame, text="DAQ: Not initialized", fg="red")
        self.lbl_status.grid(row=1, column=2, columnspan=4, padx=5, pady=5, sticky="w")

        for child in cfg_frame.winfo_children():
            child.grid_configure(padx=3, pady=3)

        # Power display
        display_frame = tk.LabelFrame(main_frame, text="Photodetector Power")
        display_frame.pack(fill="both", expand=True, pady=10)

        # PDA50B2
        tk.Label(display_frame, text="PDA50B2 Power (MW):", font=("Arial", 11, "bold")).grid(
            row=0,
            column=0,
            sticky="e",
            padx=5,
            pady=5,
        )
        self.lbl_pda50b2_power = tk.Label(
            display_frame,
            text="--",
            font=("Arial", 18, "bold"),
            fg="#0044aa",
        )
        self.lbl_pda50b2_power.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        tk.Label(display_frame, text="Voltage (V):").grid(
            row=1,
            column=0,
            sticky="e",
            padx=5,
            pady=2,
        )
        self.lbl_pda50b2_voltage = tk.Label(display_frame, text="--",font=("Arial", 40, "bold"))
        self.lbl_pda50b2_voltage.grid(row=1, column=1, sticky="w", padx=5, pady=2)

        # PDA100A2
        tk.Label(display_frame, text="PDA100A2 Power (MW):", font=("Arial", 11, "bold")).grid(
            row=2,
            column=0,
            sticky="e",
            padx=5,
            pady=10,
        )
        self.lbl_pda100a2_power = tk.Label(
            display_frame,
            text="--",
            font=("Arial", 18, "bold"),
            fg="#006600",
        )
        self.lbl_pda100a2_power.grid(row=2, column=1, sticky="w", padx=5, pady=10)

        tk.Label(display_frame, text="Voltage (V):").grid(
            row=3,
            column=0,
            sticky="e",
            padx=5,
            pady=2,
        )
        self.lbl_pda100a2_voltage = tk.Label(display_frame, text="--")
        self.lbl_pda100a2_voltage.grid(row=3, column=1, sticky="w", padx=5, pady=2)

        for child in display_frame.winfo_children():
            child.grid_configure(padx=5, pady=3)

        # Controls
        ctrl_frame = tk.Frame(main_frame)
        ctrl_frame.pack(fill="x", pady=5)

        self.btn_start = tk.Button(
            ctrl_frame,
            text="Start",
            width=10,
            command=self.start_monitoring,
            state="disabled",
            bg="green",
            fg="white",
        )
        self.btn_start.pack(side="left", padx=5)

        self.btn_stop = tk.Button(
            ctrl_frame,
            text="Stop",
            width=10,
            command=self.stop_monitoring,
            state="disabled",
            bg="red",
            fg="white",
        )
        self.btn_stop.pack(side="left", padx=5)

        self.lbl_run_status = tk.Label(ctrl_frame, text="Monitor: Stopped")
        self.lbl_run_status.pack(side="left", padx=15)

        stale_lock_label = "Stale lock: allow DAQ reads anyway (unsafe if Santec is scanning)"
        self.chk_ignore_lock = tk.Checkbutton(
            ctrl_frame,
            text=stale_lock_label,
            variable=self.var_ignore_santec_lock,
        )
        self.chk_ignore_lock.pack(side="left", padx=10)
        _attach_tooltip(self.chk_ignore_lock, _STALE_LOCK_TOOLTIP)

    def init_daq(self) -> None:
        """Initialize the DAQ and test read once."""
        device = self.ent_device.get().strip()
        ch1 = self.ent_ch1.get().strip()
        ch2 = self.ent_ch2.get().strip()

        if not device or not ch1 or not ch2:
            messagebox.showerror("Error", "Please specify DAQ device and both channels.")
            return

        if santec_daq_busy() and not self.var_ignore_santec_lock.get():
            messagebox.showwarning(
                "Santec scanning",
                "qt3santec has the DAQ (scan in progress). Stop the scan or enable "
                "'Stale lock: allow DAQ reads anyway (unsafe if Santec is scanning)' "
                "only if you are sure the marker is stale—not during a real sweep.",
            )
            return

        try:
            # Test connection by reading once.
            test_ctrl = PhotodetectorController(device, ch1, ch2)
            v1, v2 = test_ctrl.read_both_detectors()

            # If we get here, DAQ is working; keep a controller instance.
            self.detector_ctrl = PhotodetectorController(device, ch1, ch2)
            self.lbl_status.config(
                text=f"DAQ: Initialized ({device}, {ch1}, {ch2})",
                fg="green",
            )
            self.lbl_pda50b2_voltage.config(text=f"{v1:.4f}")
            self.lbl_pda100a2_voltage.config(text=f"{v2:.4f}")
            p1 = self._voltage_to_mw(v1)
            p2 = self._voltage_to_mw(v2)
            self.lbl_pda50b2_power.config(text=f"{p1:.4f}")
            self.lbl_pda100a2_power.config(text=f"{p2:.4f}")

            self.btn_start.config(state="normal")
            self.btn_stop.config(state="disabled")
            self.lbl_run_status.config(text="Monitor: Ready")
        except Exception as e:
            self.detector_ctrl = None
            self.lbl_status.config(text="DAQ: Error", fg="red")
            self.btn_start.config(state="disabled")
            self.btn_stop.config(state="disabled")
            messagebox.showerror("DAQ Error", str(e))

    def _voltage_to_mw(self, voltage: float) -> float:
        """Convert voltage (V) to power (MW) using fixed calibration."""
        return voltage / self.VOLT_TO_MW_FACTOR

    def _set_power_widgets_paused(self, paused: bool) -> None:
        if paused:
            self.lbl_pda50b2_power.config(fg="#888888")
            self.lbl_pda100a2_power.config(fg="#888888")
            self.lbl_pda50b2_voltage.config(fg="#888888")
            self.lbl_pda100a2_voltage.config(fg="#888888")
        else:
            self.lbl_pda50b2_power.config(fg="#0044aa")
            self.lbl_pda100a2_power.config(fg="#006600")
            self.lbl_pda50b2_voltage.config(fg="black")
            self.lbl_pda100a2_voltage.config(fg="black")

    def start_monitoring(self) -> None:
        if self.detector_ctrl is None:
            messagebox.showerror("Error", "Initialize DAQ before starting monitoring.")
            return
        if self.running:
            return

        self.running = True
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.lbl_run_status.config(text="Monitor: Running")
        self._schedule_next_update()

    def stop_monitoring(self) -> None:
        self.running = False
        self._set_power_widgets_paused(False)
        self.btn_start.config(state="normal" if self.detector_ctrl else "disabled")
        self.btn_stop.config(state="disabled")
        self.lbl_run_status.config(text="Monitor: Stopped")

    def _schedule_next_update(self) -> None:
        if self.running:
            self.root.after(self.update_interval_ms, self._update_readings)

    def _update_readings(self) -> None:
        if not self.running or self.detector_ctrl is None:
            return

        try:
            if santec_daq_busy() and not self.var_ignore_santec_lock.get():
                self.lbl_run_status.config(
                    text="Monitor: Running — paused (Santec scan, DAQ shared)",
                )
                self._set_power_widgets_paused(True)
            else:
                self.lbl_run_status.config(text="Monitor: Running")
                self._set_power_widgets_paused(False)
                v1, v2 = self.detector_ctrl.read_both_detectors()
                p1 = self._voltage_to_mw(v1)
                p2 = self._voltage_to_mw(v2)

                self.lbl_pda50b2_voltage.config(text=f"{v1:.4f}")
                self.lbl_pda100a2_voltage.config(text=f"{v2:.4f}")
                self.lbl_pda50b2_power.config(text=f"{p1:.4f}")
                self.lbl_pda100a2_power.config(text=f"{p2:.4f}")

            self.lbl_status.config(fg="green")
        except Exception as e:
            # Stop monitoring on error to avoid spamming the DAQ.
            self.running = False
            self.btn_start.config(state="normal")
            self.btn_stop.config(state="disabled")
            self.lbl_run_status.config(text="Monitor: Error")
            self.lbl_status.config(text=f"DAQ: Error ({e})", fg="red")
        finally:
            self._schedule_next_update()

    def on_closing(self) -> None:
        """Cleanly stop monitoring and close the window."""
        self.running = False
        # No persistent DAQ task is kept open in this minimal app, so nothing to close.
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = PowerMonitorApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()

