"""End-to-end Phase 2 Terrain Computation Pipeline.

Orchestrates:
1. Descriptive elevation statistics, coverage, and hypsometric distribution.
2. Slope derivation (Zevenbergen-Thorne default and Horn) accounting for pixel spacing and affine transform.
3. Quantitative slope comparison against NASA supplied slope (bias, MAE, RMSE, MedAE, discrepancy analysis).
4. Aspect calculation with documented azimuth convention (degrees clockwise from North, flat as -1.0).
5. Multi-scale roughness standard deviation at three physical neighbourhood scales (15 m, 35 m, 75 m).
6. Georeferenced GeoTIFF exports to data/processed/terrain/site04/ preserving lunar WKT and transform.
7. Diagnostic PNG maps with colourbars, coordinate axes, and lunar geodetic annotations.
8. Machine-readable Phase 2 report saved to data/metadata/terrain/.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional

import numpy as np
import rasterio

# Configure matplotlib for headless server environments
try:
    os.environ["MPLCONFIGDIR"] = tempfile.gettempdir()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    matplotlib = None
    plt = None
    HAS_MATPLOTLIB = False

from app.scientific_engines.terrain.aspect import calculate_aspect, summarize_aspect
from app.scientific_engines.terrain.elevation import calculate_elevation_statistics, write_geotiff
from app.scientific_engines.terrain.loader import (
    SiteTerrainDataset,
    TerrainRasterMetadata,
    load_site_dataset,
    require_compatible_grid,
)
from app.scientific_engines.terrain.roughness import ROUGHNESS_SCALES_M, compute_multi_scale_roughness
from app.scientific_engines.terrain.slope import (
    calculate_slope,
    compare_slopes,
    extract_pixel_spacing_from_transform,
)


def render_diagnostic_map(
    data: np.ndarray,
    bounds: Tuple[float, float, float, float],
    title: str,
    output_path: Path,
    cmap: str = "viridis",
    cbar_label: str = "",
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
) -> Path:
    """Generate and save a publication-quality diagnostic PNG map."""
    if not HAS_MATPLOTLIB or plt is None:
        return output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)
    left, bottom, right, top = bounds

    fig, ax = plt.subplots(figsize=(7, 6), dpi=150)
    extent = [left / 1000.0, right / 1000.0, bottom / 1000.0, top / 1000.0]

    im = ax.imshow(
        data,
        extent=extent,
        origin="upper",
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        interpolation="nearest",
    )

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label(cbar_label, fontsize=10)

    ax.set_title(title, fontsize=11, fontweight="bold", pad=10)
    ax.set_xlabel("Lunar Polar Stereographic Easting (km)", fontsize=9)
    ax.set_ylabel("Lunar Polar Stereographic Northing (km)", fontsize=9)
    ax.tick_params(labelsize=8)

    plt.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)

    return output_path


def run_phase2_terrain_pipeline(
    raw_site_dir: Path = Path("data/raw/terrain/site04"),
    processed_dir: Path = Path("data/processed/terrain/site04"),
    metadata_dir: Path = Path("data/metadata/terrain"),
    site: str = "Site04",
    generate_diagnostics: bool = True,
) -> Dict[str, Any]:
    """Execute complete Phase 2 terrain computation suite for a lunar landing site.

    Returns:
        Structured machine-readable dictionary summarizing all results and outputs.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    processed_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    diag_dir = processed_dir / "diagnostics"
    if generate_diagnostics:
        diag_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load validated inputs
    dataset = load_site_dataset(raw_site_dir, site=site, load_arrays=True)
    require_compatible_grid(dataset)
    surf_raster = dataset.elevation
    nasa_slp_raster = dataset.slope
    if surf_raster is None or surf_raster.data is None:
        raise ValueError(f"Elevation raster missing for {site}")
    if nasa_slp_raster is None or nasa_slp_raster.data is None:
        raise ValueError(f"NASA slope raster missing for {site}")

    dem = surf_raster.data
    meta = surf_raster.metadata
    transform = meta.transform
    bounds = meta.bounds

    # 2. Elevation descriptive statistics and distribution
    elev_stats = calculate_elevation_statistics(dem, nodata=meta.nodata)
    elev_geotiff_path = processed_dir / f"{site}_processed_elevation.tif"
    write_geotiff(
        dem,
        meta,
        elev_geotiff_path,
        description=f"Processed LOLA elevation for {site}",
    )

    # 3. Slope derivation using Zevenbergen-Thorne and Horn
    calc_slope_zt = calculate_slope(dem, transform=transform, method="zevenbergen_thorne")
    calc_slope_horn = calculate_slope(dem, transform=transform, method="horn")

    # Slope comparison against NASA supplied slope
    comparison_zt = compare_slopes(calc_slope_zt, nasa_slp_raster.data)
    comparison_horn = compare_slopes(calc_slope_horn, nasa_slp_raster.data)

    slope_diff = calc_slope_zt - nasa_slp_raster.data

    slope_geotiff_path = processed_dir / f"{site}_calculated_slope_deg.tif"
    write_geotiff(
        calc_slope_zt,
        meta,
        slope_geotiff_path,
        description=f"Calculated 5m Slope (deg) for {site} via 2nd-order central difference",
        units="degrees",
    )

    slope_diff_geotiff_path = processed_dir / f"{site}_slope_difference_deg.tif"
    write_geotiff(
        slope_diff,
        meta,
        slope_diff_geotiff_path,
        description=f"Slope difference (calculated - NASA supplied) in degrees for {site}",
        units="degrees",
    )

    # 4. Aspect derivation
    aspect_deg = calculate_aspect(dem, transform=transform, method="zevenbergen_thorne")
    aspect_summary = summarize_aspect(aspect_deg)

    aspect_geotiff_path = processed_dir / f"{site}_calculated_aspect_deg.tif"
    write_geotiff(
        aspect_deg,
        meta,
        aspect_geotiff_path,
        description=f"Calculated 5m Aspect (deg clockwise from North, flat=-1) for {site}",
        units="degrees",
    )

    # 5. Multi-scale roughness calculation (15m, 35m, 75m)
    roughness_results = compute_multi_scale_roughness(dem, transform=transform, scales_m=ROUGHNESS_SCALES_M)

    roughness_output_paths: Dict[str, str] = {}
    roughness_metadata_report: Dict[str, Any] = {}

    for scale_key, (r_arr, r_meta) in roughness_results.items():
        w_meters = int(r_meta["nominal_scale_m"])
        r_path = processed_dir / f"{site}_roughness_{w_meters}m.tif"
        write_geotiff(
            r_arr,
            meta,
            r_path,
            description=f"Local elevation std dev at {w_meters}m scale for {site}",
        )
        roughness_output_paths[f"{scale_key}_{w_meters}m"] = str(r_path)
        roughness_metadata_report[scale_key] = r_meta

    # 6. Diagnostic maps generation
    diagnostic_map_paths: Dict[str, str] = {}
    if generate_diagnostics:
        # Elevation
        p_elev = diag_dir / f"{site}_elevation_map.png"
        render_diagnostic_map(
            dem, bounds, f"{site} Elevation (LOLA 5m)", p_elev, cmap="viridis", cbar_label="Elevation (m)"
        )
        diagnostic_map_paths["elevation"] = str(p_elev)

        # Calculated Slope
        p_slp = diag_dir / f"{site}_calculated_slope_map.png"
        render_diagnostic_map(
            calc_slope_zt, bounds, f"{site} Calculated Slope (deg)", p_slp, cmap="magma", cbar_label="Slope (deg)", vmin=0, vmax=50
        )
        diagnostic_map_paths["calculated_slope"] = str(p_slp)

        # Supplied Slope
        p_slp_nasa = diag_dir / f"{site}_supplied_slope_map.png"
        render_diagnostic_map(
            nasa_slp_raster.data, bounds, f"{site} NASA Supplied Slope (deg)", p_slp_nasa, cmap="magma", cbar_label="Slope (deg)", vmin=0, vmax=50
        )
        diagnostic_map_paths["supplied_slope"] = str(p_slp_nasa)

        # Slope Difference
        p_slp_diff = diag_dir / f"{site}_slope_difference_map.png"
        render_diagnostic_map(
            slope_diff, bounds, f"{site} Slope Difference (Calculated - NASA)", p_slp_diff, cmap="bwr", cbar_label="Difference (deg)", vmin=-0.05, vmax=0.05
        )
        diagnostic_map_paths["slope_difference"] = str(p_slp_diff)

        # Aspect
        p_asp = diag_dir / f"{site}_aspect_map.png"
        render_diagnostic_map(
            aspect_deg, bounds, f"{site} Terrain Aspect (Clockwise from North)", p_asp, cmap="twilight", cbar_label="Aspect (deg, flat=-1)", vmin=0, vmax=360
        )
        diagnostic_map_paths["aspect"] = str(p_asp)

        # Roughness maps
        for scale_key, (r_arr, r_meta) in roughness_results.items():
            w_meters = int(r_meta["nominal_scale_m"])
            p_r = diag_dir / f"{site}_roughness_{w_meters}m_map.png"
            render_diagnostic_map(
                r_arr, bounds, f"{site} Roughness ({w_meters}m scale)", p_r, cmap="cividis", cbar_label="Elevation Std Dev (m)"
            )
            diagnostic_map_paths[f"roughness_{w_meters}m"] = str(p_r)

    # 7. Comprehensive Phase 2 Report
    report = {
        "report_type": "LUNA-SCOPE Phase 2 Terrain Computation Report",
        "site": site,
        "timestamp_utc": timestamp,
        "phase2_complete": True,
        "georeferencing_and_crs": {
            "coordinate_system": "Lunar South-Polar Stereographic",
            "reference_frame": "MOON_ME associated with DE421 ephemeris",
            "semi_major_axis_m": 1737400.0,
            "origin_latitude": -90.0,
            "central_meridian": 0.0,
            "linear_units": "metre",
            "grid_resolution_m": [meta.resolution[0], meta.resolution[1]],
            "bounds": meta.bounds,
            "transform": meta.transform,
            "width": meta.width,
            "height": meta.height,
        },
        "elevation_summary": elev_stats,
        "slope_analysis": {
            "primary_method": "zevenbergen_thorne_central_difference",
            "alternative_method_evaluated": "horn_1981_weighted",
            "zevenbergen_thorne_vs_nasa_supplied": comparison_zt,
            "horn_vs_nasa_supplied": comparison_horn,
        },
        "aspect_analysis": aspect_summary,
        "roughness_analysis": {
            "scale_classification": "provisional_analytical_scales",
            "qualification_status": "provisional_analytical_scales_unsupported_by_specific_mission_hardware_dimensions",
            "scale_justifications": {
                "small_15m": "Provisional analytical micro-scale (3x3 pixels / 15m span): captures short-baseline elevation variability and local breaks-of-slope without certified vehicle wheel/chassis constraints.",
                "medium_35m": "Provisional analytical meso-scale (7x7 pixels / 35m span): captures intermediate crater relief and touchdown-scale topographic variation without certified lander gear constraints.",
                "large_75m": "Provisional analytical macro-scale (15x15 pixels / 75m span): captures regional undulating relief and mesoscale crater rim texture.",
            },
            "scales": roughness_metadata_report,
        },
        "generated_geotiffs": {
            "elevation": str(elev_geotiff_path),
            "calculated_slope": str(slope_geotiff_path),
            "slope_difference": str(slope_diff_geotiff_path),
            "calculated_aspect": str(aspect_geotiff_path),
            **roughness_output_paths,
        },
        "diagnostic_maps": diagnostic_map_paths,
        "scientific_limitations": [
            "Pixel spacing is not measurement spacing; consult this site's LDEC observation coverage.",
            "Roughness scales (15 m, 35 m, 75 m) are provisional analytical scales based on generic planetary geomorphometric baselines, not validated against certified flight vehicle or lander hardware dimensions.",
            "Local roughness and slope reflect interpolated topography and should be interpreted alongside toterr and slperr uncertainty layers.",
            "Slope calculations assume planar patches over 2*dx (10 m); sub-pixel micro-roughness below 5 m is unresolved by LOLA.",
            "Aspect is undefined on near-horizontal surfaces and coded as -1.0.",
        ],
    }

    report_path = metadata_dir / f"{site.lower()}_phase2_terrain_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(report_path)

    return report


def run_phase3_hazard_pipeline(
    raw_site_dir: Path = Path("data/raw/terrain/site04"),
    processed_dir: Path = Path("data/processed/terrain/site04"),
    metadata_dir: Path = Path("data/metadata/terrain"),
    site: str = "Site04",
    generate_diagnostics: bool = True,
    reuse_phase2_roughness: bool = False,
) -> Dict[str, Any]:
    """Execute complete Phase 3 Terrain Hazard Screening Pipeline for a lunar landing site.

    Orchestrates:
    1. Loading validated Phase 1 and Phase 2 inputs.
    2. Physical hazard indicators (slope, multi-scale roughness).
    3. Epistemic data-quality indicators (elevation uncertainty, slope uncertainty, observation count).
    4. Gated combined categorical screening (max physical, gated by quality).
    5. Georeferenced GeoTIFF exports to data/processed/terrain/site04/.
    6. Machine-readable Phase 3 report saved to data/metadata/terrain/.
    7. Diagnostic maps if visualization backend is available.

    Returns:
        Structured machine-readable dictionary summarizing screening results.
    """
    from app.scientific_engines.terrain.hazards import generate_hazard_screening

    dataset = load_site_dataset(raw_site_dir, site=site, load_arrays=True)
    require_compatible_grid(dataset)
    roughness_results = None
    if reuse_phase2_roughness:
        roughness_results = {}
        meta = dataset.elevation.metadata
        for key, scale in ROUGHNESS_SCALES_M.items():
            path = processed_dir / f"{site}_roughness_{int(scale)}m.tif"
            with rasterio.open(path) as src:
                if (src.height, src.width, tuple(src.transform)[:6], src.crs.to_wkt()) != (
                    meta.height, meta.width, meta.transform, meta.crs_wkt
                ):
                    raise ValueError(f"Incompatible Phase 2 roughness grid: {path}")
                if src.tags().get("SOURCE_DEM_SHA256") != meta.sha256_hash:
                    raise ValueError(f"Stale or unverified Phase 2 roughness source: {path}")
                roughness_results[key] = (src.read(1, masked=True).filled(np.nan), {})
    report = generate_hazard_screening(
        site_dataset=dataset,
        processed_dir=processed_dir,
        metadata_dir=metadata_dir,
        site=site,
        roughness_results=roughness_results,
    )

    # Optional diagnostic maps
    if generate_diagnostics and HAS_MATPLOTLIB and plt is not None:
        diag_dir = processed_dir / "diagnostics"
        diag_dir.mkdir(parents=True, exist_ok=True)
        meta = dataset.elevation.metadata
        bounds = meta.bounds

        # Helper to load and render
        for key, path_str in report.get("indicator_geotiffs", {}).items():
            p = Path(path_str)
            if p.exists():
                with rasterio.open(p) as src:
                    arr = src.read(1)
                out_png = diag_dir / f"{site}_hazard_{key}_map.png"
                render_diagnostic_map(
                    arr, bounds, f"{site} Hazard Indicator: {key}",
                    out_png, cmap="YlOrRd", cbar_label="Class (0=UNK, 1=LOW, 2=MOD, 3=HIGH)",
                    vmin=0, vmax=3,
                )

        comb_path = Path(report.get("combined_geotiff", ""))
        if comb_path.exists():
            with rasterio.open(comb_path) as src:
                arr = src.read(1)
            out_png = diag_dir / f"{site}_combined_hazard_screen_map.png"
            render_diagnostic_map(
                arr, bounds, f"{site} Combined Terrain Hazard Screening",
                out_png, cmap="RdYlGn_r", cbar_label="Screening Class (0=UNK, 1=LOW, 2=MOD, 3=HIGH)",
                vmin=0, vmax=3,
            )

    return report
