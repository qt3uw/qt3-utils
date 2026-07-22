# use ctypes for easy access to dll
from ctypes import *
import os
from pathlib import Path

import qt3utils


def _microdrive_dll_directory() -> Path:
    """Directory containing MicroDrive.dll (same package as qt3_positioners_shared.yaml)."""
    return Path(qt3utils.__file__).resolve().parent / 'config_files'


class MCL_Microdrive:

    def __init__(self):
        dll_dir = _microdrive_dll_directory()
        if hasattr(os, 'add_dll_directory'):
            if dll_dir.is_dir():
                os.add_dll_directory(str(dll_dir))
            else:
                os.add_dll_directory(os.getcwd())

        # load the dll
        self.dll = cdll.MicroDrive

        self.dll.MCL_ReleaseHandle.restype = None
        self.dll.MCL_ReleaseAllHandles.restype = None
        self.dll.MCL_PrintDeviceInfo.restype = None
    
    # Handle Management

    def init_handle(self):
        """Requests control of a single Mad City Labs Micro-Drive.

        If multiple Mad City Labs Micro-Drives are attached but not yet 
        controlled, it is indeterminate which of the uncontrolled
        Micro-Drives this function will gain control of. Use a combination of 
        grab_all_handles(), get_all_handles, and get_handle_by_serial to acquire
        the handle to a specific device.

        Returns:
            Returns a valid handle (int).

        Raises:
            MCL Exception
        """
        err = self.dll.MCL_InitHandle()
        if err == 0:
            raise MCL_MD_Exceptions(-8)
        return err

    def init_handle_or_get_existing(self):
        """Request control of a single Mad City Labs Micro-Drive. If all 
        attached Micro-Drives are controlled, this function will return a handle
        to one of the Micro-Drives currently controlled by the DLL.

        If multiple Mad City Labs Micro-Drives are attached but not yet 
        controlled, it is indeterminate which of the uncontrolled Micro-Drives 
        this function will gain control of. If all Micro-Drives are controlled 
        by the DLL, multiple calls to this function will cycle through all 
        of the controlled Micro-Drives.

        Returns:
            Returns a valid handle (int).

        Raises:
            MCL Exception
        """
        err = self.dll.MCL_InitHandleOrGetExisting()
        if err == 0:
            raise MCL_MD_Exceptions(-8)
        return err

    def grab_handle(self, device_id):
        """Requests control of a specific type of Mad City Labs Micro-Drive.

        If multiple Mad City Labs Micro-Drives of the same type are attached but
        not yet controlled, it is indeterminate which of the uncontrolled 
        Micro-Drives this function will gain control of. Use a combination 
        of grab_all_handles(), get_all_handles, and get_handle_by_serial to 
        acquire the handle to a specific device.

        Args:
            device_id (int): Specifies the type of Micro-Drive.
                    Micro-Drive 9472 0x2500
                    Micro-Drive1 9473 0x2501
                    Micro-Drive3 9475 0x2503
                    NanoCyte Micro-Drive 13568 0x3500
                    Micro-Drive4 9476 0x2504
                    Micro-Drive6 9478 0x2506
                    Micro-Drive4P 9600 0x2580
                    Micro-Drive UHV 9601 0x2581
                    Mad-Tweezer 9506 0x2522

        Returns:
            Returns a valid handle (int).

        Raises:
            MCL Exception
        """
        err = self.dll.MCL_GrabHandle(c_ushort(device_id))
        if err == 0:
            raise MCL_MD_Exceptions(-8)
        return err

    def grab_handle_or_get_existing(self, device_id):
        """Requests control of a specific type of Mad City Labs device. If all 
        attached Micro-Drives of the specified type are controlled, this 
        function will return a handle to one of the Micro-Drives of that type
        currently controlled by the DLL.

        If multiple Mad City Labs Micro-Drives of the specified type are
        attached but not yet controlled, it is indeterminate which of those 
        Micro-Drives this function will gain control of. If all the Micro-Drives
        of the specified type are currently controlled by the DLL, multiple 
        calls to this function will cycle through all of the 
        controlled Micro-Drives of the specified type.

        Args:
            device_id (int): Specifies the type of Micro-Drive.
                    Micro-Drive           9472  0x2500
                    Micro-Drive1          9473  0x2501
                    Micro-Drive3          9475  0x2503
                    NanoCyte Micro-Drive  13568 0x3500
                    Micro-Drive4          9476  0x2504
                    Micro-Drive6          9478  0x2506
                    Micro-Drive4P         9600  0x2580
                    Micro-Drive UHV       9601  0x2581
                    Mad-Tweezer           9506  0x2522

        Returns:
            Returns a valid handle (int).

        Raises:
            MCL Exception
        """
        err = self.dll.MCL_GrabHandleOrGetExisting(c_ushort(device_id))
        if err == 0:
            raise MCL_MD_Exceptions(-8)
        return err

    def grab_all_handles(self):
        """Requests control of all of the attached Mad City Labs Micro-Drives
        that are not yet under control.

        After calling this function use get_handle_by_serial to get the handle 
        of a specific device. Use number_of_current_handles and get_all_handles
        to get a list of the handles acquired by this function. Remember that 
        this function will take control of all of the attached Micro-Drives not 
        currently under control. Some of the acquired handles may need to be 
        released if those Micro-Drives are needed in other applications.

        Returns:
            Returns the number of Micro-Drives currently controlled by this
            instance of the DLL.

        Raises:
            MCL Exception
        """
        err = self.dll.MCL_GrabAllHandles()
        if err < 0:
            raise MCL_MD_Exceptions(err)
        return err

    def get_all_handles(self, size):
        """Fills a list with valid handles to the Micro-Drives currently under
        the control of this instance of the DLL.

        Args:
            size (int): Size of the 'handles' array

        Returns:
            Returns the number of valid handles put into the handles list (int).
            Returns list of handles (list of ints).
        """
        handles_list = (c_int32 * size)()
        num_handles = self.dll.MCL_GetAllHandles(pointer(handles_list), size)
        return num_handles, handles_list

    def number_of_current_handles(self):
        """Returns the number of Micro-Drives currently controlled by this 
        instance of the DLL.

        Returns:
            Number of Micro-Drives controlled (int).
        """
        return self.dll.MCL_NumberOfCurrentHandles();

    def get_handle_by_serial(self, serial_num):
        """Searches Micro-Drives currently controlled for a Micro-Drive whose 
        serial number matches 'serial'.

        Since this function only searches through Micro-Drives which the DLL is 
        controlling, grab_all_handles() or multiple calls to 
        (init/grab)_handle should be called before using this function.

        Args:
            serial_num (int): Serial # of the Micro-Drive to find.

        Returns:
            Returns a valid handle or returns 0 to indicate failure (int).

        Raises:
            MCL Exception
        """
        err = self.dll.MCL_GetHandleBySerial(c_ushort(serial_num))
        if err == 0:
            raise MCL_MD_Exceptions(-8)
        return err

    def release_handle(self, handle):
        """Releases control of the specified Micro-Drive.
        
        Args:
            handle (int): Specifies which Micro-Drive to communicate with.
         """

        return self.dll.MCL_ReleaseHandle(handle)

    def release_all_handles(self):
        """Releases control of all Micro-Drives controlled by this instance 
        of the DLL.
        """
        return self.dll.MCL_ReleaseAllHandles()

    # Motion Control

    def status(self, handle): 
        """Reads the limit switches.

        Args:
            handle (int): Specifies which Micro-Drive to communicate with.

        Returns:
            Returns status bits based on the status of the limit switches. Limit
            switch bits are set to '1' if the limit has not been reached 
            and '0' if the stage is at the limit. Reference the Status Bits 
            section to interpret the status data (unsigned short).

        Raises:
            MCL Exception
        """
        status = c_ushort()
        err = self.dll.MCL_MDStatus(byref(status), handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)
        return status.value

    def stop(self, handle):
        """Stops the stage from moving.

        Args:
            handle (int): Specifies which Micro-Drive to communicate with.

        Returns:
            Returns status bits based on the status of the limit switches. Limit
            switch bits are set to '1' if the limit has not been reached 
            and '0' if the stage is at the limit. Reference the Status Bits 
            section to interpret the status data (unsigned short).

        Raises:
            MCL Exception
        """
        status = c_ushort()
        err = self.dll.MCL_MDStop(byref(status), handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)
        return status.value
    
    def move_status(self, handle):
        """Queries the device to see if it is moving. This function should be 
        called prior to reading the encoders as the encoders should not be read
        when the stage is in motion.

        Args:
            handle (int): Specifies which Micro-Drive to communicate with.

        Returns:
            Returns '1' if the stage is moving or '0' otherwise.

        Raises:
            MCL Exception
        """
        is_moving = c_int32()
        err = self.dll.MCL_MicroDriveMoveStatus(byref(is_moving), handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)
        return is_moving.value
    
    def wait(self, handle): 
        """Waits long enough for the previously commanded move to finish.

        Args:
            handle (int): Specifies which Micro-Drive to communicate with.

        Raises:
            MCL Exception
        """
        err = self.dll.MCL_MicroDriveWait(handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)

    # Movement and Ecoders for MicroDrive

    def move_three_axes_m(self,
                          axis1, velocity1, microsteps1,
                          axis2, velocity2, microsteps2,
                          axis3, velocity3, microsteps3,
                          handle): 
        """Standard movement function that moves three axes using microsteps. 

        Acceleration and deceleration ramps are generated for the specified 
        motion. In some cases when taking smaller steps the velocity parameter 
        may be coerced to its maximum achievable value. The maximum and minimum
        velocities can be found using the axis_information function. The maximum
        velocity differs depending on how many axes are commanded to move.
        Care should be taken not to access the Micro-Drive while the microstage 
        is moving for any reason other than stopping it. Doing so will adversely 
        affect the internal timers of the Micro-Drive which generate the 
        required step pulses for the specified movement.

        Args:
            axis(1/2/3) (int): Which axis to move.  If using a Micro-Drive1,
                this argument is ignored.
                M1=1, M2=2, M3=3, M4=4, M5=5, M6=6 

            velocity(1/2/3) (double): Speed in mm/s for translational stages. 
                Speed in r/s for rotational stages.

            microsteps(1/2/3) (int): Number of microsteps to move the stage.
                A positive number of microsteps moves the stage axis toward 
                its LS2. A negative number of microsteps moves the stage axis
                toward its LS1. A value of 0 will result in the axis not moving.

            handle (int): Specifies which Micro-Drive to communicate with.

        Raises:
            MCL Exception
        """
        err = self.dll.MCL_MDMoveThreeAxesM(axis1,
                                            c_double(velocity1),
                                            microsteps1, 
                                            axis2,
                                            c_double(velocity2),
                                            microsteps2,
                                            axis3,
                                            c_double(velocity3),
                                            microsteps3, 
                                            handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)

    def move_three_axes_r(self,
                          axis1, velocity1, distance1, rounding1,
                          axis2, velocity2, distance2, rounding2,
                          axis3, velocity3, distance3, rounding3,
                          handle): 
        """Standard movement function that moves three axes using 
        distance and rounding.
        
        Acceleration and deceleration ramps are generated for the specified 
        motion. In some cases when taking smaller steps the velocity parameter 
        may be coerced to its maximum achievable value. The maximum and minimum 
        velocities can be found using the axis_information function. The maximum
        velocity differs depending on how many axes are commanded to move.
        Care should be taken not to access the Micro-Drive while the microstage
        is moving for any reason other than stopping it. Doing so will adversely 
        affect the internal timers of the Micro-Drive which generate the 
        required step pulses for the specified movement.

        Args:
            axis(1/2/3) (int): Which axis to move. If using a Micro-Drive1,
                        this argument is ignored.
                        M1=1, M2=2, M3=3, M4=4, M5=5, M6=6

            velocity(1/2/3) (double): Speed in mm/s for translational stages. 
                Speed in r/s for rotational stages.

            distance(1/2/3) (double): Distance to move the stage. Distance in mm
                for translational stages and r for rotational stages. A positive
                distance moves the stage axis toward its LS2. A negative 
                distances moves the stage axis toward its LS1. A value 
                of 0.0 will result in the axis not moving.

            rounding(1/2/3) (int): Determines how to round the distance:
                0 - Nearest microstep.
                1 - Nearest full step.
                2 - Nearest half step.

            handle (int): Specifies which Micro-Drive to communicate with.

        Raises:
            MCL Exception
        """
        err = self.dll.MCL_MDMoveThreeAxesR(axis1,
                                            c_double(velocity1),
                                            c_double(distance1),
                                            rounding1,
                                            axis2,
                                            c_double(velocity2),
                                            c_double(distance2),
                                            rounding2,
                                            axis3,
                                            c_double(velocity3),
                                            c_double(distance3),
                                            rounding3,
                                            handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)

    def move_three_axes(self,
                        axis1, velocity1, distance1,
                        axis2, velocity2, distance2,
                        axis3, velocity3, distance3,
                        handle): 
        """Standard movement function that moves three axes using distance.
        
        Acceleration and deceleration ramps are generated for the specified
        motion. In some cases when taking smaller steps the velocity parameter 
        may be coerced to its maximum achievable value. The maximum and minimum 
        velocities can be found using MCL_MDAxisInformation. The maximum 
        velocity differs depending on how many axes are commanded to move.
        Care should be taken not to access the Micro-Drive while the microstage 
        is moving for any reason other than stopping it. Doing so will adversely
        affect the internal timers of the Micro-Drive which generate the 
        required step pulses for the specified movement.

        Args:
            axis(1/2/3) (int): Which axis to move. If using a Micro-Drive1,
                        this argument is ignored.
                        M1=1, M2=2, M3=3, M4=4, M5=5, M6=6

            velocity(1/2/3) (double): Speed in mm/s for translational stages. 
                Speed in r/s for rotational stages.

            distance(1/2/3) (double): Distance to move the stage. Distance in mm
                for translational stages and r for rotational stages. A positive 
                distance moves the stage axis toward its LS2. A negative 
                distance moves the stage axis toward its LS1. A value of 0.0
                will result in the axis not moving.

            handle (int): Specifies which Micro-Drive to communicate with.

        Raises:
            MCL Exception
        """
        err = self.dll.MCL_MDMoveThreeAxes(axis1,
                                           c_double(velocity1),
                                           c_double(distance1),
                                           axis2, 
                                           c_double(velocity2),
                                           c_double(distance2),
                                           axis3, 
                                           c_double(velocity3), 
                                           c_double(distance3),
                                           handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)

    def move_m(self, axis, velocity, microsteps, handle):
        """Standard movement function. Acceleration and deceleration ramps are
        generated for the specified motion. In some cases when taking smaller 
        steps the velocity parameter may be coerced to its maximum achievable 
        value. The maximum and minimum velocities can be found using the 
        axis_information function.

        Care should be taken not to access the Micro-Drive while the microstage
        is moving for any reason other than stopping it. Doing so will adversely
        affect the internal timers of the Micro-Drive which generate the 
        required step pulses for the specified movement.

        Args:
            axis (int): Which axis to move. If using a Micro-Drive1, this
                argument is ignored.
                M1=1, M2=2, M3=3, M4=4, M5=5, M6=6
                
            velocity (double): Speed in mm/s for translational stages. 
                Speed in r/s for rotational stages.

            microsteps (int): Number of microsteps to move the stage. A positive
                number of microsteps moves the stage axis toward its LS2. A 
                negative number of microsteps moves the stage axis toward 
                its LS1. A value of 0 will result in the axis not moving.

            handle (int): Specifies which Micro-Drive to communicate with.

        Raises:
            MCL Exception
        """
        err = self.dll.MCL_MDMoveM(axis, c_double(velocity), microsteps, handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)

    def move_r(self, axis, velocity, distance, rounding, handle):
        """Standard movement function. Acceleration and deceleration ramps are 
        generated for the specified motion. In some cases when taking smaller 
        steps the velocity parameter may be coerced to its maximum achievable 
        value. The maximum and minimum velocities can be found using the 
        axis_information function. Care should be taken not to access the 
        Micro-Drive while the microstage is moving for any reason other than
        stopping it. Doing so will adversely affect the internal timers of the
        Micro-Drive which generate the required step pulses for the 
        specified movement.

        Args:
            axis (int): Which axis to move. If using a Micro-Drive1,
                this argument is ignored.
                    M1=1, M2=2, M3=3, M4=4, M5=5, M6=6  

            velocity (double): Speed in mm/s for translational stages. 
                Speed in r/s for rotational stages.

            distance (double): Distance to move the stage. Distance in mm for 
                translational stages and r for rotational stages. A positive 
                distance moves the stage axis toward its LS2. A negative 
                distance moves the stage axis toward its LS1. A value of 0.0 
                will result in the axis not moving.

            rounding (int): Determines how to round the distance parameter:
                        0 - Nearest microstep.
                        1 - Nearest full step.
                        2 - Nearest half step.

            handle (int): Specifies which Micro-Drive to communicate with.

        Raises:
            MCL Exception
        """
        err = self.dll.MCL_MDMoveR(axis, c_double(velocity), c_double(distance),
                                   rounding, handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)
    
    def move(self, axis, velocity, distance, handle): 
        """Standard movement function. Acceleration and deceleration ramps are 
        generated for the specified motion. In some cases when taking smaller 
        steps the velocity parameter may be coerced to its maximum achievable 
        value. The maximum and minimum velocities can be found using the 
        axis_information function. Care should be taken not to access the 
        Micro-Drive while the microstage is moving for any reason other than 
        stopping it. Doing so will adversely affect the internal timers of the 
        Micro-Drive which generate the required step pulses for the
        specified movement.

        Args:
            axis (int): Which axis to move. If using a Micro-Drive1,
                this argument is ignored.
                    M1=1, M2=2, M3=3, M4=4, M5=5, M6=6 

            velocity (double): Speed in mm/s for translational stages. 
                Speed in r/s for rotational stages.

            distance (double): Distance to move the stage. Distance in mm for 
                translational stages and r for rotational stages. A positive 
                distance moves the stage axis toward its LS2. A negative 
                distances moves the stage axis toward its LS1. A value of 0.0 
                will result in the axis not moving.

            handle (int): Specifies which Micro-Drive to communicate with.

        Raises:
            MCL Exception 
        """
        err = self.dll.MCL_MDMove(axis, c_double(velocity), c_double(distance),
                                  handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)

    def single_step(self, axis, direction, handle): 
        """Takes a single step in the specified direction.
        
        Args:
            axis (int): Which axis to move. If using a Micro-Drive1,
            this argument is ignored.
                M1=1, M2=2, M3=3, M4=4, M5=5, M6=6

            directions (int): 1 = move toward LS2, -1 = move toward LS1.

            handle (int): Specifies which Micro-Drive to communicate with.

        Raises:
            MCL Exception
        """
        err = self.dll.MCL_MDSingleStep(axis, direction, handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)

    def reset_encoders(self, handle): 
        """Resets all encoders

        Resetting an encoder makes the current position of the microstage the 
        zero position of the encoder.

        Args:
            handle (int): Specifies which Micro-Drive to communicate with.

        Returns:
            Returns status bits based on the status of the limit switches. Limit
            switch bits are set to '1' if the limit has not been reached and '0'
            if the stage is at the limit. Reference the Status Bits section to
            interpret the status data (unsigned short).
            
        Raises:
            MCL Exception
        """
        status = c_ushort()
        err = self.dll.MCL_MDResetEncoders(byref(status), handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)
        return status.value

    def reset_encoder(self, axis, handle): 
        """Resets specific encoder

        Resetting an encoder makes the current position of the microstage the 
        zero position of the encoder.

        Args:
            axis (int): Which axis to reset. If using a Micro-Drive1,
            this argument is ignored.
                M1=1, M2=2, M3=3, M4=4, M5=5, M6=6

            handle (int): Specifies which Micro-Drive to communicate with.

        Returns:
            Returns status bits based on the status of the limit switches. Limit
            switch bits are set to '1' if the limit has not been reached and '0'
            if the stage is at the limit. Reference the Status Bits section to 
            interpret the status data (unsigned short).
            
        Raises:
            MCL Exception
        """
        status = c_ushort()
        err = self.dll.MCL_MDResetEncoder(axis, byref(status), handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)
        return status.value

    def read_encoders(self, handle):
        """Reads all encoders. Encoder values are in millimeters.

        The position values may be inverted. The inversion is a result of how
        the encoder sensor was attached and varies by microstage design.

        Args:
            handle (int): Specifies which Micro-Drive to communicate with.

        Returns:
            Returns 4 values, for each encoder, if the axis is available (int).

        Raises:
            MCL Exception
        """
        e1 = c_double()
        e2 = c_double()
        e3 = c_double()
        e4 = c_double()
        err = self.dll.MCL_MDReadEncoders(byref(e1), byref(e2), byref(e3),
                                          byref(e4), handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)
        return e1.value, e2.value, e3.value, e4.value

    def current_position_m(self, axis, handle):
        """Reads the number of microsteps taken since the beginning 
        of the program.

        This function will fail if the stage is still moving when it is called.

        Args:
            axis (int): Which axis to read. If using a Micro-Drive1,
                 this argument is ignored.
                    M1=1, M2=2, M3=3, M4=4, M5=5, M6=6

            handle (int): Specifies which Micro-Drive to communicate with.

        Returns:
            Returns the number of microsteps taken in the specified axis (int).

        Raises:
            MCL Exception
        """
        microsteps = c_int32()
        err = self.dll.MCL_MDCurrentPositionM(axis, byref(microsteps), handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)
        return microsteps.value

    def axis_information(self, axis, handle):    
        """Gather Information about the resolution and speed of the Micro-Drive.

        Args:
            axis (int): Axis to query. (M1=1, M2=2, M3=3, M4=4, M5=5, M6=6)
            handle (int): Specifies which Micro-Drive to communicate with.

        Returns:
            Encoder resolution in um (double).
            Size of a single step in 'units' (double).
            Maximum velocity in 'units/second' of a single axis move (double).
            Maximum velocity in 'units/second of a two axis move (double).
            Maximum velocity in 'units/second' of a three axis move (double).
            Minimum velocity in 'units/second' of a move (double).
            '1' if the units of the axis are in millimeters, 
            '2' if the units of the axis are in radians (double).

        Raises:
            MCL Exception
        """
        encoder_resolution = c_double()
        step_size = c_double()
        max_velocity = c_double()
        max_velocity_twoaxis = c_double()
        max_velocity_threeaxis = c_double()
        min_velocity = c_double()
        units = c_int()
        err = self.dll.MCL_MDAxisInformation(axis, 
                                           byref(encoder_resolution),
                                           byref(step_size),
                                           byref(max_velocity),
                                           byref(max_velocity_twoaxis),
                                           byref(max_velocity_threeaxis),
                                           byref(min_velocity),
                                           byref(units),
                                           handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)
        return (encoder_resolution.value, step_size.value, max_velocity.value,
               max_velocity_twoaxis.value, max_velocity_threeaxis.value, 
               min_velocity.value, units.value)

    def encoders_present(self, handle):
        """Determine which encoders are present in the Micro-Drive.

        Args:    
            handle (int): Specifies which Micro-Drive to communicate with.

        Returns: 
            Returns bitmap of available encoders. 0 - Unavailable, 1 - Available
                x x x x 3 2 1 0
                Bit 0 - Encoder 1
                Bit 1 - Encoder 2
                Bit 2 - Encoder 3
                Bit 3 - Encoder 4

        Raises:
            MCL Exception
        """
        encoder_bitmap = c_uint8()
        err = self.dll.MCL_MDEncodersPresent(byref(encoder_bitmap), handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)
        return bin(encoder_bitmap.value)

    #Rotational Stage
    
    def find_home(self, axis, handle):
        """Commands a rotational stage to perform a sequence of rotations to 
        find its home index.

        Requirements:
            Mad-Tweezer rotational axis. Product ID 0x2522.

        Args:
            axis (int): Axis to query. (M1=1, M2=2, M3=3, M4=4, M5=5, M6=6)
            handle (int): Specifies which Mad-Tweezer to communicate with.

        Raises:
            MCL Exception
        """
        err = self.dll.MCL_MDFindHome(axis, handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)

    def set_mode(self, axis, mode, handle):
        """Switches a rotational axis performance between high speed and high 
        precision. axis_information should be used after changing the mode to
        determine the new minimum and maximum velocity for the rotational axis.
        
        Requirements:
            Mad-Tweezer rotational axis. Product ID 0x2522.

        Args:
            axis (int): Axis to set. (M1=1, M2=2, M3=3, M4=4, M5=5, M6=6)
            mode (int): High Speed = 1. High Precision = 3.
            handle (int): Specifies which Mad-Tweezer to communicate with.
        
        Raises:
           MCL Exception
        """
        err = self.dll.MCL_MDSetMode(axis, mode, handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)

    def get_mode(self, axis, handle):
        """Query the rotational axis for its current performance mode.

        Requirements:
            Mad-Tweezer rotational axis. Product ID 0x2522.

        Args:
            axis (int): Axis to Query. (M1=1, M2=2, M3=3, M4=4, M5=5, M6=6)
            handle (int): Specifies which Mad-Tweezer to communicate with.

        Returns:
            '1' for High Speed mode. '3' for High Precison mode.

        Raises:
            MCL Exception
        """
        mode = c_int32()
        err = self.dll.MCL_MDGetMode(axis, byref(mode), handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)
        return mode.value

    # Device Information

    def get_firmware_version(self, handle):
        """Gives access to the Firmware version and profile information.

        Args:
            handle (int): Specifies which Micro-Drive to communicate with.

        Returns:
            Returns firmware version number (short).
            Returns firmware profile number (short).    

        Raises:
            MCL Exception
        """
        version = c_short()
        profile = c_short()
        err = self.dll.MCL_GetFirmwareVersion(byref(version), byref(profile),
                                              handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)
        return version.value, profile.value

    def get_serial_number(self, handle):
        """Returns the serial number of the Micro-Drive. This information can be
        useful if you need support for your device or if you are attempting to 
        tell the difference between two similar Micro-Drives.

        Args:
            handle (int): Specifies which Micro-Drive to communicate with.

        Returns:
            Returns the serial number of the specified Micro-Drive.

        Raises:
            MCL Exception
        """
        err = self.dll.MCL_GetSerialNumber(handle)
        if err < 0:
            raise MCL_MD_Exceptions(err)
        return err

    def dll_version(self):
        """Gives access to the DLL version information. This information is 
        useful if you need support.

        Returns:
            Returns DLL version number (short).
            Returns DLL revision number (short).
        """
        version = c_short()
        revision = c_short()
        self.dll.MCL_DLLVersion(byref(version), byref(revision))
        return version.value, revision.value
    
    def get_product_id(self, handle):
        """Allows the program to query the product id of the device 
        represented by 'handle'.

        Args:
            handle (int): Specifies which Micro-Drive to communicate with.

        Returns:
            Returns product ID number (unsigned short).

        Raises:
            MCL Exception
        """
        pid = c_ushort()
        err = self.dll.MCL_GetProductID(byref(pid), handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)
        return pid.value
    
    def get_axis_info(self, handle):
        """Allows the program to query which axes are available.

        Args:
            handle (int): Specifies which Micro-Drive to communicate with.

        Returns:
            Returns bitmap of all valid axes for the current Micro-Drive.
                Bit 0: Set to 1 if M1 is valid.
                Bit 1: Set to 1 if M2 is valid.
                Bit 2: Set to 1 if M3 is valid.
                Bit 3: Set to 1 if M4 is valid.
                Bit 4: Set to 1 if M5 is valid.
                Bit 5: Set to 1 if M6 is valid.
        
        Raises:
            MCL Exception
        """
        axis_bitmap = c_uint8()
        err = self.dll.MCL_GetAxisInfo(byref(axis_bitmap), handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)
        return bin(axis_bitmap.value)
    
    def get_full_step_size(self, handle):
        """Allows the program to query the size of a full step.
       
        This information combined with the micro step size from axis_information
        can be used to determine the number of micro steps per full step. Some 
        applications may wish to stop on full steps or half steps. The rounding 
        arguments for the move functions will round to either full, half,
        or nearest step.

        Args:
            handle (int): Specifies which Micro-Drive to communicate with.

        Returns:
            Returns size of a full step. In millimeters for translational 
            stages. In radians for rotational stages (double).
        
        Raises:
            MCL Exception
        """
        step_size = c_double()
        err = self.dll.MCL_GetFullStepSize(byref(step_size), handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)
        return step_size.value 

    def get_tirf_module_calibration(self, handle):
        """Returns the distance the stage must move from the negative limit 
        switch to satisfy the EPI mode condition.

        Requirements:
            Firmware profile bit 2 equal to 1. (0x0002)

        Args:
            handle (int): Specifies which Micro-Drive to communicate with.

        Returns:
            Returns the distance from the negative limit to EPI in mm (double).

        Raises:
            MCL Exception
        """
        cal_mm = c_double()
        err = self.dll.MCL_GetTirfModuleCalibration(byref(cal_mm), handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)
        return cal_mm

    def get_tirf_module_axis(self, handle):
        """Returns the stage axis that is configured to act as the
        tirf module axis.

        Requirements:
            Firmware profile bit 4 equal to 1. (0x0008)

        Args:
            handle (int): Specifies which Micro-Drive to communicate with.

        Returns:
            Returns stage axis acting as the tirf module (int).

        Raises:
            MCL Exception
        """
        tirf_axis = c_int32()
        err = self.dll.MCL_GetTirfModuleAxis(byref(tirf_axis), handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)
        return tirf_axis.value

    def read_temperature(self, axis, handle):
        """Read the temperature in Celsius of a Micro-Drive axis.

        Requirements:
            Micro-Drive UHV. Product ID 0x2581.

        Args:
            axis (int): Which axis to read for the temperature. 
                M1=1, M2=2, M3=3, M4=4
            handle (int): Specifies which Micro-Drive to communicate with.

        Returns: 
            Returns temperature of the specified axis in Celsius (double).

        Raises:
            MCL Exception
        """
        temperature = c_double()
        err = self.dll.MCL_MDReadTemperature(axis, byref(temperature), handle)
        if err != 0:
            raise MCL_MD_Exceptions(err)
        return temperature.value



class MCL_MD_Exceptions(Exception):
    def __init__(self, err):
        error_messages = {
            -1 : 'MCL General Error occurred: -1',
            -2 : 'MCL Device Error occurred: -2',
            -3 : 'MCL Device Not Attached: -3',
            -4 : 'MCL General Error occurred: -4',
            -5 : 'MCL Usage Error occurred: -5',
            -6 : 'MCL Argument Error occurred: -6',
            -7 : 'MCL Invalid Axis: -7',
            -8 : 'MCL Invalid Handle: -8'
        }
        message = error_messages.get(err, f"Unknown error with code {err}")
        super().__init__(message)
