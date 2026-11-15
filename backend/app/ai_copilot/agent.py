"""
LUNA-SCOPE AI Mission Copilot.

Local deterministic tool-using decision-support agent.
Uses existing scientific functions.
No external API or paid LLM required.
"""

import json
import re
import uuid

from app.ai_copilot.tools import execute_tool


SESSIONS = {}

DEFAULT_PROFILE = "ROVER_EXPLORATION_V1"

SYNTHETIC_NOTICE = (
    "SCIENTIFIC DATA WARNING: The current Mission Intelligence "
    "site fixtures and mission profile are marked SYNTHETIC_EXAMPLE. "
    "These are illustrative software-test values, not verified "
    "NASA measurements. They must not be used for real mission planning."
)

SITE_ALIASES = {
    "shackleton rim": "SHACKLETON_RIM",
    "shackleton": "SHACKLETON_RIM",
    "malapert massif": "MALAPERT_MASSIF",
    "malapert": "MALAPERT_MASSIF",
    "de gerlache rim": "DE_GERLACHE_RIM",
    "de gerlache": "DE_GERLACHE_RIM",
    "gerlache": "DE_GERLACHE_RIM",
}


# --------------------------------------------------
# SESSION MANAGEMENT
# --------------------------------------------------

def get_session(session_id=None):
    """Create or retrieve an in-memory conversation session."""

    if not session_id:
        session_id = str(uuid.uuid4())

    if session_id not in SESSIONS:
        SESSIONS[session_id] = {
            "last_site_ids": [],
            "last_active_site": None,
            "last_profile": DEFAULT_PROFILE,
            "history": []
        }

    return session_id, SESSIONS[session_id]


# --------------------------------------------------
# SITE IDENTIFICATION AND FOLLOW-UP HANDLING
# --------------------------------------------------

def identify_sites(question, session):
    """Identify named sites or resolve basic follow-up references."""

    text = question.lower()

    found = [
        site_id
        for alias, site_id in SITE_ALIASES.items()
        if re.search(r"\b" + re.escape(alias) + r"\b", text)
    ]

    found = list(dict.fromkeys(found))

    # Explicitly named sites take priority.
    if found:
        session["last_site_ids"] = found
        session["last_active_site"] = found[-1]
        return found

    # Handle requests referring to another site after a comparison.
    other_site_phrases = [
        "other site",
        "another site",
        "remaining site",
        "second site"
    ]

    if any(phrase in text for phrase in other_site_phrases):

        previous_sites = session.get("last_site_ids", [])
        active_site = session.get("last_active_site")

        alternatives = [
            site for site in previous_sites
            if site != active_site
        ]

        if alternatives:
            selected_site = alternatives[0]
            session["last_active_site"] = selected_site
            return [selected_site]

    # Handle follow-up questions referring to the active site.
    follow_up_phrases = [
        "its",
        "their",
        "this site",
        "that site",
        "the site",
        "what about",
        "tell me more",
        "what are the risks",
        "what about its risks",
        "terrain there",
        "explain further",
        "more details"
    ]

    if any(phrase in text for phrase in follow_up_phrases):

        active_site = session.get("last_active_site")

        if active_site:
            return [active_site]

        return session.get("last_site_ids", [])

    return []


# --------------------------------------------------
# TOOL RESULT VALIDATION
# --------------------------------------------------

def format_tool_result(result):
    """Ensure tools return a dictionary."""

    if not isinstance(result, dict):
        return {
            "success": False,
            "error": "The scientific tool returned an unexpected result."
        }

    return result


# --------------------------------------------------
# ASSESSMENT SCORE EXTRACTION
# --------------------------------------------------

def extract_overall_score(assessment):
    """Extract score from assessment.score.overall."""

    if not isinstance(assessment, dict):
        return None

    score_data = assessment.get("score")

    if isinstance(score_data, dict):
        return score_data.get("overall")

    return None


# --------------------------------------------------
# TERRAIN SUMMARY FORMATTING
# --------------------------------------------------

def format_terrain_summary(terrain_data):
    """Format terrain metrics, hazards, uncertainty and provenance."""

    if not isinstance(terrain_data, dict):
        return "Terrain summary is unavailable."

    sections = {
        "ELEVATION SUMMARY": terrain_data.get("elevation_summary"),
        "SLOPE SUMMARY": terrain_data.get("slope_summary"),
        "ROUGHNESS SUMMARY": terrain_data.get("roughness_summary"),
        "OBSERVATION AND UNCERTAINTY": (
            terrain_data.get("epistemic_quality_and_observation")
        ),
        "HAZARD SCREENING": terrain_data.get("hazard_screening_summary"),
        "DATA PROVENANCE": terrain_data.get("data_provenance")
    }

    output = []

    for title, value in sections.items():

        output.append("")
        output.append(title)
        output.append("-" * 35)

        if value is None:
            output.append(
                "Information not available in the terrain report."
            )
        else:
            output.append(
                json.dumps(value, indent=2, default=str)
            )

    output.append("")
    output.append("SCIENTIFIC LIMITATIONS")
    output.append("-" * 35)

    limitations = terrain_data.get("scientific_limitations")

    if limitations:
        for limitation in limitations:
            output.append(f"- {limitation}")
    else:
        output.append("No limitations reported.")

    return "\n".join(output)


# --------------------------------------------------
# MAIN COPILOT FUNCTION
# --------------------------------------------------

def ask_copilot(question: str, session_id=None) -> dict:
    """Process a mission question using deterministic scientific tools."""

    if not isinstance(question, str) or not question.strip():
        return {
            "success": False,
            "error": "Please enter a mission question."
        }

    if len(question) > 5000:
        return {
            "success": False,
            "error": "Question exceeds 5000 characters."
        }

    question = question.strip()
    text = question.lower()

    session_id, session = get_session(session_id)

    sites = identify_sites(question, session)
    profile = session["last_profile"]

    tools_used = []
    evidence = []

    # Ask for clarification when no site is identified.
    if not sites:
        return {
            "success": True,
            "session_id": session_id,
            "question": question,
            "answer": (
                "Which lunar landing site would you like me to investigate?\n\n"
                "Available sites:\n"
                "- Shackleton Rim\n"
                "- Malapert Massif\n"
                "- de Gerlache Rim"
            ),
            "tools_used": [],
            "evidence": [],
            "data_notice": SYNTHETIC_NOTICE
        }

    # --------------------------------------------------
    # REQUEST DETECTION
    # --------------------------------------------------

    comparison_requested = (
        len(sites) >= 2
        or any(word in text for word in ["compare", "comparison", "rank"])
    )

    terrain_requested = any(
        word in text
        for word in [
            "terrain",
            "slope",
            "hazard",
            "roughness",
            "elevation",
            "uncertainty",
            "provenance"
        ]
    )

    assessment_requested = any(
        word in text
        for word in [
            "suitable",
            "feasible",
            "feasibility",
            "score",
            "recommend",
            "risk",
            "mission",
            "compare",
            "assessment",
            "rank",
            "constraint"
        ]
    )

    # Comparison needs at least two sites.
    if comparison_requested and len(sites) < 2:
        return {
            "success": True,
            "session_id": session_id,
            "question": question,
            "answer": (
                "Please identify at least two lunar sites for comparison."
            ),
            "tools_used": [],
            "evidence": [],
            "data_notice": SYNTHETIC_NOTICE
        }

    # --------------------------------------------------
    # EXECUTE SCIENTIFIC TOOLS
    # --------------------------------------------------

    if comparison_requested:

        result = execute_tool(
            "compare_landing_sites",
            {
                "site_ids": sites,
                "mission_profile_id": profile
            }
        )

        result = format_tool_result(result)

        tools_used.append("compare_landing_sites")
        evidence.append(result)

        # Remember the highest-ranked site for follow-up questions.
        comparison = result.get("comparison", [])

        if result.get("success") and isinstance(comparison, list):

            ranked_sites = sorted(
                (
                    item for item in comparison
                    if isinstance(item, dict)
                ),
                key=lambda item: (
                    item.get("rank") is None,
                    item.get("rank") or 999
                )
            )

            if ranked_sites:
                top_site = ranked_sites[0].get("site_id")

                if top_site:
                    session["last_active_site"] = top_site

    else:

        for site_id in sites:

            # Retrieve terrain information when requested.
            if terrain_requested:

                result = execute_tool(
                    "terrain_information",
                    {"site_id": site_id}
                )

                tools_used.append("terrain_information")
                evidence.append(format_tool_result(result))

            # Retrieve mission assessment when requested.
            if assessment_requested or not terrain_requested:

                result = execute_tool(
                    "site_assessment",
                    {
                        "site_id": site_id,
                        "mission_profile_id": profile
                    }
                )

                tools_used.append("site_assessment")
                evidence.append(format_tool_result(result))

    # --------------------------------------------------
    # SEPARATE SUCCESSFUL AND FAILED RESULTS
    # --------------------------------------------------

    successful_results = [
        item for item in evidence
        if isinstance(item, dict) and item.get("success")
    ]

    failed_results = [
        item for item in evidence
        if isinstance(item, dict) and not item.get("success")
    ]

    # --------------------------------------------------
    # BUILD RESPONSE
    # --------------------------------------------------

    answer_parts = [
        "LUNA-SCOPE AI MISSION COPILOT",
        "",
        f"Mission profile: {profile}",
        f"Sites investigated: {', '.join(sites)}",
        ""
    ]

    comparison_found = False

    # --------------------------------------------------
    # PROCESS COMPARISON RESULTS
    # --------------------------------------------------

    for result in successful_results:

        comparison = result.get("comparison")

        if isinstance(comparison, list) and comparison:

            comparison_found = True

            ranked_sites = sorted(
                (
                    item for item in comparison
                    if isinstance(item, dict)
                ),
                key=lambda item: (
                    item.get("rank") is None,
                    item.get("rank") or 999
                )
            )

            answer_parts.extend([
                "MISSION SITE COMPARISON",
                "=" * 35
            ])

            for site in ranked_sites:

                name = site.get(
                    "site_name",
                    site.get("site_id", "Unknown site")
                )

                feasibility = site.get("feasibility", "UNKNOWN")
                score = site.get("overall_score", "Not available")
                rank = site.get("rank")

                answer_parts.extend([
                    "",
                    f"Site: {name}",
                    f"Feasibility: {feasibility}",
                    f"Overall score: {score}",
                    (
                        f"Rank: {rank}"
                        if rank is not None
                        else "Rank: Not available"
                    )
                ])

                failures = site.get("failed_constraints", [])

                if failures:
                    answer_parts.append("Failed requirements:")

                    for failure in failures:
                        answer_parts.append(f"- {failure}")

                risks = site.get("risk_factors", [])

                if risks:
                    answer_parts.append("Risk factors:")

                    for risk in risks:
                        answer_parts.append(f"- {risk}")

                recommendation = site.get("recommendation")

                if recommendation:
                    answer_parts.append(
                        f"Assessment: {recommendation}"
                    )

            # Identify the first-ranked feasible site.
            recommended_site = next(
                (
                    site for site in ranked_sites
                    if site.get("rank") == 1
                    and site.get("feasibility") == "FEASIBLE"
                ),
                None
            )

            answer_parts.extend([
                "",
                "MISSION RECOMMENDATION",
                "=" * 35
            ])

            if recommended_site:
                name = recommended_site.get(
                    "site_name",
                    recommended_site.get("site_id")
                )

                answer_parts.append(
                    f"{name} ranks first and satisfies the "
                    "configured mandatory mission requirements."
                )
            else:
                answer_parts.append(
                    "No first-ranked feasible site was identified "
                    "in the comparison results."
                )

    # --------------------------------------------------
    # PROCESS TERRAIN RESULTS
    # --------------------------------------------------

    for result in successful_results:

        terrain_data = result.get("terrain_data")

        if not isinstance(terrain_data, dict):
            continue

        answer_parts.extend([
            "",
            "LUNAR TERRAIN ANALYSIS",
            "=" * 35,
            f"Site: {terrain_data.get('site_name', result.get('site_id', 'Unknown'))}",
            f"Terrain ID: {terrain_data.get('site_id', 'Unknown')}",
            format_terrain_summary(terrain_data)
        ])

    # --------------------------------------------------
    # PROCESS INDIVIDUAL SITE ASSESSMENTS
    # --------------------------------------------------

    if not comparison_found:

        for result in successful_results:

            assessment = result.get("assessment")

            if not isinstance(assessment, dict):
                continue

            answer_parts.extend([
                "",
                "MISSION SITE ASSESSMENT",
                "=" * 35,
                (
                    f"Site: {assessment.get('site_name', assessment.get('site_id', 'Unknown'))}"
                ),
                f"Feasibility: {assessment.get('feasibility', 'UNKNOWN')}"
            ])

            # Correct extraction: assessment.score.overall
            score = extract_overall_score(assessment)

            if score is not None:
                answer_parts.append(f"Overall score: {score}")
            else:
                answer_parts.append("Overall score: Not available")

            failures = assessment.get("failed_constraints", [])

            if failures:
                answer_parts.append("Failed requirements:")

                for failure in failures:
                    answer_parts.append(f"- {failure}")
            else:
                answer_parts.append("Failed requirements: None reported")

            risks = assessment.get("risk_factors", [])

            if risks:
                answer_parts.append("Risk factors:")

                for risk in risks:
                    answer_parts.append(f"- {risk}")

            recommendation = assessment.get("recommendation")

            if recommendation:
                answer_parts.append(f"Assessment: {recommendation}")

    # --------------------------------------------------
    # HANDLE TOOL ERRORS
    # --------------------------------------------------

    if failed_results:

        answer_parts.extend([
            "",
            "UNAVAILABLE INFORMATION"
        ])

        for failure in failed_results:
            answer_parts.append(
                failure.get("error", "Unknown scientific tool error.")
            )

    if not successful_results and not failed_results:
        answer_parts.append(
            "No scientific evidence was returned by the tools."
        )

    # --------------------------------------------------
    # SCIENTIFIC DATA DISCLOSURE
    # --------------------------------------------------

    answer_parts.extend([
        "",
        "SCIENTIFIC DATA WARNING",
        SYNTHETIC_NOTICE,
        "",
        "SYSTEM NOTE",
        "This Copilot uses deterministic question routing "
        "and existing LUNA-SCOPE scientific tools.",
        "It is not a live LLM-generated scientific conclusion."
    ])

    answer = "\n".join(answer_parts)

    # --------------------------------------------------
    # STORE CONVERSATION HISTORY
    # --------------------------------------------------

    session["history"].append({
        "question": question,
        "sites": sites,
        "tools_used": tools_used
    })

    session["history"] = session["history"][-10:]

    return {
        "success": True,
        "session_id": session_id,
        "question": question,
        "answer": answer,
        "tools_used": tools_used,
        "evidence": evidence,
        "data_notice": SYNTHETIC_NOTICE
    }