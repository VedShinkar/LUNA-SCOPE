"""
LUNA-SCOPE Scenario Comparison Engine

Compares lunar mission scenarios using
feasibility and preliminary weighted scores.

Initial inputs are synthetic test data.
"""

from .recommendations import generate_recommendation


def compare_scenarios(site_ids, profile_id):

    # Validate the site list.
    if not isinstance(site_ids, list) or not site_ids:
        raise ValueError("Site IDs must be a non-empty list.")

    # Reject invalid site IDs.
    if any(
        not isinstance(site_id, str) or not site_id.strip()
        for site_id in site_ids
    ):
        raise ValueError("Every site ID must be a non-empty string.")

    # Reject duplicate site IDs.
    if len(site_ids) != len(set(site_ids)):
        raise ValueError("Duplicate site IDs are not allowed.")

    results = []

    # Evaluate each lunar location.
    for site_id in site_ids:

        result = generate_recommendation(
            site_id,
            profile_id
        )

        results.append(result)

    # Define transparent comparison priority.
        # Sort all sites by overall score, highest first.
    # Feasibility remains independent of ranking.
    results.sort(
        key=lambda item: (
            item.get("overall_score") is None,
            -(item.get("overall_score")
              if item.get("overall_score") is not None else 0),
            item["site_id"]
        )
    )

    # Assign ranks to all sites with an available score.
    current_rank = 0
    previous_score = None

    for position, result in enumerate(results, start=1):
        score = result.get("overall_score")

        if score is None:
            result["rank"] = None
            continue

        if score != previous_score:
            current_rank = position

        result["rank"] = current_rank
        previous_score = score

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

