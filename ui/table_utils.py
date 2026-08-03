"""Small helpers that keep table/tree column headers aligned with their data.

Qt does not use the same alignment for headers and data by default:

* ``QTableWidget`` (and ``QTableView``) centre their column headers, while the
  text inside the cells is drawn left aligned.
* ``QTreeWidget`` (and ``QTreeView``) already left align their headers.

That mismatch made the tables in AstroFileManager look untidy - the header sat
in the middle of the column while the values underneath hugged the left edge
(issue #296).  The helpers below give every table and tree in the application a
single, consistent rule: **headers are left aligned, exactly like the data.**

Typical use, right after the header labels have been set::

    from ui.table_utils import align_headers_with_data

    self.projects_table = QTableWidget()
    self.projects_table.setHorizontalHeaderLabels(["Project Name", "Object"])
    align_headers_with_data(self.projects_table)
"""

from PyQt6.QtCore import Qt

# Alignment shared by every column header and every data cell: text hugs the
# left edge of the column and is centred vertically within the row.
DATA_ALIGNMENT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter


def align_headers_with_data(view) -> None:
    """Left align the column headers of a table or tree so they match the data.

    The function accepts any Qt item view that exposes a horizontal header,
    which covers ``QTableWidget``/``QTableView`` (via ``horizontalHeader()``)
    and ``QTreeWidget``/``QTreeView`` (via ``header()``).

    Args:
        view: The table or tree widget whose headers should be left aligned.

    Returns:
        None. The view is modified in place; unsupported or missing widgets are
        ignored so callers never have to guard the call.
    """
    try:
        # QTableWidget/QTableView expose horizontalHeader(); QTreeWidget and
        # QTreeView expose header(). Both return a QHeaderView.
        if hasattr(view, "horizontalHeader"):
            header = view.horizontalHeader()
        elif hasattr(view, "header"):
            header = view.header()
        else:
            # Not an item view with a header (nothing to align).
            return

        if header is None:
            return

        # setDefaultAlignment() applies to every section that does not carry an
        # explicit Qt.ItemDataRole.TextAlignmentRole value, which is the case
        # for headers created with setHorizontalHeaderLabels()/setHeaderLabels().
        header.setDefaultAlignment(DATA_ALIGNMENT)

        # Headers can also be built from explicit header items, which carry
        # their own alignment and would therefore override the default set
        # above. Update those items as well so nothing is left centred.
        if hasattr(view, "horizontalHeaderItem"):
            # QTableWidget: one header item per column.
            for column in range(view.columnCount()):
                header_item = view.horizontalHeaderItem(column)
                if header_item is not None:
                    header_item.setTextAlignment(DATA_ALIGNMENT)
        elif hasattr(view, "headerItem"):
            # QTreeWidget: a single header item that holds every column.
            header_item = view.headerItem()
            if header_item is not None:
                for column in range(view.columnCount()):
                    header_item.setTextAlignment(column, DATA_ALIGNMENT)
    except Exception as exc:  # pragma: no cover - defensive, never fatal
        # Alignment is purely cosmetic, so a failure here must never stop the
        # application from showing its data.
        print(f"Warning: could not align column headers: {exc}")


def align_widget_cell(layout) -> None:
    """Left align a widget that is embedded in a table cell.

    Cells that hold a widget (a checkbox, for example) are laid out inside a
    small container.  Centring that container would leave the widget floating
    in the middle of the column while its header sits on the left, so this
    helper pins the widget to the left edge with the same small indent Qt uses
    for ordinary cell text.

    Args:
        layout: The QLayout holding the cell widget.

    Returns:
        None. The layout is modified in place.
    """
    try:
        layout.setAlignment(DATA_ALIGNMENT)
        # A 4px indent matches the padding Qt applies to plain text cells.
        layout.setContentsMargins(4, 0, 0, 0)
    except Exception as exc:  # pragma: no cover - defensive, never fatal
        print(f"Warning: could not align cell widget: {exc}")
