import tkinter as tk
from tkinter import ttk, messagebox
import csv
import os
from datetime import datetime
import pyvisa
import time
import threading
import nidaqmx
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from qt3utils.applications.qt3_daq_busy_marker import (
    clear_santec_daq_busy,
    mark_santec_daq_busy,
)

# ==============================================================================
# CONFIGURATION
# ==============================================================================
SWITCH_IP = '192.168.0.94'
SWITCH_PORT = 5020

# Using Socket Port 5000 based on tests
LASER_CONFIG = [
    {'ip': '192.168.0.96', 'switch_port': 1, 'socket_port': 5000},
    {'ip': '192.168.0.99', 'switch_port': 2, 'socket_port': 5000},
    # {'ip': '192.168.0.97', 'switch_port': 3, 'socket_port': 5000},
]

# Default NI-DAQ settings for photodetectors (used by Connect System)
DEFAULT_DAQ_DEVICE = "Dev1"
DEFAULT_PD_CHANNEL_PDA50B2 = "ai2"
DEFAULT_PD_CHANNEL_PDA10CS2 = "ai1"
DEFAULT_PD_CHANNEL_PDA100A2 = "ai0"

# ==============================================================================
# PHOTODETECTOR CONTROLLER
# ==============================================================================
class PhotodetectorController:
    """Controller for reading voltage from two or three photodetectors via NI DAQ."""
    
    def __init__(self, device_name='Dev1', channel1='ai0', channel2='ai1', channel3=None,
                 min_voltage=-10.0, max_voltage=10.0):
        """
        Initialize photodetector controller.
        
        Args:
            device_name: NI DAQ device name (e.g., 'Dev1')
            channel1: Analog input channel for first detector (PDA50B2)
            channel2: Analog input channel for second detector (PDA10CS2)
            channel3: Optional analog input for third detector (PDA100A2)
            min_voltage: Minimum expected voltage
            max_voltage: Maximum expected voltage
        """
        self.device_name = device_name
        self.channel1 = channel1
        self.channel2 = channel2
        self.channel3 = channel3
        self.min_voltage = min_voltage
        self.max_voltage = max_voltage
        self.continuous_task = None
        self.continuous_running = False
        self.continuous_samples = []
        self.continuous_timestamps = []
        
    def read_both_detectors(self):
        """
        Read voltage from both detectors (channel1, channel2) simultaneously.
        
        Returns:
            tuple: (voltage1, voltage2) in volts
        """
        try:
            with nidaqmx.Task() as task:
                task.ai_channels.add_ai_voltage_chan(
                    f"{self.device_name}/{self.channel1}",
                    min_val=self.min_voltage,
                    max_val=self.max_voltage
                )
                task.ai_channels.add_ai_voltage_chan(
                    f"{self.device_name}/{self.channel2}",
                    min_val=self.min_voltage,
                    max_val=self.max_voltage
                )
                data = task.read(number_of_samples_per_channel=1)
                if isinstance(data, (list, tuple)) and len(data) >= 2:
                    v1 = float(data[0][0] if hasattr(data[0], '__getitem__') else data[0])
                    v2 = float(data[1][0] if hasattr(data[1], '__getitem__') else data[1])
                    return (v1, v2)
                else:
                    raise RuntimeError(f"Unexpected data format from DAQ: {type(data)}")
        except Exception as e:
            raise RuntimeError(f"Error reading detectors: {e}")

    def read_three_detectors(self):
        """
        Read voltage from all three detectors (channel1, channel2, channel3) simultaneously.
        Requires channel3 to be set.
        
        Returns:
            tuple: (voltage1, voltage2, voltage3) in volts
        """
        if not self.channel3:
            raise RuntimeError("Third channel not configured")
        try:
            with nidaqmx.Task() as task:
                task.ai_channels.add_ai_voltage_chan(
                    f"{self.device_name}/{self.channel1}",
                    min_val=self.min_voltage,
                    max_val=self.max_voltage
                )
                task.ai_channels.add_ai_voltage_chan(
                    f"{self.device_name}/{self.channel2}",
                    min_val=self.min_voltage,
                    max_val=self.max_voltage
                )
                task.ai_channels.add_ai_voltage_chan(
                    f"{self.device_name}/{self.channel3}",
                    min_val=self.min_voltage,
                    max_val=self.max_voltage
                )
                data = task.read(number_of_samples_per_channel=1)
                if isinstance(data, (list, tuple)) and len(data) >= 3:
                    v1 = float(data[0][0] if hasattr(data[0], '__getitem__') else data[0])
                    v2 = float(data[1][0] if hasattr(data[1], '__getitem__') else data[1])
                    v3 = float(data[2][0] if hasattr(data[2], '__getitem__') else data[2])
                    return (v1, v2, v3)
                else:
                    raise RuntimeError(f"Unexpected data format from DAQ: {type(data)}")
        except Exception as e:
            raise RuntimeError(f"Error reading detectors: {e}")
    
    def start_continuous_sampling(self, sample_rate_hz=200, samples_per_read=100):
        """
        Start continuous sampling from two or three detectors.
        """
        if self.continuous_running:
            self.stop_continuous_sampling()
        
        try:
            self.continuous_task = nidaqmx.Task()
            self.continuous_task.ai_channels.add_ai_voltage_chan(
                f"{self.device_name}/{self.channel1}",
                min_val=self.min_voltage,
                max_val=self.max_voltage
            )
            self.continuous_task.ai_channels.add_ai_voltage_chan(
                f"{self.device_name}/{self.channel2}",
                min_val=self.min_voltage,
                max_val=self.max_voltage
            )
            if self.channel3:
                self.continuous_task.ai_channels.add_ai_voltage_chan(
                    f"{self.device_name}/{self.channel3}",
                    min_val=self.min_voltage,
                    max_val=self.max_voltage
                )
            self.continuous_task.timing.cfg_samp_clk_timing(
                rate=sample_rate_hz,
                sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS
            )
            self.continuous_task.start()
            self.continuous_running = True
            self.continuous_samples = []
            self.continuous_timestamps = []
            self.samples_per_read = samples_per_read
            self.sample_rate = sample_rate_hz
        except Exception as e:
            self.continuous_running = False
            raise RuntimeError(f"Error starting continuous sampling: {e}")
    
    def read_continuous_samples(self, timeout=1.0):
        """
        Read samples from continuous sampling task.
        
        Returns:
            tuple: (samples1, samples2, samples3_or_None, timestamps)
            samples3 is None when only two channels are configured.
        """
        if not self.continuous_running or self.continuous_task is None:
            return None, None, None, None
        
        try:
            data = self.continuous_task.read(
                number_of_samples_per_channel=self.samples_per_read,
                timeout=timeout
            )
            if not isinstance(data, (list, tuple)) or len(data) < 2:
                return None, None, None, None
            
            samples1 = np.array(data[0])
            samples2 = np.array(data[1])
            samples3 = np.array(data[2]) if self.channel3 and len(data) >= 3 else None
            
            num_samples = len(samples1)
            if num_samples == 0:
                return None, None, None, None
                
            if len(self.continuous_timestamps) == 0:
                start_time = time.time()
            else:
                start_time = self.continuous_timestamps[-1] + (1.0 / self.sample_rate)
            
            timestamps = np.linspace(
                start_time,
                start_time + (num_samples - 1) / self.sample_rate,
                num_samples
            )
            
            if samples3 is not None:
                self.continuous_samples.append((samples1, samples2, samples3))
            else:
                self.continuous_samples.append((samples1, samples2))
            self.continuous_timestamps.extend(timestamps.tolist())
            
            return samples1, samples2, samples3, timestamps
        except nidaqmx.errors.DaqReadError:
            return None, None, None, None
        except Exception as e:
            return None, None, None, None
    
    def stop_continuous_sampling(self):
        """Stop continuous sampling task."""
        if self.continuous_task is not None:
            try:
                if self.continuous_running:
                    self.continuous_task.stop()
                self.continuous_task.close()
            except:
                pass
            self.continuous_task = None
        self.continuous_running = False
    
    def get_all_continuous_data(self):
        """
        Get all collected continuous sampling data (first two channels only).
        
        Returns:
            tuple: (samples1_all, samples2_all, timestamps_all)
        """
        if not self.continuous_samples:
            return np.array([]), np.array([]), np.array([])
        
        samples1_list = [s[0] for s in self.continuous_samples]
        samples2_list = [s[1] for s in self.continuous_samples]
        
        samples1_all = np.concatenate(samples1_list) if samples1_list else np.array([])
        samples2_all = np.concatenate(samples2_list) if samples2_list else np.array([])
        timestamps_all = np.array(self.continuous_timestamps)
        
        return samples1_all, samples2_all, timestamps_all
    
    def clear_continuous_data(self):
        """Clear stored continuous sampling data."""
        self.continuous_samples = []
        self.continuous_timestamps = []

    def reset_continuous_timeline(self):
        """Reset the timestamp timeline so the next read uses time.time() as base.
        Call at the start of each new scan so timestamps align with wall clock after a delay."""
        self.continuous_timestamps = []

# ==============================================================================
# BACKEND CONTROLLER
# ==============================================================================
class SantecController:
    def __init__(self):
        self.rm = pyvisa.ResourceManager()
        self.switch = None
        self.lasers = []
        self.active_laser = None
        self.is_connected = False

    def connect(self):
        try:
            # 1. Connect Switch
            switch_addr = f'TCPIP0::{SWITCH_IP}::{SWITCH_PORT}::SOCKET'
            self.switch = self.rm.open_resource(switch_addr)
            self.switch.write_termination = '\r'
            self.switch.read_termination = '\r'
            self.switch.timeout = 3000
            self.switch.query("*IDN?") 

            # 2. Connect Lasers
            self.lasers = []
            for cfg in LASER_CONFIG:
                addr = f"TCPIP0::{cfg['ip']}::{cfg['socket_port']}::SOCKET"
                try:
                    inst = self.rm.open_resource(addr)
                    inst.write_termination = '\r'
                    inst.read_termination = '\r'
                    inst.timeout = 3000
                    inst.write(":SYST:COMM:COD 0") # Force Legacy Mode
                    inst.write(":POW:ATT:AUT 1") # Force auto power control mode
                    
                    idn = inst.query("*IDN?").strip()
                    min_wav = float(inst.query(":WAV:MIN?"))
                    max_wav = float(inst.query(":WAV:MAX?"))
                    
                    self.lasers.append({
                        'obj': inst,
                        'ip': cfg['ip'],
                        'port': cfg['switch_port'],
                        'min': min_wav,
                        'max': max_wav,
                        'idn': idn
                    })
                except Exception as e:
                    print(f"Failed to connect to laser {cfg['ip']}: {e}")

            if not self.lasers:
                raise Exception("No lasers connected successfully.")

            self.is_connected = True
            return f"Connected: Switch + {len(self.lasers)} Lasers"

        except Exception as e:
            self.is_connected = False
            raise e

    def _select_best_laser(self, target_nm):
        candidates = [l for l in self.lasers if l['min'] <= target_nm <= l['max']]
        if not candidates: return None
        if len(candidates) == 1: return candidates[0]

        best_laser = None
        max_edge_dist = -1.0

        for laser in candidates:
            dist = min(target_nm - laser['min'], laser['max'] - target_nm)
            if dist > max_edge_dist:
                max_edge_dist = dist
                best_laser = laser
        return best_laser

    def check_valid_range(self, start_nm, end_nm):
        start_valid = any(l['min'] <= start_nm <= l['max'] for l in self.lasers)
        end_valid = any(l['min'] <= end_nm <= l['max'] for l in self.lasers)
        return start_valid and end_valid

    def set_wavelength(self, target_nm):
        chosen = self._select_best_laser(target_nm)
        if not chosen: raise ValueError(f"{target_nm}nm is out of range.")

        if self.active_laser != chosen:
            if self.active_laser: self.active_laser['obj'].write(":POW:STAT 0")
            self.switch.write(f"CH {chosen['port']}")
            time.sleep(0.2) 
            self.active_laser = chosen

        inst = chosen['obj']
        inst.write(f":WAV {target_nm}")
        if inst.query(":POW:STAT?").strip() == "0": inst.write(":POW:STAT 1")

    def set_power(self, power_value):
        """Set the optical output power level.
        
        Args:
            power_value: Power level in dBm (range: -15 to +13 dBm)
        
        Raises:
            ValueError: If power value is out of valid range
            RuntimeError: If no laser is available
        """
        if not self.lasers:
            raise RuntimeError("No lasers connected.")
        
        # Validate power range: -15dBm to +13dBm
        if power_value < -15.0 or power_value > 13.0:
            raise ValueError(f"Power must be between -15 and +13 dBm. Got {power_value} dBm.")
        
        # Use active laser if available, otherwise use first laser
        if self.active_laser:
            inst = self.active_laser['obj']
        else:
            # If no active laser, use first available laser
            inst = self.lasers[0]['obj']
            # Switch to this laser
            if self.switch:
                self.switch.write(f"CH {self.lasers[0]['port']}")
                time.sleep(0.2)
            self.active_laser = self.lasers[0]
        
        # Set power using Legacy mode command :POW
        inst.write(f":POW {power_value}")
        
        # Ensure power is on
        if inst.query(":POW:STAT?").strip() == "0":
            inst.write(":POW:STAT 1")

    def check_continuous_range(self, start_nm, end_nm):
        """Check if start and end wavelengths are within a single laser's range.
        Returns the laser object if valid, None otherwise."""
        for laser in self.lasers:
            if laser['min'] <= start_nm <= laser['max'] and laser['min'] <= end_nm <= laser['max']:
                return laser
        return None

    def configure_continuous_sweep(self, laser, start_nm, stop_nm, speed_nm_per_s, mode):
        """Configure continuous sweep parameters on a specific laser.
        
        Args:
            laser: Laser dictionary object
            start_nm: Start wavelength in nm
            stop_nm: Stop wavelength in nm
            speed_nm_per_s: Sweep speed (1, 2, 5, 10, 20, 50, 100, or 200 nm/s)
            mode: Sweep mode (1=one-way continuous, 3=two-way continuous)
        """
        valid_speeds = [1, 2, 5, 10, 20, 50, 100, 200]
        if speed_nm_per_s not in valid_speeds:
            raise ValueError(f"Speed must be one of {valid_speeds} nm/s")
        
        if mode not in [1, 3]:
            raise ValueError("Mode must be 1 (one-way) or 3 (two-way)")
        
        inst = laser['obj']
        
        # Switch to this laser if not already active
        if self.active_laser != laser:
            if self.active_laser: self.active_laser['obj'].write(":POW:STAT 0")
            self.switch.write(f"CH {laser['port']}")
            time.sleep(0.2)
            self.active_laser = laser
        
        # Configure sweep parameters
        inst.write(f":WAV:SWE:STARt {start_nm}")
        inst.write(f":WAV:SWE:STOP {stop_nm}")
        inst.write(f":WAV:SWE:SPE {speed_nm_per_s}")
        inst.write(f":WAV:SWE:MOD {mode}")
        
        # Ensure power is on
        if inst.query(":POW:STAT?").strip() == "0":
            inst.write(":POW:STAT 1")

    def start_continuous_sweep(self, laser):
        """Start continuous sweep on a laser."""
        inst = laser['obj']
        inst.write(":WAV:SWE 1")

    def start_repeat_sweep(self, laser):
        """Start repeat scan on a laser."""
        inst = laser['obj']
        inst.write(":WAV:SWE:REP")

    def stop_continuous_sweep(self, laser):
        """Stop continuous sweep on a laser."""
        inst = laser['obj']
        inst.write(":WAV:SWE 0")

    def get_sweep_status(self, laser):
        """Get current sweep status.
        
        Returns:
            0: Stopped
            1: Running
            3: Standing by trigger
            4: Preparation for sweep start
        """
        inst = laser['obj']
        status = inst.query(":WAV:SWE?").strip()
        # Handle both legacy and SCPI responses
        try:
            return int(status)
        except ValueError:
            # SCPI format might have + prefix
            return int(status.lstrip('+'))

    def close(self):
        for laser in self.lasers:
            try: laser['obj'].write(":POW:STAT 0"); laser['obj'].close()
            except: pass
        if self.switch:
            try: self.switch.close()
            except: pass

# ==============================================================================
# FRONTEND GUI
# ==============================================================================
class LaserSweepApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Santec Laser Controller")
        self.ctrl = SantecController()
        self.stop_flag = False
        self.is_running = False
        
        # Photodetector controller and data storage
        self.detector_ctrl = None  # Will be initialized when DAQ is configured
        self.detector_data = {
            'PDA50B2': {
                'voltages': [],  # List of voltage readings
                'wavelengths': [],  # List of corresponding wavelengths
                'scans': [],  # List of scan numbers for each reading
                'timestamps': []  # List of timestamps
            },
            'PDA10CS2': {
                'voltages': [],
                'wavelengths': [],
                'scans': [],
                'timestamps': []
            }
        }
        self.current_scan = 0
        
        self._build_gui()

    def _build_gui(self):
        # Set minimum window size to prevent resizing when switching modes
        self.root.minsize(600, 500)
        
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Hardware init: VISA (lasers + switch) and NI-DAQ photodetectors are separate steps
        init_frame = tk.LabelFrame(main_frame, text="Initialization")
        init_frame.pack(fill="x", padx=10, pady=5)
        init_inner = tk.Frame(init_frame)
        init_inner.pack(fill="x", padx=5, pady=5)
        self.btn_connect_lasers = tk.Button(
            init_inner,
            text="Initialize lasers & optical switch",
            command=self.connect_lasers_and_switch,
            bg="#dddddd",
        )
        self.btn_connect_lasers.pack(fill="x", padx=5, pady=3)
        self.btn_connect_detectors = tk.Button(
            init_inner,
            text="Initialize photodetectors",
            command=self.connect_photodetectors,
            bg="#dddddd",
        )
        self.btn_connect_detectors.pack(fill="x", padx=5, pady=3)

        status_frame = tk.Frame(main_frame)
        status_frame.pack(fill="x", padx=10, pady=(0, 5))
        self.lbl_status = tk.Label(
            status_frame,
            text="Status: Lasers/switch — not connected | Photodetectors — not connected",
            fg="red",
            anchor="w",
            justify="left",
        )
        self.lbl_status.pack(side="left", fill="x", expand=True)

        # Manual Control
        manual_frame = tk.LabelFrame(main_frame, text="Manual Control")
        manual_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(manual_frame, text="Set Wavelength (nm):").pack(side="left", padx=5)
        self.ent_manual_wav = tk.Entry(manual_frame, width=10)
        self.ent_manual_wav.pack(side="left", padx=5)
        self.btn_set_manual = tk.Button(manual_frame, text="Set", command=self.set_manual_wavelength, state="disabled")
        self.btn_set_manual.pack(side="left", padx=5)
        
        tk.Label(manual_frame, text="Set Power (dBm):").pack(side="left", padx=5)
        self.ent_manual_power = tk.Entry(manual_frame, width=10)
        self.ent_manual_power.pack(side="left", padx=5)
        self.btn_set_power = tk.Button(manual_frame, text="Set Power", command=self.set_manual_power, state="disabled")
        self.btn_set_power.pack(side="left", padx=5)

        # Sweep Type Selection
        sweep_type_frame = tk.Frame(main_frame)
        sweep_type_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(sweep_type_frame, text="Sweep Type:").pack(side="left", padx=5)
        self.combo_sweep_type = ttk.Combobox(sweep_type_frame, width=20, state="readonly", values=["Step Sweep", "Continuous Sweep"])
        self.combo_sweep_type.pack(side="left", padx=5)
        self.combo_sweep_type.set("Step Sweep")
        self.combo_sweep_type.bind("<<ComboboxSelected>>", self._toggle_sweep_type)

        # Sweep Config (Step Sweep)
        self.sweep_frame = tk.LabelFrame(main_frame, text="Sweep Configuration")
        self.sweep_frame.pack(fill="x", padx=10, pady=5)

        # Row 0: Range and Sweep direction option
        tk.Label(self.sweep_frame, text="Start (nm):").grid(row=0, column=0, sticky="e")
        self.ent_start = tk.Entry(self.sweep_frame, width=10); self.ent_start.grid(row=0, column=1)
        tk.Label(self.sweep_frame, text="End (nm):").grid(row=0, column=2, sticky="e")
        self.ent_end = tk.Entry(self.sweep_frame, width=10); self.ent_end.grid(row=0, column=3)
        tk.Label(self.sweep_frame, text="Direction:").grid(row=0, column=4, sticky="e")
        self.combo_sweep_direction = ttk.Combobox(self.sweep_frame, width=12, state="readonly", values=["One-way", "Two-way"])
        self.combo_sweep_direction.grid(row=0, column=5, sticky="w")
        self.combo_sweep_direction.set("Two-way")
        self.combo_sweep_direction.bind("<<ComboboxSelected>>", self._toggle_one_way)

        # Row 1: Upsweep
        tk.Label(self.sweep_frame, text="Upsweep Time (s):").grid(row=1, column=0, sticky="e")
        self.ent_up_time = tk.Entry(self.sweep_frame, width=10); self.ent_up_time.grid(row=1, column=1)
        
        tk.Label(self.sweep_frame, text="Up Pixels:").grid(row=1, column=2, sticky="e")
        self.ent_up_pixels = tk.Entry(self.sweep_frame, width=10); self.ent_up_pixels.grid(row=1, column=3)
        
        tk.Label(self.sweep_frame, text="Up Subpixels:").grid(row=1, column=4, sticky="e")
        self.ent_up_sub = tk.Entry(self.sweep_frame, width=5); self.ent_up_sub.grid(row=1, column=5)
        self.ent_up_sub.insert(0, "1")

        # Row 2: Downsweep
        self.lbl_down_time = tk.Label(self.sweep_frame, text="Downsweep Time (s):")
        self.lbl_down_time.grid(row=2, column=0, sticky="e")
        self.ent_down_time = tk.Entry(self.sweep_frame, width=10); self.ent_down_time.grid(row=2, column=1)
        
        self.lbl_down_pixels = tk.Label(self.sweep_frame, text="Down Pixels:")
        self.lbl_down_pixels.grid(row=2, column=2, sticky="e")
        self.ent_down_pixels = tk.Entry(self.sweep_frame, width=10); self.ent_down_pixels.grid(row=2, column=3)

        self.lbl_down_sub = tk.Label(self.sweep_frame, text="Down Subpixels:")
        self.lbl_down_sub.grid(row=2, column=4, sticky="e")
        self.ent_down_sub = tk.Entry(self.sweep_frame, width=5); self.ent_down_sub.grid(row=2, column=5)
        self.ent_down_sub.insert(0, "1")

        # Row 3: Repeats
        tk.Label(self.sweep_frame, text="Scans:").grid(row=3, column=0, sticky="e")
        self.ent_scans = tk.Entry(self.sweep_frame, width=10); self.ent_scans.grid(row=3, column=1)
        tk.Label(self.sweep_frame, text="Delay (s):").grid(row=3, column=2, sticky="e")
        self.ent_delay = tk.Entry(self.sweep_frame, width=10); self.ent_delay.grid(row=3, column=3)

        for child in self.sweep_frame.winfo_children(): child.grid_configure(padx=5, pady=5)

        # Continuous Sweep Config
        self.cont_sweep_frame = tk.LabelFrame(main_frame, text="Continuous Sweep Configuration")
        self.cont_sweep_frame.pack(fill="x", padx=10, pady=5)

        # Row 0: Range and Laser selection
        tk.Label(self.cont_sweep_frame, text="Start (nm):").grid(row=0, column=0, sticky="e")
        self.ent_cont_start = tk.Entry(self.cont_sweep_frame, width=10); self.ent_cont_start.grid(row=0, column=1)
        tk.Label(self.cont_sweep_frame, text="End (nm):").grid(row=0, column=2, sticky="e")
        self.ent_cont_end = tk.Entry(self.cont_sweep_frame, width=10); self.ent_cont_end.grid(row=0, column=3)
        tk.Label(self.cont_sweep_frame, text="Laser:").grid(row=0, column=4, sticky="e")
        self.combo_cont_laser = ttk.Combobox(self.cont_sweep_frame, width=20, state="readonly")
        self.combo_cont_laser.grid(row=0, column=5, sticky="w")
        self.combo_cont_laser.set("Auto")

        # Row 1: Speed and Mode
        tk.Label(self.cont_sweep_frame, text="Speed (nm/s):").grid(row=1, column=0, sticky="e")
        self.combo_cont_speed = ttk.Combobox(self.cont_sweep_frame, width=10, state="readonly", values=["1", "2", "5", "10", "20", "50", "100", "200"])
        self.combo_cont_speed.grid(row=1, column=1)
        self.combo_cont_speed.set("10")
        tk.Label(self.cont_sweep_frame, text="Mode:").grid(row=1, column=2, sticky="e")
        self.combo_cont_mode = ttk.Combobox(self.cont_sweep_frame, width=15, state="readonly", values=["One-way", "Two-way"])
        self.combo_cont_mode.grid(row=1, column=3, sticky="w")
        self.combo_cont_mode.set("One-way")

        # Row 2: Scans, Delay, Sample Rate (Hz)
        tk.Label(self.cont_sweep_frame, text="Scans:").grid(row=2, column=0, sticky="e")
        self.ent_cont_scans = tk.Entry(self.cont_sweep_frame, width=10); self.ent_cont_scans.grid(row=2, column=1)
        tk.Label(self.cont_sweep_frame, text="Delay (s):").grid(row=2, column=2, sticky="e")
        self.ent_cont_delay = tk.Entry(self.cont_sweep_frame, width=10); self.ent_cont_delay.grid(row=2, column=3)
        tk.Label(self.cont_sweep_frame, text="Sample Rate (Hz):").grid(row=2, column=4, sticky="e")
        self.ent_sample_rate = tk.Entry(self.cont_sweep_frame, width=10); self.ent_sample_rate.grid(row=2, column=5)
        self.ent_sample_rate.insert(0, "200")

        for child in self.cont_sweep_frame.winfo_children(): child.grid_configure(padx=5, pady=5)
        
        # Calculate and set consistent heights for both frames to prevent resizing
        self.root.update_idletasks()  # Update to get actual sizes
        step_height = self.sweep_frame.winfo_reqheight()
        cont_height = self.cont_sweep_frame.winfo_reqheight()
        max_height = max(step_height, cont_height)
        
        # Set minimum height for both frames
        self.sweep_frame.config(height=max_height)
        self.cont_sweep_frame.config(height=max_height)
        
        # Initially hide continuous sweep frame
        self.cont_sweep_frame.pack_forget()

        # Actions - placed after sweep configuration sections
        self.action_frame = tk.Frame(main_frame)
        self.action_frame.pack(fill="x", padx=10, pady=10)
        self.btn_start = tk.Button(self.action_frame, text="START", bg="green", fg="white", font=("Arial", 10, "bold"), command=self.start_sweep_thread, state="disabled")
        self.btn_start.pack(side="left", fill="x", expand=True, padx=5)
        self.btn_stop = tk.Button(self.action_frame, text="STOP", bg="red", fg="white", font=("Arial", 10, "bold"), command=self.stop_sweep, state="disabled")
        self.btn_stop.pack(side="left", fill="x", expand=True, padx=5)
        self.lbl_experiment_status = tk.Label(self.action_frame, text="Experiment: Idle", font=("Arial", 10), fg="#333")
        self.lbl_experiment_status.pack(side="left", padx=15, pady=2)

        # Visualization Section
        self.viz_frame = tk.LabelFrame(main_frame, text="Visualization")
        self.viz_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Control panel for visualization
        viz_control_frame = tk.Frame(self.viz_frame)
        viz_control_frame.pack(fill="x", padx=5, pady=5)
        
        # Row 1: Detector, Mode, Clear Data
        tk.Label(viz_control_frame, text="Detector:").pack(side="left", padx=5)
        self.combo_detector = ttk.Combobox(viz_control_frame, width=15, state="readonly", 
                                          values=["PDA50B2", "PDA10CS2"])
        self.combo_detector.pack(side="left", padx=5)
        self.combo_detector.set("PDA50B2")
        self.combo_detector.bind("<<ComboboxSelected>>", self._on_detector_selection_changed)
        
        tk.Label(viz_control_frame, text="Mode:").pack(side="left", padx=5)
        self.combo_viz_mode = ttk.Combobox(viz_control_frame, width=15, state="readonly",
                                          values=["Heat Map", "Wavelength Graph"])
        self.combo_viz_mode.pack(side="left", padx=5)
        self.combo_viz_mode.set("Wavelength Graph")
        self.combo_viz_mode.bind("<<ComboboxSelected>>", self._on_viz_mode_changed)
        
        self.btn_clear_data = tk.Button(viz_control_frame, text="Clear Data", 
                                        command=self.clear_detector_data, bg="#dddddd")
        self.btn_clear_data.pack(side="left", padx=5)
        self.btn_export_data = tk.Button(viz_control_frame, text="Export Data",
                                         command=self.export_detector_data, bg="#dddddd")
        self.btn_export_data.pack(side="left", padx=5)
        
        # Row 2: Axis bounds controls
        viz_bounds_frame = tk.Frame(self.viz_frame)
        viz_bounds_frame.pack(fill="x", padx=5, pady=5)
        
        # Voltage bounds (for both modes)
        tk.Label(viz_bounds_frame, text="Voltage (V):").pack(side="left", padx=5)
        tk.Label(viz_bounds_frame, text="Min:").pack(side="left", padx=2)
        self.ent_v_min = tk.Entry(viz_bounds_frame, width=8)
        self.ent_v_min.pack(side="left", padx=2)
        tk.Label(viz_bounds_frame, text="Max:").pack(side="left", padx=2)
        self.ent_v_max = tk.Entry(viz_bounds_frame, width=8)
        self.ent_v_max.pack(side="left", padx=2)
        
        # Wavelength bounds (for wavelength graph)
        tk.Label(viz_bounds_frame, text="Wavelength (nm):").pack(side="left", padx=(10, 5))
        tk.Label(viz_bounds_frame, text="Min:").pack(side="left", padx=2)
        self.ent_wl_min = tk.Entry(viz_bounds_frame, width=8)
        self.ent_wl_min.pack(side="left", padx=2)
        tk.Label(viz_bounds_frame, text="Max:").pack(side="left", padx=2)
        self.ent_wl_max = tk.Entry(viz_bounds_frame, width=8)
        self.ent_wl_max.pack(side="left", padx=2)
        
        # Scan bounds (for heat map)
        tk.Label(viz_bounds_frame, text="Scan:").pack(side="left", padx=(10, 5))
        tk.Label(viz_bounds_frame, text="Min:").pack(side="left", padx=2)
        self.ent_scan_min = tk.Entry(viz_bounds_frame, width=8)
        self.ent_scan_min.pack(side="left", padx=2)
        tk.Label(viz_bounds_frame, text="Max:").pack(side="left", padx=2)
        self.ent_scan_max = tk.Entry(viz_bounds_frame, width=8)
        self.ent_scan_max.pack(side="left", padx=2)
        
        # Auto-scale button
        self.btn_auto_scale = tk.Button(viz_bounds_frame, text="Auto Scale", 
                                        command=self._apply_auto_scale, bg="#dddddd")
        self.btn_auto_scale.pack(side="left", padx=(10, 5))
        
        # Apply bounds button
        self.btn_apply_bounds = tk.Button(viz_bounds_frame, text="Apply Bounds", 
                                         command=self._apply_bounds, bg="#dddddd")
        self.btn_apply_bounds.pack(side="left", padx=5)
        
        # Store bounds state
        self.viz_bounds = {
            'v_min': None,
            'v_max': None,
            'wl_min': None,
            'wl_max': None,
            'scan_min': None,
            'scan_max': None
        }

        # Plot + toolbar in their own frame. Pack the toolbar first (bottom) so Tk
        # reserves its height; packing an expanding canvas first can starve or
        # clip the toolbar and cover the hover coordinate readout.
        self.viz_plot_frame = tk.Frame(self.viz_frame)
        self.viz_plot_frame.pack(fill=tk.BOTH, expand=True)

        self.viz_fig = Figure(figsize=(8, 5), dpi=100)
        self.viz_ax = self.viz_fig.add_subplot(111)
        self.viz_canvas = FigureCanvasTkAgg(self.viz_fig, master=self.viz_plot_frame)
        self.viz_toolbar = NavigationToolbar2Tk(
            self.viz_canvas, self.viz_plot_frame, pack_toolbar=False)
        self.viz_toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.viz_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.viz_toolbar.update()
        self.viz_toolbar.lift()
        
        # Store colorbar reference for cleanup
        self.viz_colorbar = None
        
        # Initialize empty plot
        self._update_visualization()

    def log(self, msg):
        print(msg)

    def _refresh_connection_status(self):
        """Update status label from ctrl.is_connected and detector_ctrl."""
        if self.ctrl.is_connected:
            laser_part = f"Lasers/switch — OK ({len(self.ctrl.lasers)} lasers)"
        else:
            laser_part = "Lasers/switch — not connected"
        if self.detector_ctrl:
            pd_part = f"Photodetectors — OK ({DEFAULT_DAQ_DEVICE})"
        else:
            pd_part = "Photodetectors — not connected"
        if self.ctrl.is_connected and self.detector_ctrl:
            fg = "green"
        elif self.ctrl.is_connected or self.detector_ctrl:
            fg = "darkorange"
        else:
            fg = "red"
        self.lbl_status.config(
            text=f"Status: {laser_part} | {pd_part}",
            fg=fg,
        )
    
    def _init_detectors_defaults(self):
        """Initialize photodetector DAQ using built-in defaults (Dev1 / ai2, ai1, ai0)."""
        device_name = DEFAULT_DAQ_DEVICE
        channel1 = DEFAULT_PD_CHANNEL_PDA50B2
        channel2 = DEFAULT_PD_CHANNEL_PDA10CS2
        channel3 = DEFAULT_PD_CHANNEL_PDA100A2

        test_ctrl = PhotodetectorController(device_name, channel1, channel2, channel3=channel3)
        test_ctrl.read_three_detectors()

        self.detector_ctrl = PhotodetectorController(device_name, channel1, channel2, channel3=channel3)
        ch_info = f"{channel1}, {channel2}, {channel3}"
        self.log(f"Detectors initialized: {device_name}, Channels: {ch_info}")
    
    def clear_detector_data(self):
        """Clear all collected detector data."""
        for detector in self.detector_data:
            self.detector_data[detector]['voltages'] = []
            self.detector_data[detector]['wavelengths'] = []
            self.detector_data[detector]['scans'] = []
            self.detector_data[detector]['timestamps'] = []
        self.current_scan = 0
        if self.detector_ctrl:
            self.detector_ctrl.clear_continuous_data()
        self._update_visualization()
        self.log("Detector data cleared.")

    def _set_experiment_status(self, text):
        """Update the experiment status label (call from main thread or via root.after(0, ...))."""
        if hasattr(self, 'lbl_experiment_status'):
            self.lbl_experiment_status.config(text=text)
    
    def export_detector_data(self):
        """Export all detector data to a CSV file in tidy format (one file, both detectors)."""
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        try:
            os.makedirs(data_dir, exist_ok=True)
        except OSError as e:
            self.log(f"Export failed: could not create data directory: {e}")
            messagebox.showerror("Export Failed", f"Could not create data directory:\n{data_dir}\n{e}")
            return
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(data_dir, f"qt3santec_{timestamp_str}.csv")
        header = ["detector", "wavelength_nm", "voltage_V", "scan", "timestamp"]
        rows = []
        for detector_name, data in self.detector_data.items():
            n = min(len(data["voltages"]), len(data["wavelengths"]),
                    len(data["scans"]), len(data["timestamps"]))
            for i in range(n):
                rows.append([
                    detector_name,
                    data["wavelengths"][i],
                    data["voltages"][i],
                    data["scans"][i],
                    data["timestamps"][i],
                ])
        if not rows:
            self.log("Export skipped: no data to export.")
            messagebox.showinfo("Export", "No data to export. Collect data first.")
            return
        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerows(rows)
            self.log(f"Exported {len(rows)} rows to {filename}")
            messagebox.showinfo("Export", f"Exported {len(rows)} rows to:\n{filename}")
        except OSError as e:
            self.log(f"Export failed: {e}")
            messagebox.showerror("Export Failed", str(e))
    
    def _on_detector_selection_changed(self, event=None):
        """Callback when detector selection changes."""
        self._update_visualization()
    
    def _on_viz_mode_changed(self, event=None):
        """Callback when visualization mode changes."""
        self._update_visualization()
    
    def _apply_auto_scale(self):
        """Auto-scale axes based on current data."""
        detector_name = self.combo_detector.get()
        data = self.detector_data[detector_name]
        
        if data['voltages']:
            voltages = np.array(data['voltages'])
            v_min, v_max = np.min(voltages), np.max(voltages)
            # Add small margin
            v_range = v_max - v_min
            if v_range > 0:
                margin = v_range * 0.05
                self.ent_v_min.delete(0, tk.END)
                self.ent_v_min.insert(0, f"{v_min - margin:.4f}")
                self.ent_v_max.delete(0, tk.END)
                self.ent_v_max.insert(0, f"{v_max + margin:.4f}")
            else:
                self.ent_v_min.delete(0, tk.END)
                self.ent_v_min.insert(0, f"{v_min - 0.1:.4f}")
                self.ent_v_max.delete(0, tk.END)
                self.ent_v_max.insert(0, f"{v_max + 0.1:.4f}")
        
        viz_mode = self.combo_viz_mode.get()
        if viz_mode in ("Wavelength Graph", "Heat Map") and data['wavelengths']:
            wavelengths = np.array(data['wavelengths'])
            wl_min, wl_max = np.min(wavelengths), np.max(wavelengths)
            wl_range = wl_max - wl_min
            if wl_range > 0:
                margin = wl_range * 0.05
                self.ent_wl_min.delete(0, tk.END)
                self.ent_wl_min.insert(0, f"{wl_min - margin:.2f}")
                self.ent_wl_max.delete(0, tk.END)
                self.ent_wl_max.insert(0, f"{wl_max + margin:.2f}")
        
        if viz_mode == "Heat Map" and data['scans']:
            scans = np.array(data['scans'])
            scan_min, scan_max = int(np.min(scans)), int(np.max(scans))
            self.ent_scan_min.delete(0, tk.END)
            self.ent_scan_min.insert(0, f"{scan_min}")
            self.ent_scan_max.delete(0, tk.END)
            self.ent_scan_max.insert(0, f"{scan_max}")
        
        self._apply_bounds()
    
    def _apply_bounds(self):
        """Apply user-specified bounds and update visualization."""
        # Read bounds from entries
        try:
            v_min_str = self.ent_v_min.get().strip()
            self.viz_bounds['v_min'] = float(v_min_str) if v_min_str else None
        except ValueError:
            self.viz_bounds['v_min'] = None
        
        try:
            v_max_str = self.ent_v_max.get().strip()
            self.viz_bounds['v_max'] = float(v_max_str) if v_max_str else None
        except ValueError:
            self.viz_bounds['v_max'] = None
        
        try:
            wl_min_str = self.ent_wl_min.get().strip()
            self.viz_bounds['wl_min'] = float(wl_min_str) if wl_min_str else None
        except ValueError:
            self.viz_bounds['wl_min'] = None
        
        try:
            wl_max_str = self.ent_wl_max.get().strip()
            self.viz_bounds['wl_max'] = float(wl_max_str) if wl_max_str else None
        except ValueError:
            self.viz_bounds['wl_max'] = None
        
        try:
            scan_min_str = self.ent_scan_min.get().strip()
            self.viz_bounds['scan_min'] = int(scan_min_str) if scan_min_str else None
        except ValueError:
            self.viz_bounds['scan_min'] = None
        
        try:
            scan_max_str = self.ent_scan_max.get().strip()
            self.viz_bounds['scan_max'] = int(scan_max_str) if scan_max_str else None
        except ValueError:
            self.viz_bounds['scan_max'] = None
        
        # Update visualization
        self._update_visualization()
    
    def _update_visualization(self):
        """Update visualization based on current detector and mode selection."""
        if not hasattr(self, 'viz_ax'):
            return
        
        # Remove existing colorbar if it exists
        if self.viz_colorbar is not None:
            self.viz_colorbar.remove()
            self.viz_colorbar = None
        
        detector_name = self.combo_detector.get()
        viz_mode = self.combo_viz_mode.get()
        
        self.viz_ax.clear()
        
        if viz_mode == "Heat Map":
            self.update_heatmap(detector_name)
        else:  # Wavelength Graph
            self.update_wavelength_graph(detector_name)
        
        self.viz_canvas.draw()
    
    def update_heatmap(self, detector_name):
        """Update heat map: scan vs wavelength, color encodes mean voltage per bin."""
        data = self.detector_data[detector_name]
        title = f'{detector_name} - Heat Map'

        def _axes_labels():
            self.viz_ax.set_xlabel('Scan Number')
            self.viz_ax.set_ylabel('Wavelength (nm)')
            self.viz_ax.set_title(title)

        if not data['voltages'] or not data['wavelengths']:
            self.viz_ax.text(0.5, 0.5, 'No data collected yet',
                             ha='center', va='center', transform=self.viz_ax.transAxes)
            _axes_labels()
            return

        n = min(len(data['voltages']), len(data['wavelengths']), len(data['scans']))
        if n == 0:
            _axes_labels()
            return

        voltages = np.array(data['voltages'][:n])
        wavelengths = np.array(data['wavelengths'][:n])
        scans = np.array(data['scans'][:n])

        valid = np.isfinite(voltages) & np.isfinite(wavelengths)
        if not np.any(valid):
            self.viz_ax.text(0.5, 0.5, 'No valid data',
                             ha='center', va='center', transform=self.viz_ax.transAxes)
            _axes_labels()
            return

        voltages = voltages[valid]
        wavelengths = wavelengths[valid]
        scans = scans[valid]

        unique_scans = np.unique(scans)
        if len(unique_scans) == 0:
            _axes_labels()
            return

        v_min_data, v_max_data = np.min(voltages), np.max(voltages)
        if v_max_data == v_min_data:
            v_max_data = v_min_data + 0.1

        v_min = self.viz_bounds['v_min'] if self.viz_bounds['v_min'] is not None else v_min_data
        v_max = self.viz_bounds['v_max'] if self.viz_bounds['v_max'] is not None else v_max_data

        wl_min_data, wl_max_data = np.min(wavelengths), np.max(wavelengths)
        if wl_max_data == wl_min_data:
            wl_max_data = wl_min_data + 0.1

        wl_min = self.viz_bounds['wl_min'] if self.viz_bounds['wl_min'] is not None else wl_min_data
        wl_max = self.viz_bounds['wl_max'] if self.viz_bounds['wl_max'] is not None else wl_max_data

        scan_min_data, scan_max_data = int(unique_scans[0]), int(unique_scans[-1])
        scan_min = self.viz_bounds['scan_min'] if self.viz_bounds['scan_min'] is not None else scan_min_data
        scan_max = self.viz_bounds['scan_max'] if self.viz_bounds['scan_max'] is not None else scan_max_data

        scan_mask = (unique_scans >= scan_min) & (unique_scans <= scan_max)
        filtered_scans = unique_scans[scan_mask]

        if len(filtered_scans) == 0:
            self.viz_ax.text(0.5, 0.5, 'No data in specified scan range',
                             ha='center', va='center', transform=self.viz_ax.transAxes)
            _axes_labels()
            return

        num_bins = 50
        heatmap_data = np.full((num_bins, len(filtered_scans)), np.nan)

        for i, scan_num in enumerate(filtered_scans):
            m = scans == scan_num
            wl_s = wavelengths[m]
            v_s = voltages[m]
            if len(wl_s) == 0:
                continue
            stat, _, _ = stats.binned_statistic(
                wl_s, v_s, statistic='mean', bins=num_bins, range=(wl_min, wl_max))
            heatmap_data[:, i] = stat

        if not np.any(np.isfinite(heatmap_data)):
            self.viz_ax.text(0.5, 0.5, 'No data in wavelength / scan range',
                             ha='center', va='center', transform=self.viz_ax.transAxes)
            _axes_labels()
            return

        masked = np.ma.masked_invalid(heatmap_data)

        im = self.viz_ax.imshow(
            masked, aspect='auto', origin='lower',
            extent=[scan_min - 0.5, scan_max + 0.5, wl_min, wl_max],
            cmap='viridis', interpolation='nearest',
            vmin=v_min, vmax=v_max)
        self.viz_colorbar = self.viz_fig.colorbar(im, ax=self.viz_ax, label='Voltage (V)')
        _axes_labels()

        xmin = float(scan_min) - 0.5
        xmax = float(scan_max) + 0.5
        self.viz_ax.set_xlim(xmin, xmax)
        self.viz_ax.set_ylim(wl_min, wl_max)
        # One tick per column, centered under the column (MaxNLocator(integer=True)
        # falls back to fractional ticks when the x span is too narrow for its default).
        ncols = len(filtered_scans)
        dx = (xmax - xmin) / ncols
        tick_pos = xmin + (np.arange(ncols) + 0.5) * dx
        tick_labels = [str(int(s)) for s in filtered_scans]
        self.viz_ax.set_xticks(tick_pos)
        self.viz_ax.set_xticklabels(tick_labels)

    def update_wavelength_graph(self, detector_name):
        """Update wavelength vs voltage graph for selected detector."""
        data = self.detector_data[detector_name]
        
        if not data['voltages'] or not data['wavelengths']:
            self.viz_ax.text(0.5, 0.5, 'No data collected yet', 
                           ha='center', va='center', transform=self.viz_ax.transAxes)
            self.viz_ax.set_xlabel('Wavelength (nm)')
            self.viz_ax.set_ylabel('Voltage (V)')
            self.viz_ax.set_title(f'{detector_name} - Wavelength Graph')
            return
        
        # Use consistent length (guard against race where sweep thread appends mid-read)
        n = min(len(data['wavelengths']), len(data['voltages']), len(data['scans']), len(data['timestamps']))
        if n == 0:
            self.viz_ax.text(0.5, 0.5, 'No valid data',
                           ha='center', va='center', transform=self.viz_ax.transAxes)
            self.viz_ax.set_xlabel('Wavelength (nm)')
            self.viz_ax.set_ylabel('Voltage (V)')
            self.viz_ax.set_title(f'{detector_name} - Wavelength Graph')
            return
        wavelengths = np.array(data['wavelengths'][:n])
        voltages = np.array(data['voltages'][:n])
        scans_full = np.array(data['scans'][:n])

        # Filter out invalid data
        valid_mask = np.isfinite(wavelengths) & np.isfinite(voltages)
        if np.sum(valid_mask) == 0:
            self.viz_ax.text(0.5, 0.5, 'No valid data', 
                           ha='center', va='center', transform=self.viz_ax.transAxes)
            self.viz_ax.set_xlabel('Wavelength (nm)')
            self.viz_ax.set_ylabel('Voltage (V)')
            self.viz_ax.set_title(f'{detector_name} - Wavelength Graph')
            return
        
        wavelengths = wavelengths[valid_mask]
        voltages = voltages[valid_mask]
        scans = scans_full[valid_mask]
        
        # Apply user-specified bounds or use data range
        wl_min_data, wl_max_data = np.min(wavelengths), np.max(wavelengths)
        v_min_data, v_max_data = np.min(voltages), np.max(voltages)
        
        wl_min = self.viz_bounds['wl_min'] if self.viz_bounds['wl_min'] is not None else wl_min_data
        wl_max = self.viz_bounds['wl_max'] if self.viz_bounds['wl_max'] is not None else wl_max_data
        v_min = self.viz_bounds['v_min'] if self.viz_bounds['v_min'] is not None else v_min_data
        v_max = self.viz_bounds['v_max'] if self.viz_bounds['v_max'] is not None else v_max_data
        
        # Filter data within bounds
        bound_mask = (wavelengths >= wl_min) & (wavelengths <= wl_max) & \
                     (voltages >= v_min) & (voltages <= v_max)
        filtered_wavelengths = wavelengths[bound_mask]
        filtered_voltages = voltages[bound_mask]
        filtered_scans = scans[bound_mask]
        
        # Plot line graph - plot each scan separately and break at wavelength discontinuities
        # so we never connect across sweep boundaries (even if scan tags are slightly wrong)
        if len(filtered_wavelengths) > 0:
            unique_scans = np.unique(filtered_scans)
            wl_range = wl_max - wl_min
            # Break line only at sweep boundaries (discontinuity larger than this)
            gap_threshold = max(0.5, 0.15 * wl_range)

            for scan_num in unique_scans:
                scan_mask = filtered_scans == scan_num
                scan_wl = np.asarray(filtered_wavelengths[scan_mask])
                scan_v = np.asarray(filtered_voltages[scan_mask])

                if len(scan_wl) == 0:
                    continue
                if len(scan_wl) == 1:
                    self.viz_ax.plot(scan_wl, scan_v, 'b-', linewidth=0.5, alpha=0.7)
                    continue

                # Insert NaN only at sweep boundaries (large discontinuity), not on smooth downsweeps.
                # Break when |dwl| > gap_threshold: large forward jump (new sweep) or large backward jump (turn-around).
                # Do NOT break on small negative dwl (smooth high->low sweep) so downsweeps draw as lines.
                wl_plot = []
                v_plot = []
                for i in range(len(scan_wl)):
                    wl_plot.append(scan_wl[i])
                    v_plot.append(scan_v[i])
                    if i < len(scan_wl) - 1:
                        dwl = scan_wl[i + 1] - scan_wl[i]
                        if abs(dwl) > gap_threshold:
                            wl_plot.append(np.nan)
                            v_plot.append(np.nan)
                wl_plot = np.array(wl_plot)
                v_plot = np.array(v_plot)
                self.viz_ax.plot(wl_plot, v_plot, 'b-', linewidth=0.5, alpha=0.7)
        else:
            self.viz_ax.text(0.5, 0.5, 'No data in specified range', 
                           ha='center', va='center', transform=self.viz_ax.transAxes)
        
        self.viz_ax.set_xlabel('Wavelength (nm)')
        self.viz_ax.set_ylabel('Voltage (V)')
        self.viz_ax.set_title(f'{detector_name} - Wavelength Graph')
        self.viz_ax.grid(True, alpha=0.3)
        
        # Apply axis limits
        self.viz_ax.set_xlim(wl_min, wl_max)
        self.viz_ax.set_ylim(v_min, v_max)

    def _toggle_sweep_type(self, event=None):
        """Show/hide sweep sections based on selected sweep type"""
        sweep_type = self.combo_sweep_type.get()
        if sweep_type == "Step Sweep":
            self.cont_sweep_frame.pack_forget()
            # Pack step sweep frame before action frame to maintain order
            self.sweep_frame.pack(fill="x", padx=10, pady=5, before=self.action_frame)
            # Update action buttons to use step sweep
            self.btn_start.config(command=self.start_sweep_thread)
            self.btn_stop.config(command=self.stop_sweep)
        elif sweep_type == "Continuous Sweep":
            self.sweep_frame.pack_forget()
            # Pack continuous sweep frame before action frame to maintain order
            self.cont_sweep_frame.pack(fill="x", padx=10, pady=5, before=self.action_frame)
            # Update action buttons to use continuous sweep
            self.btn_start.config(command=self.start_continuous_sweep_thread)
            self.btn_stop.config(command=self.stop_continuous_sweep)

    def _toggle_one_way(self, *args):
        """Show/hide downsweep fields based on sweep direction selection"""
        direction = self.combo_sweep_direction.get()
        is_one_way = (direction == "One-way")
        if is_one_way:
            self.lbl_down_time.grid_remove()
            self.ent_down_time.grid_remove()
            self.lbl_down_pixels.grid_remove()
            self.ent_down_pixels.grid_remove()
            self.lbl_down_sub.grid_remove()
            self.ent_down_sub.grid_remove()
        else:
            self.lbl_down_time.grid()
            self.ent_down_time.grid()
            self.lbl_down_pixels.grid()
            self.ent_down_pixels.grid()
            self.lbl_down_sub.grid()
            self.ent_down_sub.grid()

    def connect_lasers_and_switch(self):
        try:
            laser_msg = self.ctrl.connect()
            self.btn_connect_lasers.config(state="disabled")
            self.btn_set_manual.config(state="normal")
            self.btn_set_power.config(state="normal")
            self.btn_start.config(state="normal")

            laser_options = ["Auto"]
            for i, laser in enumerate(self.ctrl.lasers):
                laser_options.append(f"Laser {i+1} ({laser['min']:.1f}-{laser['max']:.1f} nm)")
            self.combo_cont_laser["values"] = laser_options
            self.combo_cont_laser.set("Auto")

            self._refresh_connection_status()
            self.log(f"{laser_msg}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def connect_photodetectors(self):
        try:
            if self.detector_ctrl:
                try:
                    self.detector_ctrl.stop_continuous_sampling()
                except Exception:
                    pass
                self.detector_ctrl = None
            self._init_detectors_defaults()
            self.btn_connect_detectors.config(state="disabled")
            self._refresh_connection_status()
            self.log("Photodetectors (DAQ) connected.")
        except Exception as e:
            self.detector_ctrl = None
            self._refresh_connection_status()
            messagebox.showwarning(
                "Photodetectors (NI-DAQ)",
                "Photodetector init failed:\n\n"
                f"{e}\n\n"
                "Wavelength sweeps can still run if lasers are connected; detector logging will be skipped.",
            )

    def set_manual_wavelength(self):
        try:
            val = float(self.ent_manual_wav.get())
            self.ctrl.set_wavelength(val)
            self.log(f"Manual Set: {val} nm")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def set_manual_power(self):
        try:
            val = float(self.ent_manual_power.get())
            self.ctrl.set_power(val)
            self.log(f"Manual Set Power: {val} dBm")
        except ValueError as e:
            messagebox.showerror("Error", str(e))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def start_sweep_thread(self):
        try:
            # Validate and convert inputs with better error messages
            start_str = self.ent_start.get().strip()
            if not start_str:
                raise ValueError("Start wavelength is required.")
            start = float(start_str)
            
            end_str = self.ent_end.get().strip()
            if not end_str:
                raise ValueError("End wavelength is required.")
            end = float(end_str)
            
            if not self.ctrl.check_valid_range(start, end): 
                raise ValueError("Range invalid.")
            
            up_time_str = self.ent_up_time.get().strip()
            if not up_time_str:
                raise ValueError("Upsweep time is required.")
            up_time = float(up_time_str)
            
            up_pix_str = self.ent_up_pixels.get().strip()
            if not up_pix_str:
                raise ValueError("Up pixels is required.")
            up_pix = int(up_pix_str)
            
            up_sub_str = self.ent_up_sub.get().strip()
            up_sub = max(1, int(up_sub_str)) if up_sub_str else 1
            
            # Get sweep direction from dropdown
            direction = self.combo_sweep_direction.get()
            is_one_way = (direction == "One-way")
            
            down_time_str = self.ent_down_time.get().strip()
            if not is_one_way:
                if not down_time_str:
                    raise ValueError("Downsweep time is required (or select 'One-way' direction).")
                down_time = float(down_time_str)
            else:
                down_time = 0.0  # Not used in one-way mode
            
            down_pix_str = self.ent_down_pixels.get().strip()
            if not is_one_way:
                if not down_pix_str:
                    raise ValueError("Down pixels is required (or select 'One-way' direction).")
                down_pix = int(down_pix_str)
            else:
                down_pix = 0  # Not used in one-way mode
            
            down_sub_str = self.ent_down_sub.get().strip()
            down_sub = max(1, int(down_sub_str)) if down_sub_str else 1
            
            scans_str = self.ent_scans.get().strip()
            if not scans_str:
                raise ValueError("Number of scans is required.")
            scans = int(scans_str)
            
            delay_str = self.ent_delay.get().strip()
            if not delay_str:
                raise ValueError("Delay is required.")
            delay = float(delay_str)
            
            self.sweep_params = {
                'start': start, 'end': end,
                'up_time': up_time,
                'up_pix': up_pix,
                'up_sub': up_sub,
                'down_time': down_time,
                'down_pix': down_pix,
                'down_sub': down_sub,
                'scans': scans,
                'delay': delay,
                'one_way': is_one_way
            }
        except ValueError as e:
            error_msg = str(e)
            if "could not convert" in error_msg.lower() or "invalid literal" in error_msg.lower():
                messagebox.showerror("Input Error", "Please enter valid numbers in all required fields.")
            else:
                messagebox.showerror("Input Error", error_msg)
            return

        self.stop_flag = False
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        threading.Thread(target=self.run_sweep, daemon=True).start()

    def stop_sweep(self):
        self.stop_flag = True
        self.log("Stopping...")

    def start_continuous_sweep_thread(self):
        try:
            # Validate and convert inputs with better error messages
            start_str = self.ent_cont_start.get().strip()
            if not start_str:
                raise ValueError("Start wavelength is required.")
            start = float(start_str)
            
            end_str = self.ent_cont_end.get().strip()
            if not end_str:
                raise ValueError("End wavelength is required.")
            end = float(end_str)
            
            speed = int(self.combo_cont_speed.get())
            mode_str = self.combo_cont_mode.get()
            mode = 1 if mode_str == "One-way" else 3
            
            scans_str = self.ent_cont_scans.get().strip()
            if not scans_str:
                raise ValueError("Number of scans is required.")
            scans = int(scans_str)
            
            delay_str = self.ent_cont_delay.get().strip()
            if not delay_str:
                raise ValueError("Delay is required.")
            delay = float(delay_str)
            
            # Determine which laser to use
            laser = None
            laser_selection = self.combo_cont_laser.get()
            if laser_selection == "Auto":
                laser = self.ctrl.check_continuous_range(start, end)
                if not laser:
                    raise ValueError(f"Range {start}-{end} nm is not within any single laser's range.")
            else:
                # Extract laser index from selection (e.g., "Laser 1 (...)" -> index 0)
                laser_idx = int(laser_selection.split()[1]) - 1
                if laser_idx < 0 or laser_idx >= len(self.ctrl.lasers):
                    raise ValueError("Invalid laser selection.")
                laser = self.ctrl.lasers[laser_idx]
                if not (laser['min'] <= start <= laser['max'] and laser['min'] <= end <= laser['max']):
                    raise ValueError(f"Range {start}-{end} nm is not within selected laser's range ({laser['min']:.1f}-{laser['max']:.1f} nm).")
            
            self.cont_sweep_params = {
                'laser': laser,
                'start': start,
                'end': end,
                'speed': speed,
                'mode': mode,
                'scans': scans,
                'delay': delay
            }
        except ValueError as e:
            error_msg = str(e)
            if "could not convert" in error_msg.lower() or "invalid literal" in error_msg.lower():
                messagebox.showerror("Input Error", "Please enter valid numbers in all required fields.")
            else:
                messagebox.showerror("Input Error", error_msg)
            return

        self.stop_flag = False
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        threading.Thread(target=self.run_continuous_sweep, daemon=True).start()

    def stop_continuous_sweep(self):
        self.stop_flag = True
        if hasattr(self, 'cont_sweep_params'):
            try:
                self.ctrl.stop_continuous_sweep(self.cont_sweep_params['laser'])
            except:
                pass
        self.log("Stopping continuous sweep...")

    def run_continuous_sweep(self):
        p = self.cont_sweep_params
        mark_santec_daq_busy()
        self.log(f"--- Starting Continuous Sweep ---")
        self.log(f"Laser: {p['laser']['ip']} ({p['laser']['min']:.1f}-{p['laser']['max']:.1f} nm)")
        self.log(f"Range: {p['start']:.3f} - {p['end']:.3f} nm")
        self.log(f"Speed: {p['speed']} nm/s, Mode: {'One-way' if p['mode'] == 1 else 'Two-way'}")
        self.log(f"Number of scans: {p['scans']}")
        
        # Initialize scan counter and continuous sampling
        self.current_scan = 0
        sweep_start_time = None
        scan_start_time = None
        wavelength_range = p['end'] - p['start']  # Can be negative for backwards (start > end)
        sweep_duration = abs(p['end'] - p['start']) / p['speed']  # Time for one-way sweep (always positive)
        sample_rate = int(self.ent_sample_rate.get().strip() or "200")  # For diagnostics and expected-points
        expected_points_one_way = int(sweep_duration * sample_rate)
        expected_points_two_way = int(2 * sweep_duration * sample_rate)
        
        # Start continuous sampling if detectors are initialized
        if self.detector_ctrl:
            try:
                self.detector_ctrl.start_continuous_sampling(sample_rate_hz=sample_rate)
                self.log(f"Continuous sampling started at {sample_rate} Hz")
            except Exception as e:
                self.log(f"Warning: Could not start continuous sampling: {e}")
                self.detector_ctrl = None

        try:
            # Ensure sweep is stopped before configuring
            self.ctrl.stop_continuous_sweep(p['laser'])
            time.sleep(0.2)  # Brief pause to ensure stop command is processed

            # Configure the sweep
            self.ctrl.configure_continuous_sweep(p['laser'], p['start'], p['end'], p['speed'], p['mode'])
            self.log("Sweep configured.")

            # Use repeat scan command for multiple scans
            # The repeat command will handle the repeats, but we need to monitor and stop after desired number
            completed_scans = 0
            last_status = None
            sweep_running = False
            
            # Start the repeat scan
            self.ctrl.start_repeat_sweep(p['laser'])
            self.log("Repeat scan started.")
            n_scans = p['scans']
            self.root.after(0, lambda: self._set_experiment_status(f"Experiment: Running — starting (0/{n_scans} scans)"))
            time.sleep(0.2)  # Brief pause to allow sweep to start

            first_stored_logged = True
            start_aligned = True
            last_stored_ts_current_scan = None  # O(1) completion check: avoid scanning full detector_data each iteration
            last_stored_wl_current_scan = None
            # Debounce + time-gate: laser reports status=0 at two-way turn-around; only complete after full cycle
            poll_interval_s = 0.01
            status_0_debounce_count = 0
            status_0_required = max(5, int(0.2 / poll_interval_s))  # ~0.2 s of status=0

            # Monitor sweep and count completed scans
            main_loop_skipped_cycle_cap = 0  # two-way: count skips due to elapsed > cycle_time
            while completed_scans < p['scans']:
                if self.stop_flag:
                    self.ctrl.stop_continuous_sweep(p['laser'])
                    break
                
                status = self.ctrl.get_sweep_status(p['laser'])
                
                # Track when sweep is running
                if status == 1:  # Running
                    status_0_debounce_count = 0
                    if not sweep_running:
                        sweep_running = True
                        scan_start_time = time.time()
                        if sweep_start_time is None:
                            sweep_start_time = scan_start_time
                        self.current_scan = completed_scans + 1
                        cur, n = self.current_scan, p['scans']
                        self.root.after(0, lambda c=cur, tot=n: self._set_experiment_status(f"Experiment: Running — scan {c}/{tot}"))
                        first_stored_logged = False
                        start_aligned = False
                        last_stored_ts_current_scan = None
                        last_stored_wl_current_scan = None
                        main_loop_skipped_cycle_cap = 0
                        points_stored_this_scan = 0
                        expected_pts_this_scan = expected_points_one_way if p['mode'] == 1 else expected_points_two_way
                        # Re-sync detector timestamps to wall clock so samples after delay are not skipped
                        if self.detector_ctrl and self.detector_ctrl.continuous_running:
                            self.detector_ctrl.reset_continuous_timeline()
                        # #region agent log
                        if p['mode'] != 1:
                            _ct = 2 * sweep_duration
                            try:
                                _f = open("debug-7fa4f7.log", "a")
                                _f.write('{"sessionId":"7fa4f7","hypothesisId":"H4","location":"main.py:scan_start","message":"two-way scan start","data":{"cycle_time":%s,"sweep_duration":%s,"sample_rate":%s,"expected_two_way":%s},"timestamp":%d}\n' % (_ct, sweep_duration, sample_rate, expected_points_two_way, int(time.time()*1000)))
                                _f.close()
                            except Exception: pass
                        # #endregion
                
                # Read continuous samples and correlate with wavelength
                if self.detector_ctrl and self.detector_ctrl.continuous_running:
                    try:
                        samples1, samples2, samples3, timestamps = self.detector_ctrl.read_continuous_samples()
                        if samples1 is not None and len(samples1) > 0 and scan_start_time is not None:
                            for i, ts in enumerate(timestamps):
                                elapsed = ts - scan_start_time
                                # Skip pre-start buffer (fixes scan 2 wrong first point and negative elapsed)
                                if elapsed < 0:
                                    continue
                                
                                # Align clock to first stored sample so first point is at start wavelength
                                if not start_aligned:
                                    scan_start_time = ts
                                    elapsed = 0.0
                                    start_aligned = True
                                    wavelength = p['start']
                                    if not first_stored_logged:
                                        print(f"[DIAG start] scan={self.current_scan} first_stored: ts={ts:.4f} elapsed=0 (aligned) wl={wavelength:.4f}")
                                        first_stored_logged = True
                                else:
                                    elapsed = ts - scan_start_time
                                    if p['mode'] == 1:  # One-way: only store within sweep window to get exact expected count
                                        if elapsed > sweep_duration:
                                            continue
                                        wavelength = p['start'] + (elapsed / sweep_duration) * wavelength_range
                                    else:  # Two-way: only store within one full cycle to get exact expected count
                                        cycle_time = 2 * sweep_duration
                                        if elapsed > cycle_time:
                                            main_loop_skipped_cycle_cap += 1
                                            continue
                                        if elapsed >= cycle_time:
                                            wavelength = p['start']
                                        else:
                                            cycle_pos = elapsed / cycle_time
                                            if cycle_pos < 0.5:
                                                wavelength = p['start'] + (cycle_pos * 2) * wavelength_range
                                            else:
                                                wavelength = p['end'] - ((cycle_pos - 0.5) * 2) * wavelength_range
                                    if not first_stored_logged:
                                        print(f"[DIAG start] scan={self.current_scan} first_stored: ts={ts:.4f} elapsed={elapsed:.4f}s wl={wavelength:.4f}")
                                        first_stored_logged = True
                                
                                # Hard cap: never store more than expected points per scan.
                                if points_stored_this_scan >= expected_pts_this_scan:
                                    continue
                                # Store data for both detectors
                                self.detector_data['PDA50B2']['voltages'].append(float(samples1[i]))
                                self.detector_data['PDA50B2']['wavelengths'].append(wavelength)
                                self.detector_data['PDA50B2']['scans'].append(self.current_scan)
                                self.detector_data['PDA50B2']['timestamps'].append(ts)
                                last_stored_ts_current_scan = ts
                                last_stored_wl_current_scan = wavelength
                                
                                self.detector_data['PDA10CS2']['voltages'].append(float(samples2[i]))
                                self.detector_data['PDA10CS2']['wavelengths'].append(wavelength)
                                self.detector_data['PDA10CS2']['scans'].append(self.current_scan)
                                self.detector_data['PDA10CS2']['timestamps'].append(ts)
                                points_stored_this_scan += 1
                    except Exception as e:
                        # Silently handle read errors during continuous sampling
                        pass
                
                # Debounce: only count consecutive status=0
                if status == 0:
                    status_0_debounce_count += 1
                else:
                    status_0_debounce_count = 0

                elapsed_s = (time.time() - scan_start_time) if scan_start_time is not None else 0.0
                expected_cycle_s = 2 * sweep_duration if p['mode'] != 1 else sweep_duration
                # Two-way: we cap stored data at elapsed <= cycle_time. With discrete sampling the last sample
                # is at cycle_time - dt, so allow completion when within one sample period of full cycle.
                sample_period = 1.0 / sample_rate
                min_elapsed_for_complete = max(0.0, expected_cycle_s - sample_period) if p['mode'] != 1 else 0.0

                # Two-way: gate completion on *data* time (last stored sample). Use O(1) tracked values.
                wl_near_start_ok = True
                elapsed_data_s = elapsed_s
                if p['mode'] != 1 and sweep_running and scan_start_time is not None:
                    if last_stored_ts_current_scan is not None and last_stored_wl_current_scan is not None:
                        elapsed_data_s = last_stored_ts_current_scan - scan_start_time
                        wl_span = abs(p['end'] - p['start'])
                        wl_near_start_ok = abs(last_stored_wl_current_scan - p['start']) <= 0.15 * wl_span if wl_span > 0 else True
                    else:
                        wl_near_start_ok = False
                        elapsed_data_s = 0.0
                    if elapsed_s >= 1.15 * expected_cycle_s:
                        wl_near_start_ok = True  # wall-clock fallback to avoid stuck
                elapsed_ok = elapsed_data_s >= min_elapsed_for_complete
                # Two-way: when data arrives faster than nominal we hit point cap before min_elapsed; allow completion by wall clock.
                if p['mode'] != 1 and sweep_running and points_stored_this_scan >= expected_points_two_way and elapsed_s >= expected_cycle_s:
                    elapsed_ok = True
                force_complete = sweep_running and (
                    elapsed_data_s >= expected_cycle_s if p['mode'] == 1
                    else (elapsed_data_s >= min_elapsed_for_complete or (points_stored_this_scan >= expected_points_two_way and elapsed_s >= expected_cycle_s))
                )

                # Only declare complete when status=0 for debounce period AND (two-way) elapsed >= full cycle AND last wl near start
                if ((status == 0 and sweep_running and status_0_debounce_count >= status_0_required and elapsed_ok) or force_complete) and wl_near_start_ok:
                    # Drain buffer for this scan before declaring complete (so every scan gets full data).
                    # Only add samples with ts > last_stored_ts_current_scan to avoid double-counting.
                    drain_scan_start_time = scan_start_time
                    drain_current_scan = self.current_scan
                    drain_ts_cutoff = last_stored_ts_current_scan  # Only append drain samples after this
                    drain_expected_pts = expected_points_one_way if p['mode'] == 1 else expected_points_two_way
                    if self.detector_ctrl and self.detector_ctrl.continuous_running and drain_scan_start_time is not None:
                        drain_added = 0
                        n_pts_before_drain = sum(1 for s in self.detector_data['PDA50B2']['scans'] if s == drain_current_scan)
                        empty_reads = 0
                        max_empty = 1  # Exit after one empty read to minimize gap between scans
                        for _ in range(50):
                            try:
                                s1, s2, s3, timestamps = self.detector_ctrl.read_continuous_samples(timeout=0.15)
                                if s1 is None or len(s1) == 0:
                                    empty_reads += 1
                                    if empty_reads >= max_empty:
                                        break
                                    time.sleep(0.02)
                                    continue
                                empty_reads = 0
                                for i, ts in enumerate(timestamps):
                                    if n_pts_before_drain + drain_added >= drain_expected_pts:
                                        break  # Hard cap: don't add more than expected per scan
                                    if drain_ts_cutoff is not None and ts <= drain_ts_cutoff:
                                        continue  # Already stored by main loop; avoid duplicate
                                    elapsed = ts - drain_scan_start_time
                                    if elapsed < 0:
                                        continue
                                    if p['mode'] == 1:  # One-way: only add drain samples within sweep window
                                        if elapsed > sweep_duration:
                                            continue
                                        wavelength = p['start'] + (elapsed / sweep_duration) * wavelength_range
                                    else:  # Two-way: only add drain samples within one full cycle
                                        cycle_time = 2 * sweep_duration
                                        if elapsed > cycle_time:
                                            continue
                                        if elapsed >= cycle_time:
                                            wavelength = p['start']
                                        else:
                                            cycle_pos = elapsed / cycle_time
                                            if cycle_pos < 0.5:
                                                wavelength = p['start'] + (cycle_pos * 2) * wavelength_range
                                            else:
                                                wavelength = p['end'] - ((cycle_pos - 0.5) * 2) * wavelength_range
                                    self.detector_data['PDA50B2']['voltages'].append(float(s1[i]))
                                    self.detector_data['PDA50B2']['wavelengths'].append(wavelength)
                                    self.detector_data['PDA50B2']['scans'].append(drain_current_scan)
                                    self.detector_data['PDA50B2']['timestamps'].append(ts)
                                    self.detector_data['PDA10CS2']['voltages'].append(float(s2[i]))
                                    self.detector_data['PDA10CS2']['wavelengths'].append(wavelength)
                                    self.detector_data['PDA10CS2']['scans'].append(drain_current_scan)
                                    self.detector_data['PDA10CS2']['timestamps'].append(ts)
                                    drain_added += 1
                                if n_pts_before_drain + drain_added >= drain_expected_pts:
                                    break
                                time.sleep(0.02)
                            except Exception:
                                break
                        expected_pts = expected_points_one_way if p['mode'] == 1 else expected_points_two_way
                        print(f"[DIAG drain] scan={drain_current_scan}  points_added={drain_added}  expected_this_scan={expected_pts}")
                        if drain_added > 0:
                            self.log(f"Drain complete: {drain_added} points added to scan {drain_current_scan}.")

                    # 0-point guard: only count scan complete if we have at least one point
                    det = 'PDA50B2'
                    wl_arr = np.array(self.detector_data[det]['wavelengths'])
                    sc_arr = np.array(self.detector_data[det]['scans'])
                    mask = (sc_arr == drain_current_scan)
                    n_pts = int(np.sum(mask))
                    expected_pts = expected_points_one_way if p['mode'] == 1 else expected_points_two_way
                    # #region agent log
                    if p['mode'] != 1:
                        try:
                            _el = (last_stored_ts_current_scan - drain_scan_start_time) if (drain_scan_start_time is not None and last_stored_ts_current_scan is not None) else None
                            _elj = "null" if _el is None else ("%.4f" % _el)
                            _f = open("debug-7fa4f7.log", "a")
                            _f.write('{"sessionId":"7fa4f7","hypothesisId":"H1,H2,H3,H5","location":"main.py:scan_complete","message":"two-way completion","data":{"scan":%s,"n_pts":%s,"expected_pts":%s,"drain_added":%s,"main_loop_skipped_cycle_cap":%s,"last_stored_elapsed_s":%s},"timestamp":%d}\n' % (drain_current_scan, n_pts, expected_pts, drain_added, main_loop_skipped_cycle_cap, _elj, int(time.time()*1000)))
                            _f.close()
                        except Exception: pass
                    # #endregion

                    if n_pts == 0:
                        self.log(f"Warning: scan {drain_current_scan} has 0 points; not counting as complete, retrying sweep.")
                        print(f"[DIAG 0-point] scan={drain_current_scan}  skipping completion, retrying.")
                        sweep_running = False
                        scan_start_time = None
                        status_0_debounce_count = 0
                        if not self.stop_flag:
                            self.ctrl.start_repeat_sweep(p['laser'])
                            time.sleep(0.2)
                    else:
                        completed_scans += 1
                        done, tot = completed_scans, p['scans']
                        self.root.after(0, lambda d=done, t=tot: self._set_experiment_status(f"Experiment: Running — scan {d}/{t} completed"))
                        last_idx = np.where(mask)[0][-1]
                        last_wl = float(wl_arr[last_idx])
                        print(f"[DIAG end] scan={completed_scans}  points={n_pts}  expected={expected_pts}  last_stored_wl={last_wl:.4f}  elapsed_since_start={elapsed_s:.3f}s  expected_cycle_s={expected_cycle_s:.3f}")
                        self.log(f"Scan {completed_scans}/{p['scans']} completed.")
                        self.root.after(0, self._update_visualization)
                        sweep_running = False
                        scan_start_time = None
                        status_0_debounce_count = 0

                        if completed_scans >= p['scans']:
                            self.ctrl.stop_continuous_sweep(p['laser'])
                            break

                        # Wait for delay before next scan (if not last scan)
                        if completed_scans < p['scans']:
                            self.log(f"Waiting {p['delay']} s before next scan...")
                            delay_start = time.time()
                            while time.time() - delay_start < p['delay']:
                                if self.stop_flag:
                                    self.ctrl.stop_continuous_sweep(p['laser'])
                                    break
                                time.sleep(0.1)
                            
                            # Restart repeat scan after delay if not stopped
                            if not self.stop_flag:
                                self.ctrl.start_repeat_sweep(p['laser'])
                                time.sleep(0.2)  # Brief pause to allow sweep to start
                
                last_status = status
                time.sleep(0.01)  # Check more frequently for better sampling

        except Exception as e:
            self.log(f"Error: {e}")
        finally:
            clear_santec_daq_busy()
            # Stop continuous sampling
            if self.detector_ctrl:
                try:
                    self.detector_ctrl.stop_continuous_sampling()
                except:
                    pass
            
            try:
                self.ctrl.stop_continuous_sweep(p['laser'])
            except:
                pass
            self.log("Continuous sweep done.")
            self.stop_flag = False
            self.root.after(0, lambda: self._set_experiment_status("Experiment: Idle"))
            # Final visualization update
            if self.detector_ctrl:
                self.root.after(0, self._update_visualization)
            self.root.after(0, lambda: [self.btn_start.config(state="normal"), self.btn_stop.config(state="disabled")])

    def run_sweep(self):
        p = self.sweep_params
        mark_santec_daq_busy()
        self.log(f"--- Starting Sweep ---")
        total_up = p['up_pix'] * p['up_sub']
        total_down = p['down_pix'] * p['down_sub']
        n_scans = p['scans']
        self.root.after(0, lambda: self._set_experiment_status(f"Experiment: Running — starting (0/{n_scans} scans)"))
        
        # Initialize scan counter
        self.current_scan = 0

        try:
            self.ctrl.set_wavelength(p['start'])
            time.sleep(1.0)

            for i in range(p['scans']):
                if self.stop_flag: break
                self.current_scan = i + 1
                cur, tot = self.current_scan, p['scans']
                self.root.after(0, lambda c=cur, t=tot: self._set_experiment_status(f"Experiment: Running — scan {c}/{t}"))
                self.log(f"Scan {i+1}/{p['scans']}")

                if total_up > 0:
                    step_nm = (p['end'] - p['start']) / total_up
                    start_t = time.perf_counter()
                    for step in range(1, total_up + 1):
                        if self.stop_flag: break
                        current_wavelength = p['start'] + (step * step_nm)
                        self.ctrl.set_wavelength(current_wavelength)
                        
                        # Read detectors if initialized
                        if self.detector_ctrl:
                            try:
                                if self.detector_ctrl.channel3:
                                    v1, v2, _ = self.detector_ctrl.read_three_detectors()
                                else:
                                    v1, v2 = self.detector_ctrl.read_both_detectors()
                                self.detector_data['PDA50B2']['voltages'].append(v1)
                                self.detector_data['PDA50B2']['wavelengths'].append(current_wavelength)
                                self.detector_data['PDA50B2']['scans'].append(self.current_scan)
                                self.detector_data['PDA50B2']['timestamps'].append(time.time())
                                
                                self.detector_data['PDA10CS2']['voltages'].append(v2)
                                self.detector_data['PDA10CS2']['wavelengths'].append(current_wavelength)
                                self.detector_data['PDA10CS2']['scans'].append(self.current_scan)
                                self.detector_data['PDA10CS2']['timestamps'].append(time.time())
                            except Exception as e:
                                self.log(f"Warning: Detector read error: {e}")
                        
                        elapsed = time.perf_counter() - start_t
                        target = (step / total_up) * p['up_time']
                        if target > elapsed: time.sleep(target - elapsed)

                if self.stop_flag: break

                if not p['one_way'] and total_down > 0:
                    step_nm = (p['end'] - p['start']) / total_down
                    start_t = time.perf_counter()
                    for step in range(1, total_down + 1):
                        if self.stop_flag: break
                        current_wavelength = p['end'] - (step * step_nm)
                        self.ctrl.set_wavelength(current_wavelength)
                        
                        # Read detectors if initialized
                        if self.detector_ctrl:
                            try:
                                if self.detector_ctrl.channel3:
                                    v1, v2, _ = self.detector_ctrl.read_three_detectors()
                                else:
                                    v1, v2 = self.detector_ctrl.read_both_detectors()
                                self.detector_data['PDA50B2']['voltages'].append(v1)
                                self.detector_data['PDA50B2']['wavelengths'].append(current_wavelength)
                                self.detector_data['PDA50B2']['scans'].append(self.current_scan)
                                self.detector_data['PDA50B2']['timestamps'].append(time.time())
                                
                                self.detector_data['PDA10CS2']['voltages'].append(v2)
                                self.detector_data['PDA10CS2']['wavelengths'].append(current_wavelength)
                                self.detector_data['PDA10CS2']['scans'].append(self.current_scan)
                                self.detector_data['PDA10CS2']['timestamps'].append(time.time())
                            except Exception as e:
                                self.log(f"Warning: Detector read error: {e}")
                        
                        elapsed = time.perf_counter() - start_t
                        target = (step / total_down) * p['down_time']
                        if target > elapsed: time.sleep(target - elapsed)
                elif p['one_way'] and i < p['scans'] - 1:
                    # Reset to start position for next scan
                    self.ctrl.set_wavelength(p['start'])
                    time.sleep(0.5)  # Brief pause after reset

                # Update visualization after each scan
                if self.detector_ctrl:
                    self.root.after(0, self._update_visualization)

                if i < p['scans'] - 1: time.sleep(p['delay'])

        except Exception as e:
            self.log(f"Error: {e}")
        finally:
            clear_santec_daq_busy()
            self.log("Done.")
            self.stop_flag = False
            self.root.after(0, lambda: self._set_experiment_status("Experiment: Idle"))
            # Final visualization update
            if self.detector_ctrl:
                self.root.after(0, self._update_visualization)
            self.root.after(0, lambda: [self.btn_start.config(state="normal"), self.btn_stop.config(state="disabled")])

    # --- CORRECTED: Defined INSIDE the class ---
    def on_closing(self):
        self.stop_flag = True
        clear_santec_daq_busy()
        # Stop any running continuous sweeps
        if hasattr(self, 'cont_sweep_params'):
            try:
                self.ctrl.stop_continuous_sweep(self.cont_sweep_params['laser'])
            except:
                pass
        # Stop detector continuous sampling
        if self.detector_ctrl:
            try:
                self.detector_ctrl.stop_continuous_sampling()
            except:
                pass
        try:
            self.ctrl.close()
        except:
            pass
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = LaserSweepApp(root)
    # Now we can reference on_closing correctly
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()