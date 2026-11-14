"""
LUNA-SCOPE Mission Feasibility Checker

Checks whether a lunar location satisfies
the mandatory mission requirements.

Initial inputs are synthetic test data.
"""

import math
from numbers import Real

from .mission_profiles import get_mission_profile
from .mock_data import get_lunar_site


# Physical limits for lunar site measurements.
SITE_MEASUREMENT_LIMITS = {
    "sunlight_hours": (0, None),
    "earth_visibility_hours": (0, None),
    "solar_energy_wh": (0, None),
    "slope_deg": (0, 90),
    "terrain_hazard_score": (0, 1)
}


def validate_site_measurements(site):
    """
    Validate physical measurements before feasibility calculations.

    Missing values are allowed and handled as INSUFFICIENT_DATA.
    Invalid values raise ValueError.
    """

    for field, (minimum, maximum) in SITE_MEASUREMENT_LIMITS.items():

        actual = site.get(field)

        # Missing measurements are handled separately.
        if actual is None:
            continue

        # Reject booleans, strings and other non-numeric values.
        if (
            isinstance(actual, bool)
            or not isinstance(actual, Real)
        ):
            raise ValueError(
                f"Invalid measurement '{field}': "
                "value must be numeric."
            )

        # Reject NaN and infinity.
        if not math.isfinite(actual):
            raise ValueError(
                f"Invalid measurement '{field}': "
                "value must be finite."
            )

        # Check minimum physical limit.
        if actual < minimum:
            raise ValueError(
                f"Invalid measurement '{field}': "
                f"value cannot be below {minimum}."
            )

        # Check maximum physical limit where applicable.
        if maximum is not None and actual > maximum:
            raise ValueError(
                f"Invalid measurement '{field}': "
                f"value cannot exceed {maximum}."
            )

    return True


def check_feasibility(site_id, profile_id):

    # Load validated mission profile and lunar site.
    profile = get_mission_profile(profile_id)
    site = get_lunar_site(site_id)

    # Validate physical measurements before calculations.
    validate_site_measurements(site)

    requirements = profile["requirements"]

    checks = {

        "minimum_sunlight_hours": (
            site.get("sunlight_hours"),
            ">=",
            requirements["minimum_sunlight_hours"]
        ),

        "minimum_earth_visibility_hours": (
            site.get("earth_visibility_hours"),
            ">=",
            requirements["minimum_earth_visibility_hours"]
        ),

        "minimum_solar_energy_wh": (
            site.get("solar_energy_wh"),
            ">=",
            requirements["minimum_solar_energy_wh"]
        ),

        "maximum_slope_deg": (
            site.get("slope_deg"),
            "<=",
            requirements["maximum_slope_deg"]
        ),

        "maximum_terrain_hazard_score": (
            site.get("terrain_hazard_score"),
            "<=",
            requirements["maximum_terrain_hazard_score"]
        )

    }

    results = []
    failed_constraints = []
    missing_inputs = []

    # Check each mission requirement.
    for requirement, (actual, operator, required) in checks.items():

        if actual is None:

            missing_inputs.append(requirement)

            results.append({
                "requirement": requirement,
                "status": "INSUFFICIENT_DATA",
                "actual": None,
                "required": required
            })

            continue

        if operator == ">=":
            passed = actual >= required
        else:
            passed = actual <= required

        status = "PASS" if passed else "FAIL"

        result = {
            "requirement": requirement,
            "status": status,
            "actual": actual,
            "required": required
        }

        results.append(result)

        if not passed:
            failed_constraints.append(result)

        # Determine overall feasibility.
    # A confirmed mandatory failure takes priority over missing data.
    if failed_constraints:
        feasibility = "NOT_FEASIBLE"

    elif missing_inputs:
        feasibility = "INSUFFICIENT_DATA"

    else:
        feasibility = "FEASIBLE"

    return {

        "site_id": site_id,

        "site_name": site["site_name"],

        "mission_profile_id": profile_id,

        "feasibility": feasibility,

        "constraint_results": results,

        "failed_constraints": failed_constraints,

        "missing_inputs": missing_inputs,

        "data_status": site.get(
            "data_status",
            "INSUFFICIENT_DATA"
        )

    }


if __name__ == "__main__":

    sites = [
        "SHACKLETON_RIM",
        "MALAPERT_MASSIF",
        "DE_GERLACHE_RIM"
    ]

    profile_id = "ROVER_EXPLORATION_V1"

    print("\nLUNA-SCOPE MISSION FEASIBILITY REPORT")
    print("=" * 45)

    for site_id in sites:

        assessment = check_feasibility(
            site_id,
            profile_id
        )

        print("\nSite:", assessment["site_name"])

        print("Feasibility:", assessment["feasibility"])

        print("\nRequirement Results:")

        for result in assessment["constraint_results"]:

            print(
                result["requirement"],
                ":",
                result["status"]
            )

        print(
            "\nFailed Constraints:",
            len(assessment["failed_constraints"])
        )

        print("Data Status:", assessment["data_status"])

        print("-" * 45)