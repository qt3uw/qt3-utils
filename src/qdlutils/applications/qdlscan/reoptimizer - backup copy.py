import logging
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple, Union

import numpy as np
from scipy.optimize import curve_fit

from qdlutils.applications.qdlscan.application_controller import ScanController

logger = logging.getLogger(__name__)

AXIS_INDEX = {"x": 0, "y": 1, "z": 2}


@dataclass
class AxisOptimizationResult:
    axis: str
    start_position: float
    scan_start: float
    scan_stop: float
    n_pixels: int
    scan_time: float
    data_positions: np.ndarray
    data_count_rates: np.ndarray
    final_position: float
    fit_success: bool
    fit_method: str
    message: str = ""


class Reoptimizer:
    """
    Headless line-scan optimizer for experiment pipelines.

    This class reuses the same core qdlscan controller calls used by the GUI
    optimization flow, but without creating any Tk windows.
    """

    def __init__(
        self,
        application_controller: ScanController,
        axis_limits: Optional[Dict[str, Tuple[float, float]]] = None,
        optimization_method: str = "gaussian",
        minimum_peak_height: float = 100.0,
        initial_position: Optional[Union[Tuple[float, float, float], Dict[str, float]]] = None,
    ) -> None:
        self.application_controller = application_controller
        self.axis_limits = axis_limits or {}
        self.optimization_method = optimization_method
        self.minimum_peak_height = minimum_peak_height
        self._axis_position_tracker: Dict[str, float] = {}

        if initial_position is not None:
            if isinstance(initial_position, dict):
                for axis in AXIS_INDEX:
                    if axis in initial_position and initial_position[axis] is not None:
                        self._axis_position_tracker[axis] = float(initial_position[axis])
            else:
                self._axis_position_tracker["x"] = float(initial_position[0])
                self._axis_position_tracker["y"] = float(initial_position[1])
                self._axis_position_tracker["z"] = float(initial_position[2])

    def _get_axis_position(self, axis: str) -> float:
        """Return axis position from controller, falling back to tracked value."""
        position_vector = self.application_controller.get_position()
        raw_position = position_vector[AXIS_INDEX[axis]]
        if raw_position is None:
            if axis in self._axis_position_tracker:
                return float(self._axis_position_tracker[axis])
            raise RuntimeError(
                f"Axis '{axis}' position is undefined (controller returned None). "
                "Provide initial_position to Reoptimizer or seed controller position before optimize_axis()."
            )

        axis_position = float(raw_position)
        self._axis_position_tracker[axis] = axis_position
        return axis_position

    def optimize_axis(
        self,
        axis: str,
        scan_range: float,
        n_pixels: int,
        scan_time: float,
        move_to_optimum: bool = True,
    ) -> AxisOptimizationResult:
        if axis not in AXIS_INDEX:
            raise ValueError(f"Invalid axis: {axis}")
        if scan_range <= 0:
            raise ValueError("scan_range must be > 0")
        if n_pixels < 1:
            raise ValueError("n_pixels must be >= 1")
        if scan_time <= 0:
            raise ValueError("scan_time must be > 0")

        start_position_axis = self._get_axis_position(axis)

        scan_start, scan_stop = self._compute_scan_window(
            axis=axis,
            center_position=start_position_axis,
            scan_range=scan_range,
        )

        counts = self.application_controller.scan_axis(
            axis=axis,
            start=scan_start,
            stop=scan_stop,
            n_pixels=n_pixels,
            scan_time=scan_time,
        )

        time_per_pixel = scan_time / n_pixels
        count_rates = counts / time_per_pixel
        positions = np.linspace(start=scan_start, stop=scan_stop, num=n_pixels)

        final_position, fit_success, fit_method, message = self._determine_optimal_position(
            positions=positions,
            count_rates=count_rates,
            start_position=start_position_axis,
            min_position=scan_start,
            max_position=scan_stop,
        )

        if move_to_optimum:
            self.application_controller.set_axis(axis=axis, position=float(final_position))
            self._axis_position_tracker[axis] = float(final_position)

        return AxisOptimizationResult(
            axis=axis,
            start_position=start_position_axis,
            scan_start=scan_start,
            scan_stop=scan_stop,
            n_pixels=n_pixels,
            scan_time=scan_time,
            data_positions=positions,
            data_count_rates=count_rates,
            final_position=float(final_position),
            fit_success=fit_success,
            fit_method=fit_method,
            message=message,
        )

    def optimize_axes(
        self,
        order: Iterable[str],
        scan_ranges: Dict[str, float],
        n_pixels: Union[int, Dict[str, int]],
        scan_times: Union[float, Dict[str, float]],
        move_to_optimum: bool = True,
    ) -> Dict[str, AxisOptimizationResult]:
        results: Dict[str, AxisOptimizationResult] = {}

        for axis in order:
            axis_pixels = n_pixels[axis] if isinstance(n_pixels, dict) else n_pixels
            axis_scan_time = scan_times[axis] if isinstance(scan_times, dict) else scan_times

            results[axis] = self.optimize_axis(
                axis=axis,
                scan_range=scan_ranges[axis],
                n_pixels=int(axis_pixels),
                scan_time=float(axis_scan_time),
                move_to_optimum=move_to_optimum,
            )

        return results

    def _compute_scan_window(
        self,
        axis: str,
        center_position: float,
        scan_range: float,
    ) -> Tuple[float, float]:
        min_position = center_position - (scan_range / 2.0)
        max_position = center_position + (scan_range / 2.0)

        if axis in self.axis_limits:
            allowed_min, allowed_max = self.axis_limits[axis]

            if min_position < allowed_min:
                shift = allowed_min - min_position
                min_position += shift
                max_position += shift
            if max_position > allowed_max:
                shift = allowed_max - max_position
                min_position += shift
                max_position += shift

        return min_position, max_position

    def _determine_optimal_position(
        self,
        positions: np.ndarray,
        count_rates: np.ndarray,
        start_position: float,
        min_position: float,
        max_position: float,
    ) -> Tuple[float, bool, str, str]:
        if self.optimization_method == "none":
            return float(start_position), True, "none", "Optimization method set to none."

        if self.optimization_method != "gaussian":
            raise ValueError(f"Unsupported optimization_method: {self.optimization_method}")

        def fit_function(x: np.ndarray, a: float, x0: float, sigma: float, c: float) -> np.ndarray:
            return a * np.exp(-((x - x0) ** 2) / (2.0 * sigma ** 2)) + c

        max_counts_idx = int(np.argmax(count_rates))
        max_counts = float(count_rates[max_counts_idx])
        position_max_counts = float(positions[max_counts_idx])
        min_counts = float(np.min(count_rates))

        a = max_counts - min_counts
        x0 = position_max_counts
        sigma = 0.300
        c = min_counts

        try:
            p, _ = curve_fit(
                f=fit_function,
                xdata=positions,
                ydata=count_rates,
                p0=[a, x0, sigma, c],
                bounds=[
                    [self.minimum_peak_height, min_position, 0.250, 0.0],
                    [np.inf, max_position, np.inf, np.inf],
                ],
            )
            return float(p[1]), True, "gaussian", "Gaussian fit converged."

        except Exception as exc:
            logger.info(f"Gaussian fit failed, falling back to argmax: {exc}")
            return position_max_counts, False, "argmax", "Gaussian fit failed; used argmax fallback."
