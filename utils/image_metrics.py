"""
Image quality metrics calculation for AstroFileManager.

This module calculates astrophotography image quality metrics directly from
image pixel data using Astropy and photutils, so metrics no longer have to be
imported from an external tool such as PixInsight's SubFrame Selector.

The metrics calculated for each image are:

* Half Flux Diameter (HFD) - The diameter of a circle that contains half of
  a star's total flux. Smaller values usually indicate sharper focus / better
  seeing.
* Sky Flux Mean - The average background (sky) flux level of the image after
  sigma clipping out the stars.
* Star Roundness - How round the detected stars are on average. Values close
  to 0 indicate round stars; larger absolute values indicate elongated stars
  (for example, from tracking or guiding errors).
* Number of Stars - How many stars were detected in the image.
* SNR Weight - A relative signal-to-noise weight for the image based on the
  brightness of the detected stars compared to the background noise.

All calculations include basic error handling. If a metric cannot be
calculated (for example, photutils is not installed or no stars are found),
the corresponding value is returned as ``None`` so callers can store a NULL
in the database.
"""

from typing import Dict, Optional

# The database columns (and dictionary keys) produced by this module. Keeping
# this list in one place makes it easy for other modules (import worker,
# database migration, UI) to stay in sync with the metrics that are stored.
METRIC_KEYS = [
    "hfd",
    "sky_flux_mean",
    "star_roundness",
    "num_stars",
    "snr_weight",
]


# SQLite column definitions for each metric. Used both when creating a new
# database and when migrating an existing one so the schema stays consistent.
METRIC_COLUMNS = {
    "hfd": "REAL",
    "sky_flux_mean": "REAL",
    "star_roundness": "REAL",
    "num_stars": "INTEGER",
    "snr_weight": "REAL",
}


def ensure_metric_columns(cursor) -> None:
    """
    Ensure the image-metric columns exist on the ``xisf_files`` table.

    This performs a lightweight, idempotent migration: it checks the existing
    columns and adds any missing metric columns with ``ALTER TABLE``. It is
    safe to call on every application start and before any metric write.

    Args:
        cursor: An open sqlite3 cursor. The caller is responsible for
                committing the connection.
    """
    # Find the columns that already exist on the table.
    cursor.execute("PRAGMA table_info(xisf_files)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    # Add any metric column that is not present yet.
    for column_name, column_type in METRIC_COLUMNS.items():
        if column_name not in existing_columns:
            cursor.execute(
                f"ALTER TABLE xisf_files ADD COLUMN {column_name} {column_type}"
            )


def _empty_metrics() -> Dict[str, Optional[float]]:
    """
    Return a metrics dictionary where every value is ``None``.

    This is used as a safe default when metrics cannot be calculated.

    Returns:
        dict: Dictionary with all metric keys set to None.
    """
    return {key: None for key in METRIC_KEYS}


def _calculate_hfd(bg_subtracted_data, sources, max_stars: int = 100) -> Optional[float]:
    """
    Calculate the average Half Flux Diameter (HFD) for the detected stars.

    The HFD of a single star is the diameter of a circle centered on the star
    that contains half of the star's total flux. This implementation uses the
    common flux-weighted definition:

        HFD = 2 * sum(value_i * distance_i) / sum(value_i)

    where ``value_i`` is the background-subtracted pixel value and
    ``distance_i`` is the distance of that pixel from the star centroid. The
    result is averaged over the brightest stars in the image.

    Args:
        bg_subtracted_data: 2D numpy array of image pixel values that has
                            already had the background median subtracted. This
                            is the same array passed to ``DAOStarFinder`` so the
                            detection and HFD measurement stay consistent (no
                            double subtraction and matching centroids).
        sources: Astropy table of detected sources (from DAOStarFinder).
        max_stars: Maximum number of (brightest) stars to use for the average.

    Returns:
        float: The average HFD in pixels, or None if it cannot be calculated.
    """
    import numpy as np

    try:
        # DAOStarFinder centroid column names differ between photutils versions
        # ('xcentroid'/'ycentroid' in older releases, 'x_centroid'/'y_centroid'
        # in newer ones). Detect whichever pair is present.
        x_col = "xcentroid" if "xcentroid" in sources.colnames else "x_centroid"
        y_col = "ycentroid" if "ycentroid" in sources.colnames else "y_centroid"
        if x_col not in sources.colnames or y_col not in sources.colnames:
            return None

        # Use the brightest stars for a stable, representative measurement.
        # DAOStarFinder provides a 'flux' column we can sort on.
        if "flux" in sources.colnames:
            sorted_sources = sources[np.argsort(sources["flux"])[::-1]]
        else:
            sorted_sources = sources

        # Half-size of the square cutout taken around each star, in pixels.
        box_half = 8
        height, width = bg_subtracted_data.shape

        hfd_values = []

        for source in sorted_sources[:max_stars]:
            # Centroid of the star.
            x_center = float(source[x_col])
            y_center = float(source[y_col])

            # Determine cutout boundaries, clamped to the image edges.
            x_min = int(max(0, np.floor(x_center) - box_half))
            x_max = int(min(width, np.floor(x_center) + box_half + 1))
            y_min = int(max(0, np.floor(y_center) - box_half))
            y_max = int(min(height, np.floor(y_center) + box_half + 1))

            # Skip stars too close to the edge to measure reliably.
            if x_max - x_min < 3 or y_max - y_min < 3:
                continue

            # Take an explicit copy of the slice so clipping negatives below
            # does not modify (or raise a warning on) the shared background-
            # subtracted array, which is only a view into the original data.
            cutout = bg_subtracted_data[y_min:y_max, x_min:x_max].astype(float).copy()

            # The background has already been subtracted globally, so here we
            # only clip negatives to zero so noise pixels below the background
            # do not distort the flux-weighting.
            cutout[cutout < 0] = 0

            total_flux = cutout.sum()
            if total_flux <= 0:
                continue

            # Build a grid of distances from each pixel to the star centroid.
            y_indices, x_indices = np.mgrid[y_min:y_max, x_min:x_max]
            distances = np.sqrt(
                (x_indices - x_center) ** 2 + (y_indices - y_center) ** 2
            )

            # Flux-weighted mean radius, times two, is the HFD.
            hfd = 2.0 * (cutout * distances).sum() / total_flux
            if hfd > 0:
                hfd_values.append(hfd)

        if not hfd_values:
            return None

        return float(np.median(hfd_values))

    except Exception:
        # Any unexpected numerical error should not crash the caller.
        return None


def calculate_metrics_from_data(data) -> Dict[str, Optional[float]]:
    """
    Calculate image quality metrics from a 2D image array.

    Args:
        data: A numpy array containing the image pixel data. If the array is
              3D (multi-channel), the first channel is used.

    Returns:
        dict: Dictionary with the calculated metrics. Keys are defined in
              ``METRIC_KEYS``. Any metric that cannot be calculated is None.
    """
    metrics = _empty_metrics()

    # Import heavy scientific libraries lazily so the rest of the application
    # keeps working even if they are not installed. The metrics simply stay
    # None in that case.
    try:
        import numpy as np
        from astropy.stats import sigma_clipped_stats
        from photutils.detection import DAOStarFinder
    except ImportError:
        # photutils (or numpy/astropy) is not available - return empty metrics.
        return metrics

    try:
        if data is None:
            return metrics

        data = np.asarray(data)

        # If the image has multiple channels (e.g. shape (H, W, 3) or (3, H, W)),
        # reduce it to a single 2D plane so the detection routines work.
        if data.ndim == 3:
            # Assume the smallest axis is the channel axis.
            channel_axis = int(np.argmin(data.shape))

            if data.shape[channel_axis] == 3:
                # For a true 3-channel colour image, combine the Red, Green and
                # Blue channels using the standard CIE luminance weights
                # (Y = 0.299*R + 0.587*G + 0.114*B). This preserves star
                # profiles far better than a uniform average, which over-weights
                # the noisier blue channel.
                cie_weights = np.array([0.299, 0.587, 0.114], dtype=float)

                if channel_axis == 0:
                    # Shape is (3, H, W): move the channel axis to the end so we
                    # can apply the weights with a simple dot product.
                    data = np.moveaxis(data, 0, -1)

                # After the (possible) reorientation the channel axis is last,
                # so the dot product collapses it into a single 2D plane.
                data = np.dot(data, cie_weights)
            else:
                # Not a standard 3-channel image (e.g. a stacked mono cube):
                # fall back to a plain average to get a luminance-like plane.
                data = data.mean(axis=channel_axis)

        if data.ndim != 2:
            return metrics

        # Work in floating point for the statistics.
        data = data.astype(float)

        # Estimate the background statistics using sigma clipping, which
        # ignores the bright star pixels. This gives us a robust mean, median
        # and standard deviation of the sky background.
        mean, median, std = sigma_clipped_stats(data, sigma=3.0)

        # Sky Flux Mean is the sigma-clipped mean background level.
        metrics["sky_flux_mean"] = float(mean)

        # Subtract the background once, globally, right after computing the
        # statistics. Using this single background-subtracted array for both
        # detection and the HFD measurement avoids double subtraction and keeps
        # the star centroids consistent between the two steps.
        bg_subtracted_data = data - median

        # Guard against a completely flat image where std is zero, which would
        # make star detection meaningless and could cause divide-by-zero.
        if std <= 0:
            metrics["num_stars"] = 0
            return metrics

        # Detect stars. The FWHM is an initial guess for the typical star size
        # and the threshold is set well above the background noise so we only
        # pick up real stars.
        finder = DAOStarFinder(fwhm=3.0, threshold=5.0 * std)
        sources = finder(bg_subtracted_data)

        if sources is None or len(sources) == 0:
            # No stars found - record a star count of zero and stop here.
            metrics["num_stars"] = 0
            return metrics

        # Number of detected stars.
        metrics["num_stars"] = int(len(sources))

        # Star Roundness: DAOStarFinder reports two roundness statistics per
        # star ('roundness1' and 'roundness2'). We take the MAXIMUM absolute
        # value across all stars and both statistics. Using the maximum (rather
        # than an average) means a single badly elongated star - for example
        # from a wind gust or periodic tracking error along one axis - is not
        # diluted away, giving stricter quality control on tracking.
        roundness_values = []
        for column in ("roundness1", "roundness2"):
            if column in sources.colnames:
                roundness_values.append(np.abs(np.asarray(sources[column], dtype=float)))
        if roundness_values:
            combined_roundness = np.concatenate(roundness_values)
            metrics["star_roundness"] = float(np.max(combined_roundness))

        # SNR Weight: a relative signal-to-noise measure. We take the median
        # peak brightness of the detected stars (above background) and divide
        # by the background noise (standard deviation). This favors images with
        # brighter stars relative to the noise floor.
        if "peak" in sources.colnames:
            peaks = np.asarray(sources["peak"], dtype=float)
            median_peak = float(np.median(peaks))
            metrics["snr_weight"] = float(median_peak / std)

        # Half Flux Diameter, averaged over the brightest stars. We reuse the
        # same background-subtracted array that was used for detection.
        metrics["hfd"] = _calculate_hfd(bg_subtracted_data, sources)

    except Exception:
        # If anything unexpected happens, return whatever we managed to
        # calculate so far (with the rest left as None).
        return metrics

    return metrics


def calculate_image_metrics(filepath) -> Dict[str, Optional[float]]:
    """
    Calculate image quality metrics for a single XISF or FITS file.

    This is the main entry point used by the import worker and the
    "Calculate Image Metrics" context-menu action in the View Catalog tab.

    Args:
        filepath: Path to the image file (XISF or FITS), as a str or Path.

    Returns:
        dict: Dictionary with the calculated metrics. Keys are defined in
              ``METRIC_KEYS``. Any metric that cannot be calculated is None.
    """
    # Imported here to avoid a hard dependency at module import time and to
    # keep this module self-contained.
    from utils.fits_reader import get_image_data

    try:
        data = get_image_data(filepath)
    except Exception:
        # File could not be read - return empty metrics rather than raising,
        # so a single bad file does not abort a whole batch import.
        return _empty_metrics()

    return calculate_metrics_from_data(data)
