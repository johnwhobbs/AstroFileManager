"""
Update Manager for AstroFileManager.

Handles checking for updates from GitHub and downloading/applying them.
"""

import os
import sys
import shutil
import tempfile
import zipfile
from typing import Optional, Dict, Any, Callable
from pathlib import Path
import urllib.request
import urllib.error
import json
from constants import __VERSION__


class UpdateManager:
    """
    Manages application updates from GitHub repository.

    Provides functionality to check for new versions, download updates,
    and prepare the application for restart with the new version.
    """

    GITHUB_REPO = "johnwhobbs/AstroFileManager"
    GITHUB_API_BASE = "https://api.github.com/repos"

    def __init__(self, preferred_branch: str = "main"):
        """
        Initialize the UpdateManager.

        Args:
            preferred_branch: The branch to check for updates (main or development)
        """
        self.preferred_branch = preferred_branch
        self.current_version = __VERSION__
        self.app_dir = Path(__file__).parent.parent.resolve()
        # File to store the current commit SHA
        self.commit_sha_file = self.app_dir / '.update_commit_sha'

    def _get_current_commit_sha(self) -> Optional[str]:
        """
        Get the currently installed commit SHA.

        Returns:
            The commit SHA string, or None if not available
        """
        try:
            if self.commit_sha_file.exists():
                with open(self.commit_sha_file, 'r') as f:
                    sha = f.read().strip()
                    return sha if sha else None
        except Exception:
            pass
        return None

    def _save_commit_sha(self, commit_sha: str) -> bool:
        """
        Save the commit SHA of the currently installed version.

        Args:
            commit_sha: The commit SHA to save

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            with open(self.commit_sha_file, 'w') as f:
                f.write(commit_sha)
            return True
        except Exception as e:
            print(f"Error saving commit SHA: {e}")
            return False

    def check_for_updates(self, progress_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        """
        Check if updates are available on GitHub.

        Args:
            progress_callback: Optional callback function to report progress

        Returns:
            Dictionary with update information:
            {
                'update_available': bool,
                'latest_version': str,
                'current_version': str,
                'branch': str,
                'commit_sha': str,
                'commit_message': str,
                'commit_date': str,
                'error': str (if error occurred)
            }
        """
        if progress_callback:
            progress_callback("Checking for updates...")

        try:
            # Get the latest commit info from the preferred branch
            url = f"{self.GITHUB_API_BASE}/{self.GITHUB_REPO}/branches/{self.preferred_branch}"

            # Create request with User-Agent header (GitHub API requires it)
            req = urllib.request.Request(url)
            req.add_header('User-Agent', f'AstroFileManager/{self.current_version}')

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))

            commit_info = data['commit']
            commit_sha = commit_info['sha']
            commit_message = commit_info['commit']['message']
            commit_date = commit_info['commit']['author']['date']

            # Get the currently installed commit SHA
            current_commit_sha = self._get_current_commit_sha()

            # Determine if an update is available by comparing commit SHAs
            # Update is available if:
            # 1. We don't have a stored commit SHA (first time checking), OR
            # 2. The latest commit SHA is different from our stored SHA
            if current_commit_sha is None:
                # No stored SHA, assume update is available for the first check
                update_available = True
            else:
                # Compare the full commit SHAs
                update_available = (commit_sha != current_commit_sha)

            result = {
                'update_available': update_available,
                'latest_version': commit_sha[:7],  # Short SHA
                'current_version': self.current_version,
                'current_commit_sha': current_commit_sha[:7] if current_commit_sha else 'Unknown',
                'branch': self.preferred_branch,
                'commit_sha': commit_sha,
                'commit_message': commit_message.split('\n')[0],  # First line only
                'commit_date': commit_date,
                'error': None
            }

            if progress_callback:
                progress_callback("Update check complete")

            return result

        except urllib.error.URLError as e:
            error_msg = f"Network error: {str(e)}"
            if progress_callback:
                progress_callback(f"Error: {error_msg}")
            return {
                'update_available': False,
                'error': error_msg
            }
        except Exception as e:
            error_msg = f"Error checking for updates: {str(e)}"
            if progress_callback:
                progress_callback(f"Error: {error_msg}")
            return {
                'update_available': False,
                'error': error_msg
            }

    def download_update(self,
                       progress_callback: Optional[Callable[[str], None]] = None,
                       percent_callback: Optional[Callable[[int], None]] = None) -> Optional[Path]:
        """
        Download the latest version from GitHub.

        Args:
            progress_callback: Optional callback for status messages
            percent_callback: Optional callback for download percentage (0-100)

        Returns:
            Path to the downloaded zip file, or None if download failed
        """
        try:
            # Download the repository as a zip file
            zip_url = f"https://github.com/{self.GITHUB_REPO}/archive/refs/heads/{self.preferred_branch}.zip"

            if progress_callback:
                progress_callback(f"Downloading from {self.preferred_branch} branch...")

            # Create a temporary file for the download
            temp_dir = Path(tempfile.gettempdir())
            zip_path = temp_dir / f"AstroFileManager_update_{self.preferred_branch}.zip"

            # Download with progress reporting
            def report_progress(block_num, block_size, total_size):
                if percent_callback and total_size > 0:
                    downloaded = block_num * block_size
                    percent = min(int((downloaded / total_size) * 100), 100)
                    percent_callback(percent)

            urllib.request.urlretrieve(zip_url, zip_path, reporthook=report_progress)

            if progress_callback:
                progress_callback("Download complete")

            return zip_path

        except Exception as e:
            error_msg = f"Error downloading update: {str(e)}"
            if progress_callback:
                progress_callback(f"Error: {error_msg}")
            return None

    def apply_update(self,
                    zip_path: Path,
                    commit_sha: Optional[str] = None,
                    progress_callback: Optional[Callable[[str], None]] = None) -> bool:
        """
        Apply the downloaded update by extracting files.

        Args:
            zip_path: Path to the downloaded zip file
            commit_sha: Optional commit SHA to save after successful update
            progress_callback: Optional callback for status messages

        Returns:
            True if update was applied successfully, False otherwise
        """
        try:
            if progress_callback:
                progress_callback("Preparing to apply update...")

            # Create a backup directory
            backup_dir = self.app_dir.parent / f"AstroFileManager_backup_{self.current_version}"

            # Extract to a temporary location first
            temp_extract_dir = Path(tempfile.gettempdir()) / "AstroFileManager_update_extract"
            if temp_extract_dir.exists():
                shutil.rmtree(temp_extract_dir)
            temp_extract_dir.mkdir(parents=True)

            if progress_callback:
                progress_callback("Extracting update files...")

            # Extract the zip file
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract_dir)

            # The extracted folder will be named AstroFileManager-<branch>
            extracted_folder = temp_extract_dir / f"AstroFileManager-{self.preferred_branch}"

            if not extracted_folder.exists():
                # Try without the branch suffix
                extracted_folder = temp_extract_dir / "AstroFileManager"
                if not extracted_folder.exists():
                    raise Exception("Could not find extracted folder")

            if progress_callback:
                progress_callback("Creating backup of current version...")

            # Create backup of current installation (optional but recommended)
            if not backup_dir.exists():
                shutil.copytree(self.app_dir, backup_dir,
                              ignore=shutil.ignore_patterns('*.pyc', '__pycache__', '*.db', '*.db-journal'))

            if progress_callback:
                progress_callback("Applying update files...")

            # Copy new files over existing ones
            # Preserve certain files/directories that shouldn't be overwritten
            preserve_patterns = ['*.db', '*.db-journal', '__pycache__', '*.pyc']

            for item in extracted_folder.rglob('*'):
                if item.is_file():
                    relative_path = item.relative_to(extracted_folder)
                    dest_path = self.app_dir / relative_path

                    # Skip files we want to preserve
                    skip = False
                    for pattern in preserve_patterns:
                        if item.match(pattern):
                            skip = True
                            break

                    if skip:
                        continue

                    # Create parent directory if it doesn't exist
                    dest_path.parent.mkdir(parents=True, exist_ok=True)

                    # Copy the file
                    shutil.copy2(item, dest_path)

            if progress_callback:
                progress_callback("Update applied successfully")

            # Save the commit SHA if provided so we can track what version we're on
            if commit_sha:
                self._save_commit_sha(commit_sha)
                if progress_callback:
                    progress_callback(f"Saved commit SHA: {commit_sha[:7]}")

            # Clean up
            shutil.rmtree(temp_extract_dir, ignore_errors=True)

            return True

        except Exception as e:
            error_msg = f"Error applying update: {str(e)}"
            if progress_callback:
                progress_callback(f"Error: {error_msg}")
            return False

    def prepare_restart(self) -> Dict[str, Any]:
        """
        Prepare information needed to restart the application.

        Returns:
            Dictionary with restart information:
            {
                'executable': str (path to Python executable),
                'script': str (path to main script),
                'working_dir': str (current working directory)
            }
        """
        return {
            'executable': sys.executable,
            'script': str(self.app_dir / 'AstroFileManager.py'),
            'working_dir': str(self.app_dir)
        }

    @staticmethod
    def restart_application():
        """
        Restart the application.

        This will close the current instance and start a new one.
        """
        try:
            # Get the Python executable and script path
            python = sys.executable
            script = sys.argv[0]

            # Start a new instance
            if sys.platform == 'win32':
                os.startfile(script)
            else:
                os.execv(python, [python] + sys.argv)

        except Exception as e:
            print(f"Error restarting application: {e}")
            sys.exit(1)
