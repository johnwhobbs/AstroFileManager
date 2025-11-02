# XISF Catalog Manager

A PyQt6-based desktop application for cataloging and managing XISF astrophotography files. This application reads FITS header information from XISF files and stores them in a SQLite database for easy browsing and analysis.

## Features

- **Import XISF Files**: Import individual files or entire folders (including subfolders)
- **Automatic Metadata Extraction**: Reads FITS keywords including:
  - Telescope and instrument information
  - Object name
  - Filter type
  - Exposure time
  - CCD temperature
  - Binning settings
  - Observation date
- **Hierarchical Catalog View**: Browse your images organized by Object → Filter → Date → Individual Files
- **Statistics Dashboard**: View your most recently imaged objects and objects with the most total exposure time
- **Duplicate Detection**: Uses file hashing to prevent duplicate entries
- **Persistent Settings**: Window size and column widths are saved between sessions

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
2. Or click "Import Folder" to import all XISF files from a folder and its subfolders
3. Monitor progress in the log window
4. View import summary when complete

**Clear Database:**
- Click "Clear Database" to remove all records (requires confirmation)

### View Catalog Tab

Browse your XISF files in a hierarchical tree structure:

```
▼ M31 (Object)
  ▼ Ha (Filter)
    ▼ 2024-10-15 (Date)
      • M31_Ha_001.xisf
      • M31_Ha_002.xisf
    ▼ 2024-10-14
      • M31_Ha_003.xisf
  ▼ OIII
    ▼ 2024-10-15
      • M31_OIII_001.xisf
```

- Click the arrows to expand/collapse sections
- View telescope and instrument information for each file
- Click "Refresh" to update the view

### Statistics Tab

View two key statistics:

**10 Most Recent Objects:**
- Shows objects you've imaged most recently
- Sorted by most recent observation date
- Displays total number of files per object

**Top 10 Objects by Total Exposure:**
- Shows objects with the most accumulated exposure time
- Displays exposure in both seconds and hours
- Helps track your imaging progress

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
1. Reading the timestamp from the FITS header
2. Subtracting 12 hours (to normalize imaging sessions that span midnight)
3. Storing only the date in YYYY-MM-DD format

This ensures that imaging sessions are grouped by their actual observation night rather than being split across calendar days.

## File Hash Detection

The application calculates a SHA256 hash for each imported file. If you attempt to import the same file again (even from a different location), it will update the existing record rather than creating a duplicate entry.

## Settings Persistence

The application automatically saves:
- Window size and position
- Column widths in all tables and tree views

Settings are restored when you reopen the application.

## Troubleshooting

**"Database not found" error:**
- Make sure you've created the database using `create_database.py` first
- The database file `xisf_catalog.db` must be in the same directory as the GUI script

**Date fields showing NULL:**
- Ensure your XISF files contain the DATE-LOC FITS keyword
- The application supports dates with fractional seconds up to 7 digits

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

**v1.0.0** - Initial release
- Import and catalog XISF files
- Hierarchical catalog view
- Statistics dashboard
- Persistent settings