# Issue #200: Instrument Name Matching for Calibration Frames

## Summary
Updated the calibration frame matching logic to require that the instrument name (camera) matches when pairing dark and bias frames with light and flat frames.

## Changes Made

### 1. Core Calibration Logic (`core/calibration.py`)

#### Updated Methods:
All six matching methods now include an optional `instrument` parameter:

- **`find_matching_darks()`** (line 54)
  - Added `instrument` parameter
  - Added instrument matching to SQL queries (handles NULL values)
  - Matches both regular and master dark frames by instrument

- **`find_matching_bias()`** (line 137)
  - Added `instrument` parameter
  - Added instrument matching to SQL queries (handles NULL values)
  - Matches both regular and master bias frames by instrument

- **`find_matching_flats()`** (line 215)
  - Added `instrument` parameter
  - Added instrument matching to SQL queries (handles NULL values)
  - Matches both regular and master flat frames by instrument

- **`preload_calibration_data()`** (line 372)
  - Updated cache keys to include `instrume` field
  - Darks cache key: `(exp, temp, xbin, ybin, instrume)`
  - Bias cache key: `(temp, xbin, ybin, instrume)`
  - Flats cache key: `(filt, date, temp, xbin, ybin, instrume)`

- **`find_matching_darks_from_cache()`** (line 460)
  - Added `instrument` parameter
  - Updated cache lookup to match instrument (handles NULL values)

- **`find_matching_bias_from_cache()`** (line 523)
  - Added `instrument` parameter
  - Updated cache lookup to match instrument (handles NULL values)

- **`find_matching_flats_from_cache()`** (line 582)
  - Added `instrument` parameter
  - Updated cache lookup to match instrument (handles NULL values)

### 2. Session Queries (`ui/background_workers.py`)

- **`SessionsLoaderWorker.run()`** (line 205-222)
  - Added `instrume` to SELECT clause
  - Added `instrume` to GROUP BY clause
  - Session data now includes instrument for each session

### 3. Session Tab UI (`ui/sessions_tab.py`)

#### Two locations updated:

1. **Session display** (line 275-284)
   - Updated session data unpacking to include `instrume`
   - Pass `instrume` to all three cached matching functions

2. **Report generation** (line 450-488)
   - Added `instrume` to SELECT clause
   - Added `instrume` to GROUP BY clause
   - Updated session data unpacking to include `instrume`
   - Pass `instrume` to all three direct matching functions

### 4. Database Schema (`create_db.py`)

#### Updated Indexes:
All three calibration indexes now include the `instrume` field for better query performance:

- **`idx_calibration_darks`** (line 74)
  - Now indexes: `(exposure, ccd_temp, xbinning, ybinning, instrume)`

- **`idx_calibration_flats`** (line 80)
  - Now indexes: `(filter, date_loc, ccd_temp, xbinning, ybinning, instrume)`

- **`idx_calibration_bias`** (line 86)
  - Now indexes: `(ccd_temp, xbinning, ybinning, instrume)`

- **New index: `idx_instrume`** (line 65)
  - Added separate index on `instrume` field for general lookups

### 5. Migration Script (`migrate_add_instrument_indexes.py`)

Created a new migration script to update existing databases:
- Drops old calibration indexes
- Creates new indexes with instrument field
- Adds instrument index if missing
- Includes error handling and progress reporting

## Technical Details

### NULL Handling
The implementation properly handles NULL instrument values using SQL pattern:
```sql
AND (instrume = ? OR (instrume IS NULL AND ? IS NULL))
```

This ensures:
- Frames with NULL instrument only match sessions with NULL instrument
- Frames with a specific instrument only match sessions with that instrument
- No cross-matching between different instruments

### Cache Key Structure
Cache keys now include instrument as the last element:
- **Darks**: `(exposure_rounded, temp_rounded, xbinning, ybinning, instrume)`
- **Bias**: `(temp_rounded, xbinning, ybinning, instrume)`
- **Flats**: `(filter, date, temp_rounded, xbinning, ybinning, instrume)`

### Backward Compatibility
All `instrument` parameters are optional with default value `None`, maintaining backward compatibility with existing code.

## Migration Instructions

### For New Databases
New databases created with `create_db.py` will automatically have the correct indexes.

### For Existing Databases
Run the migration script:
```bash
python migrate_add_instrument_indexes.py [path_to_database]
```

Or use default database location:
```bash
python migrate_add_instrument_indexes.py
```

## Testing Recommendations

1. **Test with single instrument**: Verify frames from one camera match correctly
2. **Test with multiple instruments**: Verify frames from different cameras don't cross-match
3. **Test with NULL instruments**: Verify legacy data without instrument field still works
4. **Test with mixed data**: Verify sessions with instrument data don't match calibration frames without instrument data
5. **Test performance**: Verify the new indexes improve query performance for large datasets

## Impact

### What This Fixes
- Prevents incorrect calibration frame matching when using multiple cameras
- Ensures dark/bias frames taken with one camera aren't applied to images from a different camera
- Maintains data integrity for multi-instrument setups

### What This Doesn't Break
- Existing code without instrument data continues to work
- NULL instrument values are properly handled
- Backward compatible with legacy databases (after migration)
- No changes to public API signatures (instrument parameter is optional)
