import numpy as np

import qt3utils.errors

class ZHL4240Wplus:
    def __init__(self):

        self.max_allowed_input_power_dbm = -5
        #values obtained from https://www.minicircuits.com/WebStore/dashboard.html?model=ZHL-4240W%2B
        self._gain = np.array([[10, 43.15],
                                [20, 43.67],
                                [30, 43.68],
                                [40, 43.58],
                                [50, 43.40],
                                [60, 43.21],
                                [70, 43.05],
                                [80, 42.92],
                                [90, 42.79],
                                [100, 42.70],
                                [150, 42.38],
                                [200, 42.33],
                                [250, 42.33],
                                [300, 42.38],
                                [350, 42.44],
                                [400, 42.43],
                                [450, 42.38],
                                [500, 42.25],
                                [550, 42.22],
                                [600, 42.23],
                                [650, 42.27],
                                [700, 42.26],
                                [750, 42.22],
                                [800, 42.16],
                                [850, 42.09],
                                [900, 41.99],
                                [950, 41.90],
                                [1000, 41.83],
                                [1050, 41.78],
                                [1100, 41.76],
                                [1150, 41.77],
                                [1200, 41.84],
                                [1250, 41.99],
                                [1300, 42.24],
                                [1350, 42.55],
                                [1400, 42.89],
                                [1450, 43.15],
                                [1500, 43.32],
                                [1550, 43.37],
                                [1600, 43.35],
                                [1650, 43.32],
                                [1700, 43.32],
                                [1750, 43.38],
                                [1800, 43.54],
                                [1850, 43.71],
                                [1900, 43.81],
                                [2000, 43.83],
                                [2100, 43.71],
                                [2200, 43.55],
                                [2300, 43.46],
                                [2400, 43.52],
                                [2500, 43.37],
                                [2600, 42.96],
                                [2700, 42.48],
                                [2800, 42.29],
                                [2900, 42.40],
                                [3000, 42.64],
                                [3100, 42.75],
                                [3200, 42.56],
                                [3300, 42.24],
                                [3400, 42.11],
                                [3500, 42.21],
                                [3600, 42.57],
                                [3700, 43.05],
                                [3800, 43.18],
                                [3900, 43.34],
                                [4000, 42.64],
                                [4100, 42.20],
                                [4200, 41.30]])

    def raise_for_power(self, input_power_dbm):
        if input_power_dbm > self.max_allowed_input_power_dbm:
            raise qt3utils.errors.QT3Error(f'{input_power_dbm} dbm exceeds maximum allowed power for this device ({self.max_allowed_input_power_dbm} dbm)')

    def gain(self, frequency_in_MHz = 2870):
        '''
        returns the gain of the device at a particular frequency
        '''
        return np.interp(frequency_in_MHz,
                         xp = self._gain[:,0],
                         fp = self._gain[:,1],
                         right = -99,
                         left = -99)

    def power_in_milliwatts(self, input_dbm, frequency_in_MHz = 2870):
        gain = self.gain(frequency_in_MHz)
        output_in_dbm = gain + input_dbm
        return 10**(output_in_dbm/10)
