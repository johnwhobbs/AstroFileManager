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


def _detect_file_type(filepath):
    """
    Detect whether a file is XISF or FITS based on its extension.

    Args:
        filepath: Path to the file (str or Path object)

    Returns:
        str: 'xisf' for XISF files, 'fits' for FITS files, or None if unknown
    """
    ext = Path(str(filepath)).suffix.lower()
    if ext == '.xisf':
        return 'xisf'
    elif ext in ['.fits', '.fit']:
        return 'fits'
    return None


def read_header_keywords(filepath):
    """
    Read all header keywords from a XISF or FITS file for display.

    This reads the complete FITS header so it can be shown to the user,
    unlike read_fits_keywords() which only extracts a fixed subset used
    by the database.

    Args:
        filepath: Path to the file (str or Path object)

    Returns:
        list: A list of (keyword, value, comment) tuples. The comment
              is an empty string when none is available.

    Raises:
        Exception: If the file cannot be read or the type is unsupported.
    """
    file_type = _detect_file_type(filepath)
    entries = []

    if file_type == 'fits':
        # Read the primary header using astropy
        with fits.open(filepath) as hdul:
            header = hdul[0].header
            for card in header.cards:
                # Each card is (keyword, value, comment)
                keyword = str(card.keyword)
                # Skip blank and comment/history separator cards for a cleaner view
                if keyword == '':
                    continue
                entries.append((keyword, str(card.value), str(card.comment)))

    elif file_type == 'xisf':
        # Import lazily so this module does not require the xisf package
        # unless a XISF file is actually being read.
        import xisf

        xisf_file = xisf.XISF(str(filepath))
        metadata = xisf_file.get_images_metadata()[0]
        fits_keywords = metadata.get('FITSKeywords', {})

        for keyword, values in fits_keywords.items():
            # XISF stores each keyword as a list of {'value':..., 'comment':...}
            if isinstance(values, list) and values:
                value = values[0].get('value', '')
                comment = values[0].get('comment', '')
            else:
                value = values
                comment = ''
            entries.append((str(keyword), str(value), str(comment)))

    else:
        raise Exception(f"Unsupported file type for header reading: {filepath}")

    return entries


def get_image_data(filepath):
    """
    Read the image pixel data from a XISF or FITS file.

    Args:
        filepath: Path to the file (str or Path object)

    Returns:
        numpy.ndarray: The image data. May be 2D (grayscale) or
                       3D (multi-channel) depending on the source file.

    Raises:
        Exception: If the file cannot be read or the type is unsupported.
    """
    file_type = _detect_file_type(filepath)

    if file_type == 'fits':
        with fits.open(filepath) as hdul:
            return hdul[0].data

    elif file_type == 'xisf':
        # Import lazily so this module does not require the xisf package
        # unless a XISF file is actually being read.
        import xisf

        xisf_file = xisf.XISF(str(filepath))
        return xisf_file.read_image(0)

    else:
        raise Exception(f"Unsupported file type for image reading: {filepath}")
