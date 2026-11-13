"""
LUNA-SCOPE Scoring Engine

Calculates a preliminary mission suitability score
using configurable weighted criteria.

All initial test inputs are synthetic.
The scoring method is a preliminary heuristic,
not a scientifically validated landing-site assessment.
"""

from .mission_profiles import get_mission_profile
from .mock_data import get_lunar_site
from .feasibility import check_feasibility


def calculate_percentage(actual, target, higher_is_better=True):
    """
    Convert a measurement into a score between 0 and 100.
    """

    if actual is None or target is None or target <= 0:
        return None

    if higher_is_better:
        score = (actual / target) * 100

    else:
        score = (target / actual) * 100 if actual > 0 else 100

    return min(100, max(0, score))


def calculate_site_score(site_id, profile_id):

    profile = get_mission_profile(profile_id)
    site = get_lunar_site(site_id)

    requirements = profile["requirements"]
    weights = profile["weights"]

    # Check mandatory mission requirements
    feasibility_result = check_feasibility(
        site_id,
        profile_id
    )

    # Check whether required measurements are available
    required_fields = [
        "sunlight_hours",
        "earth_visibility_hours",
        "solar_energy_wh",
        "slope_deg",
        "terrain_hazard_score"
    ]

    missing_inputs = [
        field for field in required_fields
        if site.get(field) is None
    ]

    if missing_inputs:

        return {
            "site_id": site_id,
            "feasibility": "INSUFFICIENT_DATA",
            "overall_score": None,
            "missing_inputs": missing_inputs
        }

    # 1. Solar energy score
    solar_score = calculate_percentage(
        site["solar_energy_wh"],
        requirements["minimum_solar_energy_wh"]
    )

    # 2. Communication score
    communication_score = calculate_percentage(
        site["earth_visibility_hours"],
        requirements["minimum_earth_visibility_hours"]
    )

    # 3. Terrain score
    slope_score = calculate_percentage(
        site["slope_deg"],
        requirements["maximum_slope_deg"],
        higher_is_better=False
    )

    hazard_score = calculate_percentage(
        site["terrain_hazard_score"],
        requirements["maximum_terrain_hazard_score"],
        higher_is_better=False
    )

    terrain_score = (slope_score + hazard_score) / 2

    # 4. Illumination score
    illumination_score = calculate_percentage(
        site["sunlight_hours"],
        requirements["minimum_sunlight_hours"]
    )

    criterion_scores = {
        "solar_energy": round(solar_score, 2),
        "communication": round(communication_score, 2),
        "terrain": round(terrain_score, 2),
        "illumination": round(illumination_score, 2)
    }

    # Calculate weighted overall score
    overall_score = sum(
        criterion_scores[name] * weights[name]
        for name in weights
    )

    overall_score = round(overall_score, 2)

    return {
        "site_id": site_id,
        "site_name": site["site_name"],
        "feasibility": feasibility_result["feasibility"],
        "overall_score": overall_score,
        "criterion_scores": criterion_scores,
        "failed_constraints": feasibility_result["failed_constraints"],
        "data_status": site["data_status"],
        "scoring_method": "PRELIMINARY_V1"
    }


if __name__ == "__main__":

    sites = [
        "SHACKLETON_RIM",
        "MALAPERT_MASSIF",
        "DE_GERLACHE_RIM"
    ]

    profile_id = "ROVER_EXPLORATION_V1"

    print("\nLUNA-SCOPE MISSION SCORING REPORT")
    print("=" * 50)

    for site_id in sites:

        result = calculate_site_score(
            site_id,
            profile_id
        )

        print("\nSite:", result["site_id"])

        print("Feasibility:", result["feasibility"])

        print("Overall Score:", result["overall_score"])

        if result["overall_score"] is not None:

            print("\nCriterion Scores:")

            for name, score in result["criterion_scores"].items():

                print(name, ":", score)

        print("\nData Status:", result.get("data_status"))

        print("-" * 50)