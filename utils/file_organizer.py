"""
File organization utilities for AstroFileManager.

This module contains utility functions for organizing XISF files into
standardized folder structures with metadata-based naming conventions.
"""

import os
import re
from typing import Optional


def generate_organized_path(repo_path: str, obj: Optional[str], filt: Optional[str],
                           imgtyp: Optional[str], exp: Optional[float], temp: Optional[float],
                           xbin: Optional[int], ybin: Optional[int], date: Optional[str],
                           original_filename: str) -> str:
    """
    Generate the organized path and filename for a file.

    Args:
        repo_path: Base repository path
        obj: Object/target name
        filt: Filter name
        imgtyp: Image type (Light, Dark, Flat, Bias)
        exp: Exposure time in seconds
        temp: CCD temperature in Celsius
        xbin: X-axis binning
        ybin: Y-axis binning
        date: Observation date (YYYY-MM-DD)
        original_filename: Original filename

    Returns:
        Full path to the organized file location
    """
    # Sanitize values
    obj = obj or "Unknown"
    filt = filt or "NoFilter"
    imgtyp = imgtyp or "Unknown"
    date = date or "0000-00-00"

    # Determine binning string
    if xbin and ybin:
        try:
            binning = f"Bin{int(float(xbin))}x{int(float(ybin))}"
        except (ValueError, TypeError):
            binning = "Bin1x1"
    else:
        binning = "Bin1x1"

    # Determine temp string (round to nearest degree)
    if temp is not None:
        try:
            temp_float = float(temp)
            temp_str = f"{int(round(temp_float))}C"
        except (ValueError, TypeError):
            temp_str = "0C"
    else:
        temp_str = "0C"

    # Extract sequence number from original filename if possible
    seq_match = re.search(r'_(\d+)\.(xisf|fits?)$', original_filename, re.IGNORECASE)
    seq = seq_match.group(1) if seq_match else "001"

    # Determine file type and path structure
    if 'light' in imgtyp.lower():
        # Lights/[Object]/[Filter]/[filename]
        subdir = os.path.join("Lights", obj, filt)
        try:
            exp_str = f"{int(float(exp))}s" if exp else "0s"
        except (ValueError, TypeError):
            exp_str = "0s"
        # Add "Master_Light_" prefix for master frames, no prefix for regular lights
        if 'master' in imgtyp.lower():
            new_filename = f"{date}_Master_Light_{obj}_{filt}_{exp_str}_{temp_str}_{binning}_{seq}.xisf"
        else:
            new_filename = f"{date}_{obj}_{filt}_{exp_str}_{temp_str}_{binning}_{seq}.xisf"

    elif 'dark' in imgtyp.lower():
        # Calibration/Darks/[exp]_[temp]_[binning]/[filename]
        try:
            exp_str = f"{int(float(exp))}s" if exp else "0s"
        except (ValueError, TypeError):
            exp_str = "0s"
        subdir = os.path.join("Calibration", "Darks", f"{exp_str}_{temp_str}_{binning}")
        # Add "Master_" prefix for master frames
        prefix = "Master_" if 'master' in imgtyp.lower() else ""
        new_filename = f"{date}_{prefix}Dark_{exp_str}_{temp_str}_{binning}_{seq}.xisf"

    elif 'flat' in imgtyp.lower():
        # Calibration/Flats/[date]/[filter]_[temp]_[binning]/[filename]
        subdir = os.path.join("Calibration", "Flats", date, f"{filt}_{temp_str}_{binning}")
        # Add "Master_" prefix for master frames
        prefix = "Master_" if 'master' in imgtyp.lower() else ""
        new_filename = f"{date}_{prefix}Flat_{filt}_{temp_str}_{binning}_{seq}.xisf"

    elif 'bias' in imgtyp.lower():
        # Calibration/Bias/[temp]_[binning]/[filename]
        subdir = os.path.join("Calibration", "Bias", f"{temp_str}_{binning}")
        # Add "Master_" prefix for master frames
        prefix = "Master_" if 'master' in imgtyp.lower() else ""
        new_filename = f"{date}_{prefix}Bias_{temp_str}_{binning}_{seq}.xisf"

    else:
        # Unknown type - put in root with original structure
        subdir = "Uncategorized"
        new_filename = original_filename

    return os.path.join(repo_path, subdir, new_filename)
