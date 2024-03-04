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
    make_tab_view,
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

        # Electronics Settings
        self.spectrometer_config.vertical_shift_speed = config_dict.get(
            'vertical_shift_speed', float(self.spectrometer_config.vertical_shift_speed))

        # self.spectrometer_config.ad_channel = config_dict.get(
        #     'ad_channel', int(self.spectrometer_config.ad_channel))
        # self.spectrometer_config.output_amplifier = config_dict.get(
        #     'output_amplifier', int(self.spectrometer_config.output_amplifier))

        default_hss = str((
            self.spectrometer_config.ad_channel,
            self.spectrometer_config.output_amplifier,
            self.spectrometer_config.horizontal_shift_speed
        ))
        hss_value = config_dict.get('horizontal_shift_speed', default_hss)
        if hss_value is None:
            hss_value = default_hss
        hss_value = hss_value[1:-1].replace(' ', '').split(',')
        self.spectrometer_config.ad_channel = int(hss_value[0])
        self.spectrometer_config.output_amplifier = int(hss_value[1])
        self.spectrometer_config.horizontal_shift_speed = float(hss_value[2])

        # Temperature Settings
        self.spectrometer_config.sensor_temperature_set_point = config_dict.get(
            'target_sensor_temperature', self.spectrometer_config.sensor_temperature_set_point)
        self.spectrometer_config.cooler_persistence_mode = config_dict.get(
            'cooler_persistence', self.spectrometer_config.cooler_persistence_mode)

    def configure_view(self, gui_root: tk.Toplevel) -> None:
        """
        This method launches a GUI window to configure the data controller.
        """
        config_win = tk.Toplevel(gui_root)
        config_win.grab_set()
        config_win.title('Andor Spectrometer Settings')
        label_padx = 10

        tab_view = make_tab_view(config_win, tab_pady=0)

        device_tab = ttk.Frame(tab_view)
        spectrograph_tab = ttk.Frame(tab_view)
        acquisition_tab = ttk.Frame(tab_view)
        electronics_tab = ttk.Frame(tab_view)
        temperature_tab = ttk.Frame(tab_view)

        tab_view.add(device_tab, text='Devices')
        tab_view.add(spectrograph_tab, text='Spectrograph')
        tab_view.add(acquisition_tab, text='Acquisition')
        tab_view.add(electronics_tab, text='Electronics')
        tab_view.add(temperature_tab, text='Temperature')

        # Device Settings
        row = 0
        device_settings_frame = make_label_frame(device_tab, 'Device Index', row)

        frame_row = 0
        ccd_device_list = prepare_list_for_option_menu(self.spectrometer_config.ccd_device_list)
        ccd_device_value = str(self.spectrometer_config.ccd_device_index)
        ccd_device_value = ccd_device_value if ccd_device_value in ccd_device_list else 'None'
        _, _, ccd_device_index_var = make_label_and_option_menu(
            device_settings_frame, 'CCD', frame_row,
            ccd_device_list, ccd_device_value, label_padx)

        frame_row += 1
        spg_device_list = prepare_list_for_option_menu(self.spectrometer_config.spg_device_list)
        spg_device_value = str(self.spectrometer_config.spg_device_index)
        spg_device_value = spg_device_value if spg_device_value in spg_device_list else 'None'
        _, _, spg_device_index_var = make_label_and_option_menu(
            device_settings_frame, 'Spectrograph', frame_row,
            spg_device_list, spg_device_value, label_padx)

        # Spectrograph Settings
        row = 0
        turret_frame = make_label_frame(spectrograph_tab, 'Turret', row)

        frame_row = 0
        grating_list = prepare_list_for_option_menu(self.spectrometer_config.grating_list)
        _, _, grating_var = make_label_and_option_menu(
            turret_frame, 'Grating', frame_row,
            grating_list, self.spectrometer_config.current_grating, label_padx)

        frame_row += 1
        _, _, center_wavelength_var = make_label_and_entry(
            turret_frame, 'Center Wavelength (nm)', frame_row,
            self.spectrometer_config.center_wavelength, tk.DoubleVar, label_padx)

        row += 1
        calibration_frame = make_label_frame(spectrograph_tab, 'Calibration', row)

        frame_row = 0
        _, _, pixel_offset_var = make_label_and_entry(
            calibration_frame, 'Pixel Offset', frame_row,
            self.spectrometer_config.pixel_offset, tk.DoubleVar, label_padx)

        frame_row += 1
        _, _, wavelength_offset_var = make_label_and_entry(
            calibration_frame, 'Wavelength Offset (nm)', frame_row,
            self.spectrometer_config.wavelength_offset, tk.DoubleVar, label_padx)

        row += 1
        port_frame = make_label_frame(spectrograph_tab, 'Ports', row)

        frame_row = 0
        flipper_mirror_list = self.spectrometer_config.SpectrographFlipperMirrorPort._member_names_
        _, _, input_port_var = make_label_and_option_menu(
            port_frame, 'Input', frame_row,
            flipper_mirror_list, self.spectrometer_config.input_port, label_padx)

        frame_row += 1
        _, _, output_port_var = make_label_and_option_menu(
            port_frame, 'Output', frame_row,
            flipper_mirror_list, self.spectrometer_config.output_port, label_padx)

        # Acquisition Settings
        row = 0
        modes_frame = make_label_frame(acquisition_tab, 'Modes', row)

        frame_row = 0
        _, _, read_mode_var = make_label_and_option_menu(
            modes_frame, 'Read', frame_row,
            self.spectrometer_config.SUPPORTED_READ_MODES, self.spectrometer_config.read_mode, label_padx)

        frame_row += 1
        _, _, acquisition_mode_var = make_label_and_option_menu(
            modes_frame, 'Acquisition', frame_row,
            self.spectrometer_config.SUPPORTED_ACQUISITION_MODES, self.spectrometer_config.acquisition_mode, label_padx)

        frame_row += 1
        _, _, trigger_mode_var = make_label_and_option_menu(
            modes_frame, 'Trigger', frame_row,
            self.spectrometer_config.SUPPORTED_TRIGGER_MODES, self.spectrometer_config.trigger_mode, label_padx)

        row += 1
        timing_frame = make_label_frame(acquisition_tab, 'Timing', row)

        frame_row = 0
        _, _, exposure_time_var = make_label_and_entry(
            timing_frame, 'Exposure (s)', frame_row,
            self.spectrometer_config.exposure_time, tk.DoubleVar, label_padx)

        frame_row += 1
        _, _, no_of_accumulations_var = make_label_and_entry(
            timing_frame,  'No. of Accumulations', frame_row,
            self.spectrometer_config.number_of_accumulations, tk.IntVar, label_padx)

        frame_row += 1
        _, _, accumulation_cycle_time_var = make_label_and_entry(
            timing_frame, 'Accumulation Cycle (s)', frame_row,
            self.spectrometer_config.accumulation_cycle_time, tk.DoubleVar, label_padx)

        frame_row += 1
        _, _, no_of_kinetics_var = make_label_and_entry(
            timing_frame, 'No. of Kinetics', frame_row,
            self.spectrometer_config.number_of_kinetics, tk.IntVar, label_padx)

        frame_row += 1
        _, _, kinetic_cycle_time_var = make_label_and_entry(
            timing_frame, 'Kinetic Cycle (s)', frame_row,
            self.spectrometer_config.kinetic_cycle_time, tk.DoubleVar, label_padx)

        row += 1
        data_pre_processing_frame = make_label_frame(acquisition_tab, 'Data Pre-processing', row)

        frame_row = 0
        _, _, baseline_clamp_var = make_label_and_check_button(
            data_pre_processing_frame, 'Clamp Baseline', frame_row,
            self.spectrometer_config.baseline_clamp, label_padx)

        frame_row += 1
        _, _, cosmic_ray_removal_var = make_label_and_check_button(
            data_pre_processing_frame, 'Cosmic Ray Removal', frame_row,
            self.spectrometer_config.remove_cosmic_rays, label_padx)

        row += 1
        single_track_mode_frame = make_label_frame(acquisition_tab, 'Single Track Setup', row)

        frame_row = 0
        label_text = f'Center Row [1, {self.spectrometer_config.ccd_info.number_of_pixels_vertically}]'
        _, _, single_track_center_row_var = make_label_and_entry(
            single_track_mode_frame, label_text, frame_row,
            self.spectrometer_config.single_track_read_mode_parameters.track_center_row, tk.IntVar, label_padx)

        frame_row += 1
        _, _, single_track_height_var = make_label_and_entry(
            single_track_mode_frame, 'Height', frame_row,
            self.spectrometer_config.single_track_read_mode_parameters.track_height, tk.IntVar, label_padx)

        # Electronics Settings
        row = 0
        vertical_shift_frame = make_label_frame(electronics_tab, 'Vertical Shift', row)

        frame_row = 0
        vertical_shift_speed_options = prepare_list_for_option_menu(
            self.spectrometer_config.ccd_info.available_vertical_shift_speeds)
        vss_value = str(self.spectrometer_config.vertical_shift_speed)
        vss_value = vss_value if vss_value in vertical_shift_speed_options else 'None'
        _, _, vertical_speed_var = make_label_and_option_menu(
            vertical_shift_frame, 'Speed (μs)', frame_row,
            vertical_shift_speed_options, vss_value, label_padx)

        row += 1
        horizontal_shift_frame = make_label_frame(electronics_tab, 'Horizontal Shift', row)

        frame_row = 0
        # ad_channel_list = prepare_list_for_option_menu(
        #     range(self.spectrometer_config.ccd_info.number_of_ad_channels))
        # ad_value = str(self.spectrometer_config.ad_channel)
        # ad_value = ad_value if ad_value in ad_channel_list else 'None'
        # _, _, ad_channel_var = make_label_and_option_menu(
        #     horizontal_shift_frame, 'A/D Channel', frame_row,
        #     ad_channel_list, ad_value, label_padx)
        #
        # frame_row += 1
        # amp_channel_list = prepare_list_for_option_menu(
        #     range(self.spectrometer_config.ccd_info.number_of_output_amplifiers))
        # amp_value = str(self.spectrometer_config.output_amplifier)
        # amp_value = amp_value if amp_value in amp_channel_list else 'None'
        # _, _, amp_var = make_label_and_option_menu(
        #     horizontal_shift_frame, 'Output Amplifier', frame_row,
        #     amp_channel_list, amp_value, label_padx)

        frame_row += 1
        hss_list = [(ad, amp, hss)
                    for ad, amp in self.spectrometer_config.ccd_info.available_horizontal_shift_speeds
                    for hss in self.spectrometer_config.ccd_info.available_horizontal_shift_speeds[(ad, amp)]]
        horizontal_shift_speed_options = prepare_list_for_option_menu(hss_list)
        hss_value = str(self.spectrometer_config.horizontal_shift_speed)
        hss_value = hss_value if hss_value in horizontal_shift_speed_options else 'None'
        _, _, vertical_speed_var = make_label_and_option_menu(
            horizontal_shift_frame, '       A/D Channel\n   Output Amplifier\nReadout Rate (MHz)', frame_row,
            horizontal_shift_speed_options, hss_value, label_padx)

        frame_row += 1
        pre_amp_gain_list = prepare_list_for_option_menu(
            self.spectrometer_config.ccd_info.available_pre_amp_gains)
        pre_amp_gain_value = str(self.spectrometer_config.pre_amp_gain)
        pre_amp_gain_value = pre_amp_gain_value if pre_amp_gain_value in pre_amp_gain_list else 'None'
        _, _, pre_amp_gain_var = make_label_and_option_menu(
            horizontal_shift_frame, 'Pre-Amplifier Gain', frame_row,
            pre_amp_gain_list, pre_amp_gain_value, label_padx)

        # Temperature Settings
        row = 0
        temperature_set_point_frame = make_label_frame(temperature_tab, 'Set Point', row)

        frame_row = 0
        _, _, target_sensor_temperature_var = make_label_and_entry(
            temperature_set_point_frame, 'Target Temperature (°C)', frame_row,
            self.spectrometer_config.sensor_temperature_set_point, tk.IntVar, label_padx)

        row += 1
        cooler_frame = make_label_frame(temperature_tab, 'Cooler', row)

        frame_row = 0
        _, _, cooler_persistence_var = make_label_and_check_button(
            cooler_frame, 'Persistent Cooling', frame_row,
            self.spectrometer_config.cooler_persistence_mode, label_padx)

        # Pack variables into a dictionary to pass to the _set_from_gui method
        gui_info = {
            # Devices
            # - Device Index
            'ccd_device_index': ccd_device_index_var,
            'spg_device_index': spg_device_index_var,
            # Spectrograph
            # - Turret
            'grating': grating_var,
            'center_wavelength': center_wavelength_var,
            # - Calibration
            'pixel_offset': pixel_offset_var,
            'wavelength_offset': wavelength_offset_var,
            # - Ports
            'input_port': input_port_var,
            'output_port': output_port_var,
            # Acquisition
            # - Modes
            'read_mode': read_mode_var,
            'acquisition_mode': acquisition_mode_var,
            'trigger_mode': trigger_mode_var,
            # - Timing
            'exposure_time': exposure_time_var,
            'no_of_accumulations': no_of_accumulations_var,
            'accumulation_cycle_time': accumulation_cycle_time_var,
            'no_of_kinetics': no_of_kinetics_var,
            'kinetic_cycle_time': kinetic_cycle_time_var,
            # - Data-Pre-Processing
            'baseline_clamp': baseline_clamp_var,
            'cosmic_ray_removal': cosmic_ray_removal_var,
            # - Single Track Setup
            'single_track_center_row': single_track_center_row_var,
            'single_track_height': single_track_height_var,
            # Electronics
            # - Vertical Shift
            'vertical_shift_speed': vertical_speed_var,
            # - Horizontal Shift
            # 'ad_channel': ad_channel_var,
            # 'output_amplifier': amp_var,
            'horizontal_shift_speed': vertical_speed_var,
            'pre_amp_gain': pre_amp_gain_var,
            # Temperature
            # - Set Point
            'target_sensor_temperature': target_sensor_temperature_var,
            # - Cooler
            'cooler_persistence': cooler_persistence_var,
        }

        row = 1
        ttk.Button(config_win, text='Set', command=lambda: self._set_from_gui(gui_info)).grid(row=row, column=0, pady=5)
        ttk.Button(config_win, text='Close', command=config_win.destroy).grid(row=row, column=1, pady=5)

        tab_view.select(2)

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
