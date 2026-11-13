"""
LUNA-SCOPE Mission Assessment

Combines feasibility, scoring and recommendations
into one structured mission assessment.

Current implementation uses synthetic test data.
"""

from .feasibility import check_feasibility
from .scoring_engine import calculate_site_score
from .recommendations import generate_recommendation
from .mock_data import get_lunar_site


def assess_mission(
    site_id,
    profile_id,
    scenario_id=None,
    equipment_profile_id=None
):

    # Retrieve the original site information
    site = get_lunar_site(site_id)

    # Run the individual assessment components
    feasibility = check_feasibility(site_id, profile_id)

    scoring = calculate_site_score(site_id, profile_id)

    recommendation = generate_recommendation(
        site_id,
        profile_id
    )

    # Identify missing information
    missing_inputs = feasibility["missing_inputs"]

    # Determine data quality status
    if feasibility["feasibility"] == "INSUFFICIENT_DATA":

        data_status = "INSUFFICIENT_DATA"

    else:

        data_status = site.get(
            "data_status",
            "INSUFFICIENT_DATA"
        )

    # Record limitations
    limitations = [
        "Current assessment uses synthetic example data.",
        "Results are not actual NASA measurements.",
        "Terrain and celestial calculations require integration "
        "with the respective scientific modules.",
        "Preliminary scoring is not a certified site-suitability model."
    ]

    # Build the final assessment
    assessment = {

        "scenario_id": scenario_id,

        "site_id": site_id,
        
        "site_name": site["site_name"],

        "mission_profile_id": profile_id,

        "equipment_profile_id": equipment_profile_id,

        "feasibility": feasibility["feasibility"],

        "failed_constraints": feasibility["failed_constraints"],

        "score": {

            "overall": scoring.get("overall_score"),

            "scale": "0_to_100",
           
            "status": "PRELIMINARY",

            "method_version": "PRELIMINARY_V1",

            "criterion_scores": scoring.get(
                "criterion_scores",
                {}
            )

        },

        "risk_factors": recommendation["risk_factors"],

        "recommendation": recommendation["recommendation"],

        "data_quality": {

            "assessment_status": data_status,

            "missing_inputs": missing_inputs,

            "limitations": limitations

        },

        "raw_inputs": site

    }

    return assessment


if __name__ == "__main__":

    sites = [
        "SHACKLETON_RIM",
        "MALAPERT_MASSIF",
        "DE_GERLACHE_RIM"
    ]

    profile_id = "ROVER_EXPLORATION_V1"

    print("\nLUNA-SCOPE COMPLETE MISSION ASSESSMENT")
    print("=" * 60)

    for site_id in sites:

        result = assess_mission(
            site_id,
            profile_id,
            scenario_id="DEMO_SCENARIO_01",
            equipment_profile_id="ROVER_BASELINE_V1"
        )

        print("\nSite:", result["site_id"])

        print("Feasibility:", result["feasibility"])

        print("Overall Score:", result["score"]["overall"])

        print("Failed Constraints:",
              len(result["failed_constraints"]))

        print("Risk Factors:", result["risk_factors"])

        print("Recommendation:", result["recommendation"])

        print("Data Quality:",
              result["data_quality"]["assessment_status"])

        print("-" * 60)