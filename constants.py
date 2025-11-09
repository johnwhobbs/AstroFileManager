"""
Constants for AstroFileManager.

Centralized configuration values for calibration matching, import settings, etc.
"""

# ============================================================================
# CONSTANTS
# ============================================================================

# Calibration matching tolerances
TEMP_TOLERANCE_DARKS = 1.0      # °C tolerance for dark frame matching
TEMP_TOLERANCE_FLATS = 3.0      # °C tolerance for flat frame matching
TEMP_TOLERANCE_BIAS = 1.0       # °C tolerance for bias frame matching
EXPOSURE_TOLERANCE = 0.1        # seconds tolerance for exposure matching

# Frame count thresholds
MIN_FRAMES_RECOMMENDED = 20     # Recommended minimum frames for good quality
MIN_FRAMES_ACCEPTABLE = 10      # Acceptable minimum frames

# Import settings
IMPORT_BATCH_SIZE = 50          # Number of files to process in a batch
DATE_OFFSET_HOURS = 12          # Hours to subtract for date normalization
