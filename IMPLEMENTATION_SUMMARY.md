# Master Frames Import Feature - Implementation Summary

## Issue #204: Add ability to import master frames to a project

### Overview
This implementation adds the ability to import and track master calibration frames (Master Dark, Master Flat, Master Bias) within projects. After files have been checked out for pre-processing and stacking is complete, users can now import the resulting master frames and display them in the project detail section.

### Changes Made

#### 1. Database Schema Changes

**New Table: `project_master_frames`**
- Tracks master calibration frames linked to projects
- Fields:
  - `id`: Primary key
  - `project_id`: Foreign key to projects table
  - `file_id`: Foreign key to xisf_files table
  - `frame_type`: Type of master frame (Master Dark/Flat/Bias)
  - `filter`: Filter name (for flats)
  - `exposure`: Exposure time
  - `ccd_temp`: CCD temperature
  - `binning`: Binning configuration (e.g., "1x1")
  - `imported_date`: Timestamp when imported
  - `notes`: Optional notes
- Includes CASCADE deletion when project or file is deleted
- Has UNIQUE constraint on (project_id, file_id) to prevent duplicates

**Files Modified:**
- `create_db.py`: Added table creation and indexes for new databases
- `migrate_add_project_master_frames.py`: NEW - Migration script for existing databases

#### 2. Core Business Logic

**File: `core/project_manager.py`**

**New DataClass:**
- `MasterFrame`: Represents a master calibration frame with all metadata

**New Methods:**
- `import_master_frames(project_id, file_ids)`: Import master frames to a project
  - Extracts metadata from xisf_files table
  - Automatically determines frame type from imagetyp field
  - Returns count of successfully imported frames
  - Handles duplicates gracefully

- `get_master_frames(project_id)`: Retrieve all master frames for a project
  - Returns list of MasterFrame objects with file details
  - Ordered by frame type, filter, and exposure

- `remove_master_frame(master_frame_id)`: Remove a master frame link
  - Only removes the project association, not the actual file

- `get_master_frames_summary(project_id)`: Get count summary by type
  - Returns dictionary like: {'Master Dark': 3, 'Master Flat': 5}

#### 3. User Interface

**File: `ui/projects_tab.py`**

**New UI Elements:**
- "Import Master Frames" button in toolbar
  - Enabled only when a project is selected
  - Opens import dialog

- "Master Calibration Frames" section in project details
  - Displays table of imported master frames
  - Shows: Type, Filter, Exposure, Temperature, Binning, Filename
  - Hidden when no master frames imported
  - Compact table with scroll support for many frames

**New Methods:**
- `display_master_frames(master_frames)`: Display master frames table
- `import_master_frames()`: Open import dialog and refresh on completion

**File: `ui/import_master_frames_dialog.py` (NEW)**

**Features:**
- Browse and select master frames from catalog
- Filter by frame type (Master Darks, Flats, Bias)
- Shows which frames are already imported (grayed out)
- Displays frame metadata: Type, Filter, Exposure, Temperature, Binning
- Select All / Deselect All buttons
- Real-time selection count
- Prevents duplicate imports

#### 4. Testing and Validation

**File: `test_master_frames.py` (NEW)**
- Validates database schema
- Checks for project_master_frames table and columns
- Tests ProjectManager methods
- Provides guidance for next steps

### Usage Instructions

#### For Existing Databases:
1. Run migration script:
   ```bash
   python migrate_add_project_master_frames.py [path_to_database]
   ```

#### For New Databases:
- The `project_master_frames` table is automatically created when running `create_db.py`

#### Using the Feature:
1. Launch AstroFileManager
2. Go to Projects tab
3. Select a project
4. Click "Import Master Frames" button
5. Filter master frame types if desired
6. Select frames to import (checkboxes)
7. Click "Import Selected"
8. View imported frames in "Master Calibration Frames" section

### Integration with Existing Features

**Consistent Display Style:**
- Master frames section follows the same design pattern as Filter Goals Progress
- Uses similar table styling and column configuration
- Fits within the existing splitter layout (Goals | Master Frames | Next Steps)

**Data Integrity:**
- Leverages existing xisf_files table (no file duplication)
- CASCADE deletion ensures orphaned records are cleaned up
- UNIQUE constraints prevent duplicate imports
- Foreign key relationships maintain referential integrity

**Backward Compatibility:**
- Migration script safely adds new table to existing databases
- Feature is optional - projects work fine without master frames
- No breaking changes to existing functionality

### Code Quality

**Follows Project Standards:**
- PEP 8 compliant formatting
- Comprehensive docstrings on all functions
- Type hints where appropriate
- Clear comments for complex logic
- Consistent error handling

**Beginner-Friendly:**
- Well-documented code
- Clear variable names
- Helpful error messages
- Simple, maintainable structure

### Files Changed/Added

**New Files:**
1. `migrate_add_project_master_frames.py` - Database migration script
2. `ui/import_master_frames_dialog.py` - Import dialog UI
3. `test_master_frames.py` - Test script
4. `IMPLEMENTATION_SUMMARY.md` - This document

**Modified Files:**
1. `create_db.py` - Added project_master_frames table
2. `core/project_manager.py` - Added MasterFrame class and methods
3. `ui/projects_tab.py` - Added import button and display section

### Testing Checklist

- [x] Syntax validation (all files compile)
- [x] Database schema validation
- [x] Migration script tested
- [ ] UI workflow tested (requires running application)
- [ ] Import/display cycle tested
- [ ] Duplicate prevention tested
- [ ] Deletion cascade tested

### Future Enhancements (Optional)

Potential improvements for future iterations:
- Export master frames with project checkout
- Master frame quality metrics display
- Batch import from directory
- Master frame versioning/replacement
- Link master frames to specific sessions
- Show master frame usage in calibration matching

---

**Implementation Date:** 2026-02-17
**Issue:** #204
**Status:** Complete - Ready for workflow testing
