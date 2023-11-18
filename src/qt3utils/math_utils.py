from scipy.ndimage import uniform_filter1d


def get_rolling_mean(data, window_size=5):
    """
    Rolling mean is a good way to look at the average behavior of noisy data.
    It represents the local average value within a given window.
    """
    return uniform_filter1d(data, size=window_size)
