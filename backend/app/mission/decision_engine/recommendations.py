"""
LUNA-SCOPE Mission Recommendations

Generates explanations and risk factors
from structured mission assessment results.

Initial results use synthetic test data.
"""

from .feasibility import check_feasibility
from .scoring_engine import calculate_site_score


def generate_recommendation(site_id, profile_id):

    # Get feasibility and scoring results
    feasibility = check_feasibility(site_id, profile_id)

    scoring = calculate_site_score(site_id, profile_id)

    risks = []
    explanations = []

    # Handle missing data
    if feasibility["feasibility"] == "INSUFFICIENT_DATA":

        return {
            "site_id": site_id,
            "site_name": feasibility["site_name"],
            "feasibility": "INSUFFICIENT_DATA",
            "overall_score": None,
            "missing_inputs": feasibility["missing_inputs"],
            "risk_factors": [
                "Required mission data is missing."
            ],
            "recommendation": (
                "More reliable scientific data is required "
                "before evaluating this location."
            ),
            "data_status": feasibility["data_status"]
        }

    # Identify failed requirements
    for failure in feasibility["failed_constraints"]:

        requirement = failure["requirement"]

        actual = failure["actual"]

        required = failure["required"]

        risks.append(requirement)

        explanations.append(
            f"{requirement} failed: "
            f"actual value is {actual}, "
            f"required value is {required}."
        )

    # Generate recommendation
    if feasibility["feasibility"] == "FEASIBLE":

        recommendation = (
            "This location satisfies all configured "
            "mandatory mission requirements. "
            "It can be considered for further mission planning."
        )

    else:

        recommendation = (
            "This location does not satisfy all mandatory "
            "mission requirements. Review the failed constraints "
            "before considering it for the mission."
        )

    # Add data limitation
    if feasibility["data_status"] == "SYNTHETIC_EXAMPLE":

        risks.append("Synthetic test data")

        recommendation += (
            " This assessment uses synthetic test data "
            "and must not be treated as a real lunar site evaluation."
        )

    return {

        "site_id": site_id,

        "site_name": feasibility["site_name"],

        "feasibility": feasibility["feasibility"],

        "overall_score": scoring["overall_score"],
        "criterion_scores": scoring.get("criterion_scores"),

        "risk_factors": risks,

        "failed_constraints": explanations,

        "recommendation": recommendation,

        "data_status": feasibility["data_status"]

    }


if __name__ == "__main__":

    sites = [
        "SHACKLETON_RIM",
        "MALAPERT_MASSIF",
        "DE_GERLACHE_RIM"
    ]

    profile_id = "ROVER_EXPLORATION_V1"

    print("\nLUNA-SCOPE MISSION RECOMMENDATIONS")
    print("=" * 55)

    for site_id in sites:

        result = generate_recommendation(
            site_id,
            profile_id
        )

        print("\nLocation:", result["site_name"])

        print("Feasibility:", result["feasibility"])

        print("Score:", result["overall_score"])

        print("\nRisk Factors:")

        for risk in result["risk_factors"]:

            print("-", risk)

        print("\nExplanation:")

        for explanation in result.get(
            "failed_constraints", []
        ):

            print("-", explanation)

        print("\nRecommendation:")

        print(result["recommendation"])

        print("\nData Status:", result["data_status"])

        print("-" * 55)