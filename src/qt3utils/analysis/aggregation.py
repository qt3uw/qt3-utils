def reshape_sum_trace(a, N_rows, N_samples_per_row):
    '''
    reshapes a 1d array of repeated measurements.

    Useful in various experiments where the data is acquired for many
    repeated cycles of AOM/laser and RF/MW pulses.

    N_rows = number of repeated cycles in your data
    N_samples_per_row = number of data points within each cycle.

    The input array, should be of total length N_rows * N_samples_per_row.

    After reshape, returns the sum of the data along axis=0 such that
    the output 1D array is of length N_samples_per_row.
    '''
    return a.reshape((int(N_rows), int(N_samples_per_row))).sum(axis=0)

def reshape_mean_trace(a, N_rows, N_samples_per_row):
    '''
    reshapes a 1d array of repeated measurements.

    Useful in various experiments where the data is acquired for many
    repeated cycles of AOM/laser and RF/MW pulses.

    N_rows = number of repeated cycles in your data
    N_samples_per_row = number of data points within each cycle.

    The input array, should be of total length N_rows * N_samples_per_row.

    After reshape, returns the mean of the data along axis=0 such that
    the output 1D array is of length N_samples_per_row.
    '''
    return a.reshape((int(N_rows), int(N_samples_per_row))).mean(axis=0)
