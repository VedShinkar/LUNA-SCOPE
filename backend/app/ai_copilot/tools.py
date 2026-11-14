"""
Scientific tools for the LUNA-SCOPE AI Mission Copilot.

All tools are read-only wrappers around existing scientific modules.
The LLM interprets results but never performs scientific calculations.
"""

from typing import Any

from app.mission.decision_engine.assessment import assess_mission
from app.mission.decision_engine.feasibility import check_feasibility
from app.mission.decision_engine.scenario_comparison import compare_scenarios


def mission_feasibility(
    site_id: str,
    mission_profile_id: str
) -> dict[str, Any]:
    """Retrieve deterministic mission feasibility."""

    try:
        result = check_feasibility(
            site_id=site_id,
            profile_id=mission_profile_id
        )

        return {
            "success": True,
            "site_id": site_id,
            "mission_profile_id": mission_profile_id,
            "result": result
        }

    except (ValueError, KeyError) as error:
        return {
            "success": False,
            "error": str(error)
        }


def site_assessment(
    site_id: str,
    mission_profile_id: str
) -> dict[str, Any]:
    """Retrieve the complete mission assessment and scoring."""

    try:
        result = assess_mission(
            site_id=site_id,
            profile_id=mission_profile_id
        )

        return {
            "success": True,
            "site_id": site_id,
            "mission_profile_id": mission_profile_id,
            "assessment": result
        }

    except (ValueError, KeyError) as error:
        return {
            "success": False,
            "error": str(error)
        }


def compare_landing_sites(
    site_ids: list[str],
    mission_profile_id: str
) -> dict[str, Any]:
    """Compare multiple lunar landing sites."""

    try:
        result = compare_scenarios(
            site_ids=site_ids,
            profile_id=mission_profile_id
        )

        return {
            "success": True,
            "mission_profile_id": mission_profile_id,
            "site_ids": site_ids,
            "comparison": result
        }

    except (ValueError, KeyError) as error:
        return {
            "success": False,
            "error": str(error)
        }


def terrain_information(
    site_id: str
) -> dict[str, Any]:
    """Retrieve existing terrain information for a lunar site."""

    try:
        from app.scientific_engines.terrain.service import TerrainService

        service = TerrainService.get_instance(site_id)
        service._ensure_loaded()

        result = service.get_site_summary()

        return {
            "success": True,
            "site_id": site_id,
            "terrain_data": result
        }

    except Exception as error:
        return {
            "success": False,
            "site_id": site_id,
            "error": str(error),
            "availability": "UNAVAILABLE"
        }


# OpenAI function-calling definitions.

COPILOT_TOOLS = [
    {
        "type": "function",
        "name": "mission_feasibility",
        "description": (
            "Retrieve the deterministic feasibility result "
            "for a lunar site and mission profile."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "site_id": {
                    "type": "string",
                    "description": "Lunar landing site identifier."
                },
                "mission_profile_id": {
                    "type": "string",
                    "description": "Mission profile identifier."
                }
            },
            "required": ["site_id", "mission_profile_id"],
            "additionalProperties": False
        },
        "strict": True
    },
    {
        "type": "function",
        "name": "site_assessment",
        "description": (
            "Retrieve the complete mission assessment, "
            "scores, recommendation and data quality."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "site_id": {"type": "string"},
                "mission_profile_id": {"type": "string"}
            },
            "required": ["site_id", "mission_profile_id"],
            "additionalProperties": False
        },
        "strict": True
    },
    {
        "type": "function",
        "name": "compare_landing_sites",
        "description": (
            "Compare two or more lunar landing sites "
            "using the existing deterministic decision engine."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "site_ids": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "mission_profile_id": {"type": "string"}
            },
            "required": ["site_ids", "mission_profile_id"],
            "additionalProperties": False
        },
        "strict": True
    },
    {
        "type": "function",
        "name": "terrain_information",
        "description": (
            "Retrieve existing terrain summary information "
            "for a lunar landing site."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "site_id": {"type": "string"}
            },
            "required": ["site_id"],
            "additionalProperties": False
        },
        "strict": True
    }
]


def execute_tool(
    tool_name: str,
    arguments: dict[str, Any]
) -> dict[str, Any]:
    """Execute an approved Copilot tool."""

    available_tools = {
        "mission_feasibility": mission_feasibility,
        "site_assessment": site_assessment,
        "compare_landing_sites": compare_landing_sites,
        "terrain_information": terrain_information
    }

    tool = available_tools.get(tool_name)

    if tool is None:
        return {
            "success": False,
            "error": f"Unknown or unsupported tool: {tool_name}"
        }

    try:
        return tool(**arguments)

    except (TypeError, ValueError) as error:
        return {
            "success": False,
            "error": str(error)
        }