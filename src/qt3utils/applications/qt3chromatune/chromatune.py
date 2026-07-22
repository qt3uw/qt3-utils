import math
import threading
import time
from typing import Callable
import nkt_tools.NKTP_DLL as nkt

class Chromatune():
    MAIN_MODULE_ADDRESS = 0xF
    FILTER_MODULE_ADDRESS = 0x07

    def __init__(
        self,
        port_name: str,
        host_address: str,
        host_port: int,
        system_address: str,
        system_port: int,
        protocol_num: int = 0,
        ms_timeout: int = 100
    ):
        """Connects to the laser via ethernet and opens the port"""
        self.port_name = port_name
        port_data = nkt.pointToPointPortData(host_address, host_port, system_address, system_port, protocol_num, ms_timeout)

        add_res = nkt.pointToPointPortAdd(port_name, port_data)
        if add_res != 0:
            raise RuntimeError(f"pointToPointPortAdd failed: {nkt.P2PPortResultTypes(add_res)}")

        op_res = nkt.openPorts(port_name, autoMode=1, liveMode=1)
        if op_res != 0:
            raise RuntimeError(f"openPorts failed: {nkt.PortResultTypes(op_res)}")
        
        print("Successfully connected to Chromatune Laser")


    def close(self) -> None:
        """Turn emission off (best-effort) and tear down the port."""
        try:
            self.set_emission(False)
        except Exception:
            pass
        try:
            nkt.closePorts(self.port_name)
        finally:
            try:
                nkt.pointToPointPortDel(self.port_name)
            except Exception:
                pass

    # -------------------- helpers --------------------

    def _read_u8(self, reg: int, index: int = -1, dev: int = None) -> int:
        dev = self.MAIN_MODULE_ADDRESS if dev is None else dev
        res, val = nkt.registerReadU8(self.port_name, dev, reg, index)
        if res != 0:
            raise RuntimeError(f"registerReadU8 reg=0x{reg:02X} failed: {nkt.RegisterResultTypes(res)}")
        return val

    def _read_s16(self, reg: int, index: int = -1, dev: int = None) -> int:
        dev = self.MAIN_MODULE_ADDRESS if dev is None else dev
        res, val = nkt.registerReadS16(self.port_name, dev, reg, index)
        if res != 0:
            raise RuntimeError(f"registerReadS16 reg=0x{reg:02X} failed: {nkt.RegisterResultTypes(res)}")
        return val

    def _read_u16(self, reg: int, index: int = -1, dev: int = None) -> int:
        dev = self.MAIN_MODULE_ADDRESS if dev is None else dev
        res, val = nkt.registerReadU16(self.port_name, dev, reg, index)
        if res != 0:
            raise RuntimeError(f"registerReadU16 reg=0x{reg:02X} failed: {nkt.RegisterResultTypes(res)}")
        return val

    def _read_u32(self, reg: int, index: int = -1, dev: int = None) -> int:
        dev = self.MAIN_MODULE_ADDRESS if dev is None else dev
        res, val = nkt.registerReadU32(self.port_name, dev, reg, index)
        if res != 0:
            raise RuntimeError(f"registerReadU32 reg=0x{reg:02X} failed: {nkt.RegisterResultTypes(res)}")
        return val

    def _write_u8(self, reg: int, value: int, index: int = -1, dev: int = None) -> None:
        dev = self.MAIN_MODULE_ADDRESS if dev is None else dev
        res = nkt.registerWriteU8(self.port_name, dev, reg, value, index)
        if res != 0:
            raise RuntimeError(f"registerWriteU8 reg=0x{reg:02X} val={value} failed: {nkt.RegisterResultTypes(res)}")

    def _write_u16(self, reg: int, value: int, index: int = -1, dev: int = None) -> None:
        dev = self.MAIN_MODULE_ADDRESS if dev is None else dev
        res = nkt.registerWriteU16(self.port_name, dev, reg, value, index)
        if res != 0:
            raise RuntimeError(f"registerWriteU16 reg=0x{reg:02X} val={value} failed: {nkt.RegisterResultTypes(res)}")

    def _write_u32(self, reg: int, value: int, index: int = -1, dev: int = None) -> None:
        dev = self.MAIN_MODULE_ADDRESS if dev is None else dev
        res = nkt.registerWriteU32(self.port_name, dev, reg, value, index)
        if res != 0:
            raise RuntimeError(f"registerWriteU32 reg=0x{reg:02X} val={value} failed: {nkt.RegisterResultTypes(res)}")


    # -------------------- MAIN module API --------------------

    # Emission (0x30, U8; 0=OFF, 3=ON; intermediate during transitions)
    def get_emission(self) -> int:
        """Return raw emission state byte from reg 0x30 (0=OFF, 3=ON, others=intermediate)."""
        return self._read_u8(0x30, -1)

    def set_emission(self, on: bool) -> None:
        """Set emission (True→ON, False→OFF) via reg 0x30."""
        self._write_u8(0x30, 0x03 if on else 0x00, -1)


    # Setup (0x31, U8: 0=ConstCurrent, 1=ConstPower, 2=ExtCurr, 3=ExtPower, 4=PowerLock)
    # Note: the official sdk manual says to use unsigned 16 bit for get_setup_mode but that throws an error...
    def get_setup_mode(self) -> int:
        """Read 8-bit Setup mode from reg 0x31."""
        return self._read_u8(0x31, -1)

    def set_setup_mode(self, mode: int) -> None:
        """Write 16-bit Setup mode to reg 0x31 (0..4)."""
        if not (0 <= mode <= 4):
            raise ValueError("mode must be in 0..4")
        self._write_u16(0x31, mode, -1)


    # Interlock (0x32, 2 bytes: LSB=state, MSB=source). Write >0 to reset; write 0 to disable.
    def get_interlock_raw(self) -> int:
        """Return 16-bit interlock word from reg 0x32 (LSB=state, MSB=source)."""
        return self._read_u16(0x32, -1)

    def reset_interlock(self) -> None:
        """Reset interlock (write value >0 to reg 0x32)."""
        self._write_u8(0x32, 1, -1)

    def disable_interlock(self) -> None:
        """Disable interlock relays (write 0 to reg 0x32)."""
        self._write_u8(0x32, 0, -1)


    # Pulse picker ratio (0x34) — format varies; you can read as U16 and handle small ratios.
    def get_pulse_picker_ratio(self) -> int:
        """Read pulse picker ratio (reg 0x34). For ratios <256 it fits in 8 bits; we return U16 value."""
        return self._read_u16(0x34, -1)

    def set_pulse_picker_ratio(self, ratio: int) -> None:
        """Write pulse picker ratio (reg 0x34)."""
        if not (0 <= ratio <= 0xFFFF):
            raise ValueError("ratio must be 0..65535")
        self._write_u16(0x34, ratio, -1)


    # Watchdog interval (0x36, U8 seconds; 0 disables auto-shutoff)
    def get_watchdog_seconds(self) -> int:
        return self._read_u8(0x36, -1)

    def set_watchdog_seconds(self, seconds: int) -> None:
        if not (0 <= seconds <= 255):
            raise ValueError("watchdog seconds must be 0..255")
        self._write_u8(0x36, seconds, -1)


    # Power level setpoint (0x37, U16 permille 0..1000) and Current level (0x38, U16 permille)
    def get_power_level_permille(self) -> int:
        return self._read_u16(0x37, -1)

    def set_power_level_permille(self, permille: int) -> None:
        if not (0 <= permille <= 1000):
            raise ValueError("power permille must be 0..1000")
        self._write_u16(0x37, permille, -1)

    def get_current_level_permille(self) -> int:
        return self._read_u16(0x38, -1)

    def set_current_level_permille(self, permille: int) -> None:
        if not (0 <= permille <= 1000):
            raise ValueError("current permille must be 0..1000")
        self._write_u16(0x38, permille, -1)


    # NIM delay (0x39, U16 0..1023)
    def get_nim_delay(self) -> int:
        return self._read_u16(0x39, -1)

    def set_nim_delay(self, value: int) -> None:
        if not (0 <= value <= 1023):
            raise ValueError("NIM delay must be 0..1023")
        self._write_u16(0x39, value, -1)


    # Inlet temperature (0x11, S16 in 0.1°C)
    def get_inlet_temperature_c(self) -> float:
        tenths = self._read_s16(0x11, -1)
        return tenths / 10.0
    

    # System type (0x6B, U8: 0=EXTREME, 1=FIANIUM on older variants; Chromatune main says 0x01)
    def get_system_type(self) -> int:
        return self._read_u8(0x6B, -1)
    

    # Status bits (0x66, U16)
    # def get_status_bits(self) -> int:
    #     return self._read_u16(0x66, -1)
    
    # def status_dict(self) -> dict:
    #     """Decode a few commonly-used status bits from reg 0x66."""
    #     bits = self.get_status_bits()
    #     return {
    #         "emission_on": bool(bits & (1 << 0)),
    #         "interlock_relays_off": bool(bits & (1 << 1)),
    #         "interlock_loop_open": bool(bits & (1 << 3)),
    #         "supply_voltage_low": bool(bits & (1 << 5)),
    #         "inlet_temp_out_of_range": bool(bits & (1 << 6)),
    #         "system_error_code_present": bool(bits & (1 << 15)),
    #     }
    

    # -------------------- FILTER module (dev 0x07) --------------------

    # --- basic controls ---
    def get_shutter_mode(self) -> int:
        """reg 0x30 (U8): 0=closed, 1=open, 2=auto."""
        return self._read_u8(0x30, dev=self.FILTER_MODULE_ADDRESS)

    def set_shutter_mode(self, mode: int) -> None:
        if mode not in (0, 1, 2):
            raise ValueError("shutter mode must be 0(closed),1(open),2(auto)")
        self._write_u8(0x30, mode, dev=self.FILTER_MODULE_ADDRESS)

    def get_power_mode(self) -> int:
        """reg 0x31 (U8): 0=Manual,1=Max,2=Passive,3=Active,4=Tracker."""
        return self._read_u8(0x31, dev=self.FILTER_MODULE_ADDRESS)

    def set_power_mode(self, mode: int) -> None:
        if mode not in (0, 1, 2, 3, 4):
            raise ValueError("power mode must be 0..4")
        self._write_u8(0x31, mode, dev=self.FILTER_MODULE_ADDRESS)


    # --- filter setting (center/bandwidth/power) ---
    def get_center_wavelength_nm(self) -> float:
        v = self._read_u16(0x32, index=0, dev=self.FILTER_MODULE_ADDRESS)
        return v / 10.0

    def set_center_wavelength_nm(self, nm: float) -> None:
        self._write_u16(0x32, int(round(nm * 10)), index=0, dev=self.FILTER_MODULE_ADDRESS)

    def get_bandwidth_nm(self) -> float:
        v = self._read_u16(0x32, index=2, dev=self.FILTER_MODULE_ADDRESS)   # byte offset 2
        return v / 10.0

    def set_bandwidth_nm(self, nm: float) -> None:
        self._write_u16(0x32, int(round(nm * 10)), index=2, dev=self.FILTER_MODULE_ADDRESS)

    def get_filter_power_nw(self) -> int:
        return self._read_u32(0x32, index=4, dev=self.FILTER_MODULE_ADDRESS)  # byte offset 4

    def set_filter_power_nw(self, power_nw: int) -> None:
        if power_nw < 0:
            raise ValueError("power must be >= 0 nW")
        self._write_u32(0x32, int(power_nw), index=4, dev=self.FILTER_MODULE_ADDRESS)

    def set_filter(self, center_nm: float, bandwidth_nm: float, power_nw: int | None = None) -> None:
        self.set_center_wavelength_nm(center_nm)
        self.set_bandwidth_nm(bandwidth_nm)
        if power_nw is not None:
            self.set_filter_power_nw(power_nw)



    # --- ND filter ---
    def get_nd_attenuation_db(self) -> float:
        """reg 0x33 (U16, 0.001 dB)."""
        v = self._read_u16(0x33, dev=self.FILTER_MODULE_ADDRESS)
        return v / 1000.0

    def set_nd_attenuation_db(self, db: float) -> None:
        if db < 0:
            raise ValueError("ND attenuation must be >= 0 dB")
        self._write_u16(0x33, int(round(db * 1000)), dev=self.FILTER_MODULE_ADDRESS)


    # --- limits & identity ---
    def get_bandwidth_limits_nm(self) -> tuple[float, float]:
        """reg 0x35: (max,min) in 0.1 nm; returns (min, max) as floats."""
        bw_max = self._read_u16(0x35, index=0, dev=self.FILTER_MODULE_ADDRESS) / 10.0
        bw_min = self._read_u16(0x35, index=1, dev=self.FILTER_MODULE_ADDRESS) / 10.0
        return (bw_min, bw_max)

    def get_filter_firmware(self) -> tuple[int, str]:
        """reg 0x64: (U16 version, ASCII up to 64B)."""
        ver = self._read_u16(0x64, dev=self.FILTER_MODULE_ADDRESS)
        txt = self._read_str(0x64, 64, dev=self.FILTER_MODULE_ADDRESS)
        return ver, txt

    def get_filter_serial(self) -> str:
        """reg 0x65: 8-char ASCII serial."""
        return self._read_str(0x65, 8, dev=self.FILTER_MODULE_ADDRESS)


    # --- status & telemetry ---
    def get_status_bits_filter(self) -> int:
        """reg 0x66 (U32)."""
        return self._read_u32(0x66, dev=self.FILTER_MODULE_ADDRESS)

    def status_dict_filter(self) -> dict:
        """Decode common bits from reg 0x66."""
        b = self.get_status_bits_filter()
        return {
            "shutter_open":           bool(b & (1 << 0)),
            "interlock_off":          bool(b & (1 << 1)),
            "module_temp_oob":        bool(b & (1 << 6)),
            "driver_temp_oob":        bool(b & (1 << 7)),
            "beam_dump_temp_oob":     bool(b & (1 << 8)),
            "image_ready":            bool(b & (1 << 10)),
            "output_ok":              bool(b & (1 << 12)),
            "lwp_moving":             bool(b & (1 << 16)),
            "swp_moving":             bool(b & (1 << 17)),
            "blocking_moving":        bool(b & (1 << 18)),
            "nd_moving":              bool(b & (1 << 19)),
            "shutter_moving":         bool(b & (1 << 20)),
            "motor_stalled":          bool(b & (1 << 28)),
            "filter_setting_changed": bool(b & (1 << 29)),
            "motor_speed_degraded":   bool(b & (1 << 31)),
        }

    def get_photodiode_power_nw(self) -> int:
        """reg 0x76 (U32, nW)."""
        return self._read_u32(0x76, dev=self.FILTER_MODULE_ADDRESS)

    def get_estimated_max_power_nw(self) -> int:
        """reg 0x77 (U32, nW)."""
        return self._read_u32(0x77, dev=self.FILTER_MODULE_ADDRESS)

    def get_runtime_seconds(self) -> int:
        """reg 0x80 (U32)."""
        return self._read_u32(0x80, dev=self.FILTER_MODULE_ADDRESS)
    

    # --- Wavelength Sweep Scan ---

    def _wait_filter_idle(self, timeout_s: float = 3.0, poll_s: float = 0.02) -> bool:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            b = self.get_status_bits_filter()
            moving = (b >> 16) & 0b1_1111  # bits 16..20
            if moving == 0:
                return True
            time.sleep(poll_s)
        return False

    def sweep_wavelength(
        self,
        start_nm: float,
        end_nm: float,
        t_forward_s: float,
        *,
        t_backward_s: float | None = None,
        loops: int = 1,
        step_nm: float = 0.1,
        wait_for_idle: bool = True,
        settle_ms: int = 50,
        read_power: bool = False,
        callback: Callable | None = None,
        stop_event: threading.Event | None = None,
    ) -> None:
        """
        Blockingly sweep center wavelength between start_nm and end_nm.

        loops:
          1 → start→end only
          2 → start→end then end→start
          3 → (start→end→start) + start→end, etc.

        t_backward_s:
          If None, use t_forward_s for the backward leg.
        """
        if loops < 1:
            return

        # Clamp to device limits
        bw_min, bw_max = self.get_bandwidth_limits_nm()  # (min,max)
        # Chromatune wavelength range isn’t in that call; assume caller picks a valid range.

        # Build one leg as a list of setpoints and dwell time
        def make_leg(a_nm: float, b_nm: float, dur_s: float):
            distance = abs(b_nm - a_nm)
            steps = max(1, math.ceil(distance / max(step_nm, 1e-6)))
            dwell = dur_s / steps
            # Generate inclusive endpoints (steps points)
            if b_nm >= a_nm:
                wls = [a_nm + i * (distance / steps) for i in range(steps)]
                wls.append(b_nm)
            else:
                wls = [a_nm - i * (distance / steps) for i in range(steps)]
                wls.append(b_nm)
            return wls, dwell

        back_time = t_backward_s if t_backward_s is not None else t_forward_s

        # Execute one leg (list of wavelengths)
        def run_leg(wls: list[float], dwell_s: float):
            for wl in wls:
                if stop_event and stop_event.is_set():
                    return
                self.set_center_wavelength_nm(wl)
                if wait_for_idle:
                    self._wait_filter_idle(timeout_s=min(dwell_s, 1.0))
                if settle_ms > 0:
                    time.sleep(settle_ms / 1000.0)
                power = None
                if read_power:
                    try:
                        power = self.get_photodiode_power_nw()
                    except Exception:
                        power = None
                if callback:
                    try:
                        callback(wavelength_nm=wl, power_nw=power)
                    except Exception:
                        pass
                # Use remaining dwell time for pacing
                # (We already waited during settle + idle; this tops it up.)
                if dwell_s > 0:
                    time.sleep(max(0.0, dwell_s - (settle_ms / 1000.0)))

        # Prepare forward/backward wavelength lists once
        f_wls, f_dwell = make_leg(start_nm, end_nm, t_forward_s)
        b_wls, b_dwell = make_leg(end_nm, start_nm, back_time)

        # Ensure emission/shutter are in a sane state (best effort; ignore errors)
        try:
            self.set_shutter_mode(2)  # auto
        except Exception:
            pass

        # Run the requested number of loops
        for k in range(loops):
            # even-numbered legs: forward; odd: backward
            if (k % 2) == 0:
                run_leg(f_wls, f_dwell)
            else:
                run_leg(b_wls, b_dwell)


    # --- spectrum ---
    # def get_spectrum_range_pixels(self) -> tuple[int, int]:
    #     """reg 0xE3: (start, end); count = end - start."""
    #     start = self._read_u16(0xE3, index=0, dev=self.FILTER_MODULE_ADDRESS)
    #     end   = self._read_u16(0xE3, index=1, dev=self.FILTER_MODULE_ADDRESS)
    #     return start, end

    # def _filter_status_bits(self) -> int:
    #     return self._read_u32(0x66, dev=self.FILTER_MODULE_ADDRESS)

    # def _wait_image_ready(self, timeout_s: float = 3.0, poll_s: float = 0.05) -> bool:
    #     """Wait for 0x66 bit10 (image ready) AND bit0 (shutter open)."""
    #     import time
    #     deadline = time.time() + timeout_s
    #     while time.time() < deadline:
    #         b = self._filter_status_bits()
    #         if (b & (1 << 10)) and (b & (1 << 0)):
    #             return True
    #         time.sleep(poll_s)
    #     return False

    # def _set_array_index_bytes(self, byte_offset: int) -> None:
    #     """reg 0x8F (U32): byte offset for E4/E5 array reads."""
    #     self._write_u32(0x8F, int(byte_offset), dev=self.FILTER_MODULE_ADDRESS)

    # def read_wavelengths_nm(self) -> list[float]:
    #     """
    #     Read wavelength array (reg 0xE5). Values are U16 with 0.02 nm resolution.
    #     Wavelengths are static; cache them if desired.
    #     """
    #     start, end = self.get_spectrum_range_pixels()
    #     n = max(0, end - start)
    #     wl_nm: list[float] = []
    #     for i in range(n):
    #         self._set_array_index_bytes(2 * i)                 # 2 bytes per U16
    #         raw = self._read_u16(0xE5, dev=self.FILTER_MODULE_ADDRESS)
    #         wl_nm.append(raw * 0.02)
    #     return wl_nm

    # def read_amplitudes(self) -> list[int]:
    #     """
    #     Read spectral amplitudes (reg 0xE4). Each element is U16.
    #     Units reported in docs vary (uW/nm vs mW/nm); treat as raw counts and
    #     scale per your firmware if needed.
    #     """
    #     if not self._wait_image_ready():
    #         raise TimeoutError("Spectral image not ready / shutter not open (status 0x66)")

    #     start, end = self.get_spectrum_range_pixels()
    #     n = max(0, end - start)
    #     amps: list[int] = []
    #     for i in range(n):
    #         self._set_array_index_bytes(2 * i)
    #         raw = self._read_u16(0xE4, dev=self.FILTER_MODULE_ADDRESS)
    #         amps.append(raw)
    #     return amps

    # def read_full_spectrum(self, refresh_wavelengths: bool = False) -> tuple[list[float], list[int]]:
    #     """
    #     Return (wavelengths_nm, amplitudes). Wavelengths are cached by default.
    #     """
    #     if not hasattr(self, "_cached_wl_nm") or refresh_wavelengths:
    #         self._cached_wl_nm = self.read_wavelengths_nm()
    #     amplitudes = self.read_amplitudes()
    #     m = min(len(self._cached_wl_nm), len(amplitudes))
    #     return self._cached_wl_nm[:m], amplitudes[:m]
