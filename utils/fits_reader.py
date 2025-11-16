"""
FITS file reader module for extracting FITS keywords using astropy.

This module provides functionality to read FITS headers and extract
relevant keywords in a format compatible with the AstroFileManager database.
"""

from astropy.io import fits
from pathlib import Path


def read_fits_keywords(filepath):
    """
    Read FITS keywords from a FITS file using astropy.

    Args:
        filepath: Path to the FITS file (can be str or Path object)

    Returns:
        dict: Dictionary of FITS keywords compatible with existing XISF keyword structure

    Raises:
        Exception: If file cannot be read or is not a valid FITS file
    """
    keywords = {}

    try:
        # Convert to Path object if needed
        if isinstance(filepath, str):
            filepath = Path(filepath)

        # Open FITS file and read primary header
        with fits.open(filepath) as hdul:
            # Get primary header (first HDU)
            header = hdul[0].header

            # Map FITS header keywords to expected format
            # These are the standard FITS keywords used by most astronomy cameras
            keyword_mapping = {
                'TELESCOP': 'TELESCOP',  # Telescope name
                'INSTRUME': 'INSTRUME',  # Instrument/camera name
                'OBJECT': 'OBJECT',      # Target object name
                'FILTER': 'FILTER',      # Filter name
                'IMAGETYP': 'IMAGETYP',  # Image type (Light/Dark/Flat/Bias)
                'EXPTIME': 'EXPTIME',    # Exposure time (FITS standard)
                'EXPOSURE': 'EXPOSURE',  # Alternative exposure keyword
                'CCD-TEMP': 'CCD-TEMP',  # CCD temperature
                'XBINNING': 'XBINNING',  # X-axis binning
                'YBINNING': 'YBINNING',  # Y-axis binning
                'DATE-LOC': 'DATE-LOC',  # Local observation date
                'DATE-OBS': 'DATE-OBS',  # UTC observation date
            }

            # Extract keywords from header
            for fits_key, internal_key in keyword_mapping.items():
                if fits_key in header:
                    keywords[internal_key] = header[fits_key]

            # Handle alternative CCD temperature keywords
            # Different camera manufacturers use different keywords
            if 'CCD-TEMP' not in keywords:
                # Try alternative temperature keywords
                temp_keywords = ['TEMPERAT', 'CCD_TEMP', 'SET-TEMP', 'CCDTEMP']
                for temp_key in temp_keywords:
                    if temp_key in header:
                        keywords['CCD-TEMP'] = header[temp_key]
                        break

    except Exception as e:
        # Log error and re-raise for handling by caller
        raise Exception(f"Error reading FITS file {filepath}: {str(e)}")

    return keywords


def get_fits_image_data(filepath):
    """
    Read FITS image data from a FITS file.

    Args:
        filepath: Path to the FITS file (can be str or Path object)

    Returns:
        numpy.ndarray: Image data from primary HDU

    Note:
        This function is provided for future enhancement but is not
        currently used by the import process.
    """
    # Convert to Path object if needed
    if isinstance(filepath, str):
        filepath = Path(filepath)

    with fits.open(filepath) as hdul:
        return hdul[0].data
