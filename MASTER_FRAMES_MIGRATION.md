# Master Frames Feature Migration Guide

## For Existing Users

If you have an existing AstroFileManager database, you need to run the migration script to add support for importing master frames.

### Running the Migration

**Option 1: Default database location**
```bash
python migrate_add_project_master_frames.py
```

**Option 2: Custom database location**
```bash
python migrate_add_project_master_frames.py /path/to/your/xisf_catalog.db
```

### What the Migration Does

The migration script:
1. Checks if your database has the `projects` table (required)
2. Creates the new `project_master_frames` table
3. Adds three indexes for efficient queries
4. Does NOT modify any existing data
5. Is safe to run multiple times (idempotent)

### Verification

After running the migration, you can verify it worked:

```bash
python test_master_frames.py
```

This will check:
- ✓ Table exists with correct schema
- ✓ All expected columns are present
- ✓ Indexes are created
- ✓ ProjectManager methods work

### Rollback (if needed)

If you need to remove the master frames feature:

```bash
sqlite3 xisf_catalog.db "DROP TABLE IF EXISTS project_master_frames;"
```

Note: This will delete any imported master frame associations, but will NOT delete the actual master frame files from your catalog.

## For New Users

No migration needed! The `project_master_frames` table is automatically created when you run:

```bash
python create_db.py
```

## Troubleshooting

**Error: "Database file not found"**
- Make sure you're in the correct directory
- Specify the full path to your database file

**Error: "'projects' table does not exist"**
- Your database is missing the projects table
- You may need to run an earlier migration first
- Or create a fresh database with `create_db.py`

**Error: "Table already exists"**
- Migration already completed
- Safe to ignore - no action needed

## Need Help?

- Check `IMPLEMENTATION_SUMMARY.md` for detailed feature documentation
- Run `python test_master_frames.py` to validate your setup
- Report issues on GitHub
