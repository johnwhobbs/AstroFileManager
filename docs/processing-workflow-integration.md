# Processing Workflow Integration - Feature Recommendations

**Document Version:** 1.0
**Date:** November 2024
**Status:** Planning / Not Implemented

## Overview

This document outlines recommendations for extending AstroFileManager to support the complete astrophotography processing workflow, from raw frame acquisition through final image production.

## Current State

AstroFileManager currently excels at:
- Collection and cataloging of raw XISF and FITS files
- Calibration frame tracking and session management
- Quality analysis of imaging sessions
- Organizational structure for raw data

## Target Workflow

The typical astrophotography processing workflow consists of:

1. **Raw Acquisition** (✅ Currently Supported)
   - Light frame collection
   - Calibration frame collection (Darks, Flats, Bias)

2. **Frame Grading** (⚠️ Gap)
   - Evaluate frames using PixInsight SubFrame Selector
   - Metrics: Star count, FWHM, eccentricity, SNR, background levels
   - Approval/rejection decisions

3. **Calibration & Integration** (⚠️ Gap)
   - PixInsight Weighted Batch Preprocessing (WBPP)
   - Calibrate light frames with calibration frames
   - Create master light frame per filter

4. **Linear Processing** (⚠️ Gap)
   - Gradient removal
   - Color calibration
   - Background extraction

5. **Non-Linear Processing** (⚠️ Gap)
   - Stretching and enhancement
   - Final JPG/PNG output

## Recommendations

### 1. Subframe Quality Tracking & Approval System

**Purpose:** Bridge the gap between raw frame collection and integration by tracking frame quality metrics and approval status.

**Priority:** High
**Complexity:** Medium
**Dependencies:** None

#### Key Features

**Import SubFrame Selector CSV Data:**
- Parse and import quality metrics from PixInsight SubFrame Selector CSV exports
- Support standard SubFrame Selector output format
- Metrics to track:
  - `FWHM` (Real) - Focus quality in arcseconds
  - `Eccentricity` (Real) - Star roundness (0=perfect circle, 1=line)
  - `SNR` (Real) - Signal-to-noise ratio
  - `Star_Count` (Integer) - Number of detected stars
  - `Background_Level` (Real) - Background brightness
  - `Approval_Status` (Text) - 'approved', 'rejected', 'not_graded'
  - `Grading_Date` (Text) - When frame was evaluated

**Enhanced View Catalog:**
- Add quality metrics columns to catalog tree
- Color-code frames by approval status:
  - Green = approved
  - Red = rejected
  - Gray = not graded
- Filter to show only approved frames
- Sort by quality metrics (best FWHM first, etc.)
- Search/filter by quality thresholds

**Session Quality Dashboard:**
- Extend Sessions tab to show quality statistics per session
- Display percentage of approved frames
- Show average FWHM, eccentricity, SNR per session
- Identify sessions with poor seeing conditions
- Quality trend analysis over time

#### Database Schema Changes

```sql
-- Add quality tracking columns to existing table
ALTER TABLE xisf_files ADD COLUMN fwhm REAL;
ALTER TABLE xisf_files ADD COLUMN eccentricity REAL;
ALTER TABLE xisf_files ADD COLUMN snr REAL;
ALTER TABLE xisf_files ADD COLUMN star_count INTEGER;
ALTER TABLE xisf_files ADD COLUMN background_level REAL;
ALTER TABLE xisf_files ADD COLUMN approval_status TEXT DEFAULT 'not_graded';
ALTER TABLE xisf_files ADD COLUMN grading_date TEXT;
ALTER TABLE xisf_files ADD COLUMN grading_notes TEXT;

-- Index for common queries
CREATE INDEX idx_approval_status ON xisf_files(approval_status);
CREATE INDEX idx_fwhm ON xisf_files(fwhm);
```

#### UI Components

**New Import Option:**
- Menu item: "Import SubFrame Selector Data"
- File dialog for CSV selection
- Matching logic: filename-based
- Progress indicator during import
- Summary report of matched/unmatched frames

**View Catalog Enhancements:**
- New columns: FWHM, Eccentricity, SNR, Stars, Status
- Approval status indicator (icon/color)
- Right-click menu: "Mark as Approved/Rejected"
- Bulk approval actions

**Sessions Tab Enhancements:**
- Quality metrics summary per session
- "Export Approved Frames List" button
- Quality trend charts

#### Benefits

- Know which frames are ready for integration without opening PixInsight
- Track quality trends across imaging sessions
- Make informed decisions about which sessions to process first
- Generate approved-frames-only file lists for WBPP
- Historical quality tracking for equipment performance analysis

---

### 2. Processing Pipeline State Tracking

**Purpose:** Track the complete lifecycle of imaging data from raw frames through final processed images.

**Priority:** Medium
**Complexity:** High
**Dependencies:** Recommendation #1 (for grading state)

#### Key Features

**New "Pipeline" Tab:**
Visualize processing stages for each session with progress indicators:

1. **Raw Acquisition** (existing functionality)
2. **Graded** (frames evaluated in SubFrame Selector)
3. **Calibrated** (WBPP applied, master calibration created)
4. **Integrated** (master light frame created per filter)
5. **Linear Processing** (gradient removal, color calibration)
6. **Non-Linear Processing** (stretching, enhancement)
7. **Final Output** (JPG/PNG created)

**Master Frame Registry:**
- New database tables tracking master frames
- Link masters to source sessions and constituent frames
- Store integration parameters (rejection percentages, normalization)
- Track master calibration frames separately from master lights

**Visual Pipeline Progress:**
- Progress bars or status indicators for each session
- Color coding: green=complete, yellow=in-progress, gray=not-started
- Quick identification of sessions stuck at certain stages
- Drill-down to see which processing steps remain
- Timeline view of processing history

**Processing Metadata Storage:**
- Track PixInsight script/process used
- Store processing date/time
- Record key parameters (sigma clipping, normalization method)
- Notes field for processing decisions
- Link to processing scripts/icons used

#### Database Schema Changes

```sql
-- Master frames registry
CREATE TABLE master_frames (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    master_type TEXT NOT NULL, -- 'master_dark', 'master_flat', 'master_bias', 'master_light'
    filepath TEXT NOT NULL,
    session_id TEXT, -- Link to session (object_filter_date)
    object_name TEXT,
    filter TEXT,
    frame_count INTEGER, -- How many frames integrated
    integration_method TEXT, -- 'Average', 'Median', 'Winsorized Sigma Clipping'
    rejection_low REAL, -- Low rejection percentage
    rejection_high REAL, -- High rejection percentage
    normalization TEXT, -- 'Additive', 'Multiplicative', 'Local'
    pixel_rejection TEXT, -- 'Min/Max', 'Percentile Clipping', 'Sigma Clipping'
    created_date TEXT,
    notes TEXT,
    UNIQUE(filepath)
);

-- Link between master frames and constituent raw frames
CREATE TABLE master_frame_components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    master_frame_id INTEGER,
    raw_frame_id INTEGER,
    weight REAL, -- Integration weight (if weighted integration)
    FOREIGN KEY(master_frame_id) REFERENCES master_frames(id),
    FOREIGN KEY(raw_frame_id) REFERENCES xisf_files(id)
);

-- Processing pipeline state tracking
CREATE TABLE processing_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL, -- object_filter_date
    object_name TEXT,
    filter TEXT,
    date_loc TEXT,

    -- Pipeline stage flags
    raw_complete INTEGER DEFAULT 1, -- Always 1 if session exists
    grading_complete INTEGER DEFAULT 0,
    calibration_complete INTEGER DEFAULT 0,
    integration_complete INTEGER DEFAULT 0,
    linear_processing_complete INTEGER DEFAULT 0,
    nonlinear_processing_complete INTEGER DEFAULT 0,
    final_output_complete INTEGER DEFAULT 0,

    -- Stage metadata
    approved_frame_count INTEGER,
    master_light_id INTEGER, -- Link to master_frames
    final_output_path TEXT,

    -- Processing notes
    processing_notes TEXT,
    last_updated TEXT,

    UNIQUE(session_id),
    FOREIGN KEY(master_light_id) REFERENCES master_frames(id)
);

-- Processing history/log
CREATE TABLE processing_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    stage TEXT, -- 'grading', 'calibration', 'integration', etc.
    action TEXT, -- Description of action
    pixinsight_script TEXT, -- Script or process used
    parameters TEXT, -- JSON string of parameters
    timestamp TEXT,
    notes TEXT
);
```

#### UI Components

**New "Pipeline" Tab:**
- Session list with progress visualization
- Pipeline stage indicators (✓ complete, ⏳ in-progress, ○ not-started)
- Click session to see details
- Bulk status updates
- Filter by pipeline stage

**Master Frame Manager:**
- List all master frames (calibration and lights)
- Show constituent frames
- Display integration parameters
- Re-link or import existing masters
- Export master frame reports

**Processing History:**
- Timeline view of processing actions
- Search/filter by date, session, stage
- Notes and parameter tracking

#### Benefits

- Single source of truth for processing status
- Avoid re-processing sessions already completed
- Track which sessions need attention
- Historical record of processing decisions
- Audit trail for publication/documentation
- Identify bottlenecks in workflow

---

### 3. Integration Session Manager & WBPP File List Generator

**Purpose:** Simplify preparation of file lists for PixInsight integration and track integration outputs.

**Priority:** High
**Complexity:** Medium
**Dependencies:** Recommendation #1 (for approved frames filtering)

#### Key Features

**Smart Integration Session Builder:**
- Automatically group approved frames by object/filter combination
- Suggest optimal frame selection based on quality metrics
- Generate WBPP-compatible file lists with paths
- Include matching calibration frames automatically
- Validate calibration coverage before export

**WBPP Configuration Export:**
- Generate multiple output formats:
  - CSV file lists (light frames, darks, flats, bias)
  - PixInsight .xdrz process icons (future enhancement)
  - Plain text file lists
  - JSON configuration files
- Path format options:
  - Absolute paths
  - Relative paths
  - Windows/Linux path conversion
- Option to include only approved frames
- Configurable file list structure

**Integration Output Tracking:**
- Import master light frames back into catalog
- Link master frames to source sessions
- Track total integration time per master
- Display frame count and rejection statistics
- Link final processed images to masters
- Store integration reports from WBPP

**Integration Report Generation:**
Export detailed reports showing:
- Which frames went into each master
- Quality metrics of included frames (avg FWHM, SNR)
- Calibration frames used
- Total exposure time
- Rejection statistics (how many pixels/frames rejected)
- Integration parameters used
- Useful for documentation and sharing processing details

#### Database Schema Changes

```sql
-- Integration sessions (extends processing_states)
CREATE TABLE integration_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    object_name TEXT,
    filter TEXT,

    -- Frame selection
    light_frame_count INTEGER,
    approved_frame_count INTEGER,
    selected_frame_count INTEGER, -- How many actually used

    -- Calibration frames used
    dark_frames_used TEXT, -- JSON list of IDs
    flat_frames_used TEXT, -- JSON list of IDs
    bias_frames_used TEXT, -- JSON list of IDs

    -- Integration parameters
    integration_method TEXT,
    pixel_rejection TEXT,
    normalization TEXT,

    -- Results
    master_frame_id INTEGER,
    total_exposure_time REAL,
    rejection_rate REAL,

    -- Metadata
    created_date TEXT,
    wbpp_version TEXT,
    notes TEXT,

    FOREIGN KEY(master_frame_id) REFERENCES master_frames(id)
);

-- File list exports (for tracking)
CREATE TABLE file_list_exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    export_type TEXT, -- 'wbpp_csv', 'file_list', 'json'
    filepath TEXT,
    frame_count INTEGER,
    include_approved_only INTEGER,
    export_date TEXT
);
```

#### UI Components

**New "Integration" Tab or Extend Sessions Tab:**

**Integration Builder Panel:**
- List of integration candidates (object + filter combinations)
- Show approved frame count and total exposure
- Quality statistics (avg FWHM, SNR)
- Calibration coverage indicator
- "Build File List" button

**File List Export Dialog:**
- Format selection (CSV, TXT, JSON)
- Path format (absolute/relative)
- Filter options:
  - Approved frames only
  - Minimum quality threshold (FWHM < X)
  - Date range
- Preview before export
- Multi-session batch export

**Master Frame Import:**
- "Import Master Light" button
- Link to source session
- Parse FITS header for integration metadata
- Auto-detect constituent frames

**Integration Reports:**
- "Generate Integration Report" button
- PDF or HTML output
- Include:
  - Session details
  - Frame list with quality metrics
  - Calibration frames used
  - Integration parameters
  - Total exposure and statistics
  - Preview images (if available)

#### Implementation Details

**WBPP CSV Format:**
```csv
# Light Frames
/path/to/light/M31_Ha_001.xisf
/path/to/light/M31_Ha_002.xisf

# Dark Frames
/path/to/darks/Dark_300s_-10C_001.xisf
/path/to/darks/Dark_300s_-10C_002.xisf

# Flat Frames
/path/to/flats/Flat_Ha_-10C_001.xisf
/path/to/flats/Flat_Ha_-10C_002.xisf

# Bias Frames
/path/to/bias/Bias_-10C_001.xisf
/path/to/bias/Bias_-10C_002.xisf
```

**JSON Configuration Format:**
```json
{
  "session": {
    "object": "M31",
    "filter": "Ha",
    "date": "2024-11-15"
  },
  "light_frames": [
    "/path/to/light/M31_Ha_001.xisf",
    "/path/to/light/M31_Ha_002.xisf"
  ],
  "calibration": {
    "darks": ["/path/to/darks/Dark_300s_-10C_001.xisf"],
    "flats": ["/path/to/flats/Flat_Ha_-10C_001.xisf"],
    "bias": ["/path/to/bias/Bias_-10C_001.xisf"]
  },
  "parameters": {
    "integration_method": "winsorized_sigma_clipping",
    "normalization": "local"
  }
}
```

#### Benefits

- Eliminate manual file list creation for WBPP
- Ensure correct calibration frames are included
- Reduce errors in frame selection
- Complete audit trail from raw to final
- Simplify batch processing of multiple targets
- Quality-based frame selection automation
- One-click export for PixInsight integration

---

## Implementation Priority & Roadmap

### Phase 1: Foundation (Highest Priority)
**Recommendation #1: Subframe Quality Tracking**
- Immediate value for workflow
- Relatively straightforward implementation
- No dependencies
- Enables informed processing decisions

**Estimated Effort:** 3-4 weeks
- Database schema updates: 2 days
- CSV import functionality: 1 week
- UI enhancements (View Catalog): 1 week
- UI enhancements (Sessions tab): 1 week
- Testing & documentation: 3-4 days

### Phase 2: Integration Support (High Priority)
**Recommendation #3: Integration Session Manager**
- Builds on Phase 1 (uses approval status)
- Concrete workflow improvement
- Direct PixInsight integration

**Estimated Effort:** 3-4 weeks
- Database schema updates: 3 days
- File list export functionality: 1 week
- Integration tab UI: 1 week
- Master frame import: 1 week
- Report generation: 3-4 days
- Testing & documentation: 3-4 days

### Phase 3: Complete Tracking (Medium Priority)
**Recommendation #2: Pipeline State Tracking**
- Most comprehensive feature
- Benefits from data collected in Phases 1 & 2
- Provides holistic view of processing pipeline

**Estimated Effort:** 4-5 weeks
- Database schema updates: 1 week
- Pipeline tab UI: 2 weeks
- Master frame manager: 1 week
- Processing history tracking: 1 week
- Testing & documentation: 3-4 days

### Total Estimated Timeline
- **Phase 1:** 3-4 weeks
- **Phase 2:** 3-4 weeks (can start after Phase 1 complete)
- **Phase 3:** 4-5 weeks (can overlap with Phase 2)
- **Total:** 10-13 weeks for all three features

---

## Technical Considerations

### Database Migration
- Create migration script for existing databases
- Add new columns with sensible defaults
- Maintain backward compatibility
- Version tracking in database

### Performance
- Quality metrics will add columns but shouldn't impact performance significantly
- Indexes on approval_status and quality metrics for fast filtering
- Consider caching quality statistics in memory
- Lazy load master frame components on-demand

### Data Integrity
- Foreign key constraints for master frame relationships
- Validate CSV import data before inserting
- Transaction-based imports for rollback on errors
- Duplicate detection for master frame imports

### User Experience
- Non-intrusive: Features are optional, don't break existing workflow
- Progressive disclosure: Show quality metrics only when available
- Clear visual indicators for processing state
- Helpful tooltips and documentation

### PixInsight Integration
- Parse SubFrame Selector CSV format (well-documented)
- Generate WBPP-compatible file lists (standard format)
- Future: Direct .xdrz process icon generation
- Consider scripting API for automation

---

## Alternative Approaches Considered

### 1. Direct PixInsight Integration
**Considered:** Embedding PixInsight functionality directly
**Rejected:**
- PixInsight has proprietary formats and licensing
- Complexity and maintenance burden
- AstroFileManager focuses on management, not processing
- Better to integrate with PixInsight rather than replace it

### 2. Custom Frame Grading
**Considered:** Built-in frame grading tools
**Rejected:**
- PixInsight SubFrame Selector is industry standard
- Reinventing the wheel
- Focus on workflow integration, not reinvention
- Import existing grading data is more valuable

### 3. Full Processing Pipeline
**Considered:** Implement calibration, integration, processing
**Rejected:**
- Out of scope for management application
- PixInsight is the professional tool
- Focus on tracking and workflow, not processing
- Complementary tools work better than monolithic solutions

---

## Success Criteria

### Phase 1 Success
- [ ] Import SubFrame Selector CSV data successfully
- [ ] Display quality metrics in View Catalog
- [ ] Filter by approval status
- [ ] Sessions tab shows quality statistics
- [ ] Export approved-only frame lists

### Phase 2 Success
- [ ] Generate WBPP-compatible file lists
- [ ] Include correct calibration frames automatically
- [ ] Import master light frames
- [ ] Link masters to source sessions
- [ ] Generate integration reports

### Phase 3 Success
- [ ] Track all pipeline stages per session
- [ ] Visual pipeline progress indicators
- [ ] Processing history log functional
- [ ] Master frame manager operational
- [ ] Complete audit trail from raw to final

---

## Future Enhancements (Beyond Initial Implementation)

### Quality Analysis Tools
- Trend analysis: quality over time, by telescope, by conditions
- Weather correlation (if weather data available)
- Equipment performance tracking
- Session scoring and ranking

### Advanced Integration Features
- Automatic frame selection based on quality thresholds
- "Smart Stack" - automatically select best N frames
- Drizzle integration support
- Multi-night integration sessions

### Processing Automation
- Watch folders for new masters
- Auto-import master frames from output directories
- Batch file list generation
- Integration with other tools (NINA, SGP, etc.)

### Visualization
- Quality metric charts and graphs
- Processing timeline visualization
- Before/after image comparison
- Rejection map visualization

### Collaboration Features
- Export/import quality grading data
- Share processing recipes
- Team workflow support
- Processing notes and annotations

---

## References

### PixInsight Resources
- SubFrame Selector Documentation: https://pixinsight.com/doc/tools/SubFrameSelector/SubFrameSelector.html
- WBPP Documentation: https://pixinsight.com/doc/scripts/WeightedBatchPreprocessing/WeightedBatchPreprocessing.html
- Process Icon Format: PixInsight's proprietary .xdrz format

### Related Projects
- NINA (Nighttime Imaging 'N' Astronomy): Acquisition software
- SharpCap: Planetary imaging software
- N.I.N.A. Ground Station: Similar workflow tracking concepts

### Standards
- FITS Standard: https://fits.gsfc.nasa.gov/
- XISF Format: PixInsight's native format

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024-11-19 | Claude | Initial draft based on workflow analysis |

---

## Appendix A: SubFrame Selector CSV Format

Example SubFrame Selector output:

```csv
File,FWHM,Eccentricity,SNR,Stars,Median,Noise,Weight
M31_Ha_001.xisf,2.45,0.35,85.2,1234,1250.5,12.3,1.0
M31_Ha_002.xisf,2.87,0.42,72.1,1156,1230.2,14.5,0.85
M31_Ha_003.xisf,3.21,0.55,58.3,892,1210.8,18.2,0.45
```

**Mapping:**
- File → Match to xisf_files.filename
- FWHM → xisf_files.fwhm
- Eccentricity → xisf_files.eccentricity
- SNR → xisf_files.snr
- Stars → xisf_files.star_count
- Median → xisf_files.background_level
- Approval status → Derived from Weight or manual selection

---

## Appendix B: Example Use Cases

### Use Case 1: Frame Grading Workflow
1. Astronomer captures 50 Ha light frames
2. Runs PixInsight SubFrame Selector, exports CSV
3. Imports CSV into AstroFileManager
4. Reviews frames in View Catalog, sorted by FWHM
5. Sees 35 frames approved, 15 rejected
6. Exports approved frame list for WBPP

### Use Case 2: Integration Planning
1. Multiple imaging sessions of M31 in Ha, OIII, SII
2. Uses Integration tab to review all sessions
3. Generates separate file lists for each filter
4. Validates calibration frame coverage
5. Exports WBPP file lists
6. Runs WBPP in PixInsight
7. Imports resulting master lights back to AstroFileManager

### Use Case 3: Processing Audit Trail
1. Completes entire processing pipeline for M31
2. Records each stage in Pipeline tab
3. Links master frames to source sessions
4. Generates comprehensive integration report
5. Uses report for publication documentation
6. Shares processing details with community

---

*End of Document*
