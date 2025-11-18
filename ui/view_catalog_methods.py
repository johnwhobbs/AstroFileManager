# Replacement methods for view_catalog_tab.py to add background threading
# These replace the existing refresh_catalog_view method

def refresh_catalog_view(self) -> None:
    """Refresh the catalog view using background thread."""
    try:
        # Cancel any existing worker
        if self.loader_worker and self.loader_worker.isRunning():
            self.loader_worker.terminate()
            self.loader_worker.wait()

        # Update statistics synchronously (fast operation)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        self.update_catalog_statistics(cursor)
        conn.close()

        # Show progress
        self.catalog_progress_widget.show()
        self.catalog_status_label.setText("Loading catalog...")
        self.catalog_tree.setEnabled(False)

        # Get filter values
        imagetype_filter = self.catalog_imagetype_filter.currentText()
        object_filter = self.catalog_object_filter.currentText()

        # Create and start worker
        self.loader_worker = CatalogLoaderWorker(self.db_path, imagetype_filter, object_filter)
        self.loader_worker.progress_updated.connect(self._on_catalog_progress)
        self.loader_worker.data_ready.connect(self._on_catalog_data_ready)
        self.loader_worker.error_occurred.connect(self._on_catalog_error)
        self.loader_worker.finished.connect(self._on_catalog_finished)
        self.loader_worker.start()

    except Exception as e:
        self.catalog_progress_widget.hide()
        self.catalog_tree.setEnabled(True)
        QMessageBox.critical(self, 'Error', f'Failed to start catalog load: {e}')


def _on_catalog_progress(self, message: str) -> None:
    """Update progress message."""
    self.catalog_status_label.setText(message)


def _on_catalog_error(self, error_msg: str) -> None:
    """Handle worker error."""
    self.catalog_progress_widget.hide()
    self.catalog_tree.setEnabled(True)
    QMessageBox.critical(self, 'Error', error_msg)


def _on_catalog_finished(self) -> None:
    """Hide progress when worker finishes."""
    self.catalog_progress_widget.hide()
    self.catalog_tree.setEnabled(True)


def _on_catalog_data_ready(self, result: dict) -> None:
    """
    Build catalog tree from loaded data (runs on UI thread).

    Args:
        result: Dictionary with 'objects', 'light_data', 'calib_data' keys
    """
    try:
        # Update object filter dropdown
        objects = result.get('objects', [])
        current_object = self.catalog_object_filter.currentText()

        self.catalog_object_filter.blockSignals(True)
        self.catalog_object_filter.clear()
        self.catalog_object_filter.addItem('All')
        self.catalog_object_filter.addItems(objects)

        if current_object in ['All'] + objects:
            self.catalog_object_filter.setCurrentText(current_object)

        self.catalog_object_filter.blockSignals(False)

        # Clear and build tree
        self.catalog_tree.setUpdatesEnabled(False)
        self.catalog_tree.clear()

        # Build light frames tree from data
        light_data = result.get('light_data', [])
        if light_data:
            self._build_light_frames_from_data(light_data)

        # Build calibration frames tree from data
        calib_data = result.get('calib_data', {})
        if calib_data:
            self._build_calibration_frames_from_data(calib_data)

        self.catalog_tree.setUpdatesEnabled(True)

    except Exception as e:
        QMessageBox.critical(self, 'Error', f'Failed to build tree: {e}')


def _build_light_frames_from_data(self, light_data: list) -> None:
    """Build light frames tree from pre-loaded data."""
    if not light_data:
        return

    # Calculate totals
    total_count = len(light_data)
    total_exp = sum(row[5] or 0 for row in light_data) / 3600.0  # exposure is column 5

    light_frames_root = QTreeWidgetItem(self.catalog_tree)
    light_frames_root.setText(0, f"Light Frames ({total_count} files, {total_exp:.1f}h)")
    light_frames_root.setFlags(light_frames_root.flags() | Qt.ItemFlag.ItemIsAutoTristate)
    font = light_frames_root.font(0)
    font.setBold(True)
    light_frames_root.setFont(0, font)

    # Build tree with state tracking (same algorithm as optimized version)
    current_obj = None
    current_filter = None
    current_date = None
    obj_item = None
    filter_item = None
    date_item = None

    # Track aggregations
    obj_files = {}
    filter_files = {}
    date_files = {}

    # First pass: aggregate counts
    for row in light_data:
        obj, filt, date_loc, filename, imagetyp, exposure, temp, xbin, ybin, telescop, instrume = row

        if obj not in obj_files:
            obj_files[obj] = {'count': 0, 'exposure': 0}
        obj_files[obj]['count'] += 1
        obj_files[obj]['exposure'] += (exposure or 0)

        key_filter = (obj, filt)
        if key_filter not in filter_files:
            filter_files[key_filter] = {'count': 0, 'exposure': 0}
        filter_files[key_filter]['count'] += 1
        filter_files[key_filter]['exposure'] += (exposure or 0)

        key_date = (obj, filt, date_loc)
        if key_date not in date_files:
            date_files[key_date] = {'count': 0, 'exposure': 0}
        date_files[key_date]['count'] += 1
        date_files[key_date]['exposure'] += (exposure or 0)

    # Second pass: build tree
    for row in light_data:
        obj, filt, date_loc, filename, imagetyp, exposure, temp, xbin, ybin, telescop, instrume = row

        # Create object node if new
        if obj != current_obj:
            obj_stats = obj_files[obj]
            obj_exp_hrs = obj_stats['exposure'] / 3600.0
            obj_item = QTreeWidgetItem(light_frames_root)
            obj_item.setText(0, f"{obj or 'Unknown'} ({obj_stats['count']} files, {obj_exp_hrs:.1f}h)")
            obj_item.setFlags(obj_item.flags() | Qt.ItemFlag.ItemIsAutoTristate)
            current_obj = obj
            current_filter = None
            current_date = None

        # Create filter node if new
        if filt != current_filter:
            filter_stats = filter_files[(obj, filt)]
            filter_exp_hrs = filter_stats['exposure'] / 3600.0
            filter_item = QTreeWidgetItem(obj_item)
            filter_item.setText(0, f"{filt or 'No Filter'} ({filter_stats['count']} files, {filter_exp_hrs:.1f}h)")
            filter_item.setText(2, filt or 'No Filter')
            current_filter = filt
            current_date = None

        # Create date node if new
        if date_loc != current_date:
            date_stats = date_files[(obj, filt, date_loc)]
            date_exp_hrs = date_stats['exposure'] / 3600.0
            date_item = QTreeWidgetItem(filter_item)
            date_item.setText(0, f"{date_loc or 'No Date'} ({date_stats['count']} files, {date_exp_hrs:.1f}h)")
            date_item.setText(6, date_loc or 'No Date')
            current_date = date_loc

        # Add file node
        file_item = QTreeWidgetItem(date_item)
        file_item.setText(0, filename)
        file_item.setText(1, imagetyp or 'N/A')
        file_item.setText(2, filt or 'N/A')
        file_item.setText(3, f"{exposure:.1f}s" if exposure else 'N/A')
        file_item.setText(4, f"{temp:.1f}°C" if temp is not None else 'N/A')
        binning = f"{int(xbin)}x{int(ybin)}" if xbin and ybin else 'N/A'
        file_item.setText(5, binning)
        file_item.setText(6, date_loc or 'N/A')
        file_item.setText(7, telescop or 'N/A')
        file_item.setText(8, instrume or 'N/A')

        # Apply color coding
        color = self.get_item_color(imagetyp)
        if color:
            for col in range(9):
                file_item.setBackground(col, QBrush(color))


def _build_calibration_frames_from_data(self, calib_data: dict) -> None:
    """Build calibration frames tree from pre-loaded data."""
    darks = calib_data.get('darks', [])
    flats = calib_data.get('flats', [])
    bias = calib_data.get('bias', [])

    total_count = len(darks) + len(flats) + len(bias)
    if total_count == 0:
        return

    calib_root = QTreeWidgetItem(self.catalog_tree)
    calib_root.setText(0, f"Calibration Frames ({total_count} files)")
    calib_root.setFlags(calib_root.flags() | Qt.ItemFlag.ItemIsAutoTristate)
    font = calib_root.font(0)
    font.setBold(True)
    calib_root.setFont(0, font)

    # Build darks
    if darks:
        self._build_darks_from_data(calib_root, darks)

    # Build flats
    if flats:
        self._build_flats_from_data(calib_root, flats)

    # Build bias
    if bias:
        self._build_bias_from_data(calib_root, bias)


def _build_darks_from_data(self, calib_root, darks_data: list) -> None:
    """Build darks tree from pre-loaded data."""
    dark_root = QTreeWidgetItem(calib_root)
    dark_root.setText(0, f"Dark Frames ({len(darks_data)} files)")
    dark_root.setFlags(dark_root.flags() | Qt.ItemFlag.ItemIsAutoTristate)

    current_group = None
    current_date = None
    group_item = None
    date_item = None

    for row in darks_data:
        exp, temp, xbin, ybin, date_loc, filename, imagetyp, telescop, instrume, actual_temp = row

        # Create group node if new
        group_key = (exp, temp, xbin, ybin)
        if group_key != current_group:
            exp_str = f"{int(exp)}s" if exp else "0s"
            temp_str = f"{int(temp)}C" if temp is not None else "0C"
            binning = f"Bin{int(xbin)}x{int(ybin)}" if xbin and ybin else "Bin1x1"

            group_item = QTreeWidgetItem(dark_root)
            group_item.setText(0, f"{exp_str}_{temp_str}_{binning}")
            group_item.setText(3, exp_str)
            group_item.setText(4, temp_str)
            group_item.setText(5, binning)

            current_group = group_key
            current_date = None

        # Create date node if new
        if date_loc != current_date:
            date_item = QTreeWidgetItem(group_item)
            date_item.setText(0, date_loc or 'No Date')
            current_date = date_loc

        # Add file node
        file_item = QTreeWidgetItem(date_item)
        file_item.setText(0, filename)
        file_item.setText(1, imagetyp or 'N/A')
        file_item.setText(3, f"{exp:.1f}s" if exp else 'N/A')
        file_item.setText(4, f"{actual_temp:.1f}°C" if actual_temp is not None else 'N/A')
        binning_str = f"{int(xbin)}x{int(ybin)}" if xbin and ybin else 'N/A'
        file_item.setText(5, binning_str)
        file_item.setText(6, date_loc or 'N/A')
        file_item.setText(7, telescop or 'N/A')
        file_item.setText(8, instrume or 'N/A')

        color = self.get_item_color(imagetyp)
        if color:
            for col in range(9):
                file_item.setBackground(col, QBrush(color))


def _build_flats_from_data(self, calib_root, flats_data: list) -> None:
    """Build flats tree from pre-loaded data."""
    flat_root = QTreeWidgetItem(calib_root)
    flat_root.setText(0, f"Flat Frames ({len(flats_data)} files)")
    flat_root.setFlags(flat_root.flags() | Qt.ItemFlag.ItemIsAutoTristate)

    current_date = None
    current_group = None
    date_item = None
    group_item = None

    for row in flats_data:
        date_loc, filt, temp, xbin, ybin, filename, imagetyp, exposure, telescop, instrume, actual_temp = row

        # Create date node if new
        if date_loc != current_date:
            date_item = QTreeWidgetItem(flat_root)
            date_item.setText(0, date_loc or 'No Date')
            current_date = date_loc
            current_group = None

        # Create group node if new
        group_key = (filt, temp, xbin, ybin)
        if group_key != current_group:
            filt_str = filt or "NoFilter"
            temp_str = f"{int(temp)}C" if temp is not None else "0C"
            binning = f"Bin{int(xbin)}x{int(ybin)}" if xbin and ybin else "Bin1x1"

            group_item = QTreeWidgetItem(date_item)
            group_item.setText(0, f"{filt_str}_{temp_str}_{binning}")
            group_item.setText(2, filt_str)
            group_item.setText(4, temp_str)
            group_item.setText(5, binning)

            current_group = group_key

        # Add file node
        file_item = QTreeWidgetItem(group_item)
        file_item.setText(0, filename)
        file_item.setText(1, imagetyp or 'N/A')
        file_item.setText(2, filt or 'N/A')
        file_item.setText(3, f"{exposure:.1f}s" if exposure else 'N/A')
        file_item.setText(4, f"{actual_temp:.1f}°C" if actual_temp is not None else 'N/A')
        binning_str = f"{int(xbin)}x{int(ybin)}" if xbin and ybin else 'N/A'
        file_item.setText(5, binning_str)
        file_item.setText(6, date_loc or 'N/A')
        file_item.setText(7, telescop or 'N/A')
        file_item.setText(8, instrume or 'N/A')

        color = self.get_item_color(imagetyp)
        if color:
            for col in range(9):
                file_item.setBackground(col, QBrush(color))


def _build_bias_from_data(self, calib_root, bias_data: list) -> None:
    """Build bias tree from pre-loaded data."""
    bias_root = QTreeWidgetItem(calib_root)
    bias_root.setText(0, f"Bias Frames ({len(bias_data)} files)")
    bias_root.setFlags(bias_root.setFlags() | Qt.ItemFlag.ItemIsAutoTristate)

    current_group = None
    current_date = None
    group_item = None
    date_item = None

    for row in bias_data:
        temp, xbin, ybin, date_loc, filename, imagetyp, exposure, telescop, instrume, actual_temp, filt = row

        # Create group node if new
        group_key = (temp, xbin, ybin)
        if group_key != current_group:
            temp_str = f"{int(temp)}C" if temp is not None else "0C"
            binning = f"Bin{int(xbin)}x{int(ybin)}" if xbin and ybin else "Bin1x1"

            group_item = QTreeWidgetItem(bias_root)
            group_item.setText(0, f"{temp_str}_{binning}")
            group_item.setText(4, temp_str)
            group_item.setText(5, binning)

            current_group = group_key
            current_date = None

        # Create date node if new
        if date_loc != current_date:
            date_item = QTreeWidgetItem(group_item)
            date_item.setText(0, date_loc or 'No Date')
            current_date = date_loc

        # Add file node
        file_item = QTreeWidgetItem(date_item)
        file_item.setText(0, filename)
        file_item.setText(1, imagetyp or 'N/A')
        file_item.setText(2, filt or 'N/A')
        file_item.setText(3, f"{exposure:.1f}s" if exposure else 'N/A')
        file_item.setText(4, f"{actual_temp:.1f}°C" if actual_temp is not None else 'N/A')
        binning_str = f"{int(xbin)}x{int(ybin)}" if xbin and ybin else 'N/A'
        file_item.setText(5, binning_str)
        file_item.setText(6, date_loc or 'N/A')
        file_item.setText(7, telescop or 'N/A')
        file_item.setText(8, instrume or 'N/A')

        color = self.get_item_color(imagetyp)
        if color:
            for col in range(9):
                file_item.setBackground(col, QBrush(color))
