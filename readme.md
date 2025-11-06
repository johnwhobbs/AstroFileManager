# XISF Catalog Manager

A PyQt6-based desktop application for cataloging and managing XISF astrophotography files. This application reads FITS header information from XISF files and stores them in a SQLite database for easy browsing and analysis.

## Features

- **Import XISF Files**: Import individual files or entire folders (including all subfolders recursively)
- **Automatic Metadata Extraction**: Reads FITS keywords including:
  - Telescope and instrument information
  - Object name
  - Filter type
  - Image type (Light Frame, Dark Frame, Flat Frame, etc.)
  - Exposure time
  - CCD temperature
  - Binning settings
  - Observation date (automatically adjusted by -12 hours for session grouping)
- **Hierarchical Catalog View**: Browse your images organized by Object → Filter → Date → Individual Files
- **Statistics Dashboard**:
  - View your 10 most recently imaged objects with telescope and instrument info
  - View top 10 objects by total light frame exposure time (in hours) with equipment details
- **Maintenance Tools**:
  - Database management with safe clear database function
  - Search and replace functionality for bulk metadata corrections
  - Fix inconsistent FITS keyword values across your entire catalog
- **Settings Management**:
  - Configure database file location
  - Customize application preferences
- **Duplicate Detection**: Uses SHA256 file hashing to prevent duplicate entries
- **Persistent Settings**: Window size, position, and all column widths are saved between sessions
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

**Import Files:**
1. Click "Import XISF Files" to select individual files
2. Or click "Import Folder" to import all XISF files from a folder and all its subfolders recursively
3. Monitor progress in the log window
4. View import summary when complete

### View Catalog Tab

Browse your XISF files in a hierarchical tree structure:

```
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

**Displayed Information:**
- **Name**: Object/Filter/Date/Filename hierarchy
- **Image Type**: Light Frame, Dark Frame, Flat Frame, Bias Frame, etc.
- **Telescope**: Telescope name
- **Instrument**: Camera/instrument name

- Click the arrows to expand/collapse sections
- Click "Refresh" to update the view

### Statistics Tab

View two key statistics with equipment information:

**10 Most Recent Objects:**
- Shows objects you've imaged most recently
- Sorted by most recent observation date
- Displays telescope and instrument used for the most recent session

**Top 10 Objects by Total Exposure:**
- Shows objects with the most accumulated **light frame** exposure time
- Displays total exposure in hours (calibration frames excluded)
- Shows telescope and instrument used
- Helps track your imaging progress on each target

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

### Settings Tab

Configure application preferences and database settings.

**Database Configuration:**
- **Database Location**: Specify the path to your SQLite database file
- Change database location to work with different catalogs
- Settings are persisted between sessions

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

The application processes the DATE-LOC FITS keyword by:
1. Reading the timestamp from the FITS header (handles up to 7 decimal places in fractional seconds)
2. Subtracting 12 hours (to normalize imaging sessions that span midnight)
3. Storing only the date in YYYY-MM-DD format

This ensures that imaging sessions are grouped by their actual observation night rather than being split across calendar days.

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
- Ensure your XISF files contain the DATE-LOC FITS keyword
- The application supports dates with fractional seconds up to 7 digits (nanoseconds)
- Dates are automatically normalized by subtracting 12 hours

**Statistics showing unexpected values:**
- The "Top 10 Objects by Total Exposure" only counts Light Frames
- Dark Frames, Flat Frames, and Bias Frames are excluded from exposure calculations
- Ensure your files have the correct IMAGETYP FITS keyword

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

**v1.2.0** - Maintenance and Settings Update
- Added Maintenance tab with database management tools
- Implemented search and replace functionality for bulk metadata corrections
- Added Settings tab for database configuration
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