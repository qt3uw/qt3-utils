"""
Tkinter UI for Mad City Labs encoderless microstage control.

Mirrors qt3move microstage setup, absolute moves, stepping, and arrow-key jogging.
"""
from __future__ import annotations

import threading
import tkinter as tk
from typing import Optional
from tkinter import ttk, messagebox


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

        label = tk.Label(
            self.tooltip_window,
            text=self.text,
            background="yellow",
            foreground="black",
            relief="solid",
            borderwidth=1,
            padx=5,
            pady=3,
            font=("Arial", 9),
            wraplength=200,
        )
        label.pack()

    def on_leave(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

    def update_text(self, new_text):
        self.text = new_text


class MicrostageTkPanel:
    """
    Full microstage controls equivalent to the qt3move microstage section.
    Pass ``microstage=None`` when hardware is unavailable (shows a short message).
    """

    def __init__(
        self,
        parent: tk.Widget,
        root: tk.Misc,
        microstage,
    ) -> None:
        self.root = root
        self.microstage = microstage
        self.is_homed = False
        self.movement_in_progress = False
        self.stepping_warning_shown = False
        self._display_poll_active = False
        self._after_id: Optional[str] = None

        if microstage is None:
            ttk.Label(
                parent,
                text="Microstage not configured.",
                font="Helvetica 10",
            ).grid(row=0, column=0, sticky="w", pady=4)
            return

        self.x_set_var = tk.StringVar(value="0.0")
        self.y_set_var = tk.StringVar(value="0.0")
        self.step_var = tk.StringVar(value="1.0")
        self.step_axis_var = tk.StringVar(value="X")
        self.x_current_var = tk.StringVar(value="--")
        self.y_current_var = tk.StringVar(value="--")
        self.microstage_status_var = tk.StringVar(value="Not Homed")
        self.stepping_controller_var = tk.StringVar(value="None")

        self._build_widgets(parent)
        self._display_poll_active = True
        self._tick_position_display()

    def _build_widgets(self, parent: tk.Widget) -> None:
        outer = ttk.Frame(parent)
        outer.grid(row=0, column=0, sticky="ew")

        setup_frame = ttk.LabelFrame(outer, text="Microstage setup", padding="8")
        setup_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        setup_frame.columnconfigure((0, 1, 2), weight=1)

        find_home_button = ttk.Button(
            setup_frame, text="Calibrate Stage", command=self._find_home
        )
        find_home_button.grid(row=0, column=0, padx=4, sticky="ew")
        ToolTip(
            find_home_button,
            "Calibrate Stage: Sets the origin (0,0) at the bottom-right corner.",
        )
        ttk.Button(
            setup_frame, text="Return to Home", command=self._return_to_home
        ).grid(row=0, column=1, padx=4, sticky="ew")
        ttk.Button(
            setup_frame, text="Move to Center", command=self._move_to_center
        ).grid(row=0, column=2, padx=4, sticky="ew")

        control_frame = ttk.LabelFrame(outer, text="Microstage control", padding="8")
        control_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        ttk.Label(control_frame, text="Set (µm)").grid(row=0, column=2, padx=4, pady=4)
        ttk.Label(control_frame, text="Current (µm)").grid(row=0, column=3, padx=4, pady=4)

        ttk.Label(control_frame, text="X axis").grid(row=1, column=0, sticky="w", padx=4)
        ttk.Button(
            control_frame, text="Set Position", command=self._set_x_position
        ).grid(row=1, column=1, padx=4)
        ttk.Entry(control_frame, textvariable=self.x_set_var, width=10).grid(
            row=1, column=2
        )
        ttk.Label(
            control_frame,
            textvariable=self.x_current_var,
            width=10,
            relief="sunken",
            anchor="center",
        ).grid(row=1, column=3, padx=4)

        ttk.Label(control_frame, text="Y axis").grid(
            row=2, column=0, sticky="w", padx=4, pady=(6, 0)
        )
        ttk.Button(
            control_frame, text="Set Position", command=self._set_y_position
        ).grid(row=2, column=1, padx=4, pady=(6, 0))
        ttk.Entry(control_frame, textvariable=self.y_set_var, width=10).grid(
            row=2, column=2, pady=(6, 0)
        )
        ttk.Label(
            control_frame,
            textvariable=self.y_current_var,
            width=10,
            relief="sunken",
            anchor="center",
        ).grid(row=2, column=3, padx=4, pady=(6, 0))

        ttk.Label(control_frame, text="Microstage:").grid(
            row=3, column=0, sticky="w", padx=4, pady=(10, 0)
        )
        self.microstage_status_label = ttk.Label(
            control_frame,
            textvariable=self.microstage_status_var,
            width=20,
            relief="sunken",
            anchor="center",
        )
        self.microstage_status_label.grid(row=3, column=1, columnspan=2, padx=4, pady=(10, 0))
        self.microstage_status_tooltip = ToolTip(
            self.microstage_status_label, "Status: Not Homed"
        )

        stepping_frame = ttk.LabelFrame(
            outer, text="Microstage stepping (arrow keys)", padding="8"
        )
        stepping_frame.grid(row=2, column=0, sticky="ew")

        ttk.Label(
            stepping_frame,
            text="Enable arrow keys for:",
        ).grid(row=0, column=0, sticky="w", padx=4, pady=(0, 6))
        stepping_combo = ttk.Combobox(
            stepping_frame,
            textvariable=self.stepping_controller_var,
            values=["None", "Microstage"],
            state="readonly",
            width=14,
        )
        stepping_combo.grid(row=0, column=1, sticky="w", padx=4, pady=(0, 6))
        stepping_combo.bind("<<ComboboxSelected>>", self._on_stepping_controller_changed)

        self.microstage_stepping_frame = ttk.Frame(stepping_frame)
        self.microstage_stepping_frame.grid(row=1, column=0, columnspan=2, sticky="ew")

        ttk.Label(self.microstage_stepping_frame, text="Step (µm):").grid(
            row=0, column=0, sticky="w", padx=4
        )
        ttk.Entry(
            self.microstage_stepping_frame, textvariable=self.step_var, width=10
        ).grid(row=0, column=1, padx=4)
        ttk.Label(self.microstage_stepping_frame, text="Axis:").grid(
            row=0, column=2, sticky="w", padx=(12, 4)
        )
        ttk.Combobox(
            self.microstage_stepping_frame,
            textvariable=self.step_axis_var,
            values=["X", "-X", "Y", "-Y"],
            state="readonly",
            width=5,
        ).grid(row=0, column=3, padx=4)
        step_button = ttk.Button(
            self.microstage_stepping_frame,
            text="Step",
            command=self._step_microstage_button,
        )
        step_button.grid(row=0, column=4, padx=(12, 4))
        ToolTip(
            step_button,
            "Move by the step size along the selected axis; use arrow keys when enabled.",
        )

        self._update_stepping_visibility()
        parent.columnconfigure(0, weight=1)

    def destroy(self) -> None:
        self._display_poll_active = False
        self._unbind_stepping_keys()
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        if self.microstage is not None:
            try:
                self.microstage.close()
            except Exception:
                pass

    def _on_stepping_controller_changed(self, event=None) -> None:
        self._update_stepping_visibility()
        self._update_key_bindings()

    def _update_stepping_visibility(self) -> None:
        if self.microstage is None:
            return
        ctrl = self.stepping_controller_var.get()
        self.microstage_stepping_frame.grid_remove()
        if ctrl == "Microstage":
            self.microstage_stepping_frame.grid()

    def _update_key_bindings(self) -> None:
        self._unbind_stepping_keys()
        if self.microstage is None:
            return
        if self.stepping_controller_var.get() == "Microstage":
            self.root.bind_all("<KeyPress-Left>", self._step_microstage_left)
            self.root.bind_all("<KeyPress-Right>", self._step_microstage_right)
            self.root.bind_all("<KeyPress-Up>", self._step_microstage_up)
            self.root.bind_all("<KeyPress-Down>", self._step_microstage_down)

    def _unbind_stepping_keys(self) -> None:
        for seq in (
            "<KeyPress-Left>",
            "<KeyPress-Right>",
            "<KeyPress-Up>",
            "<KeyPress-Down>",
        ):
            try:
                self.root.unbind_all(seq)
            except tk.TclError:
                pass

    def _check_if_homed(self, show_warning=True) -> bool:
        if not self.is_homed:
            if show_warning:
                messagebox.showwarning(
                    "Calibration Required",
                    "Please run 'Calibrate Stage' first to calibrate the stage position.",
                )
            return False
        return True

    def _show_stepping_warning(self) -> None:
        if not self.stepping_warning_shown and not self.is_homed:
            messagebox.showwarning(
                "Stepping Without Calibrating",
                "Stepping without calibrating may allow movement outside safe limits. "
                "Proceed with caution.",
            )
            self.stepping_warning_shown = True

    def _run_movement_in_thread(self, movement_func, *args, **kwargs) -> None:
        if self.movement_in_progress or self.microstage is None:
            return

        def movement_wrapper():
            self.movement_in_progress = True
            try:
                movement_func(*args, **kwargs)
            except Exception as e:
                self.root.after(0, lambda err=e: self._handle_movement_error(err))
            finally:
                self.movement_in_progress = False

        threading.Thread(target=movement_wrapper, daemon=True).start()

    def _handle_movement_error(self, error) -> None:
        self.microstage_status_var.set("Error")
        self.microstage_status_label.config(foreground="red")
        messagebox.showerror("Movement Error", f"An error occurred: {error}")

    def _find_home(self) -> None:
        if self.microstage is None:
            return
        try:
            self.microstage_status_var.set("HOMING...")
            self.microstage_status_label.config(foreground="orange")
            self.root.update_idletasks()

            def find_home_thread():
                try:
                    self.microstage.find_home()
                    self.is_homed = True
                    self.microstage.get_position()
                    self.root.after(0, lambda: self.microstage_status_var.set("Ready"))
                    self.root.after(
                        0,
                        lambda: self.microstage_status_label.config(foreground="green"),
                    )
                    self.root.after(
                        0,
                        lambda: messagebox.showinfo(
                            "Calibration Complete",
                            "Stage has been calibrated. The bottom-right corner is now (0, 0).",
                        ),
                    )
                except Exception as e:
                    self.root.after(0, lambda: self.microstage_status_var.set("Error"))
                    self.root.after(
                        0,
                        lambda: self.microstage_status_label.config(foreground="red"),
                    )
                    self.root.after(
                        0,
                        lambda: messagebox.showerror(
                            "Calibration Error",
                            f"An error occurred during calibration:\n{e}",
                        ),
                    )

            threading.Thread(target=find_home_thread, daemon=True).start()
        except Exception as e:
            self.microstage_status_var.set("Error")
            self.microstage_status_label.config(foreground="red")
            messagebox.showerror("Calibration Error", f"An error occurred:\n{e}")

    def _return_to_home(self) -> None:
        if self.microstage is None or not self._check_if_homed():
            return
        try:
            self.microstage_status_var.set("MOVING...")
            self.microstage_status_label.config(foreground="orange")
            self.root.update_idletasks()

            def return_home_thread():
                try:
                    self.microstage.return_to_home()
                    self.root.after(0, lambda: self.microstage_status_var.set("Ready"))
                    self.root.after(
                        0,
                        lambda: self.microstage_status_label.config(foreground="green"),
                    )
                except Exception as e:
                    self.root.after(0, lambda: self.microstage_status_var.set("Error"))
                    self.root.after(
                        0,
                        lambda: self.microstage_status_label.config(foreground="red"),
                    )
                    self.root.after(
                        0,
                        lambda: messagebox.showerror(
                            "Return to Home Error", f"An error occurred:\n{e}"
                        ),
                    )

            threading.Thread(target=return_home_thread, daemon=True).start()
        except Exception as e:
            self.microstage_status_var.set("Error")
            self.microstage_status_label.config(foreground="red")
            messagebox.showerror("Return to Home Error", f"An error occurred:\n{e}")

    def _move_to_center(self) -> None:
        if self.microstage is None or not self._check_if_homed():
            return
        try:
            center_x = (self.microstage.x_min + self.microstage.x_max) / 2
            center_y = (self.microstage.y_min + self.microstage.y_max) / 2
            self.microstage_status_var.set("MOVING...")
            self.microstage_status_label.config(foreground="orange")
            self.root.update_idletasks()
            self.x_set_var.set(f"{center_x:.2f}")
            self.y_set_var.set(f"{center_y:.2f}")

            def move_center():
                self.microstage.move_to(center_x, center_y)

            self._run_movement_in_thread(move_center)
        except Exception as e:
            self.microstage_status_var.set("Error")
            self.microstage_status_label.config(foreground="red")
            messagebox.showerror("Move to Center Error", f"An error occurred:\n{e}")

    def _set_x_position(self) -> None:
        if self.microstage is None or not self._check_if_homed():
            return
        try:
            target_x = float(self.x_set_var.get())
            current_pos = self.microstage.get_position()
            self.microstage_status_var.set("MOVING...")
            self.microstage_status_label.config(foreground="orange")
            self.root.update_idletasks()

            def move_x():
                self.microstage.move_to(target_x, current_pos[1])

            self._run_movement_in_thread(move_x)
        except ValueError:
            messagebox.showerror(
                "Invalid Input", "Please enter a valid number for the X position."
            )
        except Exception as e:
            self.microstage_status_var.set("Error")
            self.microstage_status_label.config(foreground="red")
            messagebox.showerror("Movement Error", f"An error occurred: {e}")

    def _set_y_position(self) -> None:
        if self.microstage is None or not self._check_if_homed():
            return
        try:
            target_y = float(self.y_set_var.get())
            current_pos = self.microstage.get_position()
            self.microstage_status_var.set("MOVING...")
            self.microstage_status_label.config(foreground="orange")
            self.root.update_idletasks()

            def move_y():
                self.microstage.move_to(current_pos[0], target_y)

            self._run_movement_in_thread(move_y)
        except ValueError:
            messagebox.showerror(
                "Invalid Input", "Please enter a valid number for the Y position."
            )
        except Exception as e:
            self.microstage_status_var.set("Error")
            self.microstage_status_label.config(foreground="red")
            messagebox.showerror("Movement Error", f"An error occurred: {e}")

    def _step_microstage_button(self) -> None:
        if self.microstage is None:
            return
        self._show_stepping_warning()
        try:
            self.microstage_status_var.set("MOVING...")
            self.microstage_status_label.config(foreground="orange")
            self.root.update_idletasks()
            step_val = abs(float(self.step_var.get()))
            axis = self.step_axis_var.get()
            current_pos = self.microstage.get_position()

            def move_step():
                if axis == "X":
                    new_x = current_pos[0] + step_val
                    if self.is_homed:
                        new_x = max(
                            self.microstage.x_min,
                            min(self.microstage.x_max, new_x),
                        )
                    self.microstage.move_to(new_x, current_pos[1])
                elif axis == "-X":
                    new_x = current_pos[0] - step_val
                    if self.is_homed:
                        new_x = max(
                            self.microstage.x_min,
                            min(self.microstage.x_max, new_x),
                        )
                    self.microstage.move_to(new_x, current_pos[1])
                elif axis == "Y":
                    new_y = current_pos[1] + step_val
                    if self.is_homed:
                        new_y = max(
                            self.microstage.y_min,
                            min(self.microstage.y_max, new_y),
                        )
                    self.microstage.move_to(current_pos[0], new_y)
                elif axis == "-Y":
                    new_y = current_pos[1] - step_val
                    if self.is_homed:
                        new_y = max(
                            self.microstage.y_min,
                            min(self.microstage.y_max, new_y),
                        )
                    self.microstage.move_to(current_pos[0], new_y)

            self._run_movement_in_thread(move_step)
        except ValueError:
            messagebox.showerror(
                "Invalid Input", "Please enter a valid positive number for the Step value."
            )
        except Exception as e:
            self.microstage_status_var.set("Error")
            self.microstage_status_label.config(foreground="red")
            messagebox.showerror("Movement Error", f"An error occurred: {e}")

    def _step_microstage_left(self, event):
        if self.microstage is None:
            return
        self._show_stepping_warning()
        try:
            self.microstage_status_var.set("MOVING...")
            self.microstage_status_label.config(foreground="orange")
            self.root.update_idletasks()
            step = abs(float(self.step_var.get()))
            current_pos = self.microstage.get_position()
            new_x = current_pos[0] - step
            if self.is_homed:
                new_x = max(self.microstage.x_min, new_x)

            def move_left():
                self.microstage.move_to(new_x, current_pos[1])

            self._run_movement_in_thread(move_left)
        except ValueError:
            pass

    def _step_microstage_right(self, event):
        if self.microstage is None:
            return
        self._show_stepping_warning()
        try:
            self.microstage_status_var.set("MOVING...")
            self.microstage_status_label.config(foreground="orange")
            self.root.update_idletasks()
            step = abs(float(self.step_var.get()))
            current_pos = self.microstage.get_position()
            new_x = current_pos[0] + step
            if self.is_homed:
                new_x = min(self.microstage.x_max, new_x)

            def move_right():
                self.microstage.move_to(new_x, current_pos[1])

            self._run_movement_in_thread(move_right)
        except ValueError:
            pass

    def _step_microstage_up(self, event):
        if self.microstage is None:
            return
        self._show_stepping_warning()
        try:
            self.microstage_status_var.set("MOVING...")
            self.microstage_status_label.config(foreground="orange")
            self.root.update_idletasks()
            step = abs(float(self.step_var.get()))
            current_pos = self.microstage.get_position()
            new_y = current_pos[1] + step
            if self.is_homed:
                new_y = min(self.microstage.y_max, new_y)

            def move_up():
                self.microstage.move_to(current_pos[0], new_y)

            self._run_movement_in_thread(move_up)
        except ValueError:
            pass

    def _step_microstage_down(self, event):
        if self.microstage is None:
            return
        self._show_stepping_warning()
        try:
            self.microstage_status_var.set("MOVING...")
            self.microstage_status_label.config(foreground="orange")
            self.root.update_idletasks()
            step = abs(float(self.step_var.get()))
            current_pos = self.microstage.get_position()
            new_y = current_pos[1] - step
            if self.is_homed:
                new_y = max(self.microstage.y_min, new_y)

            def move_down():
                self.microstage.move_to(current_pos[0], new_y)

            self._run_movement_in_thread(move_down)
        except ValueError:
            pass

    def _tick_position_display(self) -> None:
        if not self._display_poll_active or self.microstage is None:
            return
        try:
            if self.is_homed:
                try:
                    x_um, y_um = self.microstage.get_position()
                    self.x_current_var.set(f"{x_um:.2f}")
                    self.y_current_var.set(f"{y_um:.2f}")
                except Exception:
                    self.x_current_var.set("Error")
                    self.y_current_var.set("Error")

            if self.microstage:
                is_moving = self.microstage.is_moving()
                current_status = self.microstage_status_var.get()
                special = {"HOMING...", "MOVING...", "Error"}

                if current_status == "HOMING...":
                    self.microstage_status_tooltip.update_text(
                        "Homing in progress; wait before issuing another move."
                    )
                elif current_status == "MOVING...":
                    self.microstage_status_tooltip.update_text(
                        "Move in progress; wait before issuing another move."
                    )
                elif current_status == "Ready":
                    self.microstage_status_tooltip.update_text(
                        "Status: Ready — the stage is ready for movement commands."
                    )
                elif current_status == "Not Homed":
                    self.microstage_status_tooltip.update_text(
                        "Status: Not Homed — run Calibrate Stage first."
                    )
                elif current_status == "Error":
                    self.microstage_status_tooltip.update_text(
                        "Status: Error — see message dialog or console."
                    )
                else:
                    self.microstage_status_tooltip.update_text(
                        f"Status: {current_status}"
                    )

                if is_moving:
                    if current_status not in special:
                        self.microstage_status_var.set("MOVING...")
                        self.microstage_status_label.config(foreground="orange")
                else:
                    if current_status == "MOVING...":
                        if self.is_homed:
                            self.microstage_status_var.set("Ready")
                            self.microstage_status_label.config(foreground="green")
                        else:
                            self.microstage_status_var.set("Not Homed")
                            self.microstage_status_label.config(foreground="orange")
                    elif current_status not in special:
                        if self.is_homed:
                            self.microstage_status_var.set("Ready")
                            self.microstage_status_label.config(foreground="green")
                        else:
                            self.microstage_status_var.set("Not Homed")
                            self.microstage_status_label.config(foreground="orange")
        except Exception as e:
            self.microstage_status_var.set("Error")
            self.microstage_status_label.config(foreground="red")
            self.root.after(
                0,
                lambda: print(f"MicrostageTkPanel display poll error: {e}"),
            )

        self._after_id = self.root.after(100, self._tick_position_display)
