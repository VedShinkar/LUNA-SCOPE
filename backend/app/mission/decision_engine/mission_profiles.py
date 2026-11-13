"""
LUNA-SCOPE Mission Profiles

Stores and validates mission requirements and scoring weights.

Initial profile values follow the team's API contract example.
"""

import math
from numbers import Real


REQUIRED_WEIGHT_KEYS = {
    "solar_energy",
    "communication",
    "terrain",
    "illumination"
}

REQUIRED_REQUIREMENT_KEYS = {
    "minimum_sunlight_hours",
    "minimum_earth_visibility_hours",
    "minimum_solar_energy_wh",
    "maximum_slope_deg",
    "maximum_terrain_hazard_score"
}


MISSION_PROFILES = {
    "ROVER_EXPLORATION_V1": {
        "mission_name": "Lunar Rover Exploration",

        "requirements": {
            "minimum_sunlight_hours": 100,
            "minimum_earth_visibility_hours": 120,
            "minimum_solar_energy_wh": 700,
            "maximum_slope_deg": 10,
            "maximum_terrain_hazard_score": 0.5
        },

        "weights": {
            "solar_energy": 0.30,
            "communication": 0.25,
            "terrain": 0.30,
            "illumination": 0.15
        },

        "weight_scale": "0_to_1",
        "profile_status": "SYNTHETIC_EXAMPLE"
    }
}


def validate_weights(profile):
    """
    Validate scoring weights.

    All required weights must:
    - Exist
    - Be numeric and finite
    - Be non-negative
    - Sum to 1.0
    """

    if not isinstance(profile, dict):
        raise ValueError("Mission profile must be a dictionary.")

    weights = profile.get("weights")

    if not isinstance(weights, dict):
        raise ValueError("Mission profile weights must be a dictionary.")

    if set(weights) != REQUIRED_WEIGHT_KEYS:
        raise ValueError(
            "Scoring weights must contain exactly these keys: "
            f"{sorted(REQUIRED_WEIGHT_KEYS)}"
        )

    for name, value in weights.items():

        if (
            isinstance(value, bool)
            or not isinstance(value, Real)
            or not math.isfinite(value)
        ):
            raise ValueError(
                f"Weight '{name}' must be a finite number."
            )

        if value < 0:
            raise ValueError(
                f"Weight '{name}' cannot be negative."
            )

    total = sum(weights.values())

    if not math.isclose(
        total,
        1.0,
        rel_tol=0,
        abs_tol=1e-6
    ):
        raise ValueError(
            f"Scoring weights must sum to 1.0. Found: {total}"
        )

    return True


def validate_mission_profile(profile):
    """
    Validate mission profile structure and requirements.
    """

    validate_weights(profile)

    requirements = profile.get("requirements")

    if not isinstance(requirements, dict):
        raise ValueError(
            "Mission requirements must be a dictionary."
        )

    if set(requirements) != REQUIRED_REQUIREMENT_KEYS:
        raise ValueError(
            "Mission requirements must contain exactly these keys: "
            f"{sorted(REQUIRED_REQUIREMENT_KEYS)}"
        )

    for name, value in requirements.items():

        if (
            isinstance(value, bool)
            or not isinstance(value, Real)
            or not math.isfinite(value)
        ):
            raise ValueError(
                f"Requirement '{name}' must be a finite number."
            )

        if value < 0:
            raise ValueError(
                f"Requirement '{name}' cannot be negative."
            )

    hazard_limit = requirements["maximum_terrain_hazard_score"]

    if not 0 <= hazard_limit <= 1:
        raise ValueError(
            "Maximum terrain hazard score must be between 0 and 1."
        )

    slope_limit = requirements["maximum_slope_deg"]

    if not 0 <= slope_limit <= 90:
        raise ValueError(
            "Maximum slope must be between 0 and 90 degrees."
        )

    if profile.get("weight_scale") != "0_to_1":
        raise ValueError(
            "Mission profile weight_scale must be '0_to_1'."
        )

    return True


def get_mission_profile(profile_id):
    """
    Retrieve and validate a mission profile.
    """

    if profile_id not in MISSION_PROFILES:
        raise ValueError(
            f"Mission profile '{profile_id}' was not found."
        )

    profile = MISSION_PROFILES[profile_id]

    validate_mission_profile(profile)

    return profile


if __name__ == "__main__":

    profile = get_mission_profile("ROVER_EXPLORATION_V1")

    print("Mission Profile Loaded Successfully!")
    print("Mission:", profile["mission_name"])
    print("Requirements:", profile["requirements"])
    print("Scoring Weights:", profile["weights"])
    print("Weights Valid:", validate_weights(profile))
    print("Profile Valid:", validate_mission_profile(profile))