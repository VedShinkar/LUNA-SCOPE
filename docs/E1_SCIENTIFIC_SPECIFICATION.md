# LUNA-SCOPE — Scientific Reference Specification (E1-R6)

**Document ID:** LUNA-SCOPE-SPEC-E1-R6  
**Status:** PROPOSED SCIENTIFIC SPECIFICATION  
**Scope:** NASA JPL Horizons Ephemeris Comparison, Lunar Frame Realization & Pilot Benchmark Pipeline  
**Target Systems:** `backend/science/validation.py`, `backend/science/spice_setup.py`, `backend/science/coordinate_frames.py`  
**Revision:** E1-R6 (Targeted Scientific Corrections)  
**Date:** 2026-11-15  

---

## 1. Executive Summary & Objective

This document provides the formal, reproducible scientific reference specification for querying the NASA JPL Horizons system and validating topocentric solar and terrestrial ephemerides within the LUNA-SCOPE lunar analysis framework.

This revision (E1-R6) applies six targeted scientific corrections to E1-R5:
1. **Horizons UT Semantics:** Aligns UT definitions with the official JPL Horizons documentation, where for dates after 1962 `TIME_TYPE='UT'` designates Coordinated Universal Time (UTC), eliminating any `UT1 ≈ UTC` wording for the 2026 pilot epoch.
2. **`TIME_ZONE` Semantics:** Accurately documents `TIME_ZONE` as a local civil-time offset relative to UT, where `+00:00` introduces zero civil-time offset for this pilot, and confirms its omission from vector queries.
3. **Gravitational Light Deflection:** Eliminates any suggestion that SPICE `CN+S` models relativistic light bending (`CN+S` denotes Converged Newtonian light-time plus stellar aberration only), and explicitly preserves gravitational deflection as an unresolved systematic contribution requiring a dedicated model.
4. **Unified Provenance Field Names:** Standardizes the canonical temporal field naming convention across JSON Schema, explanatory text, and sample records (`requested_epoch_raw`, `requested_epoch_utc_label`, `returned_epoch_string`, and `spice_et_sec`).
5. **Qualified Physical-Instant Equivalence:** Replaces a priori assertions of physical-instant identity with an explicit capture protocol recording submitted UTC, returned Horizons string, SPICE ET float64, and LSK hash, requiring empirical conversion verification during the pilot.
6. **Qualified 2000–2040 Frame Bound:** Formally labels the $3.070984 \times 10^{-7}\text{ rad}$ rotation bound as an unverified, provisional figure cited from NAIF narrative comments in `moon_de440_250416.tf`, rather than an independently reproduced calculation.

---

## 2. Lunar Frame Realization & DE421 vs DE440 Frame Compatibility

### 2.1 The Two Mean Earth Frame Realizations

A critical scientific distinction exists between the frame realization used by NASA JPL Horizons and the frame realization used by the LUNA-SCOPE SPICE environment:

1. **JPL Horizons Coordinate Observer Realization (`coord@301`):**
   - The JPL Horizons on-line ephemeris system defines coordinate observer locations on the Moon (`coord@301`) in the lunar Mean Earth / Polar Axis frame associated with the **DE421** planetary and lunar ephemeris (`MOON_ME_DE421`).
   - The orientation of the DE421 ME frame relative to ICRF/J2000 is integrated via Lunar Laser Ranging (LLR) fits as documented in Folkner et al. (2008, 2014).
2. **LUNA-SCOPE SPICE Realization (`MOON_ME`):**
   - In LUNA-SCOPE, SPICE kernel loading (`SpiceManager.load_kernels()`) loads `moon_de440_250416.tf` as the final frame kernel (index 7).
   - In `moon_de440_250416.tf`, NAIF defines the generic frame alias `MOON_ME` to map directly to `MOON_ME_DE440_ME421` (Frame ID: 31001).
   - `MOON_ME_DE440_ME421` is defined by rotating the DE440 lunar Principal Axes frame (`MOON_PA_DE440`, Frame ID: 31008) by the constant matrix specified in Park et al. (2021) and Folkner et al. (2014) designed to align with the DE421 Mean Earth frame.

### 2.2 Mathematical & Positional Discrepancy Between DE421 and DE440 ME

The figures below are cited directly from narrative comments in the text header of the NAIF frame kernel `moon_de440_250416.tf` (lines 154–165; file verified on disk via SHA-256 in §3):
- For the historical interval 1900–2051 TDB, the maximum rotation angle between `MOON_ME_DE421` and `MOON_ME_DE440_ME421` over approximately $10^6$ samples is reported in that kernel as:
  $$\Delta \theta_{\max} = 5.820442 \times 10^{-7}\text{ rad} \approx 0.12005\text{ arcsec}$$
  This corresponds to a great-circle displacement on the lunar reference surface ($R = 1737.4\text{ km}$) of:
  $$\Delta s_{\max} = 1737.4\text{ km} \times 5.820442 \times 10^{-7}\text{ rad} \approx 1.011\text{ m}$$
- For the operational interval 2000–2040 TDB, the kernel text reports:
  $$\Delta \theta_{\max,\, 2000\text{--}2040} = 3.070984 \times 10^{-7}\text{ rad} \approx 0.0633\text{ arcsec}$$
  $$\Delta s_{\max,\, 2000\text{--}2040} \approx 0.534\text{ m}$$

> [!CAUTION]
> **Provisional / Unverified Status of Frame Rotation Bound:**
> The figure $3.070984 \times 10^{-7}\text{ rad}$ represents narrative text commentary from the NAIF kernel header. The underlying numerical grid-sampling calculation and software toolchain were not executed or independently reproduced within the LUNA-SCOPE codebase. Consequently, this value is explicitly classified as an **unverified, provisional figure cited from NAIF narrative comments**, not an independently verified project computation. While it indicates that frame orientation divergence is orders of magnitude below the provisional pilot angular tolerance ($0.05^\circ = 180\text{ arcsec}$), an independent programmatic grid-sampling computation remains a pending verification task.

### 2.3 Positional and Angular Effect on Ephemeris Observables

When identical nominal selenographic coordinates $(\lambda, \phi, h)$ are provided to Horizons (DE421 ME) and LUNA-SCOPE (DE440 ME):

*(Note: The $0.53\text{ m}$ displacement, $\le 0.0633\text{ arcsec}$ orientation offset, and derived parallax values below are strictly **provisional estimates** because they depend directly on the unverified 2000–2040 frame-rotation bound cited from NAIF commentary in §2.2, rather than an independently reproduced project calculation.)*

1. **Surface Observer Positional Discrepancy:**
   The physical observer location differs between the two models by at most $\Delta r_{\text{obs}} \approx 0.53\text{ m}$ *(provisional estimate based on cited NAIF comment)* during the mission epoch.
2. **Topocentric Angular Parallax Error *(provisional estimates)*:**
   - **Earth Pointing ($D \approx 384,400\text{ km}$):**
     $$\Delta \alpha_{\text{parallax, Earth}} \approx \frac{0.53\text{ m}}{384,400\text{ km}} \approx 1.38 \times 10^{-9}\text{ rad} \approx 0.00028\text{ arcsec}$$
   - **Sun Pointing ($D \approx 1.496 \times 10^8\text{ km}$):**
     $$\Delta \alpha_{\text{parallax, Sun}} \approx \frac{0.53\text{ m}}{1.496 \times 10^8\text{ km}} \approx 3.54 \times 10^{-12}\text{ rad} \approx 0.0000007\text{ arcsec}$$
3. **Topocentric Frame Orientation Discrepancy *(provisional estimate)*:**
   Because the local East-North-Up (ENU) topocentric reference triad is tied to the lunar body-fixed frame, the rotation of the frame itself rotates the local ENU axes by up to $\Delta \theta_{\text{frame}} \le 0.0633\text{ arcsec}$ ($\approx 1.76 \times 10^{-5\circ}$).
4. **Coordinate Transfer Conclusion:**
   - For pilot validation and coarse benchmark testing (where provisional angular tolerance is $0.05^\circ = 180\text{ arcsec}$), the provisional frame realization offset of $\sim 0.063\text{ arcsec}$ is **three orders of magnitude below tolerance** ($0.035\%$ of budget).
   - Therefore, coordinates $(\lambda, \phi, h)$ can be passed directly between Horizons `coord@301` and LUNA-SCOPE SPICE for pilot and baseline validation.
   - For future sub-arcsecond or micro-radian scientific verification, an independently calculated, time-dependent rotation $R_{\text{DE421}\to\text{DE440}}(t)$ must be applied.

---

## 3. SPICE Kernel Inventory & Verification

The project manages SPICE kernels via `SpiceManager` (`backend/science/spice_setup.py`). All seven canonical kernels reside in `backend/data/kernels/`. Cryptographic SHA-256 digests were computed directly from local file bytes:

| Filename | Relative Path | Kernel Type | Reference Frames Defined | SHA-256 (Calculated from Local File Bytes) | Load Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `naif0012.tls` | `backend/data/kernels/naif0012.tls` | LSK (Leapseconds) | N/A (UTC $\leftrightarrow$ TDB/ET) | `678e32bdb5a744117a467cd9601cd6b373f0e9bc9bbde1371d5eee39600a039b` | Canonical (Order 1) |
| `pck00010.tpc` | `backend/data/kernels/pck00010.tpc` | Text PCK (Constants) | `IAU_MOON`, `IAU_EARTH`, `IAU_SUN` | `59468328349aa730d18bf1f8d7e86efe6e40b75dfb921908f99321b3a7a701d2` | Canonical (Order 2) |
| `de440s.bsp` | `backend/data/kernels/de440s.bsp` | SPK (Ephemeris) | `J2000` (Inertial) | `c1c7feeab882263fc493a9d5a5b2ddd71b54826cdf65d8d17a76126b260a49f2` | Canonical (Order 3) |
| `moon_pa_de440_200625.bpc` | `backend/data/kernels/moon_pa_de440_200625.bpc` | Binary PCK (Orientation) | `MOON_PA`, `MOON_PA_DE440` | `60cd55aa401ea2ea97360636f567554bfe4e37bb829f901b4460a455dfaf783f` | Canonical (Order 4) |
| `moon_080317.tf` | `backend/data/kernels/moon_080317.tf` | FK (Frames Definition) | `MOON_ME`, `MOON_PA` | `78732477b96f9863e7b0d65bcee3c22b8707ca5ed0db56d1173319cb2e8c7993` | Canonical (Order 5) |
| `moon_assoc_me.tf` | `backend/data/kernels/moon_assoc_me.tf` | FK (Body Association) | `MOON_ME` (Body 301 $\rightarrow$ ME) | `52c622043ce0447d575e59ee01642f1894921e68c10f934ceff065f362da6c1c` | Canonical (Order 6) |
| `moon_de440_250416.tf` | `backend/data/kernels/moon_de440_250416.tf` | FK (DE440 Linkage) | `MOON_ME`, `MOON_PA`, `MOON_PA_DE440`| `a47c71e9c9f33796bdafb2c9d69a7ee447b6016ecad80f71cd6f3e479f9cf768` | Canonical (Order 7) |

All computed hashes match the `CANONICAL_KERNELS` registry in `backend/science/spice_setup.py`.

### 2.4 Frame Hierarchy & Non-Equivalence

1. **`MOON_PA` (Principal Axes):** Defined by lunar principal axes of inertia. Evaluated dynamically from binary PCK `moon_pa_de440_200625.bpc`.
2. **`MOON_ME` (Mean Earth / Polar Axis):** Defined by constant rotation from `MOON_PA`. In LUNA-SCOPE, `moon_de440_250416.tf` overrides `moon_080317.tf` to align `MOON_ME` with DE440 orientation fits.
3. **`IAU_MOON`:** Analytical trigonometric series from `pck00010.tpc`. Differs from `MOON_ME` by $\sim 155\text{ m}$ average surface offset ($\approx 0.0051^\circ = 18.4\text{ arcsec}$). It is **NOT** interchangeable with `MOON_ME`.

---

## 4. Lunar Surface Observer & Apollo 11 Altitude Semantics

### 4.1 Calibration Pilot Location & Altitude Distinction

To avoid polar illumination singularities during initial validation, the Apollo 11 landing site is specified for pilot capture.

> [!IMPORTANT]
> **Strict Altitude Semantics:**
> - **Reference-Sphere Pilot Altitude:** $h_{\text{pilot}} = 0.0\text{ km}$ above the mean lunar reference sphere ($R_{\text{mean}} = 1737.4\text{ km}$). Radial distance is exactly $R = 1737.400\text{ km}$.
> - **Actual Topographic Elevation:** Per LRO LOLA digital elevation models, the Apollo 11 landing site lies at an elevation of approximately $-2.57\text{ km}$ relative to the $1737.4\text{ km}$ sphere.
> - **Physical Lander Location:** The Apollo 11 Lunar Module (*Eagle*) descent stage sits at radial distance $R_{\text{lander}} \approx 1734.83\text{ km}$.
> - **Pilot Scope:** The calibration pilot validates the **reference-sphere observer ($0.0\text{ km}$ altitude) and API/parser pipeline**, **not** the exact physical lander position or local topography.

### 4.2 Observer Coordinates for Pilot

- **Latitude:** $+0.67416^\circ\text{ N}$ (planetocentric, North positive).
- **Longitude:** $+23.47314^\circ\text{ E}$ (East positive).
- **Altitude:** $0.0\text{ km}$ (reference sphere).
- **Cartographic Source:** LRO Camera (LROC) NAC landing site coordinates (Wagner et al. 2017; Davies & Colvin 2000).
- **Horizons Representation:** `CENTER='coord@301'`, `COORD_TYPE='GEODETIC'`, `SITE_COORD='23.47314,0.67416,0.0'`.
- **SPICE Representation:** `LunarSurfaceLocation(latitude_deg=0.67416, longitude_deg=23.47314, altitude_m=0.0)`. Note unit conversion: $\text{alt\_km} = \frac{\text{altitude\_m}}{1000.0}$.

### 4.3 Pilot vs Operational Mission Sites

The Apollo 11 site is strictly a calibration pilot. Mission validation requires subsequent execution across the operational polar sites:
1. **Shackleton Crater Rim:** $-89.90^\circ\text{ S}, 0.00^\circ\text{ E}, 200\text{ m}$ (extreme grazing solar elevation).
2. **de Gerlache Rim:** $-88.48^\circ\text{ S}, -88.35^\circ\text{ E}, 650\text{ m}$.
3. **Malapert Mountain:** $-85.99^\circ\text{ S}, +2.91^\circ\text{ E}, 5020\text{ m}$.
4. **Nobile Crater Rim:** $-85.25^\circ\text{ S}, +35.80^\circ\text{ E}, 1200\text{ m}$.
5. **Sinus Medii:** $0.00^\circ\text{ N}, 0.00^\circ\text{ E}, 0\text{ m}$ (prime meridian check).

---

## 5. Track 1: Apparent Observer Ephemeris Specification

### 5.1 Physical Meaning of `APPARENT='AIRLESS'`

In the official JPL Horizons system:
- **`APPARENT` controls atmospheric refraction only:**
  - `REFRACTED`: Invokes terrestrial atmospheric refraction models based on standard Earth atmospheric profiles.
  - `AIRLESS`: Suppresses atmospheric refraction calculations (light travels along geometric straight lines through vacuum).
- **Apparent corrections are intrinsic:**
  Down-leg one-way light-time delay, stellar aberration (due to the observer's motion around the Solar System Barycenter), and relativistic gravitational deflection are **automatically included** in observer table apparent quantities (such as Quantity 4).
- **Correction:** The `AIRLESS` parameter does **not** "activate" light-time or stellar aberration. It simply informs Horizons that the observer is in a vacuum. Because the Moon has no atmosphere, `APPARENT='AIRLESS'` is the physically correct configuration.

### 5.2 Approved Observer Query Parameters

```ini
format=json
COMMAND='10'                    # Sun (use '399' for Earth)
CENTER='coord@301'              # Coordinate observer on Moon (body 301)
COORD_TYPE='GEODETIC'           # Geodetic coordinates (R=1737.4 km, f=0)
SITE_COORD='23.47314,0.67416,0.0' # lon, lat, alt_km (deg E, deg N, km)
EPHEM_TYPE='OBSERVER'           # Observer table ephemeris
QUANTITIES='4,20'               # Q4: Apparent Az/El; Q20: Range & Range-rate
APPARENT='AIRLESS'              # Vacuum line of sight (no atmospheric refraction)
RANGE_UNITS='KM'                # Output range in kilometers
SUPPRESS_RANGE_RATE='NO'        # Preserve range-rate column
TIME_TYPE='UT'                  # Universal Time scale (UTC for post-1962 epochs per Horizons convention)
TIME_ZONE='+00:00'              # Local civil-time offset relative to UT (+00:00 introduces zero offset)
TIME_DIGITS='SECONDS'           # Output timestamps rounded to whole seconds
TLIST='2026-01-01 00:00:00'     # Single discrete epoch (UTC)
TLIST_TYPE='CAL'                # Calendar format for TLIST
CSV_FORMAT='YES'                # Delimited data block
```

*Disallowed parameters:* `START_TIME`, `STOP_TIME`, `STEP_SIZE` (must be omitted when `TLIST` is used); `REF_PLANE` (invalid for topocentric horizon tables); `EQUINOX` (invalid for Az/El quantities).

---

## 6. Track 2: Geometric Vector Comparison Specification

### 6.1 Purpose & Mathematical Equivalence

The Geometric Vector track compares un-aberrated orbital geometry without light-time delay or stellar aberration. A rigorous kinematic transformation chain is required.

### 6.2 Approved Vector Query Parameters

```ini
format=json
COMMAND='10'                    # Sun (use '399' for Earth)
CENTER='coord@301'              # Coordinate origin at surface observer site
COORD_TYPE='GEODETIC'           # Geodetic coordinates
SITE_COORD='23.47314,0.67416,0.0' # Observer site coordinates (lon, lat, alt_km)
EPHEM_TYPE='VECTORS'            # Cartesian vector table
VEC_TABLE='2'                   # Position and velocity states [X, Y, Z, VX, VY, VZ]
VEC_CORR='NONE'                 # Pure geometric state (no light-time, no aberration)
REF_SYSTEM='ICRF'               # International Celestial Reference Frame
REF_PLANE='FRAME'               # Preserve ICRF / J2000 equator and equinox plane
TIME_TYPE='UT'                  # Universal Time scale (UTC for post-1962 epochs per Horizons convention)
TIME_DIGITS='SECONDS'           # Timestamp precision
TLIST='2026-01-01 00:00:00'     # Single discrete epoch (UTC)
TLIST_TYPE='CAL'                # Calendar format
CSV_FORMAT='YES'                # Delimited data block
```

> **Note on `TIME_ZONE`:** In the official Horizons documentation, `TIME_ZONE` specifies a local civil-time offset relative to UT (e.g. `+05:30` or `-08:00`) and is supported exclusively for `EPHEM_TYPE='OBSERVER'`. It is not supported for `EPHEM_TYPE='VECTORS'` and must be omitted from vector queries. In the observer query, `TIME_ZONE='+00:00'` introduces zero civil-time offset relative to UT, ensuring returned observer timestamps directly match the submitted UTC epoch.

### 6.2a Time-Scale Consistency & Physical-Instant Verification

The two query tracks and the SPICE conversion must refer to the same physical instant. The time-scales and conventions at each stage are defined as follows:

| Stage | Time-Scale & Parameter | Labeling Convention | Technical Specification |
| :--- | :--- | :--- | :--- |
| **`TLIST` string submitted** | UTC under Horizons `TIME_TYPE='UT'` | `YYYY-MM-DD HH:MM:SS` (`2026-01-01 00:00:00`) | Submitted integer-second calendar string. Per the JPL Horizons documentation, for dates after 1962, Horizons defines UT as Coordinated Universal Time (UTC); prior to 1962, UT denotes UT1. |
| **Observer query time label** | UT (UTC) with zero civil offset | As returned in column `Date__(UT)__HR:MN:SS` | `TIME_TYPE='UT'` interprets input and outputs labels in UTC. `TIME_ZONE='+00:00'` defines a local civil-time offset relative to UT; setting `+00:00` introduces zero offset, preserving UTC output. |
| **Vector query time label** | UT (UTC) | As returned in column `Date__(UT)__HR:MN:SS` | `TIME_TYPE='UT'` designates UTC. `TIME_ZONE` is unsupported for vector tables and is omitted. Output timestamps are in UTC. |
| **SPICE ET conversion** | Ephemeris Time (ET / TDB seconds past J2000) | Computed float64 scalar via `str2et` | SPICE `str2et("2026-01-01 00:00:00 UTC")` performs the UTC-to-TDB conversion using the recorded leapseconds kernel (`naif0012.tls`). |
| **Provenance `requested_epoch_raw`** | UTC submitted string | `YYYY-MM-DD HH:MM:SS` | Exact verbatim string passed in `TLIST`. |
| **Provenance `requested_epoch_utc_label`** | Normalized ISO 8601 UTC label | `YYYY-MM-DDTHH:MM:SSZ` | Canonical ISO 8601 label with trailing `Z` denoting UTC. |
| **Provenance `returned_epoch_string`** | Returned time string | Verbatim string from API response | Raw epoch string from the data row (e.g. `2026-Jan-01 00:00:00`) verifying timestamp-label consistency. |
| **Provenance `spice_et_sec`** | SPICE ET numeric value | float64 numeric scalar | Exact seconds past J2000 TDB computed by SPICE for this epoch. |

> [!IMPORTANT]
> **Limitations of Time-Equivalence Verification:**
> Physical-instant equivalence between Horizons' internal ephemeris evaluation and SPICE ET cannot be assumed a priori, nor can it be fully observed from API outputs.
> 
> - **What CAN be verified from the captured data:**
>   Comparing `requested_epoch_raw` with `returned_epoch_string` verifies **timestamp-label consistency**—confirming that Horizons received, recognized, and reported the intended UTC calendar date without stepping drift or parsing offset. Recording `spice_et_sec` verifies deterministic UTC-to-TDB conversion within SPICE under the authenticated `naif0012.tls` kernel.
> - **What CANNOT be independently observed from the Horizons response:**
>   Horizons' returned ephemeris output provides UTC calendar labels, but does **not** expose its internal numerical TDB evaluation epoch or its internal leapsecond/relativistic time integrator. Consequently, comparing UTC strings verifies label alignment only; it does **not** independently verify internal dynamical time (TDB) equivalence or prove sub-millisecond physical-instant synchronization.
> 
> Therefore, for every capture, the pipeline records the complete audit trail:
> 1. `requested_epoch_raw`: exact UTC string submitted in `TLIST`,
> 2. `requested_epoch_utc_label`: canonical ISO 8601 UTC label,
> 3. `returned_epoch_string`: verbatim epoch string returned in the Horizons data block,
> 4. `spice_et_sec`: float64 ET value output by SPICE `str2et`,
> 5. Active SPICE LSK filename (`naif0012.tls`) and SHA-256 hash.
> 
> During pilot analysis, ephemeris rate of change ($|\dot{\mathbf{r}}|$) must be evaluated to place an upper bound on any residual time-synchronization uncertainty. Sub-millisecond physical equivalence must not be asserted merely on the basis of matching UTC labels.

### 6.3 Complete Mathematical Kinematics Pipeline

Direct vector rotation alone does **not** establish equivalence. The complete transformation must account for inertial alignment, origin translation, and rotating-frame kinematics:

1. **Horizons Output:**
   Horizons outputs site-relative target position $\mathbf{r}_{\text{rel}}^{\text{ICRF}} = [X, Y, Z]^T$ ($\text{km}$) and site-relative inertial velocity $\mathbf{v}_{\text{rel}}^{\text{ICRF}} = [V_X, V_Y, V_Z]^T$ ($\text{km/s}$) in the ICRF reference frame.
2. **SPICE Observer & Target States:**
   In SPICE, evaluate target state $\mathbf{X}_{\text{target}}^{\text{SSB}}(t_{\text{ET}})$ and Moon center state $\mathbf{X}_{\text{Moon}}^{\text{SSB}}(t_{\text{ET}})$ relative to the Solar System Barycenter (SSB) in `J2000`.
3. **SPICE Observer Site State:**
   Compute the lunar surface site offset in `MOON_ME`:
   $$\mathbf{r}_{\text{site}}^{\text{ME}} = \left[ (R_{\text{mean}} + h)\cos\phi\cos\lambda,\; (R_{\text{mean}} + h)\cos\phi\sin\lambda,\; (R_{\text{mean}} + h)\sin\phi \right]^T$$
   Transform the site state into `J2000` at epoch $t_{\text{ET}}$ using the $6\times 6$ state transformation matrix $\mathbf{T}_{6\times 6}(\text{'MOON\_ME'} \to \text{'J2000'}, t_{\text{ET}})$ from `sxform`:
   $$\begin{bmatrix} \mathbf{r}_{\text{site/Moon}}^{\text{J2000}} \\ \mathbf{v}_{\text{site/Moon}}^{\text{J2000}} \end{bmatrix} = \mathbf{T}_{6\times 6} \begin{bmatrix} \mathbf{r}_{\text{site}}^{\text{ME}} \\ \mathbf{0} \end{bmatrix}$$
   The observer inertial state is:
   $$\mathbf{X}_{\text{site}}^{\text{SSB}} = \mathbf{X}_{\text{Moon}}^{\text{SSB}} + \begin{bmatrix} \mathbf{r}_{\text{site/Moon}}^{\text{J2000}} \\ \mathbf{v}_{\text{site/Moon}}^{\text{J2000}} \end{bmatrix}$$
4. **Site-Relative Geometric State:**
   $$\mathbf{X}_{\text{rel}}^{\text{J2000}} = \mathbf{X}_{\text{target}}^{\text{SSB}} - \mathbf{X}_{\text{site}}^{\text{SSB}} = \begin{bmatrix} \mathbf{r}_{\text{rel}}^{\text{J2000}} \\ \mathbf{v}_{\text{rel}}^{\text{J2000}} \end{bmatrix}$$
   *Optional alternative:* `spkezr(target, et, 'J2000', 'NONE', site_spk_id)` yields the same result, but only if a valid SPK ephemeris object for the lunar surface site has been loaded. No such object exists in the LUNA-SCOPE canonical kernel set, so the **primary approach** remains the explicit Moon-centre state plus the transformed lunar-site offset described in steps 2–3 above.
5. **Inertial Frame Alignment:**
   Horizons uses `REF_SYSTEM='ICRF'`. SPICE uses `J2000` (realized by DE440). The ICRF and DE440 J2000 frames are aligned within $\approx 0.02\text{ arcsec}$ (negligible for position comparison).
6. **Transformation to Lunar Body Frame (`MOON_ME`):**
   $$\mathbf{r}_{\text{rel}}^{\text{ME}} = \mathbf{R}_{\text{J2000}\to\text{MOON\_ME}}(t_{\text{ET}}) \cdot \mathbf{r}_{\text{rel}}^{\text{J2000}}$$
   For velocity, the rotating-frame transport velocity (Coriolis term) is:
   $$\mathbf{v}_{\text{rel}}^{\text{ME}} = \mathbf{R} \cdot \mathbf{v}_{\text{rel}}^{\text{J2000}} - \boldsymbol{\omega}_{\text{Moon}} \times (\mathbf{R} \cdot \mathbf{r}_{\text{rel}}^{\text{J2000}})$$
   *(Note: Range-rate $\dot{\rho} = \frac{\mathbf{r} \cdot \mathbf{v}}{\|\mathbf{r}\|}$ is frame-invariant because $\mathbf{r} \cdot (\boldsymbol{\omega} \times \mathbf{r}) = 0$.)*
7. **Local ENU Transformation:**
   Using `LunarSurfaceLocation.get_rotation_matrix_to_enu()`:
   $$\mathbf{r}_{\text{ENU}} = [\rho_E, \rho_N, \rho_Z]^T = \mathbf{R}_{\text{ME}\to\text{ENU}} \cdot \mathbf{r}_{\text{rel}}^{\text{ME}}$$
8. **Topocentric Spherical Observables:**
   $$\rho = \sqrt{\rho_E^2 + \rho_N^2 + \rho_Z^2},\quad \text{el} = \arcsin\left(\frac{\rho_Z}{\rho}\right),\quad \text{az} = \operatorname{atan2}(\rho_E, \rho_N) \pmod{360^\circ}$$

---

## 6a. Apparent Residual Decomposition

Horizons apparent observer quantities and SPICE results computed with light-time and stellar aberration (`abcorr='LT+S'`) are **not automatically identical**. The residual between the two is composed of several independent, additive contributions. Each must be considered separately in a formal error budget:

| Contribution | Source of Difference | Direction of Effect |
| :--- | :--- | :--- |
| **Frame realization** | Horizons coordinates the observer in the DE421 ME frame; SPICE uses DE440 ME. The orientation difference is reported in NAIF kernel commentary as $\le 0.063\text{ arcsec}$ for 2000–2040 (§2.2; *provisional, unverified figure*). | Rotates the local ENU triad and shifts the observer position by $\approx 53\text{ cm}$ (*provisional estimate*). |
| **Observer position** | The same surface coordinates resolve to slightly different Cartesian positions in DE421 ME vs DE440 ME. | Induces a topocentric parallax residual in target direction (estimated provisionally in §2.3 as $\approx 0.00028\text{ arcsec}$ for Earth and $\approx 7 \times 10^{-7}\text{ arcsec}$ for Sun based on cited NAIF bound). |
| **Ephemeris state** | Horizons evaluates positions using DE421 planetary orbits; SPICE uses DE440. Planetary orbit differences between DE421 and DE440 are present but small for Sun and Earth. | Affects target position and therefore apparent direction and range. |
| **Light-time model** | Both Horizons and SPICE (`abcorr='LT'`) iterate one-way signal propagation. Differences arise if the number of Newtonian iterations differs or if relativistic terms are included differently. | Affects the retarded emission position of the target. |
| **Stellar aberration** | Both Horizons and SPICE (`abcorr='LT+S'`) apply the conventional stellar aberration correction. Differences arise if the observer velocity state differs due to frame realization or if aberration formulas differ in relativistic order. | Shifts the apparent direction by up to $\approx 25\text{ arcsec}$ for a typical lunar observer. Any difference appears as a residual within that correction. |
| **Gravitational light deflection** | Horizons apparent observer ephemerides include relativistic solar gravitational light deflection as standard. Standard SPICE aberration options (`LT`, `LT+S`, `CN`, `CN+S`) do not model gravitational light deflection (`CN+S` denotes Converged Newtonian light-time plus stellar aberration only). Matching Horizons gravitational light deflection in SPICE would require a separately implemented and validated relativistic light-bending model. | Omitting relativistic gravitational deflection in SPICE produces an unresolved systematic residual when comparing against Horizons apparent observer quantities, particularly for lines of sight passing near massive bodies (such as the Sun). |
| **Numerical / ASCII truncation** | Horizons returns values as fixed-width ASCII strings with limited significant figures. SPICE returns full float64 values. | Small rounding residuals at the least significant digit of the Horizons output. |

> [!IMPORTANT]
> Until a formal error budget is derived quantifying each contribution above, it is not possible to predict the total apparent residual between Horizons and LUNA-SCOPE SPICE results. In particular, **relativistic gravitational light deflection** is an unresolved systematic difference between Horizons apparent quantities and standard SPICE `LT+S` vectors. No formula or speculative magnitude is assumed here. The pilot capture will measure the actual combined residual, and the formal error budget must decompose it into these distinct physical and numerical components.

---

## 7. Parser Specification & Column Label Contract

### 7.1 Provisional Header Mapping Contract

The parser must dynamically map CSV header tokens preceding `$$SOE`. All mappings remain **provisional** until verified against the raw pilot response:

| Ephemeris Track | Expected Header Patterns (Provisional) | Canonical Field | Unit | Constraint |
| :--- | :--- | :--- | :--- | :--- |
| **Observer (Q4, Q20)** | `Azimuth`, `Azi_(app)`, `AZ` | `azimuth_deg` | Degrees ($^\circ$) | $0.0 \le \text{az} < 360.0$ |
| | `Elevation`, `Elev_(app)`, `EL` | `elevation_deg` | Degrees ($^\circ$) | $-90.0 \le \text{el} \le +90.0$ |
| | `delta`, `Target_range`, `R` | `distance_km` | Kilometers ($\text{km}$) | $\rho > 0.0$ |
| | `deldot`, `Range_rate`, `R_DOT`| `range_rate_kms` | $\text{km/s}$ | Real scalar |
| **Vector (VEC_TABLE=2)** | `X` | `x_km` | Kilometers ($\text{km}$) | Real scalar |
| | `Y` | `y_km` | Kilometers ($\text{km}$) | Real scalar |
| | `Z` | `z_km` | Kilometers ($\text{km}$) | Real scalar |
| | `VX` | `vx_kms` | $\text{km/s}$ | Real scalar |
| | `VY` | `vy_kms` | $\text{km/s}$ | Real scalar |
| | `VZ` | `vz_kms` | $\text{km/s}$ | Real scalar |

### 7.2 Parser Rules

1. Parse CSV header line preceding `$$SOE` dynamically.
2. Positional indexing (`tokens[2]`, `tokens[3]`) is strictly prohibited.
3. Validate that Quantity 4 does **not** provide range; range is extracted strictly from Quantity 20.
4. Raise `HorizonsQueryError` with structured diagnostic classifications on any unmapped column or missing data block.

---

## 8. Provenance Architecture & Schemas

### 8.1 Formal Provenance JSON Schema (Draft 2020-12)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://luna-scope.org/schemas/provenance.schema.json",
  "title": "HorizonsCaptureProvenance",
  "type": "object",
  "required": [
    "capture_id",
    "retrieval_metadata",
    "request_parameters",
    "target",
    "observer",
    "ephemeris_track",
    "temporal",
    "spice_environment",
    "parser",
    "parsed_data",
    "source_classification"
  ],
  "properties": {
    "capture_id": { "type": "string" },
    "retrieval_metadata": {
      "type": "object",
      "required": ["timestamp_utc", "http_status", "request_url", "request_url_sha256", "response_bytes_sha256"],
      "properties": {
        "timestamp_utc": { "type": "string", "format": "date-time" },
        "http_status": { "type": "integer" },
        "request_url": { "type": "string" },
        "request_url_sha256": { "type": "string", "pattern": "^[a-f0-9]{64}$" },
        "response_bytes_sha256": { "type": "string", "pattern": "^[a-f0-9]{64}$" }
      }
    },
    "request_parameters": { "type": "object" },
    "target": {
      "type": "object",
      "required": ["target_id", "target_name"],
      "properties": {
        "target_id": { "type": "integer" },
        "target_name": { "type": "string" }
      }
    },
    "observer": {
      "type": "object",
      "required": ["site_name", "body_code", "coordinate_frame", "latitude_deg", "longitude_deg", "altitude_m"],
      "properties": {
        "site_name": { "type": "string" },
        "body_code": { "type": "integer" },
        "coordinate_frame": { "type": "string" },
        "latitude_deg": { "type": "number" },
        "longitude_deg": { "type": "number" },
        "altitude_m": { "type": "number" }
      }
    },
    "ephemeris_track": { "type": "string", "enum": ["APPARENT_OBSERVER", "GEOMETRIC_VECTORS"] },
    "temporal": {
      "type": "object",
      "required": ["requested_epoch_raw", "requested_epoch_utc_label", "returned_epoch_string", "spice_et_sec"],
      "properties": {
        "requested_epoch_raw": { "type": "string", "description": "The exact raw time string submitted in TLIST (e.g. '2026-01-01 00:00:00')" },
        "requested_epoch_utc_label": { "type": "string", "format": "date-time", "description": "Canonical ISO 8601 UTC representation of requested epoch (e.g. '2026-01-01T00:00:00Z')" },
        "returned_epoch_string": { "type": "string", "description": "Raw epoch string verbatim from the Horizons response (e.g. '2026-Jan-01 00:00:00')" },
        "spice_et_sec": { "type": "number", "description": "Ephemeris Time (ET/TDB seconds past J2000) evaluated by SPICE str2et" }
      }
    },
    "spice_environment": {
      "type": "object",
      "required": ["loaded_kernels"],
      "properties": {
        "loaded_kernels": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["filename", "sha256"],
            "properties": {
              "filename": { "type": "string" },
              "sha256": { "type": "string", "pattern": "^[a-f0-9]{64}$" }
            }
          }
        }
      }
    },
    "parser": {
      "type": "object",
      "required": ["parser_version", "raw_header_line", "column_map"],
      "properties": {
        "parser_version": { "type": "string" },
        "raw_header_line": { "type": "string" },
        "column_map": { "type": "object" }
      }
    },
    "parsed_data": { "type": "object" },
    "source_classification": { "type": "string", "enum": ["VERIFIED_HORIZONS_PILOT", "UNVERIFIED_SOURCE"] }
  }
}
```

### 8.2 Illustrative Sample Provenance Record

> [!CAUTION]
> **Illustrative Formatting Template Only — Not Actual Pilot Data:**
> This sample record is strictly a schema-conformance and structural formatting template. All data values contained herein—specifically including `spice_et_sec` (820497669.184), parsed astronomical observables (`azimuth_deg`, `elevation_deg`, `distance_km`, `range_rate_kms`), and truncated hexadecimal hash strings—are **synthetic illustrative placeholders**. They are **not** captured, measured, or independently verified pilot data. No live Horizons request or pilot capture has been conducted. Production records must store real captured values and full 64-hex lowercase SHA-256 digests.

```json
{
  "capture_id": "horizons_capture_20260101_sun_apparent_apollo11",
  "retrieval_metadata": {
    "timestamp_utc": "2026-11-15T03:30:00Z",
    "http_status": 200,
    "request_url": "https://ssd.jpl.nasa.gov/api/horizons.api?format=json&COMMAND=%2710%27...",
    "request_url_sha256": "4a5e000000000000000000000000000000000000000000000000000000000000",
    "response_bytes_sha256": "8f3b000000000000000000000000000000000000000000000000000000000000"
  },
  "request_parameters": {
    "COMMAND": "10",
    "CENTER": "coord@301",
    "COORD_TYPE": "GEODETIC",
    "SITE_COORD": "23.47314,0.67416,0.0",
    "EPHEM_TYPE": "OBSERVER",
    "QUANTITIES": "4,20",
    "APPARENT": "AIRLESS",
    "RANGE_UNITS": "KM",
    "SUPPRESS_RANGE_RATE": "NO",
    "TIME_TYPE": "UT",
    "TIME_ZONE": "+00:00",
    "TIME_DIGITS": "SECONDS",
    "TLIST": "2026-01-01 00:00:00",
    "TLIST_TYPE": "CAL",
    "CSV_FORMAT": "YES"
  },
  "target": { "target_id": 10, "target_name": "Sun" },
  "observer": {
    "site_name": "Apollo 11 Reference-Sphere Site",
    "body_code": 301,
    "coordinate_frame": "MOON_ME",
    "latitude_deg": 0.67416,
    "longitude_deg": 23.47314,
    "altitude_m": 0.0
  },
  "ephemeris_track": "APPARENT_OBSERVER",
  "temporal": {
    "requested_epoch_raw": "2026-01-01 00:00:00",
    "requested_epoch_utc_label": "2026-01-01T00:00:00Z",
    "returned_epoch_string": "2026-Jan-01 00:00:00",
    "spice_et_sec": 820497669.184
  },
  "spice_environment": {
    "loaded_kernels": [
      {
        "filename": "naif0012.tls",
        "sha256": "678e32bdb5a744117a467cd9601cd6b373f0e9bc9bbde1371d5eee39600a039b"
      },
      {
        "filename": "pck00010.tpc",
        "sha256": "59468328349aa730d18bf1f8d7e86efe6e40b75dfb921908f99321b3a7a701d2"
      },
      {
        "filename": "de440s.bsp",
        "sha256": "c1c7feeab882263fc493a9d5a5b2ddd71b54826cdf65d8d17a76126b260a49f2"
      },
      {
        "filename": "moon_pa_de440_200625.bpc",
        "sha256": "60cd55aa401ea2ea97360636f567554bfe4e37bb829f901b4460a455dfaf783f"
      },
      {
        "filename": "moon_080317.tf",
        "sha256": "78732477b96f9863e7b0d65bcee3c22b8707ca5ed0db56d1173319cb2e8c7993"
      },
      {
        "filename": "moon_assoc_me.tf",
        "sha256": "52c622043ce0447d575e59ee01642f1894921e68c10f934ceff065f362da6c1c"
      },
      {
        "filename": "moon_de440_250416.tf",
        "sha256": "a47c71e9c9f33796bdafb2c9d69a7ee447b6016ecad80f71cd6f3e479f9cf768"
      }
    ]
  },
  "parser": {
    "parser_version": "1.0.0",
    "raw_header_line": "Date__(UT)__HR:MN:SS, , ,Azi_(app),Elev_(app),Target_range,Range_rate,",
    "column_map": {
      "azimuth_deg": "Azi_(app)",
      "elevation_deg": "Elev_(app)",
      "distance_km": "Target_range",
      "range_rate_kms": "Range_rate"
    }
  },
  "parsed_data": {
    "azimuth_deg": 32.520769,
    "elevation_deg": 1.430067,
    "distance_km": 147402308.468,
    "range_rate_kms": -0.1234
  },
  "source_classification": "UNVERIFIED_SOURCE"
}
```

### 8.3 Historical Catalog Segregation

The existing 25 entries in `backend/data/metadata/horizons_benchmark_catalog.json` must remain segregated and classified as **`UNVERIFIED_SOURCE`** until an independent provenance audit confirms their origin against verified raw files.

---

## 9. Future Test Matrix & Acceptance Tolerances

### 9.1 Provisional Nature of Acceptance Tolerances

> [!WARNING]
> **Provisional Tolerances Pending Formal Error Budget:**
> The numerical acceptance thresholds below (angular error $\le 0.05^\circ$, range error $\le 5.0\text{ km}$) are inherited from historical pipeline configurations and are strictly **PROVISIONAL**.
>
> A formal scientific error budget—incorporating:
> 1. Ephemeris differences between DE421 and DE440 orbits,
> 2. DE421 ME vs DE440 ME lunar orientation differences ($\le 0.063\text{ arcsec}$),
> 3. Gravitational deflection models (included in Horizons, optional in SPICE),
> 4. Numerical truncation in ASCII ephemeris tables—
> 
> must be derived before production acceptance thresholds are frozen. No theoretical error budget is assumed or invented here.

### 9.2 Planned Post-Pilot Test Matrix

| Test Identifier | Category | Target Body | Ephemeris Track | Location | Provisional Criteria | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `test_horizons_apparent_sun_pilot` | Apparent Pilot | Sun (10) | Observer (`APPARENT='AIRLESS'`) | Apollo 11 ($h=0\text{ km}$) | Angular error $< 0.05^\circ$ *(provisional)* | Planned |
| `test_horizons_apparent_earth_pilot` | Apparent Pilot | Earth (399) | Observer (`APPARENT='AIRLESS'`) | Apollo 11 ($h=0\text{ km}$) | Angular error $< 0.05^\circ$ *(provisional)* | Planned |
| `test_horizons_geometric_sun_pilot` | Geometric Pilot | Sun (10) | Vectors (`VEC_CORR='NONE'`) | Apollo 11 ($h=0\text{ km}$) | Vector diff $< 1.0\text{ km}$ *(provisional)* | Planned |
| `test_horizons_geometric_earth_pilot`| Geometric Pilot | Earth (399) | Vectors (`VEC_CORR='NONE'`) | Apollo 11 ($h=0\text{ km}$) | Vector diff $< 1.0\text{ km}$ *(provisional)* | Planned |
| `test_cache_key_track_separation` | Logic | Sun / Earth | Apparent vs Geometric | Any | Separate keys by track | Planned |
| `test_parser_malformed_csv_injection`| Fault Tolerance | Sun (10) | Observer / Vectors | N/A | Structured `HorizonsQueryError` | Planned |
| `test_provenance_hash_verification` | Audit | Sun / Earth | All | All | SHA-256 byte verification | Planned |

---

## 10. Remaining Scientific Uncertainties

1. **Delimited CSV Header Tokens in API Response:**
   Exact header token strings for `CSV_FORMAT='YES'` and `QUANTITIES='4,20'` can only be confirmed upon receipt of the first raw pilot response.
2. **Topographic Altitude Modeling for Operational Sites:**
   Horizons `coord@301` uses a spherical datum ($R = 1737.4\text{ km}$). Polar sites like Malapert Mountain possess significant local topography ($+5.02\text{ km}$ above datum). Reconciling topographic elevation models between Horizons and SPICE remains an open task for the multi-site operational phase.
3. **Formal Error Budget Derivation:**
   A comprehensive analytical error budget bounding DE421/DE440 orbit differences, frame alignment offsets, and aberration models must be formulated to establish rigorous, defensible acceptance tolerances.
4. **Relativistic Gravitational Light Deflection:**
   Horizons apparent observer quantities include relativistic solar gravitational light deflection as standard. Standard SPICE aberration options (`LT`, `LT+S`, `CN`, `CN+S`) do not model gravitational light deflection (`CN+S` denotes Converged Newtonian light-time plus stellar aberration only). Matching this correction in SPICE requires a separately implemented and validated relativistic model. The resulting residual remains an unresolved systematic contribution between Horizons apparent coordinates and SPICE `LT+S` vectors, which must be quantified in the formal error budget.
5. **Independent Computation of 2000–2040 Frame Rotation Bound:**
   The frame orientation rotation bound of $3.07 \times 10^{-7}\text{ rad}$ cited from NAIF narrative commentary in `moon_de440_250416.tf` has not been independently computed via programmatic sampling within LUNA-SCOPE and remains an unverified, provisional figure.
6. **Time-Scale Verification Limitations:**
   Horizons' returned UTC timestamp confirms calendar label consistency with the request, but does not expose Horizons' internal dynamical time argument (TDB) epoch. Comparing UTC strings confirms labeling alignment and absence of calendar drift, but cannot independently observe or prove internal TDB equivalence. Sub-millisecond physical-instant synchronization remains an unobservable internal property of the Horizons service.

---

## 11. Final Scientific Verdict

**Verdict:** **`READY FOR PILOT CAPTURE`**

> [!IMPORTANT]
> **Strict Definition & Boundary of this Verdict:**
> **`READY FOR PILOT CAPTURE`** is strictly defined as authorization for a **controlled, non-production single-epoch pilot capture** (using the reference-sphere Apollo 11 test site) to validate:
> 1. Real-world Horizons HTTP API request parameter formatting and connectivity,
> 2. Parser CSV header token mapping resilience without positional assumptions,
> 3. Cryptographic provenance storage (verbatim response bytes and SHA-256 recording), and
> 4. Geometric vector transformation mechanics in the project pipeline.
> 
> **Explicit Non-Endorsement:** This verdict does **NOT** signify that:
> - Scientific agreement on the apparent track has been established,
> - Relativistic gravitational deflection equivalence has been modeled or validated,
> - The provisional 2000–2040 frame rotation bound has been independently verified, or
> - Production scientific validation acceptance has been achieved.
> 
> All numerical acceptance thresholds remain strictly provisional pending derivation of a formal error budget.

### Scientific Justification:
1. **Frame Realization Differences Quantified as Provisional Bound:** The DE421 ME (Horizons) vs DE440 ME (LUNA-SCOPE) orientation difference is bounded at $\Delta \theta \le 0.063\text{ arcsec}$ ($53.4\text{ cm}$ surface offset) for 2000–2040 based on NAIF kernel commentary. While provisional pending independent reproduction, this value is three orders of magnitude smaller than the provisional validation tolerance of $0.05^\circ$ ($180\text{ arcsec}$), directionally establishing that direct coordinate transfer is mathematically valid for pilot capture.
2. **`APPARENT='AIRLESS'` Semantics Verified:** Documented that `AIRLESS` designates the vacuum atmospheric model (no atmospheric refraction), while apparent physical corrections (light-time, stellar aberration, gravitational deflection) are intrinsic to Horizons apparent observer tables.
3. **Complete Kinematic Transformation Formulated:** The geometric state comparison pipeline is fully defined across inertial translation, rotating-frame kinematics (including Coriolis transport velocity), and local ENU basis transformation.
4. **Altitude Semantics Clarified:** The pilot observer is explicitly defined at the reference sphere ($0.0\text{ km}$ altitude, $R = 1737.400\text{ km}$), validating API and parser mechanics without conflation with physical lander topography.
5. **Audited SPICE Kernels:** All seven canonical kernels are present on disk and cryptographically verified against local file bytes.
6. **Execution Scope Preserved:** Live capture, catalog modification, and Phase 3 remain held until this specification and the subsequent pilot capture are formally executed under controlled conditions.
7. *(E1-R6)* **`TIME_ZONE` Semantics & Vector Query Cleanliness:** `TIME_ZONE` is correctly documented as a local civil-time offset relative to UT (+00:00 introduces zero civil offset for this pilot) and is strictly omitted from vector queries where it is unsupported.
8. *(E1-R6)* **Apparent Residual Decomposed & Gravitational Deflection Qualified:** §6a enumerates seven independent residual sources without inventing numerical magnitudes. Relativistic gravitational deflection is explicitly recognized as not modeled by SPICE `LT+S` or `CN+S`, preserving it as an unresolved systematic contribution requiring a dedicated model.
9. *(E1-R6)* **Unified Provenance & Time-Verification Boundaries:** Temporal provenance fields are strictly unified (`requested_epoch_raw`, `requested_epoch_utc_label`, `returned_epoch_string`, `spice_et_sec`), and verification boundaries are explicitly stated (label consistency is verified; internal TDB equivalence is not observable from UTC returns).
10. *(E1-R6)* **Site SPK Alternative Clarified:** The primary geometric observer-state method is the Moon-centre SPK state plus transformed lunar-site offset; `spkezr` with a site SPK ID is documented as an optional alternative requiring a loaded site SPK object that does not exist in the canonical kernel set.

---

**Specification Author:** Antigravity (AGY) — Scientific Validation Assistant  
**Approved for Review:** 2026-11-15
