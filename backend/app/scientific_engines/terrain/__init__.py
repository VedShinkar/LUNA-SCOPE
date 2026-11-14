"""Terrain scientific engine package."""
from app.scientific_engines.terrain.aspect import (
    FLAT_ASPECT_SENTINEL,
    calculate_aspect,
    create_synthetic_planar_dem,
    summarize_aspect,
)
from app.scientific_engines.terrain.elevation import (
    calculate_elevation_statistics,
    write_geotiff,
)
from app.scientific_engines.terrain.loader import (
    LOLA_CORE_PRODUCTS,
    SiteTerrainDataset,
    TerrainRaster,
    TerrainRasterMetadata,
    check_tiff_header,
    compute_sha256,
    extract_raster_metadata,
    load_site_dataset,
    read_raster_band,
)
from app.scientific_engines.terrain.pipeline import (
    render_diagnostic_map,
    run_phase2_terrain_pipeline,
    run_phase3_hazard_pipeline,
)
from app.scientific_engines.terrain.uncertainty import (
    DATA_QUALITY_THRESHOLDS,
    QUALITY_SEVERITY_TO_CODE,
    CODE_TO_QUALITY_SEVERITY,
    analyze_uncertainty_layer,
    classify_uncertainty_thresholds,
    classify_observation_coverage_confidence,
)
from app.scientific_engines.terrain.roughness import (
    ROUGHNESS_SCALES_M,
    calculate_roughness_std,
    compute_multi_scale_roughness,
    physical_scale_to_window_size,
)
from app.scientific_engines.terrain.slope import (
    calculate_slope,
    compare_slopes,
    compute_terrain_gradients,
    extract_pixel_spacing_from_transform,
)
from app.scientific_engines.terrain.validation import (
    analyze_ldec_distribution,
    evaluate_dem_validity_and_coverage,
    validate_data_integrity,
    validate_lunar_crs,
    validate_site_rasters,
    validate_spatial_alignment,
)
from app.scientific_engines.terrain.hazards import (
    HAZARD_THRESHOLDS,
    SEVERITY_TO_CODE,
    CODE_TO_SEVERITY,
    PHYSICAL_HAZARD_KEYS,
    DATA_QUALITY_KEYS,
    classify_increasing,
    classify_observation_coverage,
    generate_hazard_screening,
    write_indicator_geotiff,
)

__all__ = [
    # Phase 1: Ingestion & Validation
    "LOLA_CORE_PRODUCTS",
    "SiteTerrainDataset",
    "TerrainRaster",
    "TerrainRasterMetadata",
    "check_tiff_header",
    "compute_sha256",
    "extract_raster_metadata",
    "load_site_dataset",
    "read_raster_band",
    "analyze_ldec_distribution",
    "evaluate_dem_validity_and_coverage",
    "validate_data_integrity",
    "validate_lunar_crs",
    "validate_site_rasters",
    "validate_spatial_alignment",
    # Phase 2: Terrain Computation
    "calculate_elevation_statistics",
    "write_geotiff",
    "calculate_slope",
    "compare_slopes",
    "compute_terrain_gradients",
    "extract_pixel_spacing_from_transform",
    "FLAT_ASPECT_SENTINEL",
    "calculate_aspect",
    "create_synthetic_planar_dem",
    "summarize_aspect",
    "ROUGHNESS_SCALES_M",
    "calculate_roughness_std",
    "compute_multi_scale_roughness",
    "physical_scale_to_window_size",
    "render_diagnostic_map",
    "run_phase2_terrain_pipeline",
    "run_phase3_hazard_pipeline",
    # Phase 3: Hazard Screening & Uncertainty
    "DATA_QUALITY_THRESHOLDS",
    "QUALITY_SEVERITY_TO_CODE",
    "CODE_TO_QUALITY_SEVERITY",
    "analyze_uncertainty_layer",
    "classify_uncertainty_thresholds",
    "classify_observation_coverage_confidence",
    "HAZARD_THRESHOLDS",
    "SEVERITY_TO_CODE",
    "CODE_TO_SEVERITY",
    "PHYSICAL_HAZARD_KEYS",
    "DATA_QUALITY_KEYS",
    "classify_increasing",
    "classify_observation_coverage",
    "generate_hazard_screening",
    "write_indicator_geotiff",
]
