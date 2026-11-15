"""
Offline synthetic Horizons response fixtures for deterministic testing without network.

Guarantees 100% offline test execution.
"""

import json

# Synthetic Horizons geometric state-vector CSV response (VEC_TABLE=2) for Sun at Apollo 11 on 2026-01-01
SYNTHETIC_SUN_VECTOR_CSV = (
    "*******************************************************************************\n"
    "Ephemeris / VECTORS\n"
    "*******************************************************************************\n"
    " Date__(UT)__HR:MN:SS, , , X, Y, Z, VX, VY, VZ,\n"
    "$$SOE\n"
    "2026-Jan-01 00:00:00.0000, , , 1.450000000000000E+08, 2.500000000000000E+07,"
    " 1.000000000000000E+07, -5.000000000000000E+00, 2.800000000000000E+01,"
    " 1.200000000000000E+01,\n"
    "$$EOE\n"
    "*******************************************************************************\n"
)

SYNTHETIC_SUN_JSON_PAYLOAD = json.dumps({
    "signature": {"version": "1.2", "source": "NASA/JPL Horizons API"},
    "result": SYNTHETIC_SUN_VECTOR_CSV,
}).encode("utf-8")

# Synthetic Horizons geometric state-vector CSV response for Earth at Apollo 11 on 2026-01-01
SYNTHETIC_EARTH_VECTOR_CSV = (
    "*******************************************************************************\n"
    "Ephemeris / VECTORS\n"
    "*******************************************************************************\n"
    " Date__(UT)__HR:MN:SS, , , X, Y, Z, VX, VY, VZ,\n"
    "$$SOE\n"
    "2026-Jan-01 00:00:00.0000, , , 3.500000000000000E+05, -1.200000000000000E+05,"
    " -5.000000000000000E+04, 0.900000000000000E+00, 0.400000000000000E+00,"
    " 0.150000000000000E+00,\n"
    "$$EOE\n"
    "*******************************************************************************\n"
)

SYNTHETIC_EARTH_JSON_PAYLOAD = json.dumps({
    "signature": {"version": "1.2", "source": "NASA/JPL Horizons API"},
    "result": SYNTHETIC_EARTH_VECTOR_CSV,
}).encode("utf-8")
