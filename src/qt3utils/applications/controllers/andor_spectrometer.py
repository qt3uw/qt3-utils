import logging
import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import Tuple, Dict, Type

import numpy as np

import qt3utils.datagenerators.spectrometers.andor as andor
from qt3utils.applications.controllers.utils import (
    make_label_and_entry,
    make_label_and_option_menu,
    make_label_and_check_button,
    make_label_frame,
    make_tab_view,
    make_popup_window_and_take_threaded_action,
    prepare_list_for_option_menu,
)


class AndorSpectrometerController:

    def __init__(self, logger_level: int):
        self.logger = logging.getLogger('Andor Spectrometer Controller')
        self.logger.setLevel(logger_level)

        self.spectrometer_config = andor.AndorSpectrometerConfig()

        # Changing supported acquisition modes to remove "run until abort" which is nonsensical for this application.
        self.spectrometer_config.SUPPORTED_ACQUISITION_MODES = (
            self.spectrometer_config.AcquisitionMode.SINGLE_SCAN.name,
            self.spectrometer_config.AcquisitionMode.ACCUMULATE.name,
            self.spectrometer_config.AcquisitionMode.KINETICS.name,
        )
        self.spectrometer_daq = andor.AndorSpectrometerDataAcquisition(self.spectrometer_config)

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
        This method is run by the Application's DAQ controller
        once before the actual acquisition sequence begins.
        For this Spectrometer controller, we decide that the
        connection should only be established during scans and
        updating settings.
        Hence, we connect to the spectrometer, and wait until
        the target temperature is reached (if the setting is on).

        Raises
        ------
        RuntimeError
            If the connection to the spectrometer fails.
            This is not a fatal error since the scanning thread will catch it,
            hence preventing the acquisition sequence from starting.
        """
        self.logger.info('Starting controller.')
        self.open()
        if not self.spectrometer_config.is_open:
            raise RuntimeError('Failed to connect to Andor Spectrometer.')
        self.spectrometer_daq.wait_for_target_temperature_if_necessary()

    def stop(self) -> None:
        """
        This method runs at the end of the acquisition sequence loop
        on the Application's DAQ controller.

        We do not abort the acquisition because when stop is on the
        Application's DAQ controller, it will change the `self.running`
        parameter to False but will keep taking data until the
        currently scanned row finishes.
        So, we only need to abort acquisition when the controller closes,
        in case it closes abruptly.
        """
        self.logger.info('Stopping controller.')
        self.spectrometer_daq.stop_waiting_to_reach_temperature()
        self.close()

    def open(self) -> bool:
        """
        Attempts to establish a connection to the spectrometer.

        The device will not save its settings when it closes,
        so every time we open the connection, we should load
        the previous configuration settings.

        If this method is called

        Returns
        -------
        bool
            True if the connection was successful, False otherwise.
        """
        self.logger.info('Opening Andor Spectrometer')
        self.spectrometer_config.open()
        connection_status: bool = self.spectrometer_config.is_open
        if connection_status:
            self.logger.info('Opening Andor Spectrometer was successful.')
            if self.last_config_dict:
                self.configure(self.last_config_dict, attempt_connection=False)
            self.logger.info('Latest configuration settings were set.')
        else:
            self.logger.info('Opening Andor Spectrometer failed.')
        return connection_status

    def close(self) -> bool:
        """
        Attempts to close the connection to the spectrometer.

        Returns
        -------
        bool
            True if the disconnection was successful, False otherwise.
        """
        if not self.spectrometer_config.is_open:
            self.logger.info('Andor Spectrometer is already closed.')
            return True
        self.logger.info('Closing Andor Spectrometer')
        self.spectrometer_daq.close()
        self.spectrometer_config.close()
        connection_status: bool = not self.spectrometer_config.is_open
        if connection_status:
            self.logger.info('Closing Andor Spectrometer was successful.')
        else:
            self.logger.info('Closing Andor Spectrometer failed.')
        return connection_status

    def sample_spectrum(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        This method is used in the Application's DAQ controller
        to collect a single batch of data.

        The data is collected from the spectrometer DAQ, and the
        wavelengths are calculated from the spectrometer's
        wavelength calibration.
        When acquiring single and accumulation mode scans, the
        data and wavelengths have the same shape.
        If kinetic series mode is used, the data have an extra
        dimension for each acquired spectrum in the series.
        Wavelengths are pixel and wavelength offset-corrected.

        Returns
        -------
        Tuple[np.ndarray, np.ndarray]
            A tuple containing the measured spectrum and the wavelength array.
        """
        self.logger.debug('Sampling Spectrum')
        acq_mode = self.spectrometer_config.acquisition_mode
        if acq_mode == self.spectrometer_config.AcquisitionMode.SINGLE_SCAN.name:
            return self.spectrometer_daq.acquire('single')
        elif acq_mode == self.spectrometer_config.AcquisitionMode.ACCUMULATE.name:
            return self.spectrometer_daq.acquire('accumulation')
        elif acq_mode == self.spectrometer_config.AcquisitionMode.KINETICS.name:
            return self.spectrometer_daq.acquire('kinetic series')

    def configure(self, config_dict: dict, attempt_connection: bool = True) -> None:
        """
        Configures the spectrometer with the provided settings.

        This method is used for two main reasons.
        The first is to set the initial yaml file configurations loaded
        through the Application's DAQ controller as a dictionary.
        The second is to set the spectrometer settings after the
        spectrometer controller class has been instantiated.

        During the first instantiation, the last_config_dict will be empty,
        and the spectrometer will not be connected, so we need to connect
        it first.
        Afterward, a disconnected spectrometer means there is a
        connection error, since the spectrometer is connected in the
        config window realization (see `configure_view` method below).

        Parameters
        ----------
        config_dict: dict
            A dictionary containing the configuration settings.
        attempt_connection: bool
            Will attempt to connect to the spectrometer and then disconnect.
            This is useful for when the configuration is set in the
            Application's DAQ controller.
            Default is True.
        """
        self.logger.setLevel(logging.DEBUG)
        self.logger.debug("Calling configure on the Andor spectrometer controller")

        if not self.last_config_dict:  # Expected to run during the first instantiation.
            self.logger.debug("First instantiation of the Andor Spectrometer controller. "
                              "Establishing connection now...")
            self.open()
        elif attempt_connection:
            self.logger.debug("Subsequent call for configuration outside of configuration GUI. "
                              "Establishing connection now...")
            self.open()

        self.last_config_dict.update(config_dict)  # storing the input either way!

        # The spectrometer should already be open at this point, even
        # if this method is accessed via the set button of the config window.
        if not self.spectrometer_config.is_open:
            self.logger.error("Spectrometer is not open. Cannot configure.")
            return

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
        self.spectrometer_config.keep_clean_on_external_trigger = config_dict.get(
            'keep_clean_on_external_trigger', self.spectrometer_config.keep_clean_on_external_trigger)
        # -------------------------------
        single_track_center_row = config_dict.get(
            'single_track_center_row', self.spectrometer_config.single_track_read_mode_parameters.track_center_row)
        single_track_height = config_dict.get(
            'single_track_height', self.spectrometer_config.single_track_read_mode_parameters.track_height)
        self.spectrometer_config.single_track_read_mode_parameters = andor.SingleTrackReadModeParameters(
            single_track_center_row, single_track_height)

        # Electronics Settings
        vss_value = config_dict.get(
            'vertical_shift_speed', self.spectrometer_config.vertical_shift_speed)
        if isinstance(vss_value, str):
            vss_value = float(vss_value)
        self.spectrometer_config.vertical_shift_speed = vss_value

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
        self.spectrometer_daq.reach_temperature_before_acquisition = config_dict.get(
            'reach_temperature_before_acquisition', self.spectrometer_daq.reach_temperature_before_acquisition)
        # -------------------------------
        self.spectrometer_config.cooler = config_dict.get(
            'cooler', self.spectrometer_config.cooler)
        self.spectrometer_config.cooler_persistence_mode = config_dict.get(
            'cooler_persistence', self.spectrometer_config.cooler_persistence_mode)

        if attempt_connection:
            self.close()

    def configure_view(self, gui_root: tk.Toplevel) -> None:
        """
        Launch a window to configure the spectrometer after its
        first instantiation.

        Parameters
        ----------
        gui_root : tk.Toplevel
            The root window of the GUI.
            This is used to create the new window as a child widget.
        """
        if not self.spectrometer_config.is_open:
            self.logger.info("Spectrometer is not open. Opening it.")
            title = 'Connecting...'
            message = 'Connecting to Andor spectrometer. Please wait...'
            # Wait for spectrometer initialization in a thread.
            # This will allow us to block the main GUI with a pop-up
            # window in the meantime - and helps prevent GUI freezes.

            thread_finished_event = threading.Event()
            make_popup_window_and_take_threaded_action(
                gui_root, title, message, self.open, end_event=thread_finished_event)

            time_start = time.time()
            while not thread_finished_event.is_set() and time.time() - time_start < 30:
                time.sleep(0.1)
            if not self.spectrometer_config.is_open:
                if not thread_finished_event.is_set():
                    self.logger.error("Opening the spectrometer in a thread took too long. "
                                      "Aborting configuration window creation.")
                else:
                    self.logger.error("Failed to connect to spectrometer. "
                                      "Aborting configuration window creation.")
                return

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
            turret_frame, 'Grating (Idx: Grooves, Blaze)', frame_row,
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

        frame_row += 1
        _, _, keep_clean_on_external_trigger_var = make_label_and_check_button(
            data_pre_processing_frame, 'Keep Cleanon Ext. Trigger', frame_row,
            self.spectrometer_config.keep_clean_on_external_trigger, label_padx)

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
        hss_list = [(ad, amp, hss)
                    for ad, amp in self.spectrometer_config.ccd_info.available_horizontal_shift_speeds
                    for hss in self.spectrometer_config.ccd_info.available_horizontal_shift_speeds[(ad, amp)]]
        horizontal_shift_speed_options = prepare_list_for_option_menu(hss_list)
        hss_value = str((
            self.spectrometer_config.ad_channel,
            self.spectrometer_config.output_amplifier,
            self.spectrometer_config.horizontal_shift_speed
        ))
        hss_value = hss_value if hss_value in horizontal_shift_speed_options else 'None'
        _, _, horizontal_speed_var = make_label_and_option_menu(
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
            temperature_set_point_frame, 'Temperature (°C)', frame_row,
            self.spectrometer_config.sensor_temperature_set_point, tk.IntVar, label_padx)

        frame_row += 1
        _, _, reach_temperature_before_acq_var = make_label_and_check_button(
            temperature_set_point_frame, 'Reach before Acquisition', frame_row,
            self.spectrometer_daq.reach_temperature_before_acquisition, label_padx)

        row += 1
        cooler_frame = make_label_frame(temperature_tab, 'Cooler', row)

        frame_row = 0
        _, _, is_cooling_var = make_label_and_check_button(
            cooler_frame, 'Cooling', frame_row,
            self.spectrometer_config.cooler, label_padx)

        frame_row += 1
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
            'keep_clean_on_external_trigger': keep_clean_on_external_trigger_var,
            # - Single Track Setup
            'single_track_center_row': single_track_center_row_var,
            'single_track_height': single_track_height_var,
            # Electronics
            # - Vertical Shift
            'vertical_shift_speed': vertical_speed_var,
            # - Horizontal Shift
            'horizontal_shift_speed': horizontal_speed_var,
            'pre_amp_gain': pre_amp_gain_var,
            # Temperature
            # - Set Point
            'target_sensor_temperature': target_sensor_temperature_var,
            'reach_temperature_before_acquisition':  reach_temperature_before_acq_var,
            # - Cooler
            'cooler': is_cooling_var,
            'cooler_persistence': cooler_persistence_var,
        }

        row = 1
        set_button = ttk.Button(config_win, text='Set', command=lambda: self._on_set_click(gui_info, config_win))
        set_button.grid(row=row, column=0, pady=5)

        close_button = ttk.Button(config_win, text='Close', command=lambda: self._on_close_click(config_win))
        close_button.grid(row=row, column=1, pady=5)

        tab_view.select(2)

        # Setting window geometry, so that it opens in the middle of the parent application
        config_win.update_idletasks()
        width = config_win.winfo_reqwidth()
        height = config_win.winfo_reqheight()
        x = gui_root.winfo_x() + gui_root.winfo_width() // 2 - width // 2
        y = gui_root.winfo_y() + gui_root.winfo_height() // 2 - height // 2
        config_win.geometry(f'{width}x{height}+{x}+{y}')

    def _on_close_click(self, config_win: tk.Toplevel):
        """
        Closes the configuration window and closes the connection
        to the spectrometer.

        Parameters
        ----------
        config_win: tk.Toplevel
            The configuration window
        """
        self.logger.debug('Closing configuration window.')
        self.close()
        config_win.destroy()

    def _on_set_click(self, gui_info: Dict[str, Type[tk.Variable]], config_win: tk.Toplevel):
        """
        Sets the new spectrometer configuration in a thread,
        while the main window is disabled showing a waiting
        message in a popup window.

        Notes
        -----
        Changing configuration in a spectrometer may take
        a while because a lot of its components are moving
        parts that take time to be set.
        Using a popup window in this manner prevents the GUI
        from freezing.
        """
        title = 'Loading...'
        message = 'Loading the new spectrometer configuration.\nPlease wait...'
        self.logger.info(f'Setting new spectrometer configuration in a thread.')
        make_popup_window_and_take_threaded_action(config_win, title, message, lambda: self._set_from_gui(gui_info))

    def _set_from_gui(self, gui_vars: dict) -> None:
        """
        Sets the new spectrometer configuration from the
        configuration window variables.

        Parameters
        ----------
        gui_vars: dict
            A dictionary with keys the same as the ones appearing
            in the YAML configuration file, and `tk.Variable`s pointing
            to the corresponding spectrometer parameter.
        """
        config_dict = {k: v.get() if v.get() not in ['None', ''] else None
                       for k, v in gui_vars.items()}  # code to handle the edge case where there are "None" values
        self.logger.info(config_dict)
        self.configure(config_dict, attempt_connection=False)

    def print_config(self) -> None:
        """
        Prints the current spectrometer configuration to the console.
        """
        print("Andor spectrometer config")
        print("-------------------------")
        for key in self.last_config_dict:
            print(key, ':', self.last_config_dict[key])
        print("-------------------------")

    def __del__(self):
        self.close()
