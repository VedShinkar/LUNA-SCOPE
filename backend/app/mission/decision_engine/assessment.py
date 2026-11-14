
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


def classify_provenance(site):
    """
    Classify the provenance and verification status of site data.

    Possible classifications:
    SYNTHETIC
    VERIFIED
    UNVERIFIED
    MISSING_PROVENANCE
    UNKNOWN
    """

    source_status = site.get("data_status", "UNKNOWN")

    provenance = site.get("provenance")
    data_source = site.get("data_source")

    # Synthetic data is never treated as scientifically verified.
    if source_status == "SYNTHETIC_EXAMPLE":
        return "SYNTHETIC"

    # Reject unrecognised data statuses.
    if source_status != "AVAILABLE":
        return "UNKNOWN"

    # Provenance must be provided as a dictionary.
    if not isinstance(provenance, dict):
        return "MISSING_PROVENANCE"

    # A data source must be identified.
    if not isinstance(data_source, str) or not data_source.strip():
        return "MISSING_PROVENANCE"

    # Check required provenance fields.
    required_fields = [
        "provider",
        "product",
        "product_version",
        "processing_lineage",
        "verification_status"
    ]

    for field in required_fields:

        if field not in provenance:
            return "MISSING_PROVENANCE"

    # Provider, product and version must contain valid text.
    text_fields = [
        "provider",
        "product",
        "product_version",
        "verification_status"
    ]

    for field in text_fields:

        value = provenance.get(field)

        if not isinstance(value, str) or not value.strip():
            return "MISSING_PROVENANCE"

    # Processing lineage must be a non-empty list.
    processing_lineage = provenance.get("processing_lineage")

    if not isinstance(processing_lineage, list):
        return "MISSING_PROVENANCE"

    if not processing_lineage:
        return "MISSING_PROVENANCE"

    if not all(
        isinstance(step, str) and step.strip()
        for step in processing_lineage
    ):
        return "MISSING_PROVENANCE"

    # Verification must be explicitly established.
    if provenance["verification_status"] != "VERIFIED":
        return "UNVERIFIED"

    return "VERIFIED"


def assess_mission(
    site_id,
    profile_id
):
    """
    Perform a complete mission assessment for a lunar site.
    """

    # Retrieve the original site information.
    site = get_lunar_site(site_id)

    # Run the individual assessment components.
    feasibility = check_feasibility(
        site_id,
        profile_id
    )

    scoring = calculate_site_score(
        site_id,
        profile_id,
        feasibility_result=feasibility
    )

    recommendation = generate_recommendation(
        site_id,
        profile_id,
        feasibility_result=feasibility,
        scoring_result=scoring
   )  

    # Identify missing information.
    missing_inputs = feasibility["missing_inputs"]

    # Determine the original data status.
    source_status = site.get(
        "data_status",
        "UNKNOWN"
    )

    # Preserve insufficient-data status from feasibility.
    if feasibility["feasibility"] == "INSUFFICIENT_DATA":
        data_status = "INSUFFICIENT_DATA"
    else:
        data_status = source_status

    # Read provenance information.
    data_source = site.get("data_source")
    provenance = site.get("provenance")
    source_limitations = site.get("limitations", [])

    # Classify provenance and verification status.
    provenance_status = classify_provenance(site)

    # Generate limitations dynamically.
    limitations = []

    if provenance_status == "SYNTHETIC":

        limitations.append(
            "This assessment uses synthetic example data, "
            "not verified scientific measurements."
        )

    elif provenance_status == "VERIFIED":

        limitations.append(
            "Data provenance and verification metadata are provided. "
            "Scientific suitability still requires independent validation."
        )

    elif provenance_status == "UNVERIFIED":

        limitations.append(
            "Data source information is available, "
            "but scientific verification has not been established."
        )

    elif provenance_status == "MISSING_PROVENANCE":

        limitations.append(
            "Required data provenance information is missing or incomplete."
        )

    else:

        limitations.append(
            "Data source or scientific measurement status is unknown."
        )

    # Include limitations supplied by the data source.
    if isinstance(source_limitations, list):
        limitations.extend(source_limitations)

    # General scientific limitations.
    limitations.append(
        "Preliminary scoring is a heuristic and is not "
        "a scientifically validated landing-site suitability model."
    )

    limitations.append(
        "Terrain and celestial calculations depend on the "
        "availability and validation of their respective scientific modules."
    )

    # Build the final assessment.
    assessment = {

        "site_id": site_id,

        "site_name": site["site_name"],

        "mission_profile_id": profile_id,

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

            "provenance_status": provenance_status,

            "data_source": data_source,

            "provenance": provenance,

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
            profile_id
        )

        print("\nSite:", result["site_id"])
