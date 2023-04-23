# Import the HSR750 class from the princeton_spectrometers module
from princeton_spectrometers import HSR750

# Create an instance of HSR750
spectrometer = HSR750()

# Set the wavelength range and exposure time
spectrometer.start_wavelength = 400.0
spectrometer.end_wavelength = 800.0
spectrometer.exposure_time = 0.2

# Load the settings into the spectrometer
spectrometer.load_settings()

# Take a spectrum
spectrometer.take_spectrum()

# Get the spectrum data
spectrum_data = spectrometer.get_current_spectrum()