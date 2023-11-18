import nidaqmx

class QT3Error(Exception):
    pass

class PulseTrainWidthError(QT3Error):
    pass

class PulseBlasterError(QT3Error):
    pass

class PulseBlasterInitError(PulseBlasterError):
    pass


def convert_nidaq_daqnotfounderror(logger=None):
    """
    This decorator is used to catch nidaq._lib.DaqNotFoundError
    and convert instead raise nidaqmx.errors.DaqError so that
    the main application can catch the error and display a message.

    The nidaq._lib.DaqNotFoundError is raised when the nidaqmx
    is not supported on a particular platform (such as darwin). 

    This allows for some testing on unsupported platforms.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except nidaqmx._lib.DaqNotFoundError as e:
                if logger:
                    logger.error(f"Running '{func.__name__}'. Encountered: [{e}]")
                raise nidaqmx.errors.DaqError(e, -201169)  # this error code was found in NIDAQ website listing error codes
        return wrapper
    return decorator
