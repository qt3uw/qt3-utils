class QT3Error(Exception):
    pass

class PulseTrainWidthError(QT3Error):
    pass

class PulseBlasterError(QT3Error):
    pass

class PulseBlasterInitError(PulseBlasterError):
    pass
