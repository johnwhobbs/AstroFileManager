# XISF Catalog Manager

A PyQt6-based desktop application for cataloging and managing XISF astrophotography files. This application reads FITS header information from XISF files and stores them in a SQLite database for easy browsing and analysis.

## Features

- **Flexible Import Modes**:
  - **Import Only**: Store original file paths in database
  - **Import and Organize**: Automatically copy files to organized structure during import
  - Mode selection persists between sessions

- **Automatic Metadata Extraction**: Reads FITS keywords including:
  - Telescope and instrument information
  - Object name (automatically NULL for calibration frames)
  - Filter type
  - Image type (Light Frame, Dark Frame, Flat Frame, Bias Frame)
  - Exposure time (supports both EXPOSURE and EXPTIME keywords)
  - CCD temperature (rounded to nearest degree for grouping)
  - Binning settings
  - Observation date with smart fallback:
    - Prefers DATE-LOC (local time)
    - Falls back to DATE-OBS (UTC) with timezone conversion
    - Automatically adjusted by -12 hours for session grouping

- **Dual-Section Catalog View**: Browse your images in an organized tree structure:
  - **Light Frames**: Organized by Object → Filter → Date → Files
  - **Calibration Frames**: Organized by frame type with intelligent grouping:
    - Dark Frames: Exposure/Temp/Binning → Date → Files
    - Flat Frames: Date → Filter/Temp/Binning → Files
    - Bias Frames: Temp/Binning → Date → Files
  - Temperature-based grouping (frames within ±0.5°C grouped together)

- **Activity Analytics**:
  - GitHub-style activity heatmap showing imaging sessions throughout the year
  - Visual representation of total exposure hours per night
  - Filter by year to track imaging trends

- **Maintenance Tools**:
  - Database management with safe clear database function
  - Search and replace functionality for bulk metadata corrections
  - **File Organization**: Automatically organize files into structured folders with standardized naming
    - Separate structures for Lights and Calibration frames (Darks, Flats, Bias)
    - Preview organization plan before execution
    - Preserves original files while creating organized copies
    - Can also be triggered during import

- **Settings Management**:
  - Configure repository path for organized file storage
  - Set timezone for DATE-OBS UTC conversion
  - Choose between Standard and Dark themes
  - Import mode preference (import only vs organize during import)

- **Smart Data Handling**:
  - Calibration frames automatically imported without object field
  - Temperature rounding for intelligent frame grouping
  - Duplicate detection using SHA256 file hashing
  - Robust string-to-numeric conversion for all metadata fields

- **Persistent Settings**: Window size, position, column widths, and preferences saved between sessions
- **Dark Theme**: Easy-on-the-eyes dark interface perfect for nighttime use

## Requirements

- Python 3.7 or higher
- PyQt6
- xisf (Python XISF library)
- sqlite3 (included with Python)

## Installation

1. Install the required Python packages:

```bash
pip install PyQt6 xisf
```

2. Create the database using the database creation script:

```bash
python create_database.py
```

This creates `xisf_catalog.db` in the current directory.

3. Run the GUI application:

```bash
python xisf_catalog_gui.py
```

## Usage

### Import Tab

**Import Mode Selection:**

Choose how files should be imported:

- **Import only (store original paths)**: Traditional mode - files remain in their original location, only metadata is stored in database
- **Import and organize (copy to repository)**: Files are automatically copied to organized folder structure during import
  - Requires repository path to be set in Settings tab
  - Files organized by metadata (object, filter, date, exposure, temperature, binning)
  - Original files are preserved
  - Mode selection is saved between sessions

**Import Files:**
1. Select your preferred import mode using the radio buttons
2. Click "Import XISF Files" to select individual files, or "Import Folder" to import all XISF files from a folder and subfolders
3. If "Import and organize" mode is selected, files will be copied to the repository structure during import
4. Monitor progress in the log window (shows organization status if applicable)
5. View import summary when complete

**Import Log:**
- Shows which mode is active
- Displays repository path if organizing
- Shows "Organized: filename" for successfully organized files
- Shows warnings if organization fails (falls back to original path)

### View Catalog Tab

Browse your XISF files in a dual-section hierarchical tree structure:

**Light Frames Section:**
```
▼ Light Frames
  ▼ M31 (Object)
    ▼ Ha (Filter)
      ▼ 2024-10-15 (Date)
        • M31_Ha_001.xisf [Light Frame] [Takahashi FSQ-106EDX3] [ZWO ASI2600MM Pro]
        • M31_Ha_002.xisf [Light Frame] [Takahashi FSQ-106EDX3] [ZWO ASI2600MM Pro]
      ▼ 2024-10-14
        • M31_Ha_003.xisf [Light Frame] [Takahashi FSQ-106EDX3] [ZWO ASI2600MM Pro]
    ▼ OIII
      ▼ 2024-10-15
        • M31_OIII_001.xisf [Light Frame] [Takahashi FSQ-106EDX3] [ZWO ASI2600MM Pro]
```

**Calibration Frames Section:**
```
▼ Calibration Frames
  ▼ Dark Frames
    ▼ 300s_-10C_Bin1x1 (Exposure/Temp/Binning)
      ▼ 2024-10-15 (Date)
        • Dark_001.xisf [Dark Frame] [Takahashi FSQ-106EDX3] [ZWO ASI2600MM Pro]
        • Dark_002.xisf [Dark Frame] [Takahashi FSQ-106EDX3] [ZWO ASI2600MM Pro]
  ▼ Flat Frames
    ▼ 2024-10-15 (Date)
      ▼ Ha_-10C_Bin1x1 (Filter/Temp/Binning)
        • Flat_001.xisf [Flat Frame] [Takahashi FSQ-106EDX3] [ZWO ASI2600MM Pro]
  ▼ Bias Frames
    ▼ -10C_Bin1x1 (Temp/Binning)
      ▼ 2024-10-15 (Date)
        • Bias_001.xisf [Bias Frame] [Takahashi FSQ-106EDX3] [ZWO ASI2600MM Pro]
```

**Temperature Grouping:**
- Frames with similar temperatures (within ±0.5°C) are grouped together
- Example: frames at -10.2°C, -10.8°C, and -9.6°C all appear under "-10C"
- This intelligent grouping helps match calibration frames to light frames

**Displayed Information:**
- **Name**: Hierarchical organization by frame type, object, filter, date, etc.
- **Image Type**: Light Frame, Dark Frame, Flat Frame, Bias Frame
- **Telescope**: Telescope name
- **Instrument**: Camera/instrument name

**Navigation:**
- Click the arrows to expand/collapse sections
- Click "Refresh" to update the view after imports or changes
- All calibration frames are now visible (previously hidden)

### Analytics Tab

Visualize your imaging activity with a GitHub-style activity heatmap:

**Activity Heatmap:**
- Shows imaging sessions throughout the year in a calendar-style grid
- Each cell represents one day, color-coded by total exposure hours:
  - Gray: No imaging activity
  - Light blue: < 2 hours
  - Medium blue: 2-4 hours
  - Dark blue: 4-6 hours
  - Darkest blue: 6+ hours
- Hover over any day to see the exact date and total exposure hours
- Select different years using the dropdown to view historical data

**Use Cases:**
- Track your imaging consistency and frequency
- Identify your most productive imaging periods
- Visualize seasonal patterns in your astrophotography workflow
- Share your imaging statistics with the community

### Maintenance Tab

The Maintenance tab provides powerful tools for managing and cleaning up your catalog data.

**Database Management:**
- **Clear Database**: Safely remove all records from the database with confirmation dialog
- This is useful when starting fresh or removing old data

**Search and Replace:**

The search and replace tool allows you to fix inconsistent metadata across your entire catalog in bulk:

1. **Select FITS Keyword**: Choose which metadata field to modify:
   - TELESCOP (Telescope name)
   - INSTRUME (Camera/Instrument)
   - OBJECT (Target object name)
   - FILTER (Filter name)
   - IMAGETYP (Image type)
   - DATE-LOC (Local date)

2. **Select Current Value**: Choose from existing values in your database

3. **Enter Replacement Value**: Type the corrected or standardized value

4. **Replace**: Click to update all matching records
   - Displays confirmation dialog showing what will be changed
   - Reports number of records updated
   - Automatically refreshes the value list

**Common Use Cases:**
- Standardize telescope names (e.g., "FSQ106" → "Takahashi FSQ-106EDX3")
- Fix typos in object names (e.g., "M 31" → "M31")
- Normalize filter names (e.g., "Hydrogen Alpha" → "Ha")
- Correct instrument names across multiple imaging sessions

**File Organization:**

The File Organization tool automatically organizes your XISF files into a structured folder hierarchy with standardized naming conventions:

1. **Preview Organization Plan**: See how files will be organized before making any changes
   - Shows source and destination paths for the first 10 files
   - Displays total count of files to be organized
   - No files are modified during preview

2. **Execute File Organization**: Copy files to the organized structure
   - Creates a standardized folder hierarchy based on file type
   - Renames files using metadata-based naming conventions
   - Original files are preserved (not deleted)
   - Updates database with new file paths
   - Progress is logged in real-time

**Folder Structure:**

The organization system creates different structures based on image type:

**Light Frames:**
```
Lights/
  └── [Object]/
      └── [Filter]/
          └── [Date]_[Object]_[Filter]_[Exp]_[Temp]_[Binning]_[Seq].xisf
```
Example: `Lights/M31/Ha/2024-10-15_M31_Ha_300s_-10C_Bin1x1_001.xisf`

**Dark Frames:**
```
Calibration/
  └── Darks/
      └── [Exp]_[Temp]_[Binning]/
          └── [Date]_Dark_[Exp]_[Temp]_[Binning]_[Seq].xisf
```
Example: `Calibration/Darks/300s_-10C_Bin1x1/2024-10-15_Dark_300s_-10C_Bin1x1_001.xisf`

**Flat Frames:**
```
Calibration/
  └── Flats/
      └── [Date]/
          └── [Filter]_[Temp]_[Binning]/
              └── [Date]_Flat_[Filter]_[Temp]_[Binning]_[Seq].xisf
```
Example: `Calibration/Flats/2024-10-15/Ha_-10C_Bin1x1/2024-10-15_Flat_Ha_-10C_Bin1x1_001.xisf`

**Bias Frames:**
```
Calibration/
  └── Bias/
      └── [Temp]_[Binning]/
          └── [Date]_Bias_[Temp]_[Binning]_[Seq].xisf
```
Example: `Calibration/Bias/-10C_Bin1x1/2024-10-15_Bias_-10C_Bin1x1_001.xisf`

**Benefits:**
- Easy matching of calibration frames to light frames
- Flats organized by date for session-specific calibration (best practice)
- Consistent naming across all imaging sessions
- Simplified workflow for stacking software
- Organized by object and filter for easy browsing
- Preserves original files as backup

**Note:** You must set a Repository Path in the Settings tab before using the File Organization feature.

### Settings Tab

Configure application preferences and database settings.

**Image Repository:**
- **Repository Path**: Set the destination folder for organized XISF files
- This path is used by the File Organization feature and the "Import and organize" mode
- Browse to select a folder where organized files will be stored

**Timezone:**
- **Timezone Selection**: Set your local timezone for DATE-OBS conversion
- Dropdown includes 23 common timezones worldwide
- Used when files have DATE-OBS (UTC) but no DATE-LOC
- Important for master calibration frames which typically only have DATE-OBS
- Ensures dates are correctly converted to local time for session grouping
- Defaults to UTC if not set

**Theme:**
- **Standard Theme**: Light theme for daytime use
- **Dark Theme**: Dark theme optimized for nighttime use

All settings are automatically saved and persisted between sessions.

## Database Schema

The SQLite database contains a single table `xisf_files` with the following fields:

- `id`: Unique identifier (auto-increment)
- `file_hash`: SHA256 hash of the file (prevents duplicates)
- `filepath`: Full path to the file
- `filename`: Filename only
- `telescop`: Telescope name
- `instrume`: Instrument/camera name
- `object`: Target object name
- `filter`: Filter name
- `imagetyp`: Image type (Light Frame, Dark, Flat, etc.)
- `exposure`: Exposure time in seconds
- `ccd_temp`: CCD temperature in Celsius
- `xbinning`: X-axis binning
- `ybinning`: Y-axis binning
- `date_loc`: Observation date (YYYY-MM-DD format, adjusted by -12 hours)
- `created_at`: Record creation timestamp
- `updated_at`: Record update timestamp

## Date Processing

The application uses a smart fallback approach for date extraction:

**Primary Method - DATE-LOC:**
1. Reads the DATE-LOC timestamp from the FITS header (handles up to 7 decimal places in fractional seconds)
2. Subtracts 12 hours (to normalize imaging sessions that span midnight)
3. Stores only the date in YYYY-MM-DD format

**Fallback Method - DATE-OBS:**
If DATE-LOC is not available (common for master calibration frames):
1. Reads the DATE-OBS timestamp from the FITS header (UTC time)
2. Converts from UTC to your configured local timezone
3. Subtracts 12 hours (to normalize imaging sessions that span midnight)
4. Stores only the date in YYYY-MM-DD format

**Session Grouping:**
The 12-hour subtraction ensures that imaging sessions are grouped by their actual observation night rather than being split across calendar days. For example, images captured from 8 PM on November 7 to 2 AM on November 8 will all be grouped under "2024-11-07".

## User Interface

**Dark Theme:**
The application features a dark theme optimized for nighttime use, with:
- Dark gray backgrounds
- High contrast text
- Blue highlights for selections
- Styled buttons with hover effects

**Column Widths:**
All column widths are resizable and automatically saved. Your preferred layout will be restored when you reopen the application.

## File Hash Detection

The application calculates a SHA256 hash for each imported file. If you attempt to import the same file again (even from a different location), it will update the existing record rather than creating a duplicate entry.

## Settings Persistence

The application automatically saves:
- Window size and position
- Column widths in all tables and tree views
- All layout preferences

Settings are stored using Qt's QSettings in platform-specific locations and are restored when you reopen the application.

## Troubleshooting

**"Database not found" error:**
- Make sure you've created the database using `create_database.py` first
- The database file `xisf_catalog.db` must be in the same directory as the GUI script

**Date fields showing NULL:**
- Files need either DATE-LOC or DATE-OBS FITS keyword
- If using DATE-OBS, ensure timezone is set in Settings tab
- The application supports dates with fractional seconds up to 7 digits (nanoseconds)
- Dates are automatically normalized by subtracting 12 hours

**Organization failing during import:**
- Check that repository path is set correctly in Settings tab
- Ensure you have write permissions to the repository location
- Check disk space is available
- View import log for specific error messages

**Calibration frames not showing in View Catalog:**
- Click the "Refresh" button to update the tree view
- Expand the "Calibration Frames" section in the tree
- Ensure frames have correct IMAGETYP keyword (Dark, Flat, or Bias)

**Import errors:**
- Check that your files are valid XISF format
- Verify that the xisf Python library is installed correctly
- Review the import log for specific error messages

## File Structure

```
xisf-catalog/
├── create_database.py      # Database creation script
├── xisf_catalog_gui.py     # Main GUI application
├── xisf_catalog.db         # SQLite database (created on first run)
└── README.md               # This file
```

## License

This project is provided as-is for personal use in managing astrophotography files.

## Contributing

Feel free to submit issues or pull requests for improvements.

## Version History

**v2.0.0** - Major Update: Integrated Workflow & Enhanced Data Handling
- **Import Workflow Integration**: Added import mode selection (import only vs import and organize)
  - Files can now be organized during import instead of as separate step
  - Mode selection persists between sessions
  - Warning shown if organize mode selected without repository path
- **Timezone Support**: Added DATE-OBS with timezone conversion
  - Supports master calibration frames that only have DATE-OBS (UTC)
  - 23 common timezones available in Settings tab
  - Automatic fallback: DATE-LOC → DATE-OBS with timezone conversion
- **View Catalog Improvements**: Dual-section tree view
  - Separated Light Frames and Calibration Frames sections
  - All calibration frames now visible (Dark, Flat, Bias)
  - Intelligent grouping: Darks by exposure/temp/binning, Flats by date/filter/temp/binning, Bias by temp/binning
- **Temperature Rounding**: Frames within ±0.5°C grouped together
  - Applied to View Catalog display and file organization
  - Helps match calibration frames to light frames
  - Consistent across Dark, Flat, and Bias frames
- **Enhanced Import Logic**:
  - EXPTIME keyword support (FITS standard) in addition to EXPOSURE
  - Calibration frames automatically imported without object field
  - Robust string-to-numeric conversion for all metadata fields
  - Better error handling with detailed messages in import log
- **Analytics Tab**: Replaced Statistics tab with GitHub-style activity heatmap
  - Visual calendar showing imaging sessions throughout the year
  - Color-coded by total exposure hours per night
  - Year selector for historical data
- **Code Cleanup**: Removed legacy migration tools
  - Removed "Fix Calibration Frame Objects" (now handled during import)
  - Removed "Re-extract Exposure Times" (now handled during import)
  - Removed "Re-extract Dates" (now handled during import)
- **Bug Fixes**:
  - Fixed flat frame organization to group by date first (Issue #9)
  - Fixed database filename not updated during organization (Issue #11)
  - Fixed calibration frames not visible in View Catalog (Issue #13)
  - Fixed flat frames incorrectly imported with object field (Issue #14)
  - Fixed exposure time not importing from EXPTIME keyword (Issue #16)
  - Fixed master frames missing dates (Issue #17)
  - Fixed flat frames not grouping by temperature (Issue #20)
  - Fixed file organization during import (Issue #23)

**v1.3.0** - File Organization Feature
- Added automatic file organization with standardized naming conventions
- Separate folder structures for Lights and Calibration frames (Darks, Flats, Bias)
- Preview organization plan before execution
- Intelligent naming based on metadata (object, filter, date, exposure, temp, binning)
- Repository path configuration in Settings tab
- Preserves original files while creating organized copies

**v1.2.0** - Maintenance and Settings Update
- Added Maintenance tab with database management tools
- Implemented search and replace functionality for bulk metadata corrections
- Added Settings tab with theme configuration
- Moved Clear Database function to Maintenance tab for better organization
- Changed default tree view behavior to keep items collapsed

**v1.1.0** - Statistics and UI Improvements
- Enhanced statistics dashboard with equipment information
- Improved column management and display
- Modified displayed columns in catalog view

**v1.0.0** - Initial release
- Import and catalog XISF files from folders and subfolders
- Hierarchical catalog view (Object → Filter → Date → Files)
- Statistics dashboard with equipment information
- Persistent settings (window size and column widths)
- Dark theme UI
- Light frame-only exposure calculations
- Automatic date normalization (-12 hours)
- SHA256 file hash duplicate detection