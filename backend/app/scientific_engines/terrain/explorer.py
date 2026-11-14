"""Bounded, co-registered terrain grids for the Site04 browser explorer."""
from contextlib import ExitStack
from pathlib import Path

import numpy as np
import rasterio
from rasterio.errors import RasterioIOError
from rasterio.transform import Affine
from rasterio.windows import Window

ROOT = Path(__file__).resolve().parents[4] / "data"
SITE = "Site04"
LAYERS = {
    "slope": ("processed", "calculated_slope_deg", "deg"),
    "aspect": ("processed", "calculated_aspect_deg", "deg"),
    "roughness": ("processed", "roughness_15m", "m"),
    "coverage": ("raw", "final_adj_5mpp_ldec", "returns"),
    "uncertainty": ("raw", "final_adj_5mpp_slperr", "deg RMS"),
    "elevation_uncertainty": ("raw", "final_adj_5mpp_toterr", "m RMS"),
    "hazards": ("processed", "combined_hazard_screen", "class"),
}


def _path(root: Path, stage: str, product: str) -> Path:
    return root / stage / "terrain" / SITE.lower() / f"{SITE}_{product}.tif"


def _band(dataset, window=None):
    band = dataset.read(1, window=window, masked=True)
    return band.data, ~np.ma.getmaskarray(band) & np.isfinite(band.data)


def _encode(values, valid, unit):
    selected = values[valid]
    return {
        "values": np.where(valid, values, None).ravel().tolist(),
        "unit": unit,
        "range": [float(selected.min()), float(selected.max())] if selected.size else None,
    }


def _quad_validity(valid, rows, cols):
    window = valid[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
    # Each native quad covers its four vertices, including the right and bottom
    # boundaries of a display quad. Reduce native quads into display blocks.
    holes = ~(window[:-1, :-1] & window[1:, :-1] & window[:-1, 1:] & window[1:, 1:])
    row_blocks = np.logical_or.reduceat(holes, rows[:-1] - rows[0], axis=0)
    return ~np.logical_or.reduceat(row_blocks, cols[:-1] - cols[0], axis=1)


def load_explorer_grid(max_dimension: int, root: Path = ROOT, *, centre=None) -> dict:
    """Sample exact source pixel centres on a regular, decimated affine grid."""
    if not 2 <= max_dimension <= 384:
        raise ValueError("Grid limit must be between 2 and 384.")
    with ExitStack() as stack:
        source = stack.enter_context(rasterio.open(_path(root, "processed", "processed_elevation")))
        if source.crs is None:
            raise ValueError("The processed elevation grid has no CRS.")
        source_shape = source.shape
        window = None
        if centre is not None:
            row, col = source.index(*centre)
            if not (0 <= row < source.height and 0 <= col < source.width):
                raise ValueError("The inspection point is outside Site04.")
            width, height = min(source.width, max_dimension), min(source.height, max_dimension)
            window = Window(min(max(0, col - width // 2), source.width - width),
                            min(max(0, row - height // 2), source.height - height), width, height)
        shape = source_shape if window is None else (int(window.height), int(window.width))
        stride = max(1, (max(shape) + max_dimension - 1) // max_dimension)
        offset = (stride - 1) // 2
        rows = np.arange(offset, shape[0], stride)
        cols = np.arange(offset, shape[1], stride)
        if rows.size < 2 or cols.size < 2:
            raise ValueError("The display grid requires at least two samples on each axis.")
        samples = np.ix_(rows, cols)
        # Affines map pixel corners. Shift the output centres onto the exact sampled source centres.
        shift = offset + 0.5 - stride / 2
        transform = source.transform if window is None else source.window_transform(window)
        output_transform = transform @ Affine.translation(shift, shift) @ Affine.scale(stride)
        elevation, valid = _band(source, window)
        quad_valid = _quad_validity(valid, rows, cols)

        layers = {}
        unavailable = {}
        for name, (stage, product, unit) in LAYERS.items():
            path = _path(root, stage, product)
            if not path.is_file():
                unavailable[name] = "Raster is unavailable."
                continue
            try:
                with rasterio.open(path) as dataset:
                    if (dataset.shape, dataset.transform, dataset.crs) != (source_shape, source.transform, source.crs):
                        unavailable[name] = "Raster grid differs from the elevation grid."
                        continue
                    values, layer_valid = _band(dataset, window)
            except RasterioIOError:
                unavailable[name] = "Raster could not be read."
                continue
            layers[name] = _encode(values[samples], layer_valid[samples] & valid[samples], unit)

        return {
            "site_id": SITE,
            "site_name": "Shackleton Rim",
            "source": "NASA GSFC PGDA · LOLA",
            "source_file": Path(source.name).name,
            "source_url": "https://pgda.gsfc.nasa.gov/products/78",
            "width": int(cols.size),
            "height": int(rows.size),
            "source_width": source.width,
            "source_height": source.height,
            "source_transform": list(source.transform)[:6],
            "transform": list(output_transform)[:6],
            "crs": "Lunar South Polar Stereographic",
            "crs_wkt": source.crs.to_wkt(),
            "source_resolution": list(source.res),
            "resolution": [spacing * stride for spacing in source.res],
            "horizontal_unit": "m",
            "pixel_registration": "pixel centre",
            "source_raster_type": source.tags().get("AREA_OR_POINT"),
            "nodata_percent": float(100 * (1 - np.count_nonzero(valid) / valid.size)),
            "sampling": {"method": "source-pixel decimation" if window is None else "native-pixel window",
                         "stride": stride, "offset": offset, "window": None if window is None else window.flatten()},
            "elevation": _encode(elevation[samples], valid[samples], "m"),
            "valid": valid[samples].ravel().tolist(),
            "quad_valid": quad_valid.ravel().tolist(),
            "layers": layers,
            "unavailable": unavailable,
        }
