import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional

from chromatune import Chromatune


class ChromatuneGUI:
    def __init__(self, master: tk.Tk):
        self.master = master
        self.master.title("SuperK Chromatune Controller")
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

        # -------- Device handle --------
        self.dev: Optional[Chromatune] = None
        self._status_job = None
        self._cached_wl = None
        self._last_spectrum = ([], [])

        # -------- Connection variables --------
        self.var_portname = tk.StringVar(value="superk")
        self.var_host_ip = tk.StringVar(value="192.168.0.209")
        self.var_host_port = tk.IntVar(value=10001)
        self.var_sys_ip = tk.StringVar(value="192.168.0.139")
        self.var_sys_port = tk.IntVar(value=10001)
        self.var_timeout = tk.IntVar(value=100)
        self.var_protocol = tk.IntVar(value=0)  # 0 TCP

        # -------- MAIN module variables --------
        self.var_emission = tk.BooleanVar(value=False)
        self.var_setup_mode = tk.StringVar(value="1: Const power")
        self.var_watchdog = tk.IntVar(value=0)
        self.var_power_permille = tk.IntVar(value=500)
        self.var_current_permille = tk.IntVar(value=0)

        # -------- FILTER module variables --------
        self.var_shutter_mode = tk.IntVar(value=2)   # auto
        self.var_power_mode = tk.IntVar(value=4)     # tracker
        self.var_center_nm = tk.DoubleVar(value=550.0)
        self.var_bw_nm = tk.DoubleVar(value=10.0)
        self.var_nd_db = tk.DoubleVar(value=0.0)

        # -------- Sweep variables --------
        self.var_sw_start   = tk.DoubleVar(value=600.0)
        self.var_sw_end     = tk.DoubleVar(value=700.0)
        self.var_sw_t_fwd   = tk.DoubleVar(value=8.0)
        self.var_sw_t_bwd   = tk.DoubleVar(value=8.0)
        self.var_sw_step    = tk.DoubleVar(value=0.2)
        self.var_sw_loops   = tk.IntVar(value=2)        # 2 loops = there & back
        self.var_sw_power   = tk.BooleanVar(value=True) # read power each step?
        self.var_sw_settle_ms = tk.IntVar(value=30)
        self.var_sw_wait_idle = tk.BooleanVar(value=True)

        self._sweep_thread: Optional[threading.Thread] = None
        self._sweep_stop   = threading.Event()

        # build UI
        self._build_ui()

    # ================= UI LAYOUT =================

    def _build_ui(self):
        pad = {"padx": 8, "pady": 6}

        # ---- Connection frame ----
        frm_conn = ttk.LabelFrame(self.master, text="Connection")
        frm_conn.grid(row=0, column=0, sticky="nsew", **pad)

        ttk.Label(frm_conn, text="Port name").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm_conn, textvariable=self.var_portname, width=12).grid(row=0, column=1, sticky="w", padx=4)

        ttk.Label(frm_conn, text="Local IP").grid(row=1, column=0, sticky="w")
        ttk.Entry(frm_conn, textvariable=self.var_host_ip, width=15).grid(row=1, column=1, sticky="w", padx=4)
        ttk.Label(frm_conn, text="Local Port").grid(row=1, column=2, sticky="e")
        ttk.Entry(frm_conn, textvariable=self.var_host_port, width=7).grid(row=1, column=3, sticky="w", padx=4)

        ttk.Label(frm_conn, text="Laser IP").grid(row=2, column=0, sticky="w")
        ttk.Entry(frm_conn, textvariable=self.var_sys_ip, width=15).grid(row=2, column=1, sticky="w", padx=4)
        ttk.Label(frm_conn, text="Laser Port").grid(row=2, column=2, sticky="e")
        ttk.Entry(frm_conn, textvariable=self.var_sys_port, width=7).grid(row=2, column=3, sticky="w", padx=4)

        ttk.Label(frm_conn, text="Timeout (ms)").grid(row=0, column=2, sticky="e")
        ttk.Entry(frm_conn, textvariable=self.var_timeout, width=7).grid(row=0, column=3, sticky="w", padx=4)

        btn_connect = ttk.Button(frm_conn, text="Connect", command=self.on_connect)
        btn_connect.grid(row=0, column=4, rowspan=2, sticky="nsew", padx=6)
        btn_disconnect = ttk.Button(frm_conn, text="Disconnect", command=self.on_disconnect)
        btn_disconnect.grid(row=2, column=4, sticky="nsew", padx=6)

        # ---- Main module frame ----
        frm_main = ttk.LabelFrame(self.master, text="Main Module")
        frm_main.grid(row=1, column=0, sticky="nsew", **pad)

        cb_emit = ttk.Checkbutton(frm_main, text="Emission ON", variable=self.var_emission,
                                  command=self.on_toggle_emission)
        cb_emit.grid(row=0, column=0, sticky="w")

        cmb_setup = ttk.Combobox(
            frm_main, width=18, state="readonly",
            values=[
                "0: Const current",
                "1: Const power",
                "2: Ext mod current",
                "3: Ext mod power",
                "4: Power lock",
            ],
            textvariable=self.var_setup_mode,
        )
        cmb_setup.current(1)
        cmb_setup.bind("<<ComboboxSelected>>", self.on_set_setup_mode)
        cmb_setup.grid(row=0, column=2, padx=4)

        ttk.Label(frm_main, text="Watchdog (s)").grid(row=0, column=3, sticky="e")
        ttk.Entry(frm_main, textvariable=self.var_watchdog, width=6).grid(row=0, column=4, sticky="w")
        ttk.Button(frm_main, text="Set", command=self.on_set_watchdog).grid(row=0, column=5, padx=4)

        ttk.Label(frm_main, text="Power ‰").grid(row=1, column=0, sticky="e")
        ttk.Entry(frm_main, textvariable=self.var_power_permille, width=6).grid(row=1, column=1, sticky="w")
        ttk.Button(frm_main, text="Set", command=self.on_set_power_permille).grid(row=1, column=2, padx=4)

        ttk.Label(frm_main, text="Current ‰").grid(row=1, column=3, sticky="e")
        ttk.Entry(frm_main, textvariable=self.var_current_permille, width=6).grid(row=1, column=4, sticky="w")
        ttk.Button(frm_main, text="Set", command=self.on_set_current_permille).grid(row=1, column=5, padx=4)

        ttk.Button(frm_main, text="Reset Interlock", command=self.on_reset_interlock).grid(row=2, column=0, padx=4, pady=2)
        ttk.Button(frm_main, text="Disable Interlock", command=self.on_disable_interlock).grid(row=2, column=1, padx=4, pady=2)

        # ttk.Button(frm_main, text="Refresh Status", command=self.refresh_status_once).grid(row=2, column=4, padx=4)
        # self.lbl_status_main = ttk.Label(frm_main, text="status: —")
        # self.lbl_status_main.grid(row=2, column=5, sticky="w")

        # Disclaimer / caption at the bottom
        lbl_disclaimer = ttk.Label(
            frm_main,
            text="⚠ Note: The exact output power of the laser linearly changes with the current, not the power",
            foreground="gray",
            font=("TkDefaultFont", 8)
        )
        lbl_disclaimer.grid(
            row=99, column=0, columnspan=6,
            sticky="w", pady=(4,0)
        )


        # ---- Filter module frame ----
        frm_f = ttk.LabelFrame(self.master, text="Optical Filter")
        frm_f.grid(row=2, column=0, sticky="nsew", **pad)

        ttk.Label(frm_f, text="Shutter").grid(row=0, column=0, sticky="e")
        cmb_shut = ttk.Combobox(frm_f, width=14, state="readonly",
                                values=["0: Closed", "1: Open", "2: Auto"])
        cmb_shut.current(2)
        cmb_shut.bind("<<ComboboxSelected>>", self.on_set_shutter_mode)
        cmb_shut.grid(row=0, column=1, padx=4)

        ttk.Label(frm_f, text="Power mode").grid(row=0, column=2, sticky="e")
        cmb_pwr = ttk.Combobox(frm_f, width=18, state="readonly",
                               values=[
                                   "0: Manual",
                                   "1: Max",
                                   "2: Passive",
                                   "3: Active",
                                   "4: Tracker",
                               ])
        cmb_pwr.current(4)
        cmb_pwr.bind("<<ComboboxSelected>>", self.on_set_power_mode)
        cmb_pwr.grid(row=0, column=3, padx=4)

        ttk.Label(frm_f, text="Center (nm)").grid(row=1, column=0, sticky="e")
        ttk.Entry(frm_f, textvariable=self.var_center_nm, width=8).grid(row=1, column=1, sticky="w")
        ttk.Label(frm_f, text="BW (nm)").grid(row=1, column=2, sticky="e")
        ttk.Entry(frm_f, textvariable=self.var_bw_nm, width=8).grid(row=1, column=3, sticky="w")
        ttk.Button(frm_f, text="Set Filter", command=self.on_set_filter).grid(row=1, column=4, padx=6)

        ttk.Label(frm_f, text="ND (dB)").grid(row=2, column=0, sticky="e")
        ttk.Entry(frm_f, textvariable=self.var_nd_db, width=8).grid(row=2, column=1, sticky="w")
        ttk.Button(frm_f, text="Set ND", command=self.on_set_nd).grid(row=2, column=2, padx=6)

        # ttk.Button(frm_f, text="Refresh Filter Status", command=self.refresh_status_once).grid(row=2, column=4, padx=6)
        # self.lbl_status_filter = ttk.Label(frm_f, text="status: —")
        # self.lbl_status_filter.grid(row=2, column=5, sticky="w")


        # ---- Wavelength Sweep frame ----
        frm_w = ttk.LabelFrame(self.master, text="Wavelength Sweep")
        frm_w.grid(row=4, column=0, sticky="nsew", padx=8, pady=6)

        ttk.Label(frm_w, text="Start (nm)").grid(row=0, column=0, sticky="e")
        ttk.Entry(frm_w, textvariable=self.var_sw_start, width=8).grid(row=0, column=1, sticky="w", padx=4)

        ttk.Label(frm_w, text="End (nm)").grid(row=0, column=2, sticky="e")
        ttk.Entry(frm_w, textvariable=self.var_sw_end, width=8).grid(row=0, column=3, sticky="w", padx=4)

        ttk.Label(frm_w, text="Forward time (s)").grid(row=1, column=0, sticky="e")
        ttk.Entry(frm_w, textvariable=self.var_sw_t_fwd, width=8).grid(row=1, column=1, sticky="w", padx=4)

        ttk.Label(frm_w, text="Backward time (s)").grid(row=1, column=2, sticky="e")
        ttk.Entry(frm_w, textvariable=self.var_sw_t_bwd, width=8).grid(row=1, column=3, sticky="w", padx=4)

        ttk.Label(frm_w, text="Step (nm)").grid(row=2, column=0, sticky="e")
        ttk.Entry(frm_w, textvariable=self.var_sw_step, width=8).grid(row=2, column=1, sticky="w", padx=4)

        ttk.Label(frm_w, text="Loops").grid(row=2, column=2, sticky="e")
        ttk.Entry(frm_w, textvariable=self.var_sw_loops, width=8).grid(row=2, column=3, sticky="w", padx=4)

        ttk.Checkbutton(frm_w, text="Read power each step",
                variable=self.var_sw_power).grid(row=3, column=0, columnspan=2, sticky="w")

        ttk.Label(frm_w, text="Settle (ms)").grid(row=3, column=2, sticky="e")
        ttk.Entry(frm_w, textvariable=self.var_sw_settle_ms, width=8).grid(row=3, column=3, sticky="w", padx=4)

        ttk.Checkbutton(frm_w, text="Wait for filter idle",
                        variable=self.var_sw_wait_idle).grid(row=4, column=0, columnspan=2, sticky="w", pady=(2,0))



        btn_start = ttk.Button(frm_w, text="Start Sweep", command=self.on_start_sweep)
        btn_start.grid(row=5, column=2, sticky="ew", padx=4)

        btn_stop = ttk.Button(frm_w, text="Stop", command=self.on_stop_sweep)
        btn_stop.grid(row=5, column=3, sticky="ew", padx=4)

        self.lbl_sweep_status = ttk.Label(frm_w, text="—")
        self.lbl_sweep_status.grid(row=6, column=0, columnspan=4, sticky="w", pady=(4,0))

        lbl_sw_disclaimer = ttk.Label(
            frm_w,
            text=(
                "⚠ Changing 'Settle (ms)' and 'Wait for filter idle' affects scan speed:\n"
                "• A higher settle time increases stability but slows the sweep.\n"
                "• Waiting for idle ensures accuracy but can add extra delay."
            ),
            foreground="gray",          # subtle color
            font=("TkDefaultFont", 8),  # smaller font
            justify="left",             # align multiline text to the left
            wraplength=400              # wrap text so it doesn’t run off the window
        )
        lbl_sw_disclaimer.grid(row=99, column=0, columnspan=6, sticky="w", pady=(6, 0))


        # (optional) stretch
        for c in range(4):
            frm_w.grid_columnconfigure(c, weight=1)


        # ---- Spectrum frame ----
        # frm_s = ttk.LabelFrame(self.master, text="Spectrum")
        # frm_s.grid(row=3, column=0, sticky="nsew", **pad)

        # ttk.Button(frm_s, text="Read Full Spectrum", command=self.on_read_spectrum).grid(row=0, column=0, padx=4)
        # ttk.Button(frm_s, text="Save CSV…", command=self.on_save_csv).grid(row=0, column=1, padx=4)
        # self.lbl_spec_info = ttk.Label(frm_s, text="N=0")
        # self.lbl_spec_info.grid(row=0, column=2, padx=6)

        # self.canvas = tk.Canvas(frm_s, width=640, height=240, bg="white", highlightthickness=1, highlightbackground="#ccc")
        # self.canvas.grid(row=1, column=0, columnspan=6, padx=4, pady=4, sticky="nsew")

        # # grid stretch
        # for r in range(4):
        #     self.master.grid_rowconfigure(r, weight=0)
        # self.master.grid_rowconfigure(3, weight=1)
        # self.master.grid_columnconfigure(0, weight=1)
        # frm_s.grid_columnconfigure(5, weight=1)
        # frm_s.grid_rowconfigure(1, weight=1)

    # ================= Event Handlers =================

    def on_connect(self):
        if self.dev is not None:
            messagebox.showinfo("Already connected", "Device is already connected.")
            return
        try:
            self.dev = Chromatune(
                port_name=self.var_portname.get().strip(),
                host_address=self.var_host_ip.get().strip(),
                host_port=int(self.var_host_port.get()),
                system_address=self.var_sys_ip.get().strip(),
                system_port=int(self.var_sys_port.get()),
                protocol_num=int(self.var_protocol.get()),
                ms_timeout=int(self.var_timeout.get()),
            )
            # self._schedule_status_updates()
            messagebox.showinfo("Connected", "Successfully connected to Chromatune.")
        except Exception as e:
            self.dev = None
            messagebox.showerror("Connect failed", str(e))

    def on_disconnect(self):
        # self._cancel_status_updates()
        try:
            if self.dev:
                self.dev.close()
                messagebox.showinfo("Disconnected", "Successfully disconnected to Chromatune.")
        finally:
            self.dev = None
            # self._cached_wl = None
            # self._last_spectrum = ([], [])
            # self.canvas.delete("all")

    def on_close(self):
        self.on_disconnect()
        self.master.destroy()

    # ----- main module controls -----

    def on_toggle_emission(self):
        if not self.dev:
            return
        try:
            self.dev.set_emission(self.var_emission.get())
        except Exception as e:
            messagebox.showerror("Emission", str(e))

    def on_set_setup_mode(self, _event=None):
        if not self.dev:
            return
        try:
            # Extract the numeric prefix before ":"
            mode = int(self.var_setup_mode.get().split(":")[0])
            self.dev.set_setup_mode(mode)
            print("New setup mode:", mode)
        except Exception as e:
            messagebox.showerror("Setup mode", str(e))

    def on_set_watchdog(self):
        if not self.dev:
            return
        try:
            self.dev.set_watchdog_seconds(int(self.var_watchdog.get()))
        except Exception as e:
            messagebox.showerror("Watchdog", str(e))

    def on_set_power_permille(self):
        if not self.dev:
            return
        if self.dev.get_setup_mode() != 1:
            messagebox.showerror("Power Level", "Cannot change power in setup mode: " + str(self.dev.get_setup_mode()))
        try:
            self.dev.set_power_level_permille(int(self.var_power_permille.get()))
        except Exception as e:
            messagebox.showerror("Power level", str(e))

    def on_set_current_permille(self):
        if not self.dev:
            return
        if self.dev.get_setup_mode() != 0:
            messagebox.showerror("Current Level", "Cannot change current in setup mode: " + str(self.dev.get_setup_mode()))
        try:
            self.dev.set_current_level_permille(int(self.var_current_permille.get()))
        except Exception as e:
            messagebox.showerror("Current level", str(e))

    def on_reset_interlock(self):
        if not self.dev:
            return
        try:
            self.dev.reset_interlock()
        except Exception as e:
            messagebox.showerror("Interlock", str(e))

    def on_disable_interlock(self):
        if not self.dev:
            return
        try:
            self.dev.disable_interlock()
        except Exception as e:
            messagebox.showerror("Interlock", str(e))

    # ----- filter controls -----

    def on_set_shutter_mode(self, _event=None):
        if not self.dev:
            return
        try:
            self.dev.set_shutter_mode(self.var_shutter_mode.get())
        except Exception as e:
            messagebox.showerror("Shutter mode", str(e))

    def on_set_power_mode(self, _event=None):
        if not self.dev:
            return
        try:
            self.dev.set_power_mode(self.var_power_mode.get())
        except Exception as e:
            messagebox.showerror("Power mode", str(e))

    def on_set_filter(self):
        if not self.dev:
            return
        try:
            self.dev.set_filter(
                center_nm=float(self.var_center_nm.get()),
                bandwidth_nm=float(self.var_bw_nm.get()),
            )
            # new center/bw could change spectrum pixel mapping → refresh cache
            self._cached_wl = None
        except Exception as e:
            messagebox.showerror("Set filter", str(e))

    def on_set_nd(self):
        if not self.dev:
            return
        try:
            self.dev.set_nd_attenuation_db(float(self.var_nd_db.get()))
        except Exception as e:
            messagebox.showerror("ND attenuation", str(e))

    # ----- status -----

    # def _schedule_status_updates(self):
    #     self._cancel_status_updates()
    #     self._status_job = self.master.after(500, self._status_tick)

    # def _cancel_status_updates(self):
    #     if self._status_job:
    #         try:
    #             self.master.after_cancel(self._status_job)
    #         except Exception:
    #             pass
    #         self._status_job = None

    # def _status_tick(self):
    #     self.refresh_status_once()
    #     self._status_job = self.master.after(1000, self._status_tick)

    # def refresh_status_once(self):
    #     if not self.dev:
    #         return
    #     try:
    #         # main status
    #         bits = self.dev.get_status_bits()
    #         em_on = bool(bits & (1 << 0))
    #         self.var_emission.set(em_on)
    #         text_main = f"0x{bits:04X} (emission={'ON' if em_on else 'OFF'})"
    #         self.lbl_status_main.configure(text=text_main)
    #         # filter status
    #         b = self.dev.get_status_bits_filter()
    #         image_ready = bool(b & (1 << 10))
    #         shutter_open = bool(b & (1 << 0))
    #         text_filter = f"0x{b:08X} (img={'ready' if image_ready else '—'}, shutter={'open' if shutter_open else '—'})"
    #         self.lbl_status_filter.configure(text=text_filter)
    #     except Exception as e:
    #         self.lbl_status_main.configure(text=f"status err: {e}")
    #         self.lbl_status_filter.configure(text=f"status err: {e}")


    # ----- wavelength sweep -----

    def on_start_sweep(self):
        if not self.dev:
            messagebox.showerror("Sweep", "Not connected.")
            return
        # prevent double-start
        if self._sweep_thread and self._sweep_thread.is_alive():
            messagebox.showinfo("Sweep", "Sweep already running.")
            return

        # read & validate inputs
        try:
            start = float(self.var_sw_start.get())
            end   = float(self.var_sw_end.get())
            t_fwd = float(self.var_sw_t_fwd.get())
            t_bwd = float(self.var_sw_t_bwd.get())
            step  = float(self.var_sw_step.get())
            loops = int(self.var_sw_loops.get())
            readp = bool(self.var_sw_power.get())
            settle_ms = int(self.var_sw_settle_ms.get())
            wait_idle = bool(self.var_sw_wait_idle.get())

            if t_fwd <= 0 or t_bwd <= 0 or step <= 0 or loops < 1 or settle_ms < 0:
                raise ValueError("Times and step must be > 0; loops >= 1; settle_ms >= 0")
        except Exception as e:
            messagebox.showerror("Sweep", f"Invalid inputs: {e}")
            return

        # prepare stop flag and UI
        self._sweep_stop.clear()
        self._set_sweep_ui_running(True)
        self.lbl_sweep_status.config(text="Starting sweep…")

        # launch worker
        args = dict(start=start, end=end, t_fwd=t_fwd, t_bwd=t_bwd,
                    step=step, loops=loops, readp=readp, settle_ms=settle_ms, wait_idle=wait_idle)
        self._sweep_thread = threading.Thread(target=self._sweep_worker, args=(args,), daemon=True)
        self._sweep_thread.start()

    def on_stop_sweep(self):
        self._sweep_stop.set()
        self.lbl_sweep_status.config(text="Stopping…")

    def _set_sweep_ui_running(self, running: bool):
        state = "disabled" if running else "normal"

        # self.entry_sw_start.configure(state=state)
        # self.entry_sw_end.configure(state=state)
        # self.btn_start_sweep.configure(state=("disabled" if running else "normal"))
        # self.btn_stop_sweep.configure(state=("normal" if running else "disabled"))
        pass

    def _sweep_worker(self, args: dict):
        # optional: per-step logger
        def on_step(wavelength_nm: float, power_nw: int | None):
            # update a small status line (thread-safe via after)
            txt = f"{wavelength_nm:.2f} nm"
            if power_nw is not None:
                txt += f", {power_nw} nW"
            self.master.after(0, lambda t=txt: self.lbl_sweep_status.config(text=t))

        try:
            # Make sure emission/shutter sane (best effort)
            try:
                self.dev.set_shutter_mode(2)  # auto
                self.dev.set_emission(True)
            except Exception:
                pass

            self.dev.sweep_wavelength(
                start_nm=args["start"],
                end_nm=args["end"],
                t_forward_s=args["t_fwd"],
                t_backward_s=args["t_bwd"],
                loops=args["loops"],
                step_nm=args["step"],
                settle_ms=args["settle_ms"],
                wait_for_idle=args["wait_idle"],
                read_power=args["readp"],
                callback=on_step,
                stop_event=self._sweep_stop,
            )

            # finished or stopped
            self.master.after(0, lambda: self.lbl_sweep_status.config(
                text="Stopped" if self._sweep_stop.is_set() else "Done"
            ))
        except Exception as e:
            self.master.after(0, lambda e=e: messagebox.showerror("Sweep", str(e)))
        finally:
            self.master.after(0, lambda: self._set_sweep_ui_running(False))



    # ----- spectrum -----

    # def on_read_spectrum(self):
    #     if not self.dev:
    #         print("[DEBUG] Device not initialized, aborting spectrum read.")
    #         return
    #     print("[DEBUG] Starting background spectrum read thread...")
    #     # run in background so UI doesn't freeze while waiting for image ready
    #     t = threading.Thread(target=self._read_spectrum_worker, daemon=True)
    #     t.start()

    # def _read_spectrum_worker(self):
    #     try:
    #         print("[DEBUG] Spectrum worker started.")
    #         # cache wavelengths once unless pixel count changed
    #         if self._cached_wl is None:
    #             print("[DEBUG] No cached wavelengths, reading from device...")
    #             self._cached_wl = self.dev.read_wavelengths_nm()
    #             print(f"[DEBUG] Cached wavelengths length: {len(self._cached_wl)}")
    #         else:
    #             print(f"[DEBUG] Using cached wavelengths length: {len(self._cached_wl)}")

    #         wl, amp = self.dev.read_full_spectrum(refresh_wavelengths=False)
    #         print(f"[DEBUG] Spectrum read complete. Length wl={len(wl)}, amp={len(amp)}")

    #         self._last_spectrum = (wl, amp)
    #         self._draw_spectrum(wl, amp)
    #         print("[DEBUG] Spectrum drawn successfully.")

    #     except Exception as e:
    #         print(f"[ERROR] Exception in spectrum worker: {e}")
    #         self.master.after(0, lambda e=e: messagebox.showerror("Spectrum", str(e)))

    # def _draw_spectrum(self, wl, amp):
    #     print("[DEBUG] Entered _draw_spectrum")
    #     self.canvas.delete("all")
    #     w = int(self.canvas["width"])
    #     h = int(self.canvas["height"])
    #     n = min(len(wl), len(amp))
    #     print(f"[DEBUG] Drawing spectrum: n={n}, canvas size=({w}x{h})")

    #     self.lbl_spec_info.configure(text=f"N={n}")
    #     if n < 2:
    #         print("[DEBUG] Not enough points to draw (n<2). Exiting draw.")
    #         return

    #     xmin, xmax = min(wl), max(wl)
    #     ymin, ymax = min(amp), max(amp)
    #     print(f"[DEBUG] X range: {xmin:.2f}-{xmax:.2f}, Y range: {ymin:.2f}-{ymax:.2f}")

    #     if ymax == ymin:
    #         print("[WARN] Ymax == Ymin, adjusting to avoid divide by zero.")
    #         ymax = ymin + 1

    #     # axes
    #     margin = 32
    #     x0, y0 = margin, h - margin
    #     x1, y1 = w - margin, margin
    #     self.canvas.create_rectangle(x0, y1, x1, y0, outline="#999")

    #     # map helpers
    #     def xmap(x):
    #         return x0 + (x - xmin) * (x1 - x0) / (xmax - xmin) if xmax > xmin else x0

    #     def ymap(y):
    #         return y0 - (y - ymin) * (y0 - y1) / (ymax - ymin)

    #     # polyline (downsample if very dense)
    #     step = max(1, n // (x1 - x0))
    #     print(f"[DEBUG] Plotting step size: {step}")
    #     pts = []
    #     for i in range(0, n, step):
    #         pts.extend([xmap(wl[i]), ymap(amp[i])])
    #     print(f"[DEBUG] Number of plotted points: {len(pts)//2}")

    #     if len(pts) >= 4:
    #         self.canvas.create_line(*pts, width=1)

    #     # labels
    #     self.canvas.create_text(x0, y1 - 12, anchor="w", text=f"{xmin:.2f} nm")
    #     self.canvas.create_text(x1, y1 - 12, anchor="e", text=f"{xmax:.2f} nm")
    #     self.canvas.create_text(x0 - 4, y1, anchor="ne", text=f"{int(ymax)}")
    #     self.canvas.create_text(x0 - 4, y0, anchor="se", text=f"{int(ymin)}")

    #     print("[DEBUG] Finished drawing spectrum.")


    # # ----- export -----

    # def on_save_csv(self):
    #     wl, amp = self._last_spectrum
    #     if not wl or not amp:
    #         messagebox.showinfo("Save CSV", "No spectrum to save yet.")
    #         return
    #     path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
    #     if not path:
    #         return
    #     try:
    #         with open(path, "w", encoding="utf-8") as f:
    #             f.write("wavelength_nm,amplitude\n")
    #             for x, y in zip(wl, amp):
    #                 f.write(f"{x:.6f},{y}\n")
    #         messagebox.showinfo("Save CSV", f"Saved {len(wl)} points to {path}")
    #     except Exception as e:
    #         messagebox.showerror("Save CSV", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = ChromatuneGUI(root)
    root.mainloop()
