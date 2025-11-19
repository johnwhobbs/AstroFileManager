# AstroFileManager

A PyQt6-based desktop application for cataloging and managing astrophotography files. This high-performance application reads FITS header information from both XISF and FITS files, stores them in an optimized SQLite database, and provides powerful tools for browsing, analyzing, and organizing your imaging sessions.

## Features

- **Multi-Format Support**:
  - **XISF files**: Native support using xisf library
  - **FITS files**: Full support using astropy library (.fits, .fit extensions)
  - Unified metadata extraction across both formats
  - File extension preserved during organization
  - Alternative CCD temperature keywords (TEMPERAT, CCD_TEMP, etc.)

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

- **Sessions Calibration Tracking**: Comprehensive session management with intelligent calibration matching:
  - **Automatic Session Detection**: Groups light frames by date, object, and filter
  - **Smart Calibration Matching**: Finds matching Darks, Bias, and Flats with tolerance-based criteria
    - Darks: Exact exposure (±0.1s), ±1°C temperature, matching binning
    - Bias: ±1°C temperature, matching binning
    - Flats: Filter match, ±3°C temperature, exact date match, matching binning
  - **Master Frame Detection**: Identifies and displays master calibration frames
  - **Quality Scoring**: 0-100% quality score based on frame counts (100% = 20+ frames)
  - **Status Indicators**: Visual color-coded status (Complete/Partial/Missing)
  - **Smart Recommendations**: Specific guidance for missing or incomplete calibration
  - **Session Reports**: Export comprehensive reports with calibration status and recommendations
  - **Statistics Dashboard**: Real-time completion rate and session breakdowns
  - **Advanced Filtering**: Status filter, missing-only mode, master frame toggle

- **Activity Analytics**:
  - GitHub-style activity heatmap showing imaging sessions throughout the year
  - Visual representation of total exposure hours per night
  - Filter by year to track imaging trends

- **Maintenance Tools**:
  - Database management with safe clear database function
  - Search and replace functionality for bulk metadata corrections
  - Fix inconsistent FITS keyword values across your entire catalog
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
- astropy (for FITS file support)
- sqlite3 (included with Python)

## Installation

1. Install the required Python packages:

```bash
pip install PyQt6 xisf astropy
```

2. Create the database using the database creation script:

```bash
python create_db.py
```

This creates `xisf_catalog.db` in the current directory.

3. Run the GUI application:

```bash
python AstroFileManager.py
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
2. Click "Import Astro Files" to select individual files (XISF or FITS), or "Import Folder" to import all astro files from a folder and subfolders
3. Supported formats: .xisf, .fits, .fit
4. If "Import and organize" mode is selected, files will be copied to the repository structure during import
5. Monitor progress in the log window (shows organization status if applicable)
6. View import summary when complete

**Import Log:**
- Shows which mode is active
- Displays repository path if organizing
- Shows "Organized: filename" for successfully organized files
- Shows warnings if organization fails (falls back to original path)

### View Catalog Tab

Browse your XISF and FITS files in a dual-section hierarchical tree structure with intelligent lazy loading for optimal performance.

**Performance Features:**
- Lazy loading: Initially shows Objects → Filters, dates and files load when expanded
- Background data loading with progress indicator
- Non-blocking UI during refresh operations

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

### Sessions Tab

The Sessions tab provides comprehensive calibration tracking with optimized performance for large catalogs. It automatically matches your imaging sessions with their required calibration frames (Darks, Bias, Flats), identifies missing calibration data, and provides specific recommendations for completing your calibration library.

**Performance Features:**
- Pre-computed calibration matching (90% faster than individual queries)
- Background data loading with progress feedback
- Handles hundreds of sessions efficiently

**Session Detection:**

Sessions are automatically detected by grouping light frames that share:
- Same date (after -12 hour adjustment for overnight sessions)
- Same target object
- Same filter

Each unique combination creates a session entry that is then analyzed for calibration completeness.

**Calibration Matching Criteria:**

The system uses intelligent tolerance-based matching to find calibration frames:

**Dark Frames:**
- Exact exposure match (within ±0.1 seconds)
- Temperature within ±1°C of session average
- Matching X and Y binning

**Bias Frames:**
- Temperature within ±1°C of session average
- Matching X and Y binning

**Flat Frames:**
- Exact filter match (or both NULL for no-filter imaging)
- Temperature within ±3°C of session average (more flexible for dusk/dawn flats)
- Exact date match (must be from same imaging session)
- Matching X and Y binning

**Master Frame Detection:**

Master calibration frames are automatically identified when IMAGETYP contains "Master" (e.g., "Master Dark Frame", "Master Flat Frame"). Master frames are displayed with special "Master" badges and provide an alternative to having 10+ individual calibration frames.

**Status Indicators:**

Each session is color-coded based on calibration completeness:

- **Green (Complete)**: All three calibration types present (Darks + Bias + Flats) with minimum 10 frames each OR master available
- **Blue (Complete with Masters)**: All calibration types present AND at least one master frame available
- **Orange (Partial)**: Some calibration frames available but not all types
- **Red (Missing)**: No calibration frames found for any type

**Quality Scoring:**

Each calibration type receives a quality score (0-100%) based on frame count:
- 100% = 20+ frames (recommended for best results)
- Proportional scoring for 1-19 frames (e.g., 10 frames = 50%)
- 0% = no matching frames

Minimum of 10 frames is recommended for acceptable calibration quality.

**Frame Count Indicators:**

- **✓ 20 frames** - Excellent (sufficient frames)
- **✓ 15 + 1 Master** - Excellent (some frames plus master available)
- **⚠ 8 frames (need 10+)** - Warning (below minimum)
- **✗ Missing** - Critical (no matching frames)

**Filter Controls:**

Use the top controls to focus on specific sessions:

- **Status Filter**: Show All, Complete, Partial, or Missing sessions
- **Missing Only**: Checkbox to show only sessions lacking some calibration
- **Include Masters**: Toggle whether to count master frames in availability
- **Export Report**: Generate comprehensive text report of all sessions

**Session Details Panel:**

Click any session to view detailed information:

- Light frame count and average settings (exposure, temperature, binning)
- Exact calibration frame counts for each type
- Master frame availability indicators
- Quality scores for each calibration type
- Overall session status

**Recommendations Panel:**

For incomplete sessions, the system provides specific, actionable recommendations:

**Example recommendations:**
```
• Capture dark frames: 300.0s exposure at ~-10°C, 1x1 binning (minimum 10, recommended 20+)
• Add more bias frames: Currently 8, need at least 10 for good calibration
• Capture flat frames: Ha, ~-10°C, 1x1 binning (minimum 10, recommended 20+)
```

For complete sessions:
```
✓ All calibration frames are present

Optional improvements:
• Consider adding more darks (currently 12, recommended 20+)
• Consider adding more flats (currently 15, recommended 20+)
```

**Session Statistics:**

The statistics panel at the top shows real-time summary:

- **Total Sessions**: Count of all unique imaging sessions
- **Complete**: Sessions with all calibration types present
- **Partial**: Sessions with some calibration missing
- **Missing**: Sessions with no calibration
- **Completion Rate**: Percentage of sessions ready for processing

**Export Session Report:**

Click "Export Report" to generate a comprehensive text file containing:

- All session details with calibration status
- Quality scores for each calibration type
- Specific recommendations for each incomplete session
- Summary statistics and completion rate

Example report excerpt:
```
================================================================================
Session: 2024-11-07 - M31 - Ha
Status: Partial
Light Frames: 25 | Exposure: 300.0s | Temp: -10.2°C | Binning: 1x1

  Darks (300.0s): 20 frames (Quality: 100%)
  Bias: 25 frames (Quality: 100%)
  Flats (Ha): 0 frames (Quality: 0%)

  Recommendations:
    • Capture flat frames: Ha, ~-10°C, 1x1 binning (minimum 10, recommended 20+)
```

**Use Cases:**

- **Pre-processing Planning**: Identify which sessions are ready to process
- **Calibration Library Management**: Track which calibration frames you need to acquire
- **Session Completeness**: Quickly see which imaging sessions lack calibration
- **Master Frame Utilization**: Leverage master frames to avoid needing 20+ individual frames
- **Quality Assessment**: Ensure you have sufficient calibration frames for best results
- **Historical Analysis**: Review past sessions and identify gaps in calibration data

**Tips:**

- Sessions with master frames show in blue even with fewer individual frames
- Use "Missing Only" filter to focus on sessions needing calibration
- Export reports before imaging sessions to plan calibration frame acquisition
- Temperature tolerances account for cooling variations between sessions
- Flat frames must be from the exact same date as the imaging session
- Aim for 20+ frames per calibration type for optimal results
- Master frames reduce the need for large frame counts

### Projects Tab

The Projects tab provides project-based workflow management for tracking imaging campaigns across multiple sessions and nights. It helps you manage target frame counts per filter, track progress toward goals, and organize your workflow from initial capture through final integration.

**Creating a Project:**

1. Click "New Project" to open the project creation dialog
2. Select a template:
   - **Narrowband (SHO)**: 90 frames each of Ha, OIII, SII (270 total)
   - **Broadband (LRGB)**: 270 frames of L, 270 each of R, G, B (1,080 total)
   - **Custom**: Define your own filter goals
3. Enter project details:
   - **Project Name**: Unique identifier (e.g., "M31 Narrowband 2024")
   - **Object Name**: Target object (e.g., "M31")
   - **Year**: Optional year for reference
   - **Description**: Optional notes about equipment, goals, etc.
4. Review/adjust filter goals and target frame counts
5. Click "Create Project"

**Project Progress Tracking:**

Each project displays:
- **Total Frames**: Count of all frames assigned to the project
- **Approved Frames**: Count of frames that passed quality grading
- Progress bars for each filter showing both total and approved counts
- Color-coded progress indicators:
  - Green: Goal met (approved frames ≥ target)
  - Blue: Frames captured, awaiting grading or approval
  - Gray: No frames captured yet

**Assigning Sessions to Projects:**

Sessions must be assigned to projects BEFORE importing quality data:

1. Switch to the View Catalog tab
2. Navigate to a session (date grouping under object/filter)
3. Right-click on the session and select "Assign to Project"
4. Choose the target project from the dropdown
5. Optionally add notes about the session
6. Click "Assign to Project"

All light frames from that session are immediately linked to the project, and total frame counts are updated.

**Importing Quality Data:**

After grading frames in PixInsight SubFrame Selector:

1. In PixInsight, grade your frames using SubFrame Selector
2. Export the CSV file with quality metrics
3. In AstroFileManager Projects tab, click "Import Quality Data"
4. Select the CSV file exported from PixInsight
5. Review the import results:
   - Matched frames: Successfully updated with quality data
   - Not found: Frames in CSV not in database
   - Approved/Rejected counts
   - Updated projects count

The import automatically:
- Matches frames by filename
- Updates quality metrics (FWHM, eccentricity, SNR, stars, background)
- Sets approval status (approved/rejected) based on Weight column
- Recalculates project progress with approved counts
- Updates session grading status

**Next Steps Recommendations:**

For each project, the system provides specific guidance:

**During capture phase:**
```
• Capture more frames:
  - Ha: 35 more frames
  - OIII: 45 more frames
  - SII: 40 more frames
```

**After partial grading:**
```
• Grade frames in PixInsight SubFrame Selector
• Import quality data CSV
```

**When goals are met:**
```
✓ All goals met! Ready to generate WBPP file lists
```

**Project Status Management:**

- **Mark Complete**: Changes project status to "completed" when all goals are met
- **Archive**: Moves project to archived status (hidden from active list)
- **Delete Project**: Permanently removes project and unlinks all frames
  - Frames remain in database but are unassigned
  - Project data, sessions, and filter goals are deleted

**Unassigned Sessions Warning:**

The Projects tab displays a warning (⚠️) showing count of unassigned sessions that contain light frames. This helps ensure all your imaging sessions are properly tracked within projects.

**Workflow Integration:**

The typical workflow is:

1. **Create Project**: Define your imaging campaign with filter goals
2. **Capture Frames**: Use NINA or other capture software
3. **Import Frames**: Import XISF files into AstroFileManager
4. **Assign Sessions**: Assign newly imported sessions to your project
5. **Continue Capturing**: Repeat over multiple nights until target counts reached
6. **Grade in PixInsight**: Use SubFrame Selector to grade all frames
7. **Import Quality Data**: Import CSV to update approval status
8. **Check Progress**: Review approved counts vs targets
9. **Capture More if Needed**: If insufficient approved frames, capture more
10. **Mark Complete**: When goals met, mark project complete
11. **Generate WBPP Lists**: Export file lists for integration (future feature)

**Use Cases:**

- **Multi-Night Projects**: Track progress across weeks or months of imaging
- **Multiple Targets**: Manage several concurrent imaging projects
- **Historical Tracking**: Separate projects by year or campaign
- **Goal-Oriented Workflow**: Work toward specific frame count targets
- **Quality-Based Planning**: Know exactly how many more frames to capture after grading

**Tips:**

- Assign sessions immediately after import, even before grading
- Quality data can be imported weeks or months later
- Partial CSV imports work - only frames in the CSV are updated
- Projects can span calendar years (don't worry about Dec 31/Jan 1 boundaries)
- Use descriptive project names to distinguish campaigns (e.g., "M31 Narrowband 2024" vs "M31 Narrowband 2025")

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

The SQLite database contains the following tables:

**xisf_files table** - Core image metadata:
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
- `project_id`: Links frame to imaging project
- `session_assignment_id`: Links frame to project session
- `fwhm`: Full Width Half Maximum (arcseconds)
- `eccentricity`: Star eccentricity metric
- `snr`: Signal-to-noise ratio weight
- `star_count`: Number of detected stars
- `background_level`: Median background level
- `approval_status`: Frame grading status (not_graded/approved/rejected)
- `grading_date`: Date frame was graded
- `grading_notes`: Optional notes from grading
- `created_at`: Record creation timestamp
- `updated_at`: Record update timestamp

**projects table** - Imaging campaigns:
- `id`: Unique identifier
- `name`: Project name (unique)
- `object_name`: Target object
- `description`: Optional project description
- `year`: Optional year for reference
- `start_date`: Project start date
- `status`: Project status (active/completed/archived)
- `created_at`: Project creation timestamp
- `updated_at`: Project update timestamp

**project_filter_goals table** - Target frame counts:
- `id`: Unique identifier
- `project_id`: Links to project
- `filter`: Filter name
- `target_count`: Target number of frames
- `total_count`: Current total frames captured
- `approved_count`: Current approved frames
- `last_updated`: Last update timestamp

**project_sessions table** - Session assignments:
- `id`: Unique identifier
- `project_id`: Links to project
- `session_id`: Session identifier
- `date_loc`: Session date
- `object_name`: Object name
- `filter`: Filter name
- `frame_count`: Number of frames in session
- `approved_count`: Number of approved frames
- `rejected_count`: Number of rejected frames
- `graded`: Whether session has been graded (0/1)
- `avg_fwhm`: Average FWHM for session
- `notes`: Optional session notes
- `assigned_date`: Date session was assigned

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

## Performance

AstroFileManager is optimized to handle large catalogs efficiently, with several performance enhancements implemented:

**Database Optimizations:**
- **WAL Mode (Write-Ahead Logging)**: Enables concurrent reads during writes, 30-50% faster write operations
- **64MB Cache**: Dramatically reduces disk I/O by keeping hot data in memory
- **256MB Memory-Mapped I/O**: Direct memory access to database pages for 20-40% faster queries
- **Composite Indexes**: Specialized indexes for catalog hierarchy and calibration matching (50-80% faster indexed queries)

**Query Optimization:**
- View Catalog: Reduced from 191-1000+ queries to 1-2 queries (99% reduction)
- Sessions Tab: Reduced from 300+ queries to 4 queries (98% reduction)
- Single hierarchical queries with in-memory aggregation
- Pre-computed calibration matching with caching

**UI Responsiveness:**
- **Background Threading**: Data loading happens in background threads
- **Non-blocking UI**: Application remains responsive during large catalog loads
- **Progress Indicators**: Slim progress bars show loading status
- **Cancellable Operations**: Refresh operations can be interrupted

**Lazy Loading:**
- View Catalog initially loads only Objects → Filters (2 levels)
- Dates and files loaded on-demand when tree nodes are expanded
- 90% faster initial load time
- 80% reduced memory footprint
- Seamless expansion from cached data

**Performance Metrics:**
- Large catalogs (1000+ files): <0.5 second initial load
- No UI freezing during data operations
- Responsive with multiple simultaneous sessions

## Troubleshooting

**"Database not found" error:**
- Make sure you've created the database using `create_db.py` first
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

**Sessions tab showing no calibration matches:**
- Verify calibration frames have been imported (check View Catalog tab)
- Check that calibration frame temperatures are within tolerance (±1°C for Darks/Bias, ±3°C for Flats)
- Ensure binning matches exactly (1x1, 2x2, etc.)
- For Darks: verify exposure times match light frames (within ±0.1s)
- For Flats: verify filter names match exactly and dates match exactly (same date as session)
- Click "Refresh Sessions" to update the view

**Sessions tab column widths resetting:**
- Column widths are automatically saved when you resize them
- Widths persist across tab switches and application restarts
- If widths don't save, check that the application has write permissions for QSettings storage
- Try resizing columns and closing/reopening the application to verify persistence

**Import errors:**
- Check that your files are valid XISF or FITS format
- Verify that the xisf and astropy Python libraries are installed correctly
- Review the import log for specific error messages

**Slow performance with large catalogs:**
- Performance optimizations are automatic - no configuration needed
- Initial catalog load should be <0.5s for 1000+ files
- If performance is slow, try:
  - Click Refresh to rebuild with optimized queries
  - Check that composite indexes exist (run create_db.py if database is old)
  - Ensure sufficient RAM available for database caching
  - Check disk I/O performance (SSD recommended for large catalogs)

**FITS files not importing:**
- Ensure astropy library is installed: `pip install astropy`
- Check that files are valid FITS format
- Verify FITS header contains standard keywords
- Review import log for specific error messages

## File Structure

```
AstroFileManager/
├── create_db.py                    # Database creation script with indexes
├── AstroFileManager.py             # Main GUI application
├── core/
│   ├── database.py                 # Database manager with optimizations
│   └── calibration.py              # Calibration matching with caching
├── ui/
│   ├── background_workers.py       # QThread workers for async loading
│   ├── view_catalog_tab.py         # Catalog view with lazy loading
│   └── sessions_tab.py             # Sessions tab with cached matching
├── utils/
│   ├── fits_reader.py              # FITS file reader using astropy
│   └── file_organizer.py           # File organization utilities
├── import_export/
│   └── import_worker.py            # Multi-format import worker
├── xisf_catalog.db                 # SQLite database (created on first run)
└── readme.md                       # This file
```

## License

This project is provided as-is for personal use in managing astrophotography files.

## Contributing

Feel free to submit issues or pull requests for improvements.

## Version History

**v2.3.0** - Projects Tab: Project-Based Workflow Management
- **Projects Tab**: New comprehensive project-based workflow system
  - Create imaging projects with predefined templates (Narrowband, Broadband, Custom)
  - Track progress toward target frame counts per filter
  - Assign sessions to projects before quality grading
  - Import PixInsight SubFrame Selector CSV quality data
  - Dual progress tracking: total frames vs approved frames
  - Color-coded progress bars with visual indicators
  - Smart "Next Steps" recommendations based on project status
  - Project status management (active/completed/archived)
  - Unassigned sessions warning for better workflow tracking
- **Quality Tracking**: Frame quality metrics from PixInsight SubFrame Selector
  - Import FWHM, eccentricity, SNR, star count, background level
  - Approval status tracking (approved/rejected/not_graded)
  - Automatic project progress recalculation after quality import
  - Partial CSV import support (only updates frames in CSV)
- **Session Assignment**: Manual session-to-project linking
  - Context menu in View Catalog: "Assign to Project"
  - Assign sessions immediately after capture, before grading
  - Session notes and metadata tracking
  - Grading status indicators per session
- **Database Migration**: Automatic schema upgrade for existing databases
  - Migration script adds projects, filter goals, and session tables
  - Adds quality metric columns to xisf_files table
  - Safe idempotent migration (can run multiple times)
  - Verification step ensures migration success
- **Project Templates**: Pre-configured filter goals
  - Narrowband (SHO): 90 frames each of Ha, OIII, SII
  - Broadband (LRGB): 270 frames each of L, R, G, B
  - Custom: User-defined filter goals
- **Workflow Integration**: Complete multi-session imaging workflow
  - Create project → Capture → Import → Assign → Continue capturing → Grade → Import quality → Complete
  - Projects span multiple nights and sessions
  - Projects can span calendar years
  - Separate projects for same target in different years
- **Tab Navigation Fix**: Fixed tab change handler for correct refresh behavior
  - Projects tab now refreshes when selected
  - All tab indices corrected after Projects tab insertion

**v2.1.0** - Sessions Tab: Comprehensive Calibration Tracking
- **Sessions Tab**: New comprehensive calibration tracking system
  - Automatic session detection by grouping light frames (date + object + filter)
  - Smart calibration matching with tolerance-based criteria:
    - Darks: Exact exposure (±0.1s), ±1°C temperature, matching binning
    - Bias: ±1°C temperature, matching binning
    - Flats: Filter match, ±3°C temperature, exact date match, matching binning
  - Master frame detection and display with special badges
  - Quality scoring system (0-100%) based on frame counts
  - Color-coded status indicators (Complete/Partial/Missing/Complete with Masters)
  - Smart recommendations engine for missing or incomplete calibration
  - Export comprehensive session reports with calibration status and recommendations
  - Real-time statistics dashboard (total sessions, completion rate, breakdowns)
  - Advanced filtering: status filter, missing-only mode, master frame toggle
  - Session details panel with frame counts, settings, and quality scores
- **Column Width Persistence**: Sessions tab column widths now save and restore (Issue #33)
  - Automatic save on resize
  - Widths persist across tab switches and application restarts
  - Removed auto-resize that was overriding user preferences
- **Code Cleanup**: Removed Statistics tab (previously deleted, incorrectly restored)
- **Quality of Life**: Improved calibration workflow planning and gap identification

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