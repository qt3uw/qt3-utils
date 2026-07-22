import time
from .mcl_wrapper import MCL_Microdrive, MCL_MD_Exceptions

# --- Physical Constants ---
# The conversion factor from your manual: 1 microstep = 95.25 nm = 0.09525 µm = 0.00009525 mm
MICRONS_PER_MICROSTEP = 0.09525 
# A safe number of steps for each hop during homing, well within 16-bit limits.
HOMING_CHUNK_STEPS = 30000 # About 3 mm


class EncoderlessMicrostage:
    """
    A high-level Python wrapper to control a Mad City Labs MicroStage
    without encoders, implementing dead reckoning and high-precision move logic.
    """
    def __init__(self, config: dict = None):
        '''
        Initialize the EncoderlessMicrostage class.
        '''
        # Initialize the MCL_Microdrive and handle
        self.mcl = None
        self.handle = None
        
        # Set default configuration values
        self.x_min = 0.0
        self.x_max = 12000.0
        self.y_min = 0.0
        self.y_max = 12000.0
        self.velocity = 0.5
        
        # Apply configuration if provided
        if config:
            self.x_min = config.get('x_min', self.x_min)
            self.x_max = config.get('x_max', self.x_max)
            self.y_min = config.get('y_min', self.y_min)
            self.y_max = config.get('y_max', self.y_max)
            self.velocity = config.get('velocity', self.velocity)
        
        try:
            self.mcl = MCL_Microdrive()
            self.handle = self.mcl.init_handle()
        except Exception as e:
            print(f"FATAL: Could not connect to the stage. Error: {e}")
            raise
        
        # Internal position counters (bookkeeping) in microsteps.
        self.x_pos_steps = 0
        self.y_pos_steps = 0
        
        print(f"Connected to stage (Handle: {self.handle}). Position is unreferenced.")
        print(f"Software limits set to X: {self.x_min}-{self.x_max} µm, Y: {self.y_min}-{self.y_max} µm.")
        print("Run find_home() to establish a (0, 0) origin at the bottom-right corner.")

    def _wait_for_move(self):
        """Private helper function to block execution until a move is complete."""
        time.sleep(0.1)
        while self.is_moving():
            time.sleep(0.05)
        time.sleep(0.1)

    def find_home(self):
        """
        Performs a robust homing sequence by driving the stage against its physical
        limit switches to find the bottom-right corner, then defines it as (0, 0).
        """
        print("Starting homing sequence...")

        # --- Homing Y-Axis (moving in reverse to the 'bottom') ---
        print("Homing Y axis (moving to bottom limit)...")
        while True:
            status = bin(self.mcl.status(self.handle))
            if status[6] == "0":
                print("  - Y reverse limit switch is active.")
                break
            try:
                self.mcl.move_m(2, self.velocity, -HOMING_CHUNK_STEPS, self.handle)
            except MCL_MD_Exceptions as e:
                print("exception")
                break
            self._wait_for_move()
        
        # --- Homing X-Axis (moving forward to the 'right') ---
        # print("Homing X axis (moving to right limit)...")
        while True:
            status = bin(self.mcl.status(self.handle))

            if status[8] == "0":
                print("  - X reverse limit switch is active.")
                break
            try:
                self.mcl.move_m(1, self.velocity, -HOMING_CHUNK_STEPS, self.handle)
            except MCL_MD_Exceptions as e:
                print("exception")
                break
            self._wait_for_move()

        # Virtually set this physical location as our (0, 0) origin
        self.set_position(0, 0)
        print("Homing successful. Bottom-right corner is now defined as (0, 0).")

    def return_to_home(self):
        """Moves the stage back to the defined (0, 0) origin."""
        print("Returning to home (0, 0)...")
        self.find_home()

    def get_position(self):
        """Returns the current virtual position in micrometers (µm)."""
        x_microns = self.x_pos_steps * MICRONS_PER_MICROSTEP
        y_microns = self.y_pos_steps * MICRONS_PER_MICROSTEP
        return (x_microns, y_microns)

    def move_to(self, target_x_um, target_y_um):
        """
        Moves to an absolute position in µm with backlash compensation and optional step snapping.
        """
        
        if not (self.x_min <= target_x_um <= self.x_max and self.y_min <= target_y_um <= self.y_max):
            print(f"Target is outside allowed range of {self.x_min}-{self.x_max} by {self.y_min}-{self.y_max} µm.")
            target_x_um = max(self.x_min, min(self.x_max, target_x_um))
            target_y_um = max(self.y_min, min(self.y_max, target_y_um))
            print(f"Defaulting to nearest valid position within limits: ({target_x_um:.3f}, {target_y_um:.3f}) µm")

        
        self._execute_move(target_x_um, target_y_um)

        print(f"Arrived at {self.get_position()} µm")

    def _execute_move(self, target_x_um, target_y_um):
        """A private helper method that breaks large moves into smaller, safe chunks."""
        current_x_um, current_y_um = self.get_position()

        # --- Calculate total steps for each axis ---
        # For X-axis, user's positive (left) is hardware's negative.
        total_steps_x = round((target_x_um - current_x_um) / MICRONS_PER_MICROSTEP)
        # For Y-axis, user's positive (up) is hardware's positive.
        total_steps_y = round((target_y_um - current_y_um) / MICRONS_PER_MICROSTEP)

        # --- Execute moves sequentially, in chunks if necessary ---
        for axis, total_steps in [(1, total_steps_x), (2, total_steps_y)]:
            if total_steps == 0:
                continue
            
            remaining_steps = total_steps
            sign = 1 if total_steps > 0 else -1

            while remaining_steps != 0:
                chunk = sign * min(abs(remaining_steps), HOMING_CHUNK_STEPS)
                try:
                    self.mcl.move_m(axis, self.velocity, chunk, self.handle)
                except MCL_MD_Exceptions as e:
                    print(f"⚠️ Move aborted due to hardware error: {e}")
                    return
                self._wait_for_move()
                remaining_steps -= chunk
        
        self.set_position(target_x_um, target_y_um)

    def set_position(self, x_um=0, y_um=0):
        """Resets the internal counters to define the current location as (x, y) µm."""
        self.x_pos_steps = round(x_um / MICRONS_PER_MICROSTEP)
        self.y_pos_steps = round(y_um / MICRONS_PER_MICROSTEP)

    def is_moving(self):
        """Returns True if the stage is moving, False otherwise."""
        return True if self.mcl.move_status(self.handle) else False

    def close(self):
        """Releases the hardware handle."""
        if self.handle and self.mcl:
            self.mcl.release_handle(self.handle)
            self.handle = None
            print("Hardware handle released.")

