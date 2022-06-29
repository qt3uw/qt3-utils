import numpy as np

def signal_to_background(trace, pre_trigger, aom_width, rf_width, verbose=False,
                        aom_width_duty = 1.0):
    '''
    Assumes trace produced by qt3utils.experiments.rabi.Rabi class and
    is the aggregated data for a particular RF width.

    The inputs `pre_trigger`, `aom_width` and `rf_width` are all in units of index of the trace.
    That is, they are in units of clock ticks.

    Assumes that trace is of shape
        * pre_trigger
        * aom_width: aom on / rf off (background)
        * rf_width:  aom off / rf on
        * aom_width: aom on/ rf off  (signal)

    returns sum(signal) / sum(background)

    '''
    background_end = pre_trigger + int(aom_width*aom_width_duty)
    signal_start = pre_trigger + aom_width + rf_width
    signal_end = signal_start + int(aom_width*aom_width_duty)

    background = np.sum(trace[pre_trigger:background_end])
    signal = np.sum(trace[signal_start:signal_end])

    if verbose:
        print('background')
        print(trace[pre_trigger:background_end])
        print('signal')
        print(trace[signal_start:signal_end])

    return signal / background
