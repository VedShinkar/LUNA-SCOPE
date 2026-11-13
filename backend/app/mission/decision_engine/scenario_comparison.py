"""
LUNA-SCOPE Scenario Comparison Engine

Compares lunar mission scenarios using
feasibility and preliminary weighted scores.

Initial inputs are synthetic test data.
"""

from .recommendations import generate_recommendation


def compare_scenarios(site_ids, profile_id):

    results = []

    # Evaluate each lunar location
    for site_id in site_ids:

        result = generate_recommendation(
            site_id,
            profile_id
        )

        results.append(result)

    # Rank feasible locations first.
    # Within each feasibility group, use score.
    status_priority = {
        "FEASIBLE": 0,
        "INSUFFICIENT_DATA": 1,
        "NOT_FEASIBLE": 2
    }

    results.sort(
        key=lambda item: (
            status_priority[item["feasibility"]],
            -(item["overall_score"] or 0)
        )
    )

    # Assign ranks
    for rank, result in enumerate(results, start=1):

        result["rank"] = rank

    return results


if __name__ == "__main__":

    sites = [
        "SHACKLETON_RIM",
        "MALAPERT_MASSIF",
        "DE_GERLACHE_RIM"
    ]

    profile_id = "ROVER_EXPLORATION_V1"

    comparison = compare_scenarios(
        sites,
        profile_id
    )

    print("\nLUNA-SCOPE SCENARIO COMPARISON")
    print("=" * 55)

    for result in comparison:

        print("\nRank:", result["rank"])

        print("Location:", result["site_name"])

        print("Feasibility:", result["feasibility"])

        print("Score:", result["overall_score"])

        print("Risks:", result["risk_factors"])

        print("-" * 55)

    print("\nCOMPARISON COMPLETE")