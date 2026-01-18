# AstroFileManager

A comprehensive desktop application for managing astrophotography imaging campaigns. AstroFileManager catalogs your XISF and FITS files, tracks imaging projects across multiple nights, manages calibration frame libraries, and helps ensure you capture the right data for successful integration.

## What Does It Do?

AstroFileManager solves common astrophotography data management challenges:

- **Organize thousands of files** from multiple imaging sessions
- **Track multi-night imaging projects** with target frame counts per filter
- **Match light frames to calibration frames** automatically
- **Import quality grades** from PixInsight SubFrame Selector
- **Monitor progress** toward your imaging goals
- **Ensure complete calibration** before processing

## Quick Start

```bash
# Install dependencies
pip install PyQt6 xisf astropy

# Create database
python create_db.py

# Launch application
python AstroFileManager.py
```

## What's New in v2.4.0

**Major new features added:**

1. **Self-Update System** (Help menu → Check for Updates)
   - Update application directly from GitHub with one click
   - Choose Main (Stable) or Development (Latest) branch
   - Automatic backups before updates, database preservation

2. **Database Backup and Restore** (Maintenance tab → Database tab)
   - Create timestamped backups with one click
   - Restore from any previous backup
   - Automatic safety backup before restore

3. **Checkout Files for Processing** (Projects tab)
   - Export approved frames with matching calibration for PixInsight
   - One-click export to organized folder structure (Lights/, Darks/, Flats/, Biases/)
   - Automatic master calibration filename cleanup for WBPP compatibility
   - Only exports approved frames (quality-first approach)

4. **Reactivate Completed Projects** (Projects tab)
   - Resume work on completed projects to add more data
   - Useful when integration reveals need for more frames

5. **Calibration Frame Maintenance** (Maintenance tab → Calibration Frames tab)
   - Master Frame Temperature Tagging: Fix missing temps on PixInsight masters
   - Remove Duplicate Calibration: Clean up individual frames when masters exist
   - Remove Orphaned Calibration: Delete calibration with no matching lights

6. **Cross-Platform Configuration** (Settings tab)
   - Settings now stored in JSON file instead of Windows registry
   - Platform-independent, easy to backup

**See "Self-Update System" and "Application Tabs Overview" sections below for complete details.**

## Typical Workflows

### Workflow 1: Starting a New Imaging Project

**Goal:** Set up a new multi-night imaging campaign

1. **Create Project** (Projects tab → New Project)
   - Choose template (Narrowband SHO, Broadband LRGB, or Custom)
   - Set project name (e.g., "M31 Narrowband 2024")
   - Define target frame counts per filter

2. **Import First Night's Data** (Import Files tab)
   - Select "Import and organize" mode for automatic file organization
   - Click "Import Folder" and select your night's captures
   - Wait for import to complete

3. **Assign Sessions** (View Catalog tab)
   - Navigate to your light frames (expand Object → Filter → Date)
   - Right-click on the date node
   - Select "Assign to Project"
   - Choose your project from dropdown

4. **Monitor Progress** (Projects tab)
   - View total frames captured vs target
   - See which filters need more data
   - Check "Next Steps" recommendations

5. **Repeat** over multiple nights until targets are met

### Workflow 2: Quality Grading and Final Selection

**Goal:** Grade captured frames and update project progress

1. **Grade Frames in PixInsight**
   - Open SubFrame Selector
   - Load all frames for your project
   - Review quality metrics (FWHM, eccentricity, SNR)
   - Approve/reject frames based on criteria
   - Export CSV file with results

2. **Import Quality Data** (Projects tab → Import Quality Data)
   - Select the exported CSV file
   - Review import results (matched, approved, rejected counts)
   - System automatically updates project progress

3. **Check Final Status** (Projects tab)
   - View approved frame counts vs targets
   - Identify filters that need more captures
   - If targets met, mark project complete

4. **Generate Integration Lists**
   - Export file lists for WeightedBatchPreProcessing (future feature)
   - Begin integration in PixInsight

### Workflow 3: Managing Calibration Library

**Goal:** Build and maintain calibration frame library

1. **Capture Calibration Frames**
   - Darks: Match exposure times and temperatures of your light frames
   - Flats: Capture daily with each filter used
   - Bias: Capture at camera operating temperature

2. **Import Calibration Frames** (Import Files tab)
   - Import darks, flats, and bias frames
   - Application automatically recognizes frame types
   - Calibration frames organized separately from lights

3. **Check Calibration Status** (Sessions tab)
   - View automatic session detection (by date, object, filter)
   - See calibration matching results
   - Identify missing calibration:
     - Red: No calibration frames found
     - Orange: Partial calibration available
     - Green: Complete calibration ready

4. **Fill Gaps** (Sessions tab → recommendations)
   - Review specific recommendations for each session
   - Example: "Capture dark frames: 300.0s exposure at ~-10°C, 1x1 binning (minimum 10, recommended 20+)"
   - Capture missing calibration frames on next clear night

5. **Export Session Report** (Sessions tab → Export Report)
   - Generate comprehensive text report
   - Use as shooting list for next session
   - Track calibration library completeness

### Workflow 4: Complete Project from Capture to Processing

**Goal:** Complete end-to-end workflow from first capture to PixInsight processing

1. **Create Project** (Projects tab → New Project)
   - Set up project with target frame counts
   - Example: "NGC 7000 Narrowband 2024" with 90 Ha, 90 OIII, 90 SII

2. **First Night's Capture and Import** (Import Files tab)
   - Capture light frames and calibration frames
   - Import using "Import and organize" mode
   - Files automatically organized into repository structure

3. **Assign Session to Project** (View Catalog tab)
   - Navigate to date node under Object → Filter
   - Right-click → "Assign to Project"
   - Select your project

4. **Continue Capturing Over Multiple Nights**
   - Repeat capture, import, and assignment process
   - Monitor progress in Projects tab
   - Follow "Next Steps" recommendations

5. **Grade Frames in PixInsight**
   - Once you have sufficient data, grade all frames
   - Open SubFrame Selector in PixInsight
   - Load all light frames for the project
   - Review FWHM, eccentricity, SNR metrics
   - Approve good frames, reject poor frames
   - Export CSV with results

6. **Import Quality Data** (Projects tab)
   - Click "Import Quality Data" button
   - Select the exported CSV file
   - System updates approval status and recalculates progress
   - Review approved frame counts vs targets

7. **Checkout Files for Processing** (Projects tab)
   - Click "Checkout Files for Processing" button
   - Choose destination folder
   - Application exports:
     - All approved light frames
     - Matching dark frames for lights
     - Matching flat frames
     - Matching bias frames
     - Dark frames for the flats
   - Files organized into Lights/, Darks/, Flats/, Biases/ folders
   - Master calibration filenames cleaned (dates removed)

8. **Process in PixInsight**
   - Open WeightedBatchPreProcessing (WBPP)
   - Point to exported folder structure
   - WBPP automatically finds all files
   - Process with confidence - complete calibration verified
   - Integrate approved frames only

9. **Mark Project Complete** (Projects tab)
   - After successful integration, mark project as complete
   - Or use "Reactivate Project" if you need more data later

### Workflow 5: Organizing Existing Data

**Goal:** Import and organize historical astrophotography data

1. **Set Repository Path** (Settings tab)
   - Browse to your organized storage location
   - Application will create standardized folder structure

2. **Import Historical Data** (Import Files tab)
   - Select "Import and organize" mode
   - Import all your historical XISF/FITS files
   - Files copied to organized structure while originals preserved

3. **Review Organization** (View Catalog tab)
   - Browse lights: Object → Filter → Date → Files
   - Browse calibration: Frame Type → Grouping → Date → Files
   - Verify all files imported correctly

4. **Create Historical Projects** (Projects tab)
   - Create projects for completed imaging runs
   - Mark as "archived" for reference
   - Track what you've already captured

5. **Clean Up Metadata** (Maintenance tab)
   - Use Search & Replace to fix inconsistent values
   - Example: Standardize telescope name across all sessions
   - Ensure consistent filter names

## Self-Update System

**Purpose:** Keep AstroFileManager up-to-date with the latest features and bug fixes directly from GitHub

**Features:**
- **Automatic update checking** from GitHub repository
- **Two update branches:**
  - **Main Branch (Stable):** Production-ready releases
  - **Development Branch (Latest features):** Cutting-edge features and improvements
- **Version tracking** using commit SHA
- **Automatic backups** before applying updates
- **Database preservation** during updates
- **One-click installation** with automatic restart
- **Progress tracking** during download

**How to Update:**

1. **Check for Updates** (Help menu → Check for Updates)
   - Application checks GitHub for newer commits
   - Shows current version and latest available version
   - Displays commit message and author information

2. **Choose Update Branch** (Settings tab → Updates section)
   - Select Main Branch for stable releases
   - Select Development Branch for latest features
   - Preference saved for future update checks

3. **Install Update**
   - Click "Install Update" button in update dialog
   - Application creates automatic backup of current version
   - Downloads update as ZIP file with progress bar
   - Extracts files (preserves database files)
   - Restarts application automatically

**Important Notes:**
- Database files (*.db, *.db-journal) are never overwritten during updates
- Backup of previous version created before update (timestamped folder)
- Recommendation to create manual database backup before major updates
- Update requires internet connection to access GitHub
- Version tracking uses `.update_commit_sha` file in application directory

**When to Use:**
- Monthly or when notified of important bug fixes
- Before starting a new imaging season
- When new features are announced
- If experiencing issues that may be fixed in newer versions

## Application Tabs Overview

### View Catalog Tab

**Purpose:** Browse all imported files in hierarchical organization

**Light Frames Section:**
```
▼ Light Frames
  ▼ M31 (Object)
    ▼ Ha (Filter)
      ▼ 2024-10-15 (Date)
        • M31_Ha_001.xisf
        • M31_Ha_002.xisf
```

**Calibration Frames Section:**
```
▼ Calibration Frames
  ▼ Dark Frames
    ▼ 300s_-10C_Bin1x1
      ▼ 2024-10-15
  ▼ Flat Frames
    ▼ 2024-10-15
      ▼ Ha_-10C_Bin1x1
  ▼ Bias Frames
    ▼ -10C_Bin1x1
```

**Key Features:**
- Lazy loading for fast performance with large catalogs
- Temperature grouping (frames within ±0.5°C)
- Right-click to assign sessions to projects
- Filter by image type and object

**When to Use:**
- Browse your entire catalog
- Find specific frames by object, filter, or date
- Assign imaging sessions to projects
- Verify import results

### Projects Tab

**Purpose:** Manage multi-night imaging campaigns with target goals

**Main Features:**
- **Project Creation:** Templates for common workflows (Narrowband, Broadband, Custom)
- **Progress Tracking:** Compact table showing total and approved frame counts
- **Edit Projects:** Modify project details and filter goals
- **Quality Import:** Import PixInsight SubFrame Selector CSV data
- **Next Steps:** Smart recommendations based on progress

**Progress Display:**

| Filter | Total | Approved | Progress |
|--------|-------|----------|----------|
| Ha     | 100/90 (111%) | 85/90 (94%) | ● 94%  |
| OIII   | 50/90 (56%)   | 48/90 (53%) | ● 53%  |
| SII    | 90/90 (100%)  | 90/90 (100%) | ● 100% |

**Color-Coded Progress:**
- ● Green (100%): Goal met
- ● Light Green (75-99%): Excellent progress
- ● Orange (50-74%): Moderate progress
- ● Dark Orange (25-49%): Low progress
- ● Red (0-24%): Just starting

**Customization:**
- Resizable table columns (Project Name, Object, Year, Status, Created)
- Resizable filter goals table columns
- Adjustable splitter between goals and recommendations
- All preferences saved across sessions

**Export Files for Processing:**
- **Checkout Files for Processing** button exports approved frames with matching calibration
- Only exports frames with `approval_status = 'approved'` (must grade in PixInsight first)
- Automatically includes matching calibration frames:
  - Dark frames (matching exposure, temperature, binning)
  - Flat frames (matching filter, date, temperature, binning)
  - Bias frames (matching temperature, binning)
  - Dark frames for the flat frames
- Organizes files into subdirectories:
  - `Lights/` - Approved light frames only
  - `Darks/` - Dark frames for lights and flats
  - `Flats/` - Flat frames
  - `Biases/` - Bias frames
- **Master frame handling:** Automatically removes dates from master calibration filenames for PixInsight WBPP compatibility when processing lights from multiple nights
  - Example: `Master_Bias_20241215_-10C_Bin1x1.xisf` → `Master_Bias_-10C_Bin1x1.xisf`
- Progress tracking during export
- Ready for immediate processing in PixInsight WeightedBatchPreProcessing

**Project Management:**
- **Edit Project:** Modify project details, filter goals, and target counts after creation
- **Reactivate Project:** Change completed projects back to active status to add more data
- **Delete Project:** Remove projects from database (does not delete image files)

**UI Customization:**
- **Resizable columns:** Project Name, Object, Year, Status, Created
- **Movable columns:** Drag column headers to reorder
- **Sortable columns:** Click headers to sort (ascending/descending)
- **Column preferences:** All resize, order, and sort settings saved across sessions
- **Adjustable splitters:**
  - Main splitter between projects list and details panel
  - Secondary splitter between Filter Goals and Next Steps sections
  - Positions saved and restored

**When to Use:**
- Plan new imaging campaigns
- Track progress across multiple nights
- Import quality grades from PixInsight
- Know when you have enough data
- Edit project goals as conditions change
- Export approved frames for final processing
- Resume work on previously completed projects

### Sessions Tab

**Purpose:** Track calibration frame completeness for each imaging session

**How It Works:**
1. Automatically detects sessions (by date + object + filter)
2. Searches for matching calibration frames:
   - **Darks:** Same exposure (±0.1s), similar temp (±1°C), matching binning
   - **Bias:** Similar temp (±1°C), matching binning
   - **Flats:** Same filter, similar temp (±3°C), same date, matching binning
3. Scores calibration quality (0-100% based on frame counts)
4. Provides specific recommendations for missing calibration

**Status Indicators:**
- **Green:** Complete (all three types, 10+ frames each or master available)
- **Blue:** Complete with masters (master frames detected)
- **Orange:** Partial (some calibration missing)
- **Red:** Missing (no calibration found)

**Calibration Details Example:**
```
Session: 2024-11-07 - M31 - Ha
Light Frames: 25 | Exposure: 300.0s | Temp: -10.2°C | Binning: 1x1

  Darks (300.0s): ✓ 20 frames (Quality: 100%)
  Bias: ✓ 25 frames (Quality: 100%)
  Flats (Ha): ✗ Missing (Quality: 0%)

  Recommendations:
    • Capture flat frames: Ha, ~-10°C, 1x1 binning (minimum 10, recommended 20+)
```

**When to Use:**
- Before starting preprocessing
- Identify missing calibration frames
- Plan calibration frame captures
- Export session reports for reference
- Ensure you have everything needed for WeightedBatchPreProcessing

### Analytics Tab

**Purpose:** Visualize imaging activity over time

**Features:**
- GitHub-style activity heatmap
- Shows imaging sessions throughout the year
- Color intensity based on total exposure hours:
  - Gray: No activity
  - Light blue: < 2 hours
  - Medium blue: 2-4 hours
  - Dark blue: 4-6 hours
  - Darkest blue: 6+ hours
- Year selector for historical view

**When to Use:**
- Track imaging consistency
- Identify productive periods
- Share imaging statistics
- Review seasonal patterns

### Import Files Tab

**Purpose:** Add new files to the catalog

**Import Modes:**

**1. Import Only (store original paths)**
- Files remain in original location
- Database stores paths to files
- Good for: Organized storage you manage manually

**2. Import and Organize (copy to repository)**
- Files copied to standardized folder structure
- Original files preserved
- Database updated with new paths
- Good for: Letting application manage organization

**Supported Formats:**
- XISF files (.xisf)
- FITS files (.fits, .fit)
- Both formats treated identically

**Import Options:**
- Import Files: Select individual files
- Import Folder: Import entire folder with subdirectories recursively

**When to Use:**
- After each imaging session
- When adding historical data
- When reorganizing your library

### Maintenance Tab

**Purpose:** Database management, bulk metadata corrections, and calibration frame maintenance

**Database Tab:**

**Database Backup and Restore:**
- **Create Backup:** Generate timestamped backup of entire database
  - Default location: `~/.config/AstroFileManager/database_backups/` (Linux) or `%LOCALAPPDATA%\AstroFileManager\database_backups\` (Windows)
  - Uses SQLite backup API for safe, consistent backups
  - Shows human-readable file sizes (KB, MB, GB)
- **Restore Backup:** Replace current database with selected backup
  - Automatically creates safety backup before restore
  - Lists all available backups with creation date and size
  - Confirmation required for safety
  - Recommendation to restart after restore
- **Delete Backup:** Remove old backup files
- **Refresh Backup List:** Update list of available backups
- Backup directory configurable via config file

**Clear Database:**
- Safely clear all data with confirmation
- Start fresh when needed
- Does not affect backup files

**Calibration Frames Tab:**

**Master Frame Temperature Tagging:**
- Assign CCD-TEMP values to master calibration frames lacking temperature metadata
- Lists all master frames with current temperature status
- Highlights frames missing temperature (common with PixInsight masters)
- Bulk temperature assignment to multiple selected frames
- Updates database, renames files, and moves to correct folders
- Enables proper session matching for master frames

**Remove Duplicate Calibration Frames:**
- Identify individual calibration frames when master frames exist
- Shows count of duplicates and total disk space to reclaim
- Preview list of files to be removed
- Options:
  - Remove from database only
  - Remove from database and delete files
- Safety confirmation dialogs
- Helps clean up redundant calibration data

**Remove Orphaned Calibration Frames:**
- Find calibration frames with no matching light frames
- Identifies darks, flats, and bias frames that are no longer needed
- Shows count and total disk space
- Preview list with frame parameters (exposure, temperature, binning)
- Options:
  - Remove from database only
  - Remove from database and delete files
- Useful for cleaning up after completing projects

**Metadata Tab:**

**Search and Replace:**
- Fix inconsistent FITS keyword values
- Standardize telescope names
- Normalize filter names
- Correct object name typos
- Update instrument names

**Example Use Cases:**
```
Telescope name: "FSQ106" → "Takahashi FSQ-106EDX3"
Filter name: "Hydrogen Alpha" → "Ha"
Object name: "M 31" → "M31"
```

**File Organization Tab:**

**File Organization:**
- Preview organization before execution
- Copy files to standardized structure
- Update database with new paths
- Preserve original files

**When to Use:**
- **Before imaging season:** Create database backup
- **After major changes:** Create backup before bulk operations
- **Regular maintenance:** Monthly or after completing projects
- **Before updates:** Backup before applying application updates
- **Cleanup:** Remove duplicate or orphaned calibration frames
- **Master frames:** Tag temperature on PixInsight master calibration frames
- **Metadata fixes:** Standardize naming conventions
- **Reorganization:** Reorganize existing catalog
- **Recovery:** Restore from backup if issues occur

### Settings Tab

**Purpose:** Configure application preferences

**Available Settings:**

**Image Repository:**
- Set path for organized file storage
- Used by Import and Organize mode
- Used by File Organization feature

**Timezone:**
- Set your local timezone
- Important for DATE-OBS conversion
- Ensures correct date grouping
- Critical for master calibration frames

**Theme:**
- Standard (light theme)
- Dark (optimized for nighttime use)

**Updates:**
- **Update Branch Selection:**
  - **Main Branch (Stable):** Production-ready releases with thoroughly tested features
  - **Development Branch (Latest features):** Cutting-edge features and improvements
- Preference saved and used by "Check for Updates" feature
- Choose based on your preference for stability vs. latest features

**Configuration File Location:**
Application settings are stored in a JSON file for easy backup and cross-platform compatibility:
- **Windows:** `C:\Users\<username>\AppData\Local\AstroFileManager\config.json`
- **Linux:** `~/.config/AstroFileManager/config.json`
- **macOS:** `~/Library/Application Support/AstroFileManager/config.json`

**When to Use:**
- Initial setup
- When changing storage locations
- When timezone changes
- Theme preference adjustment
- Selecting update branch preference
- Backing up settings (copy config.json file)

## Detailed Technical Information

### Database Schema

**xisf_files table** - Core image metadata:
- Unique file identification via SHA256 hash
- Complete FITS header metadata
- Project and session linkage
- Quality metrics from SubFrame Selector
- Approval status tracking

**projects table** - Imaging campaigns:
- Project name, object, description
- Status tracking (active/completed/archived)
- Date tracking

**project_filter_goals table** - Target counts:
- Filter-specific frame targets
- Current total and approved counts
- Progress tracking

**project_sessions table** - Session assignments:
- Links imaging sessions to projects
- Tracks grading status
- Stores quality metrics

### Metadata Extraction

**Automatic extraction from FITS headers:**
- TELESCOP - Telescope name
- INSTRUME - Camera/instrument
- OBJECT - Target object (NULL for calibration)
- FILTER - Filter name
- IMAGETYP - Frame type (Light/Dark/Flat/Bias)
- EXPOSURE or EXPTIME - Exposure time
- CCD-TEMP, TEMPERAT, CCD_TEMP - Temperature
- XBINNING, YBINNING - Binning
- DATE-LOC or DATE-OBS - Observation date

**Date Processing:**
1. Prefers DATE-LOC (local time)
2. Falls back to DATE-OBS (UTC) with timezone conversion
3. Subtracts 12 hours for session grouping
4. Groups overnight sessions under single date

**Temperature Grouping:**
- Frames within ±0.5°C grouped together
- Example: -10.2°C, -10.8°C, -9.6°C all display as "-10C"
- Simplifies calibration frame matching

### File Organization Structure

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

**Why This Structure:**
- Easy matching of calibration to light frames
- Flats organized by date (session-specific calibration best practice)
- Consistent naming across all sessions
- Simplified workflow for stacking software
- Organized by object and filter for browsing

### CSV Quality Import Format

**Supported Formats:**
- Standard PixInsight SubFrame Selector CSV
- Custom exports with approval columns
- Flexible column name handling

**Approval Column Handling:**
The importer automatically detects approval status from various formats:

**Boolean Text Values:**
- "True", "Yes", "1", "Approved" → approved
- "False", "No", "0", "Rejected" → rejected

**Numeric Weight Values:**
- Weight > 0 → approved
- Weight = 0 → rejected

**Column Names:**
- Works with "Approved", "Weight", or any column name
- Specify column name during import
- Default: "Approved" column

**Required CSV Columns:**
- "Index" - Row number
- "File" - Filename or path
- Approval column (configurable name)

**Optional Quality Metrics:**
- FWHM - Full Width Half Maximum
- Eccentricity - Star eccentricity
- SNRWeight - Signal-to-noise ratio
- Stars - Star count
- Median - Background level

### Performance Optimizations

**Database:**
- WAL mode for concurrent access (30-50% faster writes)
- 64MB cache for hot data
- 256MB memory-mapped I/O
- Composite indexes for fast queries

**Query Optimization:**
- View Catalog: 1-2 queries (99% reduction from 191-1000+)
- Sessions Tab: 4 queries (98% reduction from 300+)
- Pre-computed calibration matching with caching

**UI Responsiveness:**
- Background threading for data loading
- Non-blocking operations
- Progress indicators
- Cancellable operations
- Lazy loading in View Catalog

**Performance Metrics:**
- Large catalogs (1000+ files): <0.5s initial load
- No UI freezing during operations
- Responsive with multiple sessions

### Calibration Matching Logic

**Darks Matching Criteria:**
- Exposure: Within ±0.1 seconds
- Temperature: Within ±1°C
- Binning: Exact match (X and Y)

**Bias Matching Criteria:**
- Temperature: Within ±1°C
- Binning: Exact match (X and Y)
- Exposure: Not checked (bias are zero-length exposures)

**Flats Matching Criteria:**
- Filter: Exact match (or both NULL)
- Temperature: Within ±3°C (more flexible for dusk/dawn flats)
- Date: Exact match (flats should be from same night)
- Binning: Exact match (X and Y)

**Master Frame Detection:**
- IMAGETYP contains "Master" (e.g., "Master Dark Frame")
- Displayed with special "Master" badges
- Can substitute for 10+ individual frames
- Reduces storage and processing requirements

**Quality Scoring:**
- 0-100% based on frame count
- 100% = 20+ frames (recommended)
- 50% = 10 frames (minimum acceptable)
- 0% = no frames found
- Masters boost quality score

## Requirements

- Python 3.7 or higher
- PyQt6 (GUI framework)
- xisf (XISF file support)
- astropy (FITS file support)
- sqlite3 (included with Python)

## Installation

```bash
# Install dependencies
pip install PyQt6 xisf astropy

# Create database
python create_db.py

# Launch application
python AstroFileManager.py
```

## Troubleshooting

**"Database not found" error:**
- Run `create_db.py` first
- Database file must be in same directory as application
- If issue persists, restore from backup in Maintenance tab

**Date fields showing NULL:**
- Files need DATE-LOC or DATE-OBS keyword
- Set timezone in Settings tab if using DATE-OBS
- Check that timezone matches your imaging location

**CSV import shows all rejected:**
- Check approval column name (should be "Approved")
- Verify CSV has True/False or 1/0 values
- Review import results for column detection

**Calibration frames not matching:**
- Verify temperature within tolerance (±1°C for Darks/Bias, ±3°C for Flats)
- Check binning matches exactly
- For Darks: exposure must match within ±0.1s
- For Flats: date must match exactly
- For master frames: use "Master Frame Temperature Tagging" in Maintenance tab if missing temperature

**Slow performance:**
- Normal for initial load of large catalogs
- Subsequent operations should be fast
- Check disk I/O (SSD recommended)
- Ensure sufficient RAM for database cache

**Files not importing:**
- Verify XISF/FITS format validity
- Check FITS header contains standard keywords
- Review import log for specific errors
- Ensure astropy library installed for FITS

**Update check fails:**
- Verify internet connection
- Check GitHub is accessible (not blocked by firewall)
- Try switching update branch in Settings tab
- Check `.update_commit_sha` file exists in application directory

**"Checkout Files for Processing" exports no files:**
- Ensure frames are graded in PixInsight SubFrame Selector first
- Import CSV quality data in Projects tab
- Only approved frames are exported
- Verify project has sessions assigned and approved frames

**Backup/Restore issues:**
- Ensure backup directory exists and is writable
- Check sufficient disk space for backups
- Restart application after restore as recommended
- Backup directory configurable in config.json

**Master calibration frames not matching in Sessions tab:**
- Use "Master Frame Temperature Tagging" in Maintenance tab → Calibration Frames
- Assign CCD-TEMP value that matches your light frames
- Tool will rename files and update database automatically

## Project Structure

```
AstroFileManager/
├── create_db.py                    # Database creation with schema
├── AstroFileManager.py             # Main application entry point
├── constants.py                    # Configuration constants
├── .update_commit_sha              # Current version commit tracking (auto-generated)
├── core/
│   ├── database.py                 # Database manager with backup/restore
│   ├── calibration.py              # Calibration matching logic
│   ├── project_manager.py          # Project CRUD operations
│   ├── project_templates.py        # Project templates
│   ├── config_manager.py           # Cross-platform configuration manager
│   └── update_manager.py           # Self-update system
├── ui/
│   ├── background_workers.py       # Async data loading
│   ├── view_catalog_tab.py         # Catalog browser
│   ├── projects_tab.py             # Project management
│   ├── sessions_tab.py             # Calibration tracking
│   ├── analytics_tab.py            # Activity heatmap
│   ├── import_tab.py               # File import
│   ├── maintenance_tab.py          # Database tools and calibration maintenance
│   ├── settings_tab.py             # Application settings
│   ├── new_project_dialog.py       # Create project dialog
│   ├── edit_project_dialog.py      # Edit project dialog
│   ├── export_project_dialog.py    # Export files for processing dialog
│   ├── export_project_worker.py    # Background export worker
│   └── update_dialog.py            # Update check and install dialog
├── import_export/
│   ├── import_worker.py            # Multi-format import
│   ├── csv_exporter.py             # CSV export
│   └── subframe_selector_importer.py  # Quality data import
├── utils/
│   ├── fits_reader.py              # FITS file reader
│   └── file_organizer.py           # File organization
└── xisf_catalog.db                 # SQLite database (created on first run)
```

## Version History

**v2.4.0** - Self-Update System, Database Backup/Restore, and Export Enhancements
- **Self-Update System**: Update application directly from GitHub
  - Check for updates from Main (Stable) or Development (Latest) branch
  - Automatic backup before updates
  - One-click installation with automatic restart
  - Version tracking using commit SHA
  - Database preservation during updates
- **Database Backup and Restore**: Complete database protection
  - Create timestamped backups with one click
  - Restore from any previous backup
  - View backup size and creation date
  - Safety backup created automatically before restore
  - Configurable backup directory location
- **Checkout Files for Processing**: Export approved frames for PixInsight
  - Export approved light frames with matching calibration
  - Automatically finds and includes darks, flats, bias, and flat darks
  - Organizes files into Lights/, Darks/, Flats/, Biases/ subdirectories
  - Special handling for master calibration: removes dates from filenames for WBPP compatibility
  - Progress tracking during export
  - Ready for immediate processing in WeightedBatchPreProcessing
- **Reactivate Completed Projects**: Resume work on finished projects
  - Change project status from Completed back to Active
  - Add more exposures to previously completed projects
  - Useful when initial integration reveals need for more data
- **Configuration File Storage**: Cross-platform settings management
  - Settings stored in JSON file instead of Windows registry
  - Platform-independent configuration locations
  - Human-readable format for easy debugging
  - Easy to backup and restore
- **Calibration Frame Maintenance**: Advanced cleanup tools
  - Master Frame Temperature Tagging: Assign CCD-TEMP to PixInsight master calibration frames
  - Remove Duplicate Calibration Frames: Clean up individual frames when masters exist
  - Remove Orphaned Calibration Frames: Delete calibration with no matching light frames
  - Preview before deletion with disk space recovery information
- **Projects Tab UI Enhancements**:
  - Resizable and movable columns with persistent preferences
  - Sortable columns by clicking headers
  - Column order and sort state saved across sessions
  - Improved column width management
- **Settings Tab Updates**:
  - Update branch preference (Main/Development)
  - Configuration file location documentation
  - Enhanced tooltip descriptions
- **Bug Fixes**:
  - Fixed True/False approval values in CSV import
  - Resolved update commit tracking after restart
  - Improved checkout files to only export approved frames
  - Fixed date removal for master bias and dark frames
  - Corrected bias folder naming in export structure
  - Added dark frames for flat frames in export

**v2.3.1** - Projects Tab: UI Improvements & CSV Import Enhancements
- **Projects Tab UI Overhaul**: Space-efficient design improvements
  - Replaced bulky progress bars with compact table format
  - Filter Goals displayed in tabular layout (Filter | Total | Approved | Progress)
  - Color-coded progress indicators with percentage bullets (● 100%)
  - ~70% vertical space savings while showing same data
  - Better space allocation: projects list gets 67% of screen, details get 33%
  - Resizable project table columns with saved preferences
  - Edit Project functionality to modify existing projects
- **Resizable Components**: Full layout customization
  - Resizable table columns for Filter Goals table
  - Resizable project table columns (Project Name, Object, Year, Status, Created)
  - Adjustable splitter between Filter Goals and Next Steps sections
  - Adjustable splitter between projects list and details panel
  - All resize preferences saved and restored across sessions
- **CSV Import Improvements**: Robust approval value handling
  - Fixed issue where True/False approval values were incorrectly processed
  - Unified approval logic works regardless of column name
  - Handles boolean text (True/False, Yes/No, 1/0) and numeric weights
  - Changed default column from "Weight" to "Approved" for standard format
  - Supports mixed CSV formats with flexible column detection
- **Edit Project Feature**: Modify existing projects
  - Edit project name, object, year, and description
  - Add/remove/update filter goals and target counts
  - Validates project name uniqueness
  - Recalculates frame counts after updates
- **Tab Switching Fix**: Preserved project selection across tab switches
  - Selected project and details now persist when switching tabs
  - Fixed data clearing issue on tab navigation
- **Background Worker Cleanup**: Enhanced signal management
  - Properly disconnect worker signals to prevent stale data issues
  - Fixed race conditions in Sessions and Catalog tabs
  - Improved memory management for background threads
- **Code Cleanup**: Removed development artifacts
  - Deleted migration scripts, debug tools, and test data
  - Cleaner repository with only production code

**v2.3.0** - Projects Tab: Project-Based Workflow Management
- **Projects Tab**: New comprehensive project-based workflow system
  - Create imaging projects with predefined templates (Narrowband, Broadband, Custom)
  - Track progress toward target frame counts per filter
  - Assign sessions to projects before quality grading
  - Import PixInsight SubFrame Selector CSV quality data
  - Dual progress tracking: total frames vs approved frames
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
- **Project Templates**: Pre-configured filter goals
  - Narrowband (SHO): 90 frames each of Ha, OIII, SII
  - Broadband (LRGB): 270 frames each of L, R, G, B
  - Custom: User-defined filter goals
- **Workflow Integration**: Complete multi-session imaging workflow
  - Create project → Capture → Import → Assign → Continue capturing → Grade → Import quality → Complete
  - Projects span multiple nights and sessions
  - Projects can span calendar years
  - Separate projects for same target in different years

**v2.1.0** - Sessions Tab: Comprehensive Calibration Tracking
- **Sessions Tab**: New comprehensive calibration tracking system
  - Automatic session detection by grouping light frames (date + object + filter)
  - Smart calibration matching with tolerance-based criteria
  - Master frame detection and display with special badges
  - Quality scoring system (0-100%) based on frame counts
  - Color-coded status indicators (Complete/Partial/Missing/Complete with Masters)
  - Smart recommendations engine for missing or incomplete calibration
  - Export comprehensive session reports
  - Real-time statistics dashboard
  - Advanced filtering: status filter, missing-only mode, master frame toggle
- **Column Width Persistence**: Sessions tab column widths now save and restore
- **Code Cleanup**: Removed Statistics tab
- **Quality of Life**: Improved calibration workflow planning

**v2.0.0** - Major Update: Integrated Workflow & Enhanced Data Handling
- **Import Workflow Integration**: Added import mode selection
  - Files can now be organized during import
  - Mode selection persists between sessions
- **Timezone Support**: Added DATE-OBS with timezone conversion
  - Supports master calibration frames that only have DATE-OBS (UTC)
  - 23 common timezones available
- **View Catalog Improvements**: Dual-section tree view
  - Separated Light Frames and Calibration Frames sections
  - All calibration frames now visible
- **Temperature Rounding**: Frames within ±0.5°C grouped together
- **Enhanced Import Logic**:
  - EXPTIME keyword support
  - Calibration frames automatically imported without object field
  - Robust string-to-numeric conversion
- **Analytics Tab**: Replaced Statistics tab with activity heatmap

**v1.3.0** - File Organization Feature
- Added automatic file organization with standardized naming conventions
- Separate folder structures for Lights and Calibration frames
- Preview organization plan before execution
- Repository path configuration in Settings tab

**v1.2.0** - Maintenance and Settings Update
- Added Maintenance tab with database management tools
- Implemented search and replace functionality for bulk metadata corrections
- Added Settings tab with theme configuration

**v1.1.0** - Statistics and UI Improvements
- Enhanced statistics dashboard with equipment information
- Improved column management and display

**v1.0.0** - Initial Release
- Import and catalog XISF files
- Hierarchical catalog view
- Statistics dashboard
- Persistent settings
- Dark theme UI
- SHA256 file hash duplicate detection

## License

This project is provided as-is for personal use in managing astrophotography files.

## Contributing

Feel free to submit issues or pull requests for improvements.

## Support

For questions, issues, or feature requests, please open an issue on GitHub.
