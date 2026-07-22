import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import yaml

from qt3utils.config_loader import merge_shared_positioners_into_app_config

from microstage.encoderless_wrapper import EncoderlessMicrostage
from piezo.nidaq_position import NidaqPositionController

CONFIG_FILE = 'qt3move_base.yaml'

# --- Tooltip Class ---
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.on_enter)
        self.widget.bind("<Leave>", self.on_leave)
        self.widget.bind("<Motion>", self.on_motion)
    
    def on_enter(self, event=None):
        self.show_tooltip(event)
    
    def on_motion(self, event=None):
        if self.tooltip_window:
            self.show_tooltip(event)
    
    def show_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
        
        x = self.widget.winfo_rootx() + self.widget.winfo_width() + 5
        y = self.widget.winfo_rooty() + 5
        
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(self.tooltip_window, text=self.text, 
                       background="yellow", foreground="black",
                       relief="solid", borderwidth=1, padx=5, pady=3,
                       font=("Arial", 9), wraplength=200)
        label.pack()
    
    def on_leave(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
    
    def update_text(self, new_text):
        self.text = new_text

# --- Main Application ---
class Qt3MoveApp(tk.Tk):
    def __init__(self, config_file=None):
        super().__init__()
        self.title("QT3 Move Controller")
        self.resizable(False, False)

        # Load configuration
        self.config = self._load_config(config_file)
        
        # --- Initialize Hardware Connections ---
        self.stage = None
        self.piezo_x = None
        self.piezo_y = None
        self.piezo_z = None
        
        # Initialize microstage
        try:
            microstage_config = self._get_microstage_config()
            self.stage = EncoderlessMicrostage(microstage_config)
            print("Microstage initialized successfully")
        except Exception as e:
            messagebox.showerror(
                "Microstage Connection Error",
                f"Could not initialize microstage controller.\n\nError: {e}"
            )
            # Don't destroy, continue with piezo only
        
        # Initialize piezo controllers
        try:
            piezo_configs = self._get_piezo_configs()
            if 'PiezoX' in piezo_configs:
                self.piezo_x = NidaqPositionController(**piezo_configs['PiezoX'])
                self.piezo_x.configure(piezo_configs['PiezoX'])
            if 'PiezoY' in piezo_configs:
                self.piezo_y = NidaqPositionController(**piezo_configs['PiezoY'])
                self.piezo_y.configure(piezo_configs['PiezoY'])
            if 'PiezoZ' in piezo_configs:
                self.piezo_z = NidaqPositionController(**piezo_configs['PiezoZ'])
                self.piezo_z.configure(piezo_configs['PiezoZ'])
            print("Piezo controllers initialized successfully")
        except Exception as e:
            messagebox.showerror(
                "Piezo Connection Error",
                f"Could not initialize piezo controllers.\n\nError: {e}"
            )
            # Continue without piezo controllers

        # --- GUI State Variables ---
        # Microstage variables
        self.x_set_var = tk.StringVar(value="0.0")
        self.y_set_var = tk.StringVar(value="0.0")
        self.step_var = tk.StringVar(value="1.0")
        self.step_axis_var = tk.StringVar(value="X")
        self.x_current_var = tk.StringVar(value="--")
        self.y_current_var = tk.StringVar(value="--")
        self.is_homed = False
        self.stepping_warning_shown = False
        
        # Movement indicator variables
        self.microstage_status_var = tk.StringVar(value="Ready")
        self.movement_in_progress = False
        
        # Stepping control variables
        self.stepping_controller_var = tk.StringVar(value="None")
        
        # Piezo variables
        self.piezo_x_set_var = tk.StringVar(value="0.0")
        self.piezo_y_set_var = tk.StringVar(value="0.0")
        self.piezo_z_set_var = tk.StringVar(value="0.0")
        self.piezo_x_current_var = tk.StringVar(value="---")
        self.piezo_y_current_var = tk.StringVar(value="---")
        self.piezo_z_current_var = tk.StringVar(value="---")

        self._create_widgets()
        
        # Initialize piezo position displays
        self._initialize_piezo_displays()
        
        self._update_position_display()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _load_config(self, config_file=None):
        """Load configuration from YAML file"""
        if config_file is None:
            config_file = CONFIG_FILE
        
        try:
            with open(config_file, 'r') as file:
                config = yaml.safe_load(file)
            if config:
                merge_shared_positioners_into_app_config(config)
            print(f"Loaded configuration from: {config_file}")
            return config
        except FileNotFoundError:
            print(f"Warning: Configuration file {config_file} not found. Using defaults.")
            return {}
        except Exception as e:
            print(f"Warning: Error loading configuration: {e}. Using defaults.")
            return {}

    def _get_microstage_config(self):
        """Extract microstage configuration from the loaded YAML config"""
        if not self.config:
            return None
        
        app_name = list(self.config.keys())[0] if self.config else None
        if not app_name or 'Microstage' not in self.config[app_name]:
            return None
        
        microstage_config = self.config[app_name]['Microstage'].get('configure', {})
        print(f"Microstage configuration: {microstage_config}")
        return microstage_config

    def _get_piezo_configs(self):
        """Extract piezo configurations from the loaded YAML config"""
        if not self.config:
            return {}
        
        app_name = list(self.config.keys())[0] if self.config else None
        if not app_name:
            return {}
        
        piezo_configs = {}
        piezo_axes = ['PiezoX', 'PiezoY', 'PiezoZ']
        
        for axis in piezo_axes:
            if axis in self.config[app_name]:
                config = self.config[app_name][axis].get('configure', {})
                # Convert config keys to match NidaqPositionController constructor
                piezo_configs[axis] = {
                    'device_name': config.get('device_name', 'Dev1'),
                    'write_channel': config.get('write_channel', 'ao0'),
                    'read_channel': config.get('read_channel', None),
                    'move_settle_time': config.get('move_settle_time', 0.0),
                    'scale_microns_per_volt': config.get('scale_microns_per_volt', 5.0),
                    'zero_microns_volt_offset': config.get('zero_microns_volt_offset', 5.0),
                    'min_position': config.get('min_position', -25.0),
                    'max_position': config.get('max_position', 25.0),
                    'invert_axis': config.get('invert_axis', False)
                }
                print(f"{axis} configuration: {piezo_configs[axis]}")
        
        return piezo_configs

    def _piezo_axis_values_for_ui(self):
        """Piezo axes present in hardware (for stepping axis combobox)."""
        vals = []
        if self.piezo_x:
            vals.append("X")
        if self.piezo_y:
            vals.append("Y")
        if self.piezo_z:
            vals.append("Z")
        return vals

    def _sync_step_axis_for_controller(self):
        """Keep axis combobox values and selection valid when switching Microstage / Piezo."""
        c = self.stepping_controller_var.get()
        if c not in ("Microstage", "Piezo"):
            return
        cur = self.step_axis_var.get()
        if c == "Microstage":
            vals = ["X", "Y"]
            self._microstage_axis_combo.configure(values=vals)
            if cur not in vals:
                self.step_axis_var.set("X")
        else:
            vals = self._piezo_axis_values_for_ui()
            self._piezo_axis_combo.configure(values=vals if vals else ["X"])
            if vals and cur not in vals:
                self.step_axis_var.set(vals[0])

    def _initialize_piezo_displays(self):
        """Initialize piezo position displays; show --- until user sets a position."""
        if self.piezo_x:
            try:
                pos = self.piezo_x.get_last_commanded_position()
                if pos is not None:
                    self.piezo_x_set_var.set(f"{pos:.3f}")
                    self.piezo_x_current_var.set(f"{pos:.3f}")
                else:
                    self.piezo_x_current_var.set("---")
            except Exception as e:
                print(f"Error initializing piezo X display: {e}")
        
        if self.piezo_y:
            try:
                pos = self.piezo_y.get_last_commanded_position()
                if pos is not None:
                    self.piezo_y_set_var.set(f"{pos:.3f}")
                    self.piezo_y_current_var.set(f"{pos:.3f}")
                else:
                    self.piezo_y_current_var.set("---")
            except Exception as e:
                print(f"Error initializing piezo Y display: {e}")
        
        if self.piezo_z:
            try:
                pos = self.piezo_z.get_last_commanded_position()
                if pos is not None:
                    self.piezo_z_set_var.set(f"{pos:.3f}")
                    self.piezo_z_current_var.set(f"{pos:.3f}")
                else:
                    self.piezo_z_current_var.set("---")
            except Exception as e:
                print(f"Error initializing piezo Z display: {e}")

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")

        # --- Homing and Setup Frame ---
        setup_frame = ttk.LabelFrame(main_frame, text="Setup", padding="10")
        setup_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        setup_frame.columnconfigure((0, 1, 2), weight=1)
        
        find_home_button = ttk.Button(setup_frame, text="Calibrate Stage", command=self._find_home)
        find_home_button.grid(row=0, column=0, padx=5, sticky="ew")
        ToolTip(find_home_button, "Calibrate Stage: Sets the origin (0,0) at the bottom-right corner. Maximum position (top-left corner) is (12000, 12000). Positive X is to the left, positive Y is upward.")
        
        ttk.Button(setup_frame, text="Return to Home", command=self._return_to_home).grid(row=0, column=1, padx=5, sticky="ew")
        ttk.Button(setup_frame, text="Move to Center", command=self._move_to_center).grid(row=0, column=2, padx=5, sticky="ew")

        # --- Main Position Control Frame ---
        control_frame = ttk.LabelFrame(main_frame, text="Microstage Control", padding="10")
        control_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        # Header Labels
        ttk.Label(control_frame, text="Set Value (µm)").grid(row=0, column=2, padx=5, pady=5)
        ttk.Label(control_frame, text="Current (µm)").grid(row=0, column=3, padx=5, pady=5)

        # X-Axis Controls
        ttk.Label(control_frame, text="X axis").grid(row=1, column=0, sticky="w", padx=5)
        ttk.Button(control_frame, text="Set Position", command=self._set_x_position).grid(row=1, column=1, padx=5)
        ttk.Entry(control_frame, textvariable=self.x_set_var, width=10).grid(row=1, column=2)
        ttk.Label(control_frame, textvariable=self.x_current_var, width=10, relief="sunken", anchor="center").grid(row=1, column=3, padx=5)
        
        # Y-Axis Controls
        ttk.Label(control_frame, text="Y axis").grid(row=2, column=0, sticky="w", padx=5, pady=(5,0))
        ttk.Button(control_frame, text="Set Position", command=self._set_y_position).grid(row=2, column=1, padx=5, pady=(5,0))
        ttk.Entry(control_frame, textvariable=self.y_set_var, width=10).grid(row=2, column=2, pady=(5,0))
        ttk.Label(control_frame, textvariable=self.y_current_var, width=10, relief="sunken", anchor="center").grid(row=2, column=3, padx=5, pady=(5,0))
        
        # Overall microstage status
        ttk.Label(control_frame, text="Microstage:").grid(row=3, column=0, sticky="w", padx=5, pady=(10,0))
        self.microstage_status_label = ttk.Label(control_frame, textvariable=self.microstage_status_var, width=20, relief="sunken", anchor="center")
        self.microstage_status_label.grid(row=3, column=1, columnspan=2, padx=5, pady=(10,0))
        
        # Create tooltip for status label - will update based on status
        self.microstage_status_tooltip = ToolTip(self.microstage_status_label, 
                                                  "Status: Ready")

        # --- Stepping Control Frame ---
        stepping_frame = ttk.LabelFrame(main_frame, text="Stepping Control", padding="10")
        stepping_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
        
        # Stepping controller selection
        ttk.Label(stepping_frame, text="Enable keyboard stepping for:").grid(row=0, column=0, sticky="w", padx=5, pady=(0, 5))
        stepping_controller_combo = ttk.Combobox(
            stepping_frame, 
            textvariable=self.stepping_controller_var,
            values=["None", "Microstage", "Piezo"],
            state="readonly",
            width=15
        )
        stepping_controller_combo.grid(row=0, column=1, sticky="w", padx=5, pady=(0, 5))
        stepping_controller_combo.bind("<<ComboboxSelected>>", self._on_stepping_controller_changed)
        
        # Microstage stepping controls
        self.microstage_stepping_frame = ttk.Frame(stepping_frame)
        self.microstage_stepping_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        
        ttk.Label(self.microstage_stepping_frame, text="Step (µm):").grid(row=0, column=0, sticky="w", padx=5)
        microstage_step_entry = ttk.Entry(self.microstage_stepping_frame, textvariable=self.step_var, width=10)
        microstage_step_entry.grid(row=0, column=1, padx=5)
        _ms_tip = ("Arrow keys: Left / Right (X), Up / Down (Y).")
        ToolTip(microstage_step_entry, _ms_tip)
        
        ttk.Label(self.microstage_stepping_frame, text="Axis:").grid(row=0, column=2, sticky="w", padx=(10, 5))
        self._microstage_axis_combo = ttk.Combobox(
            self.microstage_stepping_frame,
            textvariable=self.step_axis_var,
            values=["X", "Y"],
            state="readonly",
            width=5,
        )
        self._microstage_axis_combo.grid(row=0, column=3, padx=5)
        
        ttk.Button(
            self.microstage_stepping_frame,
            text="Step +",
            command=lambda: self._step_microstage_delta(1),
        ).grid(row=0, column=4, padx=(10, 3))
        ttk.Button(
            self.microstage_stepping_frame,
            text="Step −",
            command=lambda: self._step_microstage_delta(-1),
        ).grid(row=0, column=5, padx=(3, 5))
        
        # Piezo stepping controls (same layout as microstage; one step value for all axes)
        self.piezo_stepping_frame = ttk.Frame(stepping_frame)
        self.piezo_stepping_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        _piezo_axes = self._piezo_axis_values_for_ui()
        ttk.Label(self.piezo_stepping_frame, text="Step (µm):").grid(row=0, column=0, sticky="w", padx=5)
        piezo_step_entry = ttk.Entry(self.piezo_stepping_frame, textvariable=self.step_var, width=10)
        piezo_step_entry.grid(row=0, column=1, padx=5)
        _axis_list = ", ".join(_piezo_axes) if _piezo_axes else "X"
        _pz_tip = (f"Arrow keys: Left / Right (X), Up / Down (Y){', Page Up / Page Down (Z)' if self.piezo_z else '.'}")
        ToolTip(piezo_step_entry, _pz_tip)
        
        ttk.Label(self.piezo_stepping_frame, text="Axis:").grid(row=0, column=2, sticky="w", padx=(10, 5))
        self._piezo_axis_combo = ttk.Combobox(
            self.piezo_stepping_frame,
            textvariable=self.step_axis_var,
            values=_piezo_axes if _piezo_axes else ["X"],
            state="readonly",
            width=5,
        )
        self._piezo_axis_combo.grid(row=0, column=3, padx=5)
        
        ttk.Button(
            self.piezo_stepping_frame,
            text="Step +",
            command=lambda: self._step_piezo_delta(1),
        ).grid(row=0, column=4, padx=(10, 3))
        ttk.Button(
            self.piezo_stepping_frame,
            text="Step −",
            command=lambda: self._step_piezo_delta(-1),
        ).grid(row=0, column=5, padx=(3, 5))
        
        # Initially hide both stepping frames
        self._update_stepping_controls_visibility()

        # --- Piezo Control Frame ---
        if self.piezo_x or self.piezo_y or self.piezo_z:
            piezo_frame = ttk.LabelFrame(main_frame, text="Piezo Control", padding="10")
            piezo_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))
            
            # Header Labels
            ttk.Label(piezo_frame, text="Set Value (µm)").grid(row=0, column=2, padx=5, pady=5)
            ttk.Label(piezo_frame, text="Previous Value (µm)").grid(row=0, column=3, padx=5, pady=5)
            
            row = 1
            # X-Axis Piezo
            if self.piezo_x:
                ttk.Label(piezo_frame, text="Piezo X").grid(row=row, column=0, sticky="w", padx=5)
                ttk.Button(piezo_frame, text="Set Position", command=self._set_piezo_x_position).grid(row=row, column=1, padx=5)
                ttk.Entry(piezo_frame, textvariable=self.piezo_x_set_var, width=10).grid(row=row, column=2)
                ttk.Label(piezo_frame, textvariable=self.piezo_x_current_var, width=10, relief="sunken", anchor="center").grid(row=row, column=3, padx=5)
                row += 1
            
            # Y-Axis Piezo
            if self.piezo_y:
                ttk.Label(piezo_frame, text="Piezo Y").grid(row=row, column=0, sticky="w", padx=5, pady=(5,0))
                ttk.Button(piezo_frame, text="Set Position", command=self._set_piezo_y_position).grid(row=row, column=1, padx=5, pady=(5,0))
                ttk.Entry(piezo_frame, textvariable=self.piezo_y_set_var, width=10).grid(row=row, column=2, pady=(5,0))
                ttk.Label(piezo_frame, textvariable=self.piezo_y_current_var, width=10, relief="sunken", anchor="center").grid(row=row, column=3, padx=5, pady=(5,0))
                row += 1
            
            # Z-Axis Piezo
            if self.piezo_z:
                ttk.Label(piezo_frame, text="Piezo Z").grid(row=row, column=0, sticky="w", padx=5, pady=(5,0))
                ttk.Button(piezo_frame, text="Set Position", command=self._set_piezo_z_position).grid(row=row, column=1, padx=5, pady=(5,0))
                ttk.Entry(piezo_frame, textvariable=self.piezo_z_set_var, width=10).grid(row=row, column=2, pady=(5,0))
                ttk.Label(piezo_frame, textvariable=self.piezo_z_current_var, width=10, relief="sunken", anchor="center").grid(row=row, column=3, padx=5, pady=(5,0))
        

    def _toggle_key_bindings(self):
        """Enables or disables the arrow key bindings based on the checkbox state."""
        if self.stepping_enabled_var.get():
            self._enable_key_bindings()
        else:
            self._disable_key_bindings()

    def _enable_key_bindings(self):
        """Binds arrow keys to the jogging function."""
        print("Arrow key stepping enabled.")
        self.bind("<KeyPress-Up>", self._handle_key_press)
        self.bind("<KeyPress-Down>", self._handle_key_press)
        self.bind("<KeyPress-Left>", self._handle_key_press)
        self.bind("<KeyPress-Right>", self._handle_key_press)

    def _disable_key_bindings(self):
        """Unbinds arrow keys."""
        print("Arrow key stepping disabled.")
        self.unbind("<KeyPress-Up>")
        self.unbind("<KeyPress-Down>")
        self.unbind("<KeyPress-Left>")
        self.unbind("<KeyPress-Right>")
    
    def _check_if_homed(self, show_warning=True):
        if not self.is_homed:
            if show_warning:
                messagebox.showwarning("Calibration Required", "Please run 'Calibrate Stage' first to calibrate the stage position.")
            return False
        return True
    
    def _show_stepping_warning(self):
        """Show one-time warning about stepping without calibrating"""
        if not self.stepping_warning_shown and not self.is_homed:
            messagebox.showwarning(
                "Stepping Without Calibrating",
                "Warning: Stepping without calibrating the stage position may allow movement outside the safe limits (12000, 12000) and could cause hardware collisions. Proceed with caution."
            )
            self.stepping_warning_shown = True
    
    def _run_movement_in_thread(self, movement_func, *args, **kwargs):
        """Run a movement function in a background thread to keep GUI responsive"""
        if self.movement_in_progress:
            return
        
        def movement_wrapper():
            self.movement_in_progress = True
            try:
                movement_func(*args, **kwargs)
            except Exception as e:
                # Schedule error handling on main thread
                self.after(0, lambda: self._handle_movement_error(e))
            finally:
                self.movement_in_progress = False
        
        thread = threading.Thread(target=movement_wrapper, daemon=True)
        thread.start()
    
    def _handle_movement_error(self, error):
        """Handle movement errors on the main thread"""
        self.microstage_status_var.set("Error")
        self.microstage_status_label.config(foreground="red")
        messagebox.showerror("Movement Error", f"An error occurred: {error}")

    def _find_home(self):
        try:
            self.microstage_status_var.set("HOMING...")
            self.microstage_status_label.config(foreground="orange")
            # Force GUI update to show the status immediately
            self.update_idletasks()
            
            # Run homing in background thread
            def find_home_thread():
                try:
                    self.stage.find_home()
                    self.is_homed = True
                    self.stage.get_position() # Update internal state if necessary
                    
                    # Update GUI on main thread
                    self.after(0, lambda: self.microstage_status_var.set("Ready"))
                    self.after(0, lambda: self.microstage_status_label.config(foreground="green"))
                    self.after(0, lambda: messagebox.showinfo("Calibration Complete", "Stage has been calibrated. The bottom-right corner is now (0, 0)."))
                except Exception as e:
                    self.after(0, lambda: self.microstage_status_var.set("Error"))
                    self.after(0, lambda: self.microstage_status_label.config(foreground="red"))
                    self.after(0, lambda: messagebox.showerror("Calibration Error", f"An error occurred during calibration:\n{e}"))
            
            thread = threading.Thread(target=find_home_thread, daemon=True)
            thread.start()
            
        except Exception as e:
            self.microstage_status_var.set("Error")
            self.microstage_status_label.config(foreground="red")
            messagebox.showerror("Calibration Error", f"An error occurred during calibration:\n{e}")

    def _return_to_home(self):
        if not self._check_if_homed(): return
        try:
            self.microstage_status_var.set("MOVING...")
            self.microstage_status_label.config(foreground="orange")
            # Force GUI update to show the status immediately
            self.update_idletasks()
            
            # Run return to home in background thread
            def return_home_thread():
                try:
                    self.stage.return_to_home()
                    
                    # Update GUI on main thread
                    self.after(0, lambda: self.microstage_status_var.set("Ready"))
                    self.after(0, lambda: self.microstage_status_label.config(foreground="green"))
                except Exception as e:
                    self.after(0, lambda: self.microstage_status_var.set("Error"))
                    self.after(0, lambda: self.microstage_status_label.config(foreground="red"))
                    self.after(0, lambda: messagebox.showerror("Return to Home Error", f"An error occurred:\n{e}"))
            
            thread = threading.Thread(target=return_home_thread, daemon=True)
            thread.start()
            
        except Exception as e:
            self.microstage_status_var.set("Error")
            self.microstage_status_label.config(foreground="red")
            messagebox.showerror("Return to Home Error", f"An error occurred:\n{e}")
    
    def _move_to_center(self):
        if not self._check_if_homed(): return
        try:
            # Calculate center position based on limits
            center_x = (self.stage.x_min + self.stage.x_max) / 2
            center_y = (self.stage.y_min + self.stage.y_max) / 2
            
            self.microstage_status_var.set("MOVING...")
            self.microstage_status_label.config(foreground="orange")
            # Force GUI update to show the status immediately
            self.update_idletasks()
            
            # Update the set position variables to reflect the center
            self.x_set_var.set(f"{center_x:.2f}")
            self.y_set_var.set(f"{center_y:.2f}")
            
            # Run movement in background thread
            def move_center():
                self.stage.move_to(center_x, center_y)
            
            self._run_movement_in_thread(move_center)
            
        except Exception as e:
            self.microstage_status_var.set("Error")
            self.microstage_status_label.config(foreground="red")
            messagebox.showerror("Move to Center Error", f"An error occurred:\n{e}")
    
    def _set_x_position(self):
        if not self._check_if_homed(): return
        try:
            target_x = float(self.x_set_var.get())
            current_pos = self.stage.get_position()
            
            # Update status before movement
            self.microstage_status_var.set("MOVING...")
            self.microstage_status_label.config(foreground="orange")
            # Force GUI update to show the status immediately
            self.update_idletasks()
            
            # Run movement in background thread
            def move_x():
                self.stage.move_to(target_x, current_pos[1])
            
            self._run_movement_in_thread(move_x)
            
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for the X position.")
        except Exception as e:
            self.microstage_status_var.set("Error")
            self.microstage_status_label.config(foreground="red")
            messagebox.showerror("Movement Error", f"An error occurred: {e}")

    def _set_y_position(self):
        if not self._check_if_homed(): return
        try:
            target_y = float(self.y_set_var.get())
            current_pos = self.stage.get_position()
            
            # Update status before movement
            self.microstage_status_var.set("MOVING...")
            self.microstage_status_label.config(foreground="orange")
            # Force GUI update to show the status immediately
            self.update_idletasks()
            
            # Run movement in background thread
            def move_y():
                self.stage.move_to(current_pos[0], target_y)
            
            self._run_movement_in_thread(move_y)
            
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for the Y position.")
        except Exception as e:
            self.microstage_status_var.set("Error")
            self.microstage_status_label.config(foreground="red")
            messagebox.showerror("Movement Error", f"An error occurred: {e}")

    def _run_piezo_manual(self, action) -> None:
        from qt3utils.applications.piezo_daq_lock import (
            release_manual_move,
            try_acquire_manual_move,
        )

        if not try_acquire_manual_move():
            messagebox.showwarning(
                "Piezo busy",
                "qt3scan is using the piezo outputs. Wait for the scan to finish, then try again.",
            )
            return
        try:
            action()
        finally:
            release_manual_move()

    def _set_piezo_x_position(self):
        """Set piezo X position"""
        if not self.piezo_x:
            return

        def do_move():
            try:
                target_x = float(self.piezo_x_set_var.get())
                self.piezo_x.go_to_position(target_x)
                self.piezo_x_current_var.set(f"{target_x:.3f}")
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter a valid number for the Piezo X position.")
            except Exception as e:
                messagebox.showerror("Piezo X Error", f"An error occurred: {e}")

        self._run_piezo_manual(do_move)

    def _set_piezo_y_position(self):
        """Set piezo Y position"""
        if not self.piezo_y:
            return

        def do_move():
            try:
                target_y = float(self.piezo_y_set_var.get())
                self.piezo_y.go_to_position(target_y)
                self.piezo_y_current_var.set(f"{target_y:.3f}")
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter a valid number for the Piezo Y position.")
            except Exception as e:
                messagebox.showerror("Piezo Y Error", f"An error occurred: {e}")

        self._run_piezo_manual(do_move)

    def _set_piezo_z_position(self):
        """Set piezo Z position"""
        if not self.piezo_z:
            return

        def do_move():
            try:
                target_z = float(self.piezo_z_set_var.get())
                self.piezo_z.go_to_position(target_z)
                self.piezo_z_current_var.set(f"{target_z:.3f}")
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter a valid number for the Piezo Z position.")
            except Exception as e:
                messagebox.showerror("Piezo Z Error", f"An error occurred: {e}")

        self._run_piezo_manual(do_move)

    def _handle_key_press(self, event):
        # Failsafe in case bindings are somehow active when they shouldn't be
        if not self.stepping_enabled_var.get():
            return

        key_map = {
            "Up":    ('y', 1), "Down":  ('y', -1),
            "Left":  ('x', 1), "Right": ('x', -1) # Remember: Left is +X, Right is -X in our coordinate system
        }
        if event.keysym in key_map:
            axis, direction = key_map[event.keysym]
            self._step_move(axis, direction)

    def _step_move(self, axis, direction):
        if not self.stage:
            return
        
        # Show one-time warning if not homed
        self._show_stepping_warning()
        
        try:
            self.microstage_status_var.set("MOVING...")
            self.microstage_status_label.config(foreground="orange")
            self.update_idletasks()
            
            current_pos = self.stage.get_position()
            step_val = abs(float(self.step_var.get()))  # Only use positive values, direction handled by arrow key
            
            # Run movement in background thread
            def move_step():
                if axis == 'x':
                    new_target_x = current_pos[0] + (step_val * direction)
                    if self.is_homed:
                        new_target_x = max(self.stage.x_min, min(self.stage.x_max, new_target_x))
                    self.stage.move_to(new_target_x, current_pos[1])
                elif axis == 'y':
                    new_target_y = current_pos[1] + (step_val * direction)
                    if self.is_homed:
                        new_target_y = max(self.stage.y_min, min(self.stage.y_max, new_target_y))
                    self.stage.move_to(current_pos[0], new_target_y)
            
            self._run_movement_in_thread(move_step)
            
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid positive number for the Step value.")
        except Exception as e:
            self.microstage_status_var.set("Error")
            self.microstage_status_label.config(foreground="red")
            messagebox.showerror("Movement Error", f"An error occurred: {e}")
    
    def _step_microstage_delta(self, direction_sign):
        """Step microstage by step_var along selected axis; direction_sign is +1 or -1."""
        if not self.stage or direction_sign not in (-1, 1):
            return
        self._show_stepping_warning()

        try:
            self.microstage_status_var.set("MOVING...")
            self.microstage_status_label.config(foreground="orange")
            self.update_idletasks()

            step_mag = abs(float(self.step_var.get()))
            step_val = step_mag * direction_sign
            axis = self.step_axis_var.get()
            current_pos = self.stage.get_position()

            def move_step():
                if axis == "X":
                    new_x = current_pos[0] + step_val
                    if self.is_homed:
                        new_x = max(self.stage.x_min, min(self.stage.x_max, new_x))
                    self.stage.move_to(new_x, current_pos[1])
                elif axis == "Y":
                    new_y = current_pos[1] + step_val
                    if self.is_homed:
                        new_y = max(self.stage.y_min, min(self.stage.y_max, new_y))
                    self.stage.move_to(current_pos[0], new_y)

            self._run_movement_in_thread(move_step)

        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid positive number for the Step value.")
        except Exception as e:
            self.microstage_status_var.set("Error")
            self.microstage_status_label.config(foreground="red")
            messagebox.showerror("Movement Error", f"An error occurred: {e}")

    def _step_piezo_delta(self, direction_sign):
        """Step selected piezo axis by step_var; direction_sign is +1 (Step +) or -1 (Step −)."""
        if direction_sign not in (-1, 1):
            return

        axis = self.step_axis_var.get()
        piezo = {"X": self.piezo_x, "Y": self.piezo_y, "Z": self.piezo_z}.get(axis)
        if not piezo:
            return

        try:
            step = abs(float(self.step_var.get())) * direction_sign
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for the Step value.")
            return

        def do_move():
            self._piezo_arrow_step_delta(piezo, step)

        self._run_piezo_manual(do_move)

    def _update_position_display(self):
        # Update microstage display if homed
        if self.stage and self.is_homed:
            try:
                x_um, y_um = self.stage.get_position()
                self.x_current_var.set(f"{x_um:.2f}")
                self.y_current_var.set(f"{y_um:.2f}")
            except Exception as e:
                self.x_current_var.set("Error")
                self.y_current_var.set("Error")
                print(f"Error updating microstage position display: {e}")
        
        # Check microstage movement status and update indicators
        if self.stage:
            try:
                is_moving = self.stage.is_moving()
                current_status = self.microstage_status_var.get()
                
                # List of special status messages that should be preserved
                special_statuses = ["HOMING...", "MOVING...", "Error"]
                
                # Update tooltip text based on status
                if current_status == "HOMING...":
                    self.microstage_status_tooltip.update_text("Warning: Attempting to move the stage while it is already moving might cause unexpected behavior!")
                elif current_status == "MOVING...":
                    self.microstage_status_tooltip.update_text("Warning: Attempting to move the stage while it is already moving might cause unexpected behavior!")
                elif current_status == "Ready":
                    self.microstage_status_tooltip.update_text("Status: Ready - The stage is ready for movement commands.")
                elif current_status == "Not Homed":
                    self.microstage_status_tooltip.update_text("Status: Not Homed - Please run 'Calibrate Stage' to calibrate the stage position.")
                elif current_status == "Error":
                    self.microstage_status_tooltip.update_text("Status: Error - An error has occurred. Check the error message for details.")
                else:
                    self.microstage_status_tooltip.update_text(f"Status: {current_status}")
                
                if is_moving:
                    # If we're moving, show moving status unless it's a special preserved status
                    if current_status not in special_statuses:
                        self.microstage_status_var.set("MOVING...")
                        self.microstage_status_label.config(foreground="orange")
                else:
                    # Movement has stopped - update status to Ready/Not Homed
                    # But preserve special status messages until they're explicitly changed
                    if current_status == "MOVING...":
                        # Movement completed - transition to Ready
                        if self.is_homed:
                            self.microstage_status_var.set("Ready")
                            self.microstage_status_label.config(foreground="green")
                        else:
                            self.microstage_status_var.set("Not Homed")
                            self.microstage_status_label.config(foreground="orange")
                    elif current_status not in special_statuses:
                        # Normal status - update to Ready/Not Homed
                        if self.is_homed:
                            self.microstage_status_var.set("Ready")
                            self.microstage_status_label.config(foreground="green")
                        else:
                            self.microstage_status_var.set("Not Homed")
                            self.microstage_status_label.config(foreground="orange")
                    # If status is "HOMING..." or "Error", preserve it (they handle their own completion)
            except Exception as e:
                self.microstage_status_var.set("Error")
                self.microstage_status_label.config(foreground="red")
                print(f"Error checking microstage movement status: {e}")
        
        # Update piezo "Previous Value" from last commanded position (not MON readback)
        if self.piezo_x:
            try:
                pos = self.piezo_x.get_last_commanded_position()
                if pos is not None:
                    self.piezo_x_current_var.set(f"{pos:.3f}")
                else:
                    self.piezo_x_current_var.set("---")
            except Exception as e:
                self.piezo_x_current_var.set("Error")
                print(f"Error updating piezo X position: {e}")
        
        if self.piezo_y:
            try:
                pos = self.piezo_y.get_last_commanded_position()
                if pos is not None:
                    self.piezo_y_current_var.set(f"{pos:.3f}")
                else:
                    self.piezo_y_current_var.set("---")
            except Exception as e:
                self.piezo_y_current_var.set("Error")
                print(f"Error updating piezo Y position: {e}")
        
        if self.piezo_z:
            try:
                pos = self.piezo_z.get_last_commanded_position()
                if pos is not None:
                    self.piezo_z_current_var.set(f"{pos:.3f}")
                else:
                    self.piezo_z_current_var.set("---")
            except Exception as e:
                self.piezo_z_current_var.set("Error")
                print(f"Error updating piezo Z position: {e}")
        
        self.after(100, self._update_position_display)  # Faster update for movement indicators

    def _on_stepping_controller_changed(self, event=None):
        """Handle stepping controller selection change"""
        self._update_stepping_controls_visibility()
        self._sync_step_axis_for_controller()
        self._update_key_bindings()
    
    def _update_stepping_controls_visibility(self):
        """Show/hide stepping controls based on selected controller"""
        controller = self.stepping_controller_var.get()
        
        # Hide both frames initially
        self.microstage_stepping_frame.grid_remove()
        self.piezo_stepping_frame.grid_remove()
        
        # Show appropriate frame
        if controller == "Microstage":
            self.microstage_stepping_frame.grid()
        elif controller == "Piezo":
            self.piezo_stepping_frame.grid()
    
    def _update_key_bindings(self):
        """Update keyboard bindings based on selected stepping controller"""
        # Remove all existing bindings
        self.unbind_all("<KeyPress-Left>")
        self.unbind_all("<KeyPress-Right>")
        self.unbind_all("<KeyPress-Up>")
        self.unbind_all("<KeyPress-Down>")
        self.unbind_all("<KeyPress-Prior>")
        self.unbind_all("<KeyPress-Next>")
        
        controller = self.stepping_controller_var.get()
        if controller == "Microstage":
            self.bind_all("<KeyPress-Left>", self._step_microstage_left)
            self.bind_all("<KeyPress-Right>", self._step_microstage_right)
            self.bind_all("<KeyPress-Up>", self._step_microstage_up)
            self.bind_all("<KeyPress-Down>", self._step_microstage_down)
            print("Microstage stepping enabled - Use arrow keys to move microstage")
        elif controller == "Piezo":
            self.bind_all("<KeyPress-Left>", self._step_piezo_left)
            self.bind_all("<KeyPress-Right>", self._step_piezo_right)
            self.bind_all("<KeyPress-Up>", self._step_piezo_up)
            self.bind_all("<KeyPress-Down>", self._step_piezo_down)
            if self.piezo_z:
                self.bind_all("<KeyPress-Prior>", self._step_piezo_page_up)
                self.bind_all("<KeyPress-Next>", self._step_piezo_page_down)
            print(
                "Piezo stepping enabled - Arrow keys: X/Y"
                + ("; Page Up/Down: Z" if self.piezo_z else "")
            )
        else:
            print("Stepping disabled")
    
    def _step_microstage_left(self, event):
        """Step microstage left (negative X direction)"""
        if not self.stage:
            return
        
        # Show one-time warning if not homed
        self._show_stepping_warning()
        
        try:
            self.microstage_status_var.set("MOVING...")
            self.microstage_status_label.config(foreground="orange")
            self.update_idletasks()
            
            step = abs(float(self.step_var.get()))
            current_pos = self.stage.get_position()
            new_x = current_pos[0] - step
            if self.is_homed:
                new_x = max(self.stage.x_min, new_x)
            
            def move_left():
                self.stage.move_to(new_x, current_pos[1])
            
            self._run_movement_in_thread(move_left)
        except ValueError:
            pass
    
    def _step_microstage_right(self, event):
        """Step microstage right (positive X direction)"""
        if not self.stage:
            return
        
        # Show one-time warning if not homed
        self._show_stepping_warning()
        
        try:
            self.microstage_status_var.set("MOVING...")
            self.microstage_status_label.config(foreground="orange")
            self.update_idletasks()
            
            step = abs(float(self.step_var.get()))
            current_pos = self.stage.get_position()
            new_x = current_pos[0] + step
            if self.is_homed:
                new_x = min(self.stage.x_max, new_x)
            
            def move_right():
                self.stage.move_to(new_x, current_pos[1])
            
            self._run_movement_in_thread(move_right)
        except ValueError:
            pass
    
    def _step_microstage_up(self, event):
        """Step microstage up (positive Y direction)"""
        if not self.stage:
            return
        
        # Show one-time warning if not homed
        self._show_stepping_warning()
        
        try:
            self.microstage_status_var.set("MOVING...")
            self.microstage_status_label.config(foreground="orange")
            self.update_idletasks()
            
            step = abs(float(self.step_var.get()))
            current_pos = self.stage.get_position()
            new_y = current_pos[1] + step
            if self.is_homed:
                new_y = min(self.stage.y_max, new_y)
            
            def move_up():
                self.stage.move_to(current_pos[0], new_y)
            
            self._run_movement_in_thread(move_up)
        except ValueError:
            pass
    
    def _step_microstage_down(self, event):
        """Step microstage down (negative Y direction)"""
        if not self.stage:
            return
        
        # Show one-time warning if not homed
        self._show_stepping_warning()
        
        try:
            self.microstage_status_var.set("MOVING...")
            self.microstage_status_label.config(foreground="orange")
            self.update_idletasks()
            
            step = abs(float(self.step_var.get()))
            current_pos = self.stage.get_position()
            new_y = current_pos[1] - step
            if self.is_homed:
                new_y = max(self.stage.y_min, new_y)
            
            def move_down():
                self.stage.move_to(current_pos[0], new_y)
            
            self._run_movement_in_thread(move_down)
        except ValueError:
            pass

    def _piezo_arrow_step_delta(self, piezo, signed_dx):
        """Step by signed_dx µm using commanded chain (NidaqPositionController.step_position).

        Fallback go_to_position uses last commanded position, not MON readback, so step size
        stays consistent when read_channel is configured.
        """
        base_um = piezo.get_last_commanded_position()
        if base_um is None:
            base_um = piezo.get_current_position()
        try:
            piezo.step_position(signed_dx)
        except Exception:
            piezo.go_to_position(base_um + signed_dx)

    def _step_piezo_left(self, event):
        """Step piezo X left"""
        if not self.piezo_x:
            return

        def do_move():
            try:
                step = abs(float(self.step_var.get()))
                self._piezo_arrow_step_delta(self.piezo_x, -step)
            except ValueError:
                pass

        self._run_piezo_manual(do_move)

    def _step_piezo_right(self, event):
        """Step piezo X right"""
        if not self.piezo_x:
            return

        def do_move():
            try:
                step = abs(float(self.step_var.get()))
                self._piezo_arrow_step_delta(self.piezo_x, step)
            except ValueError:
                pass

        self._run_piezo_manual(do_move)

    def _step_piezo_up(self, event):
        """Step piezo Y up"""
        if not self.piezo_y:
            return

        def do_move():
            try:
                step = abs(float(self.step_var.get()))
                self._piezo_arrow_step_delta(self.piezo_y, step)
            except ValueError:
                pass

        self._run_piezo_manual(do_move)

    def _step_piezo_down(self, event):
        """Step piezo Y down"""
        if not self.piezo_y:
            return

        def do_move():
            try:
                step = abs(float(self.step_var.get()))
                self._piezo_arrow_step_delta(self.piezo_y, -step)
            except ValueError:
                pass

        self._run_piezo_manual(do_move)

    def _step_piezo_page_up(self, event):
        """Step piezo Z up (positive)"""
        if not self.piezo_z:
            return

        def do_move():
            try:
                step = abs(float(self.step_var.get()))
                self._piezo_arrow_step_delta(self.piezo_z, step)
            except ValueError:
                pass

        self._run_piezo_manual(do_move)

    def _step_piezo_page_down(self, event):
        """Step piezo Z down (negative)"""
        if not self.piezo_z:
            return

        def do_move():
            try:
                step = abs(float(self.step_var.get()))
                self._piezo_arrow_step_delta(self.piezo_z, -step)
            except ValueError:
                pass

        self._run_piezo_manual(do_move)

    def _on_closing(self):
        print("Closing application and releasing resources...")
        if self.stage:
            self.stage.close()
        # Note: NIDAQ controllers don't need explicit closing
        self.destroy()

if __name__ == "__main__":
    app = Qt3MoveApp(config_file=CONFIG_FILE)
    app.mainloop()
