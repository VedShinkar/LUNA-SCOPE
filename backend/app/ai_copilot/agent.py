"""
LUNA-SCOPE AI Mission Copilot.

Local tool-using decision-support agent.
Uses existing deterministic scientific functions.
No external API or paid LLM required.
"""

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


def get_session(session_id=None):

    if not session_id:
        session_id = str(uuid.uuid4())

    if session_id not in SESSIONS:
        SESSIONS[session_id] = {
            "last_site_ids": [],
            "last_profile": DEFAULT_PROFILE,
            "history": []
        }

    return session_id, SESSIONS[session_id]


def identify_sites(question, session):

    text = question.lower()

    found = [
        site_id
        for alias, site_id in SITE_ALIASES.items()
        if re.search(r"\b" + re.escape(alias) + r"\b", text)
    ]

    found = list(dict.fromkeys(found))

    if not found:
        found = session["last_site_ids"]

    if found:
        session["last_site_ids"] = found

    return found


def format_tool_result(result):

    if not isinstance(result, dict):
        return {
            "success": False,
            "error": "The scientific tool returned an unexpected result."
        }

    return result


def ask_copilot(question: str, session_id=None) -> dict:

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

    # Ask for clarification if no site is identified.
    if not sites:
        return {
            "success": True,
            "session_id": session_id,
            "question": question,
            "answer": (
                "Which lunar landing site would you like me to "
                "investigate?\n\n"
                "Available sites:\n"
                "- Shackleton Rim\n"
                "- Malapert Massif\n"
                "- de Gerlache Rim"
            ),
            "tools_used": [],
            "evidence": [],
            "data_notice": SYNTHETIC_NOTICE
        }

    # Detect comparison requests.
    comparison_requested = (
        len(sites) >= 2
        or any(
            word in text
            for word in ["compare", "comparison", "rank"]
        )
    )

    # Detect terrain requests.
    terrain_requested = any(
        word in text
        for word in [
            "terrain",
            "slope",
            "hazard",
            "roughness",
            "elevation"
        ]
    )

    # Detect mission assessment requests.
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
            "rank"
        ]
    )

    # Comparison requires at least two sites.
    if comparison_requested and len(sites) < 2:
        return {
            "success": True,
            "session_id": session_id,
            "question": question,
            "answer": (
                "Please identify at least two lunar sites "
                "for comparison."
            ),
            "tools_used": [],
            "evidence": [],
            "data_notice": SYNTHETIC_NOTICE
        }

    # Execute comparison tool.
    if comparison_requested:

        result = execute_tool(
            "compare_landing_sites",
            {
                "site_ids": sites,
                "mission_profile_id": profile
            }
        )

        tools_used.append("compare_landing_sites")
        evidence.append(format_tool_result(result))

    else:

        for site_id in sites:

            # Execute terrain tool when requested.
            if terrain_requested:

                result = execute_tool(
                    "terrain_information",
                    {
                        "site_id": site_id
                    }
                )

                tools_used.append("terrain_information")
                evidence.append(format_tool_result(result))

            # Execute mission assessment.
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
    # BUILD READABLE MISSION RESPONSE
    # --------------------------------------------------

    successful_results = [
        item
        for item in evidence
        if isinstance(item, dict) and item.get("success")
    ]

    failed_results = [
        item
        for item in evidence
        if isinstance(item, dict) and not item.get("success")
    ]

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
                comparison,
                key=lambda item: (
                    item.get("rank") is None,
                    item.get("rank") or 999
                )
            )

            answer_parts.append("MISSION SITE COMPARISON")
            answer_parts.append("=" * 35)

            for site in ranked_sites:

                name = site.get(
                    "site_name",
                    site.get("site_id", "Unknown site")
                )

                feasibility = site.get(
                    "feasibility",
                    "UNKNOWN"
                )

                score = site.get(
                    "overall_score",
                    "Not available"
                )

                rank = site.get("rank")

                answer_parts.append("")
                answer_parts.append(f"Site: {name}")
                answer_parts.append(
                    f"Feasibility: {feasibility}"
                )
                answer_parts.append(
                    f"Overall score: {score}/100"
                )
                answer_parts.append(
                    f"Rank: {rank if rank is not None else 'Not ranked'}"
                )

                # Failed mission requirements.
                failed_constraints = site.get(
                    "failed_constraints",
                    []
                )

                if failed_constraints:

                    answer_parts.append("Failed requirements:")

                    for constraint in failed_constraints:
                        answer_parts.append(
                            f"- {constraint}"
                        )

                else:

                    answer_parts.append(
                        "Failed requirements: None reported"
                    )

                # Risk factors.
                risks = site.get("risk_factors", [])

                if risks:

                    answer_parts.append("Risk factors:")

                    for risk in risks:
                        answer_parts.append(f"- {risk}")

                # Recommendation.
                recommendation = site.get("recommendation")

                if recommendation:
                    answer_parts.append(
                        f"Assessment: {recommendation}"
                    )

            # Identify the highest-ranked feasible site.
            recommended_site = next(
                (
                    site
                    for site in ranked_sites
                    if site.get("rank") == 1
                    and site.get("feasibility") == "FEASIBLE"
                ),
                None
            )

            answer_parts.append("")
            answer_parts.append("MISSION RECOMMENDATION")
            answer_parts.append("=" * 35)

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
    # PROCESS INDIVIDUAL SITE ASSESSMENTS
    # --------------------------------------------------

    if not comparison_found:

        for result in successful_results:

            assessment = result.get("assessment")

            if not isinstance(assessment, dict):
                continue

            answer_parts.append("MISSION SITE ASSESSMENT")
            answer_parts.append("=" * 35)

            answer_parts.append(
                f"Site: {assessment.get('site_name', assessment.get('site_id', 'Unknown'))}"
            )

            answer_parts.append(
                f"Feasibility: {assessment.get('feasibility', 'UNKNOWN')}"
            )

            answer_parts.append(
                f"Overall score: {assessment.get('overall_score', 'Not available')}/100"
            )

            failures = assessment.get(
                "failed_constraints",
                []
            )

            if failures:

                answer_parts.append("Failed requirements:")

                for failure in failures:
                    answer_parts.append(f"- {failure}")

            else:

                answer_parts.append(
                    "Failed requirements: None reported"
                )

            recommendation = assessment.get("recommendation")

            if recommendation:
                answer_parts.append(
                    f"Assessment: {recommendation}"
                )

    # --------------------------------------------------
    # HANDLE TOOL ERRORS
    # --------------------------------------------------

    if failed_results:

        answer_parts.append("")
        answer_parts.append("UNAVAILABLE INFORMATION")

        for failure in failed_results:

            answer_parts.append(
                failure.get("error", "Unknown tool error")
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

    # Construct final answer.
    answer = "\n".join(answer_parts)

    # Store conversation history.
    session["history"].append({
        "question": question,
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