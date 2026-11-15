# Horizons–SPICE Scientific Validation Subsystem

## 1. Overview and Purpose

The **Horizons–SPICE Scientific Validation Subsystem** is an isolated, optional scientific validation engine within LUNA-SCOPE (`backend/app/scientific_engines/ephemeris/`). Its purpose is to quantify agreement between NASA JPL Horizons ephemerides and LUNA-SCOPE's independent SPICE-derived lunar kinematics:

1. **Stage A:** Apparent observer validation against a 25-epoch benchmark catalog.
2. **Stage B1:** Canonical geometric Cartesian vector query builder (`VEC_TABLE=2`, `REF_SYSTEM=ICRF`) and dynamic CSV header parser.
3. **Stage B2:** SPICE geometric state construction in ICRF/J2000 and Mean Earth / Polar Axis (`MOON_ME`), with full $6\times 6$ `sxform` state transformation accounting for rotating-frame transport velocity.
4. **Stage B3:** Standalone comparison engine evaluating Cartesian and topocentric residuals against provisional tolerances, accompanied by E1-R6 §8.1 nested cryptographic provenance.
5. **Phase C0 Hardened Capture Pipeline:** An offline-deterministic HTTP capture pipeline with bounded chunked stream reading (5 MiB ceiling, 64 KiB chunks), Content-Length verification, sensitive-header redaction, and internal SHA-256 byte hashing.

---

## 2. Relationship to the Existing Ephemeris Engine

LUNA-SCOPE's core ephemeris engine operates independently for operational mission simulation:
- `observer.py`: Resolves topocentric observer coordinates from high-resolution LOLA DEM rasters.
- `geometry.py`: Computes airless apparent topocentric Sun and Earth geometry using SPICE `spkcpo` with `CN+S` (converged Newtonian light-time + stellar aberration).
- `kernels.py`: Manages the pinned NAIF kernel pool cached in `data/cache/ephemeris/`.

**Integration Principle:**  
The validation subsystem is strictly additive and isolated. It does **not** replace or modify `geometry.py`, `observer.py`, or `kernels.py`. It consumes the loaded kernel pool and provides verification capabilities without introducing any network or runtime dependencies to the main application or UI.

---

## 3. How to Run Offline Tests

All scientific validation tests run 100% offline using deterministic synthetic fixtures:

```bash
# Run the dedicated Horizons validation test suite
.venv\Scripts\python -m pytest tests/scientific_validation/test_horizons_validation.py -v

# Run the complete scientific validation suite
.venv\Scripts\python -m pytest tests/scientific_validation/ -v

# Run the full project test suite
.venv\Scripts\python -m pytest tests/ -q
```

---

## 4. How to Invoke Live Capture (Explicit Authorization Required)

Live capture connects to NASA JPL Horizons API (`https://ssd.jpl.nasa.gov/api/horizons.api`). It must **never** be executed automatically or during application startup.

To execute an authorized live capture programmatically:

```python
from app.scientific_engines.ephemeris import (
    LunarSurfaceLocation,
    capture_horizons_vector_pilot,
    compare_geometric_vectors,
)

# 1. Define location (Apollo 11 reference site per E1-R6 §2.1)
apollo_11 = LunarSurfaceLocation(
    latitude_deg=0.67416,
    longitude_deg=23.47314,
    altitude_m=0.0,
    site_name="Apollo 11",
)

# 2. Execute hardened capture (Sun = 10, Earth = 399)
result = capture_horizons_vector_pilot(
    target_id=10,
    location=apollo_11,
    iso_utc="2026-01-01T00:00:00Z",
    timeout_sec=15.0,
)

if result.success:
    print(f"Captured HTTP {result.http_status} with SHA-256: {result.response_bytes_sha256}")
    print(f"Provenance classification: {result.provenance.source_classification}")
else:
    print(f"Capture failed [{result.error_classification}]: {result.error}")
```

---

## 5. Required SPICE Kernels and Configuration

The subsystem requires the pinned NAIF kernels managed by `kernels.py` and cached in `data/cache/ephemeris/`:

| Kernel File | Type | Purpose |
|---|---|---|
| `naif0012.tls` | LSK | Leapsecond conversions (UTC to TDB/ET) |
| `de440s.bsp` | SPK | Solar System ephemeris (Sun, Earth, Moon relative to SSB) |
| `moon_pa_de440_200625.bpc` | PCK | Binary lunar principal-axis orientation |
| `moon_de440_250416.tf` | FK | Lunar reference frames (`MOON_ME`, `MOON_PA_DE440`) |
| `pck00011.tpc` | PCK | Planetary constants and target equatorial radii |

Kernels are automatically loaded on first evaluation via `kernels._load()`.

---

## 6. Provenance Classifications & Anti-Forgery Invariants

Per E1-R6 §8.1:
- `VERIFIED_HORIZONS_PILOT`: Assigned **strictly** when original raw response bytes are captured through the internal capture receipt workflow (`_create_capture_receipt`), with matching SHA-256 hashes, status 200, and genuine retrieval timestamp. Caller-supplied hash strings without raw bytes are rejected.
- `SYNTHETIC_FIXTURE`: Synthetic test fixtures and mock payloads.
- `UNVERIFIED_SOURCE`: External or unauthenticated data sources.

---

## 7. Provisional Tolerances & Status

Per E1-R6 §6.4, numerical acceptance tolerances for the geometric comparison are **provisional**:
- **Position residual tolerance:** $1.0\text{ km}$ ($\Delta r = \|\mathbf{r}_{\text{Horizons}} - \mathbf{r}_{\text{SPICE}}\|$).
- **Range residual tolerance:** $5.0\text{ km}$ ($|\Delta \text{Range}|$).
- **Angular separation tolerance:** $0.05^\circ$ ($180\text{ arcsec}$).

Evaluation statuses:
- `WITHIN_PROVISIONAL_THRESHOLD`: All residuals satisfy provisional thresholds.
- `OUTSIDE_PROVISIONAL_THRESHOLD`: One or more residuals exceed provisional thresholds.
- `NOT_ASSESSED`: Data insufficient for evaluation.

---

## 8. Scientific Limitations & Distinctions

1. **Epoch Label vs. Physical Instant:** Matching UTC labels (`TIME_TYPE=UT`) between Horizons and SPICE does not establish exact physical-instant equivalence because Horizons internal TDB integration steps are not publicly exposed in the API header.
2. **Geometric Track vs. Apparent Track:** Geometric state vectors represent the instantaneous physical position and velocity without light-time lag, stellar aberration, or atmospheric refraction. In contrast, operational tracking (`geometry.py`) uses `CN+S` converged reception light-time and stellar aberration.
3. **Gravitational Deflection:** Neither SPICE `CN+S` nor Horizons geometric vectors model general relativistic gravitational light bending by intervening masses.
4. **Pilot-Ready vs. Verified Pilot:** The codebase provides a **pilot-ready capture pipeline and comparison engine**. A verified pilot claim is valid **only** after an actual, authorized capture from `ssd.jpl.nasa.gov` has been executed, cryptographically hashed, and verified.
