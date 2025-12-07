# Auto-Update Feature Recommendation

## Executive Summary

This document outlines the recommended approach for implementing an auto-update feature in AstroFileManager that allows users to:
1. Subscribe to either the `main` or `Development` branch
2. Check for and download updates with a single click
3. Automatically restart the application after update installation

## Current Application Context

**Technology Stack:**
- Python 3.x desktop application
- PyQt6 GUI framework
- Git repository: johnwhobbs/AstroFileManager
- Current branches: `main` (stable), `Development` (latest features)
- Deployment: Users run Python source code directly

## Recommended Architecture

### Option 1: Git-Based Updates (Recommended for Development)

**Best for:** Users who already have Python/Git installed and run from source

**Approach:**
Pull latest changes directly from GitHub using Git commands, then restart the application.

**Advantages:**
- Simplest implementation
- Leverages existing Git infrastructure
- Small download sizes (only changed files)
- Easy rollback capability
- Works with existing development workflow

**Disadvantages:**
- Requires Git to be installed
- Requires Python environment setup
- Users can accidentally modify source files
- Less professional for end users

**Implementation:**
```python
import subprocess
import sys
import os
from PyQt6.QtWidgets import QMessageBox

def check_for_updates(branch='main'):
    """Check if updates are available for the selected branch."""
    try:
        # Fetch latest changes
        subprocess.run(['git', 'fetch', 'origin'], check=True, capture_output=True)

        # Check if local branch is behind remote
        result = subprocess.run(
            ['git', 'rev-list', '--count', f'HEAD..origin/{branch}'],
            capture_output=True, text=True, check=True
        )

        commits_behind = int(result.stdout.strip())
        return commits_behind > 0, commits_behind

    except Exception as e:
        return False, 0, str(e)

def download_and_install_update(branch='main'):
    """Download and install update from the selected branch."""
    try:
        # Stash any local changes
        subprocess.run(['git', 'stash'], check=True)

        # Checkout the desired branch
        subprocess.run(['git', 'checkout', branch], check=True)

        # Pull latest changes
        subprocess.run(['git', 'pull', 'origin', branch], check=True)

        # Update dependencies
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt', '--upgrade'], check=True)

        return True, None

    except Exception as e:
        return False, str(e)

def restart_application():
    """Restart the application."""
    os.execv(sys.executable, [sys.executable] + sys.argv)
```

### Option 2: PyInstaller + Custom Updater (Recommended for Production)

**Best for:** End users who want a simple executable without Python installation

**Approach:**
Package application as executable, download new version as ZIP, extract and replace files, then restart.

**Advantages:**
- Professional user experience
- No Python/Git required
- Clean, atomic updates
- Can include update verification
- Works for non-technical users

**Disadvantages:**
- More complex implementation
- Larger download sizes (full application)
- Requires build process for each update
- Platform-specific executables needed

**Implementation Overview:**
1. Package app with PyInstaller
2. Host releases on GitHub Releases
3. Download new version ZIP
4. Extract to temporary location
5. Replace old files with new files
6. Restart application

**Dependencies:**
```
PyInstaller>=5.0
requests>=2.28.0
packaging>=21.0
```

### Option 3: Hybrid Approach (Recommended)

**Best approach:** Detect environment and use appropriate method

**Implementation:**
- Check if running from Git repository → Use Git-based updates
- Check if running as executable → Use download-and-replace method
- Allow users to select update channel in Settings

## Detailed Implementation Plan

### Phase 1: Settings UI Enhancement

**Location:** `ui/settings_tab.py`

Add to Settings tab:
```python
# Update Settings Group
update_group = QGroupBox("Application Updates")
update_layout = QVBoxLayout()

# Branch selection
branch_layout = QHBoxLayout()
branch_label = QLabel("Update Channel:")
self.branch_combo = QComboBox()
self.branch_combo.addItems(['main (Stable)', 'Development (Latest Features)'])
branch_layout.addWidget(branch_label)
branch_layout.addWidget(self.branch_combo)
update_layout.addLayout(branch_layout)

# Auto-check option
self.auto_check_updates = QCheckBox("Automatically check for updates on startup")
update_layout.addWidget(self.auto_check_updates)

# Manual check button
self.check_updates_btn = QPushButton("Check for Updates Now")
self.check_updates_btn.clicked.connect(self.check_for_updates)
update_layout.addWidget(self.check_updates_btn)

# Current version display
version_label = QLabel(f"Current Version: {APP_VERSION}")
update_layout.addWidget(version_label)

update_group.setLayout(update_layout)
layout.addWidget(update_group)
```

### Phase 2: Update Manager Module

**Create:** `core/update_manager.py`

```python
"""
Update manager for AstroFileManager.
Handles checking for updates, downloading, and installing updates.
"""

import subprocess
import sys
import os
import tempfile
import shutil
from typing import Tuple, Optional
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QThread
import requests

class UpdateChecker(QThread):
    """Background thread for checking updates."""

    update_available = pyqtSignal(bool, str, int)  # available, version, commits_behind
    error_occurred = pyqtSignal(str)

    def __init__(self, branch='main'):
        super().__init__()
        self.branch = branch

    def run(self):
        """Check for updates in background."""
        try:
            available, commits = self._check_git_updates()
            version = self._get_latest_version()
            self.update_available.emit(available, version, commits)
        except Exception as e:
            self.error_occurred.emit(str(e))

    def _check_git_updates(self) -> Tuple[bool, int]:
        """Check if Git updates are available."""
        subprocess.run(['git', 'fetch', 'origin'],
                      check=True, capture_output=True)

        result = subprocess.run(
            ['git', 'rev-list', '--count', f'HEAD..origin/{self.branch}'],
            capture_output=True, text=True, check=True
        )

        commits_behind = int(result.stdout.strip())
        return commits_behind > 0, commits_behind

    def _get_latest_version(self) -> str:
        """Get the latest version from remote."""
        result = subprocess.run(
            ['git', 'describe', '--tags', '--abbrev=0', f'origin/{self.branch}'],
            capture_output=True, text=True
        )
        return result.stdout.strip() if result.returncode == 0 else 'unknown'


class UpdateInstaller(QThread):
    """Background thread for installing updates."""

    progress = pyqtSignal(str)  # Progress message
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, branch='main'):
        super().__init__()
        self.branch = branch

    def run(self):
        """Install updates in background."""
        try:
            self.progress.emit("Stashing local changes...")
            subprocess.run(['git', 'stash'], check=True, capture_output=True)

            self.progress.emit(f"Switching to {self.branch} branch...")
            subprocess.run(['git', 'checkout', self.branch],
                          check=True, capture_output=True)

            self.progress.emit("Downloading updates...")
            subprocess.run(['git', 'pull', 'origin', self.branch],
                          check=True, capture_output=True)

            self.progress.emit("Updating dependencies...")
            subprocess.run([sys.executable, '-m', 'pip', 'install',
                          '-r', 'requirements.txt', '--upgrade'],
                          check=True, capture_output=True)

            self.finished.emit(True, "Update completed successfully!")

        except subprocess.CalledProcessError as e:
            self.finished.emit(False, f"Update failed: {e.stderr.decode()}")
        except Exception as e:
            self.finished.emit(False, f"Update failed: {str(e)}")


class UpdateManager(QObject):
    """Main update manager coordinating the update process."""

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.checker = None
        self.installer = None

    def check_for_updates(self, branch='main'):
        """Start checking for updates."""
        if self.checker and self.checker.isRunning():
            return

        self.checker = UpdateChecker(branch)
        return self.checker

    def install_update(self, branch='main'):
        """Start installing update."""
        if self.installer and self.installer.isRunning():
            return

        self.installer = UpdateInstaller(branch)
        return self.installer

    @staticmethod
    def restart_application():
        """Restart the application."""
        # Save any settings
        # Close database connections
        # Restart
        os.execv(sys.executable, [sys.executable] + sys.argv)

    @staticmethod
    def is_git_repository() -> bool:
        """Check if running from a Git repository."""
        return os.path.exists('.git') and shutil.which('git') is not None
```

### Phase 3: Update Dialog UI

**Create:** `ui/update_dialog.py`

```python
"""
Update dialog for AstroFileManager.
Shows update information and progress.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QTextEdit
)
from PyQt6.QtCore import Qt


class UpdateDialog(QDialog):
    """Dialog for displaying update information and progress."""

    def __init__(self, parent=None, commits_behind=0, version='unknown'):
        super().__init__(parent)
        self.setWindowTitle("Update Available")
        self.setModal(True)
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)

        # Update info
        info_label = QLabel(
            f"<b>A new version is available!</b><br><br>"
            f"Current version is {commits_behind} commits behind<br>"
            f"Latest version: {version}"
        )
        layout.addWidget(info_label)

        # Progress bar (hidden initially)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Progress text
        self.progress_text = QTextEdit()
        self.progress_text.setReadOnly(True)
        self.progress_text.setMaximumHeight(100)
        self.progress_text.setVisible(False)
        layout.addWidget(self.progress_text)

        # Buttons
        button_layout = QHBoxLayout()
        self.update_btn = QPushButton("Download and Install")
        self.cancel_btn = QPushButton("Later")

        button_layout.addStretch()
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.update_btn)

        layout.addLayout(button_layout)

    def show_progress(self, visible=True):
        """Show or hide progress indicators."""
        self.progress_bar.setVisible(visible)
        self.progress_text.setVisible(visible)
        self.update_btn.setEnabled(not visible)

    def add_progress_message(self, message):
        """Add a progress message."""
        self.progress_text.append(message)
```

### Phase 4: Integration into Main Application

**Modify:** `AstroFileManager.py`

```python
# Add to imports
from core.update_manager import UpdateManager
from ui.update_dialog import UpdateDialog

# Add version constant
APP_VERSION = "1.0.0"  # Or read from version file

class XISFCatalogGUI(QMainWindow):
    def __init__(self):
        # ... existing code ...

        # Initialize update manager
        self.update_manager = UpdateManager(self.settings)

        # Check for updates on startup if enabled
        if self.settings.value('auto_check_updates', False):
            self.check_for_updates_silent()

    def check_for_updates_silent(self):
        """Check for updates without showing UI if none available."""
        branch = self.get_selected_branch()

        checker = self.update_manager.check_for_updates(branch)
        checker.update_available.connect(self.on_update_check_complete)
        checker.error_occurred.connect(self.on_update_check_error)
        checker.start()

    def check_for_updates_manual(self):
        """Manual update check triggered by user."""
        branch = self.get_selected_branch()

        checker = self.update_manager.check_for_updates(branch)
        checker.update_available.connect(self.on_manual_update_check)
        checker.error_occurred.connect(self.on_update_check_error)
        checker.start()

    def on_update_check_complete(self, available, version, commits):
        """Handle update check completion."""
        if available:
            self.show_update_dialog(version, commits)

    def on_manual_update_check(self, available, version, commits):
        """Handle manual update check."""
        if available:
            self.show_update_dialog(version, commits)
        else:
            QMessageBox.information(
                self, "No Updates",
                "You are running the latest version!"
            )

    def show_update_dialog(self, version, commits):
        """Show update dialog."""
        dialog = UpdateDialog(self, commits, version)

        dialog.update_btn.clicked.connect(
            lambda: self.start_update(dialog)
        )
        dialog.cancel_btn.clicked.connect(dialog.reject)

        dialog.exec()

    def start_update(self, dialog):
        """Start the update process."""
        branch = self.get_selected_branch()

        dialog.show_progress(True)

        installer = self.update_manager.install_update(branch)
        installer.progress.connect(dialog.add_progress_message)
        installer.finished.connect(
            lambda success, msg: self.on_update_complete(success, msg, dialog)
        )
        installer.start()

    def on_update_complete(self, success, message, dialog):
        """Handle update completion."""
        dialog.show_progress(False)

        if success:
            reply = QMessageBox.question(
                self, "Update Complete",
                f"{message}\n\nRestart application now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.update_manager.restart_application()
            else:
                dialog.accept()
        else:
            QMessageBox.critical(self, "Update Failed", message)

    def get_selected_branch(self):
        """Get selected update branch from settings."""
        branch_text = self.settings.value('update_branch', 'main (Stable)')
        return 'main' if 'main' in branch_text else 'Development'

    def on_update_check_error(self, error):
        """Handle update check error."""
        QMessageBox.warning(
            self, "Update Check Failed",
            f"Could not check for updates:\n{error}"
        )
```

## Security Considerations

1. **Verify Git Repository**
   - Ensure updates are pulled from the official repository
   - Validate remote URL before pulling

2. **Backup Before Update**
   - Create backup of database before update
   - Option to rollback if update fails

3. **Dependency Validation**
   - Verify requirements.txt hasn't been tampered with
   - Use hash verification for critical dependencies

4. **User Permissions**
   - Ensure user has write permissions to application directory
   - Handle permission errors gracefully

## User Experience Flow

### First-Time Setup
1. User opens Settings tab
2. Selects update channel (main or Development)
3. Optionally enables "Auto-check on startup"
4. Clicks "Save Settings"

### Automatic Update Check (on Startup)
1. Application starts
2. Background thread checks for updates (non-blocking)
3. If updates available, shows notification badge or dialog
4. User can choose to update now or later

### Manual Update Check
1. User clicks "Check for Updates Now" in Settings
2. Progress spinner shows while checking
3. If available: Shows dialog with version info
4. If not available: Shows "You're up to date!" message

### Update Installation
1. User clicks "Download and Install"
2. Progress dialog shows:
   - "Stashing local changes..."
   - "Switching to [branch] branch..."
   - "Downloading updates..."
   - "Updating dependencies..."
3. On completion: "Restart now?" prompt
4. Application restarts automatically

## Implementation Timeline

**Phase 1: Core Infrastructure** (2-3 days)
- Create `core/update_manager.py`
- Implement Git-based update checking
- Add version tracking

**Phase 2: UI Components** (2-3 days)
- Enhance `ui/settings_tab.py`
- Create `ui/update_dialog.py`
- Add progress indicators

**Phase 3: Integration** (1-2 days)
- Integrate into main application
- Connect signals and slots
- Handle edge cases

**Phase 4: Testing** (2-3 days)
- Test both branches
- Test error scenarios
- Test restart functionality
- Test with/without Git installed

**Phase 5: Documentation** (1 day)
- Update README with update instructions
- Add troubleshooting guide
- Document branch differences

## Alternative Considerations

### Future Enhancements

1. **Delta Updates**
   - Only download changed files
   - Reduce bandwidth usage

2. **Update Scheduling**
   - Schedule updates for specific times
   - Defer updates until user is ready

3. **Rollback Capability**
   - Keep previous version for quick rollback
   - "Restore previous version" option

4. **Release Notes Display**
   - Fetch and display changelog
   - Show what's new in update

5. **Update Notifications**
   - Desktop notifications when updates available
   - Email notifications (optional)

6. **Staged Rollout**
   - Beta testing group
   - Gradual rollout to all users

## Testing Checklist

- [ ] Update check works on both branches
- [ ] Update installation succeeds on both branches
- [ ] Application restarts correctly
- [ ] Dependencies update correctly
- [ ] Database remains intact after update
- [ ] Settings persist after update
- [ ] Error handling for no internet connection
- [ ] Error handling for Git not installed
- [ ] Error handling for permission issues
- [ ] Works on Windows, macOS, Linux
- [ ] Auto-check on startup works correctly
- [ ] Manual check works correctly
- [ ] User can cancel during download
- [ ] Graceful handling of interrupted updates

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Database corruption during update | Backup database before update, validate after |
| Git conflicts from user modifications | Stash changes before update, inform user |
| Network failure during download | Retry logic, resume capability |
| Dependency incompatibility | Test updates before release, version pinning |
| Application won't restart | Provide manual restart instructions |

## Conclusion

The recommended approach is **Option 3: Hybrid Approach** with **Git-based updates** as the primary implementation for the current user base (developers/technical users).

**Key Benefits:**
- Quick to implement (1-2 weeks)
- Leverages existing Git infrastructure
- Simple and reliable
- Easy to test and debug
- Supports both stable and development channels

**Next Steps:**
1. Create version tracking system
2. Implement `core/update_manager.py`
3. Add UI components to Settings tab
4. Integrate into main application
5. Test thoroughly on both branches
6. Deploy and gather user feedback

This solution provides a solid foundation that can be enhanced with more sophisticated update mechanisms (like PyInstaller + auto-updater) as the application matures and the user base expands beyond technical users.
