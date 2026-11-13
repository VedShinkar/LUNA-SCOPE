"""
LUNA-SCOPE Mission Profiles

Stores mission requirements and scoring weights
used by the Mission Decision Engine.

Initial values follow the team's API contract example.
"""

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


def get_mission_profile(profile_id):

    """
    Retrieve a mission profile using its ID.
    """

    if profile_id not in MISSION_PROFILES:
        raise ValueError(
            f"Mission profile '{profile_id}' was not found."
        )

    return MISSION_PROFILES[profile_id]


def validate_weights(profile):

    """
    Check whether scoring weights add up to 1.0.
    """

    weights = profile["weights"]

    total = sum(weights.values())

    if abs(total - 1.0) > 0.000001:
        raise ValueError(
            f"Scoring weights must add up to 1.0. Found: {total}"
        )

    return True


if __name__ == "__main__":

    profile = get_mission_profile("ROVER_EXPLORATION_V1")

    validate_weights(profile)

    print("Mission Profile Loaded Successfully!")

    print("Mission:", profile["mission_name"])

    print("Requirements:", profile["requirements"])

    print("Scoring Weights:", profile["weights"])

    print("Weights Valid:", validate_weights(profile))