import logging
import tkinter as tk
from tkinter import ttk
from typing import Tuple

import numpy as np

import qt3utils.datagenerators.spectrometers.andor as andor
from qt3utils.applications.controllers.utils import (
    make_label_and_entry,
    make_label_and_option_menu,
    make_label_and_check_button,
    make_label_frame,
    make_separator,
    prepare_list_for_option_menu,
)


class AndorSpectrometerController:

    def __init__(self, logger_level: int):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logger_level)

        self.spectrometer_config = andor.AndorSpectrometerConfig()

        # Changing supported acquisition modes to remove "run until abort" which is nonsensical for this application.
        self.spectrometer_config.SUPPORTED_ACQUISITION_MODES = (
            self.spectrometer_config.AcquisitionMode.SINGLE_SCAN.name,
            self.spectrometer_config.AcquisitionMode.ACCUMULATE.name,
            self.spectrometer_config.AcquisitionMode.KINETICS.name,
        )
        self.spectrometer_daq = andor.AndorSpectrometerDataAcquisition(self.spectrometer_config)

        self.spectrometer_config.open()

        self.last_config_dict = {}

        self.last_measured_spectrum = None
        self.last_wavelength_array = None

    @property
    def clock_rate(self) -> float:
        """
        The clock rate of a single exposure (1/exposure_time in Hz).
        """
        exposure_time = self.spectrometer_config.exposure_time
        return 1 / exposure_time if exposure_time > 0 else np.inf

    def start(self) -> None:
        """
        Nothing to be done in this method. All acquisitions are happening in the "sample_spectrum" method.
        """
        self.logger.debug('Starting controller.')

    def stop(self) -> None:
        """
        Stopping data acquisition.
        """
        self.spectrometer_daq.stop_acquisition()
        self.logger.debug('Stopping controller.')

    def close(self) -> None:
        # self.spectrometer_config.close()
        pass

    def sample_spectrum(self) -> Tuple[np.ndarray, np.ndarray]:
        acq_mode = self.spectrometer_config.acquisition_mode
        if acq_mode == self.spectrometer_config.AcquisitionMode.SINGLE_SCAN:
            return self.spectrometer_daq.acquire('single')
        elif acq_mode == self.spectrometer_config.AcquisitionMode.ACCUMULATE:
            return self.spectrometer_daq.acquire('accumulation')
        elif acq_mode == self.spectrometer_config.AcquisitionMode.KINETIC_SERIES:
            return self.spectrometer_daq.acquire('kinetic series')

    def configure(self, config_dict: dict) -> None:
        """
        This method is used to configure the spectrometer with the provided settings.
        """
        self.logger.debug("Calling configure on the Andor spectrometer controller")
        self.last_config_dict.update(config_dict)

        # Device Settings
        ccd_value = config_dict.get('ccd_device_index', self.spectrometer_config.ccd_device_index)
        self.spectrometer_config.ccd_device_index = int(ccd_value) if ccd_value is not None else -1
        spg_value = config_dict.get('spg_device_index', self.spectrometer_config.spg_device_index)
        self.spectrometer_config.spg_device_index = int(spg_value) if spg_value is not None else -1
        # Spectrograph Settings
        self.spectrometer_config.current_grating = str(config_dict.get(
            'grating', self.spectrometer_config.current_grating))
        self.spectrometer_config.center_wavelength = config_dict.get(
            'center_wavelength', self.spectrometer_config.center_wavelength)
        # -------------------------------
        self.spectrometer_config.pixel_offset = config_dict.get(
            'pixel_offset', self.spectrometer_config.pixel_offset)
        self.spectrometer_config.wavelength_offset = config_dict.get(
            'wavelength_offset', self.spectrometer_config.wavelength_offset)
        # -------------------------------
        self.spectrometer_config.input_port = config_dict.get(
            'input_port', self.spectrometer_config.input_port)
        self.spectrometer_config.output_port = config_dict.get(
            'output_port', self.spectrometer_config.output_port)

        # Acquisition Settings
        self.spectrometer_config.read_mode = config_dict.get(
            'read_mode', self.spectrometer_config.read_mode)
        self.spectrometer_config.acquisition_mode = config_dict.get(
            'acquisition_mode', self.spectrometer_config.acquisition_mode)
        self.spectrometer_config.trigger_mode = config_dict.get(
            'trigger_mode', self.spectrometer_config.trigger_mode)
        # -------------------------------
        self.spectrometer_config.exposure_time = config_dict.get(
            'exposure_time', self.spectrometer_config.exposure_time)
        self.spectrometer_config.number_of_accumulations = config_dict.get(
            'no_of_accumulations', self.spectrometer_config.number_of_accumulations)
        self.spectrometer_config.accumulation_cycle_time = config_dict.get(
            'accumulation_cycle_time', self.spectrometer_config.accumulation_cycle_time)
        self.spectrometer_config.number_of_kinetics = config_dict.get(
            'no_of_kinetics', self.spectrometer_config.number_of_kinetics)
        self.spectrometer_config.kinetic_cycle_time = config_dict.get(
            'kinetic_cycle_time', self.spectrometer_config.kinetic_cycle_time)
        # -------------------------------
        self.spectrometer_config.baseline_clamp = config_dict.get(
            'baseline_clamp', self.spectrometer_config.baseline_clamp)
        self.spectrometer_config.remove_cosmic_rays = config_dict.get(
            'cosmic_ray_removal', self.spectrometer_config.remove_cosmic_rays)
        # -------------------------------
        single_track_center_row = config_dict.get(
            'single_track_center_row', self.spectrometer_config.single_track_read_mode_parameters.track_center_row)
        single_track_height = config_dict.get(
            'single_track_height', self.spectrometer_config.single_track_read_mode_parameters.track_height)
        self.spectrometer_config.single_track_read_mode_parameters = andor.SingleTrackReadModeParameters(
            single_track_center_row, single_track_height)

        # Temperature Settings
        self.spectrometer_config.sensor_temperature_set_point = config_dict.get(
            'target_sensor_temperature', self.spectrometer_config.sensor_temperature_set_point)
        self.spectrometer_config.cooler_persistence_mode = config_dict.get(
            'cooler_persistence', self.spectrometer_config.cooler_persistence_mode)

    def configure_view(self, gui_root: tk.Toplevel) -> None:
        """
        This method launches a GUI window to configure the data controller.
        """
        # TODO: Consider putting in Tab Widget (ttk.Notebook)
        config_win = tk.Toplevel(gui_root)
        config_win.grab_set()
        config_win.title('Andor Spectrometer Settings')

        label_padx = 10

        # Device Settings
        row = 0
        device_settings_frame = make_label_frame(config_win, 'Device Settings', row)

        frame_row = 0
        ccd_device_list = prepare_list_for_option_menu(self.spectrometer_config.ccd_device_list)
        ccd_device_value = str(self.spectrometer_config.ccd_device_index)
        ccd_device_value = ccd_device_value if ccd_device_value in ccd_device_list else 'None'
        _, _, ccd_device_index_var = make_label_and_option_menu(
            device_settings_frame, 'CCD Device Index', frame_row,
            ccd_device_list, ccd_device_value, label_padx)

        frame_row += 1
        spg_device_list = prepare_list_for_option_menu(self.spectrometer_config.spg_device_list)
        spg_device_value = str(self.spectrometer_config.spg_device_index)
        spg_device_value = spg_device_value if spg_device_value in spg_device_list else 'None'
        _, _, spg_device_index_var = make_label_and_option_menu(
            device_settings_frame, 'Spectrograph Device Index', frame_row,
            spg_device_list, spg_device_value, label_padx)

        # Spectrograph Settings
        row += 1
        spg_settings_frame = make_label_frame(config_win, 'Spectrograph Settings', row)

        frame_row = 0
        grating_list = prepare_list_for_option_menu(self.spectrometer_config.grating_list)
        _, _, grating_var = make_label_and_option_menu(
            spg_settings_frame, 'Grating', frame_row,
            grating_list, self.spectrometer_config.current_grating, label_padx)

        frame_row += 1
        _, _, center_wavelength_var = make_label_and_entry(
            spg_settings_frame, 'Center Wavelength (nm)', frame_row,
            self.spectrometer_config.center_wavelength, tk.DoubleVar, label_padx)

        frame_row += 1
        make_separator(spg_settings_frame, frame_row)

        frame_row += 1
        _, _, pixel_offset_var = make_label_and_entry(
            spg_settings_frame, 'Calibration Pixel Offset', frame_row,
            self.spectrometer_config.pixel_offset, tk.DoubleVar, label_padx)

        frame_row += 1
        _, _, wavelength_offset_var = make_label_and_entry(
            spg_settings_frame, 'Calibration Wavelength Offset (nm)', frame_row,
            self.spectrometer_config.wavelength_offset, tk.DoubleVar, label_padx)

        frame_row += 1
        make_separator(spg_settings_frame, frame_row)

        frame_row += 1
        flipper_mirror_list = self.spectrometer_config.SpectrographFlipperMirrorPort._member_names_
        _, _, input_port_var = make_label_and_option_menu(
            spg_settings_frame, 'Input Port', frame_row,
            flipper_mirror_list, self.spectrometer_config.input_port, label_padx)

        frame_row += 1
        _, _, output_port_var = make_label_and_option_menu(
            spg_settings_frame, 'Output Port', frame_row,
            flipper_mirror_list, self.spectrometer_config.output_port, label_padx)

        # Acquisition Settings
        row += 1
        acq_settings_frame = make_label_frame(config_win, 'Acquisition Settings', row)

        frame_row = 0
        _, _, read_mode_var = make_label_and_option_menu(
            acq_settings_frame, 'Read Mode', frame_row,
            self.spectrometer_config.SUPPORTED_READ_MODES, self.spectrometer_config.read_mode, label_padx)

        frame_row += 1
        _, _, acquisition_mode_var = make_label_and_option_menu(
            acq_settings_frame, 'Acquisition Mode', frame_row,
            self.spectrometer_config.SUPPORTED_ACQUISITION_MODES, self.spectrometer_config.acquisition_mode, label_padx)

        frame_row += 1
        _, _, trigger_mode_var = make_label_and_option_menu(
            acq_settings_frame, 'Trigger Mode', frame_row,
            self.spectrometer_config.SUPPORTED_TRIGGER_MODES, self.spectrometer_config.trigger_mode, label_padx)

        frame_row += 1
        make_separator(acq_settings_frame, frame_row)

        frame_row += 1
        _, _, exposure_time_var = make_label_and_entry(
            acq_settings_frame, 'Exposure Time (seconds)', frame_row,
            self.spectrometer_config.exposure_time, tk.DoubleVar, label_padx)

        frame_row += 1
        _, _, no_of_accumulations_var = make_label_and_entry(
            acq_settings_frame,  'No. of Accumulations', frame_row,
            self.spectrometer_config.number_of_accumulations, tk.IntVar, label_padx)

        frame_row += 1
        _, _, accumulation_cycle_time_var = make_label_and_entry(
            acq_settings_frame, 'Accumulation Cycle Time (seconds)', frame_row,
            self.spectrometer_config.accumulation_cycle_time, tk.DoubleVar, label_padx)

        frame_row += 1
        _, _, no_of_kinetics_var = make_label_and_entry(
            acq_settings_frame, 'No. of Kinetics', frame_row,
            self.spectrometer_config.number_of_kinetics, tk.IntVar, label_padx)

        frame_row += 1
        _, _, kinetic_cycle_time_var = make_label_and_entry(
            acq_settings_frame, 'Kinetic Cycle Time (seconds)', frame_row,
            self.spectrometer_config.kinetic_cycle_time, tk.DoubleVar, label_padx)

        frame_row += 1
        make_separator(acq_settings_frame, frame_row)

        frame_row += 1
        _, _, baseline_clamp_var = make_label_and_check_button(
            acq_settings_frame, 'Clamp Baseline', frame_row,
            self.spectrometer_config.baseline_clamp, label_padx)

        frame_row += 1
        _, _, cosmic_ray_removal_var = make_label_and_check_button(
            acq_settings_frame, 'Cosmic Ray Removal', frame_row,
            self.spectrometer_config.remove_cosmic_rays, label_padx)

        frame_row += 1
        make_separator(acq_settings_frame, frame_row)

        frame_row += 1
        label_text = f'Single Track Center Row [1, {self.spectrometer_config.ccd_info.number_of_pixels_vertically}]'
        _, _, single_track_center_row_var = make_label_and_entry(
            acq_settings_frame, label_text, frame_row,
            self.spectrometer_config.single_track_read_mode_parameters.track_center_row, tk.IntVar, label_padx)

        frame_row += 1
        _, _, single_track_height_var = make_label_and_entry(
            acq_settings_frame, 'Single Track Height', frame_row,
            self.spectrometer_config.single_track_read_mode_parameters.track_height, tk.IntVar, label_padx)

        # Temperature Settings
        row += 1
        temp_settings_frame = make_label_frame(config_win, 'Temperature Settings', row)

        frame_row = 0
        _, _, target_sensor_temperature_var = make_label_and_entry(
            temp_settings_frame, 'Target Sensor Temperature (°C)', frame_row,
            self.spectrometer_config.sensor_temperature_set_point, tk.IntVar, label_padx)

        frame_row += 1
        _, _, cooler_persistence_var = make_label_and_check_button(
            temp_settings_frame, 'Cooler Persistence', frame_row,
            self.spectrometer_config.cooler_persistence_mode, label_padx)

        # Pack variables into a dictionary to pass to the _set_from_gui method
        gui_info = {
            # Device Settings
            'ccd_device_index': ccd_device_index_var,
            'spg_device_index': spg_device_index_var,
            # Spectrograph Settings
            'grating': grating_var,
            'center_wavelength': center_wavelength_var,
            # -------------------------------
            'pixel_offset': pixel_offset_var,
            'wavelength_offset': wavelength_offset_var,
            # -------------------------------
            'input_port': input_port_var,
            'output_port': output_port_var,
            # Acquisition Settings
            'read_mode': read_mode_var,
            'acquisition_mode': acquisition_mode_var,
            'trigger_mode': trigger_mode_var,
            # -------------------------------
            'exposure_time': exposure_time_var,
            'no_of_accumulations': no_of_accumulations_var,
            'accumulation_cycle_time': accumulation_cycle_time_var,
            'no_of_kinetics': no_of_kinetics_var,
            'kinetic_cycle_time': kinetic_cycle_time_var,
            # -------------------------------
            'baseline_clamp': baseline_clamp_var,
            'cosmic_ray_removal': cosmic_ray_removal_var,
            # -------------------------------
            'single_track_center_row': single_track_center_row_var,
            'single_track_height': single_track_height_var,
            # Temperature Settings
            'target_sensor_temperature': target_sensor_temperature_var,
            'cooler_persistence': cooler_persistence_var,
        }

        row += 1
        ttk.Button(config_win, text='Set', command=lambda: self._set_from_gui(gui_info)).grid(row=row, column=0)
        ttk.Button(config_win, text='Close', command=config_win.destroy).grid(row=row, column=1)

    def _set_from_gui(self, gui_vars: dict) -> None:
        """
        Sets the spectrometer configuration from the GUI.
        """
        config_dict = {k: v.get() if v.get() not in ['None', ''] else None for k, v in
                       gui_vars.items()}  # code to handle the edge case where there are "None" value
        self.logger.info(config_dict)
        self.configure(config_dict)

    def print_config(self) -> None:
        print("Andor spectrometer config")
        print("-------------------------")
        for key in self.last_config_dict:
            print(key, ':', self.last_config_dict[key])
        print("-------------------------")
