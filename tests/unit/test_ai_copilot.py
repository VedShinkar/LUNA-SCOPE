
import pytest

from app.ai_copilot import agent


@pytest.fixture(autouse=True)
def reset_sessions():
    """Start each test with a clean session."""
    agent.SESSIONS.clear()


def test_empty_question_is_rejected():
    result = agent.ask_copilot("")

    assert result["success"] is False
    assert "error" in result


def test_question_without_site_requests_clarification():
    result = agent.ask_copilot(
        "Which lunar location is best for exploration?"
    )

    assert result["success"] is True
    assert "Shackleton Rim" in result["answer"]
    assert result["tools_used"] == []


def test_single_site_question_calls_assessment(monkeypatch):
    def fake_execute_tool(tool_name, arguments):
        assert tool_name == "site_assessment"
        assert arguments["site_id"] == "SHACKLETON_RIM"

        return {
            "success": True,
            "site_id": "SHACKLETON_RIM",
            "assessment": {
                "site_name": "Shackleton Rim",
                "feasibility": "FEASIBLE",
                "overall_score": 100,
                "failed_constraints": [],
                "recommendation": "Suitable in this synthetic test."
            }
        }

    monkeypatch.setattr(
        agent,
        "execute_tool",
        fake_execute_tool
    )

    result = agent.ask_copilot(
        "Is Shackleton Rim suitable for rover exploration?"
    )

    assert result["success"] is True
    assert "site_assessment" in result["tools_used"]
    assert "Shackleton Rim" in result["answer"]


def test_comparison_question_calls_comparison_tool(monkeypatch):
    def fake_execute_tool(tool_name, arguments):
        assert tool_name == "compare_landing_sites"

        assert set(arguments["site_ids"]) == {
            "SHACKLETON_RIM",
            "MALAPERT_MASSIF"
        }

        return {
            "success": True,
            "comparison": [
                {
                    "site_id": "SHACKLETON_RIM",
                    "site_name": "Shackleton Rim",
                    "feasibility": "FEASIBLE",
                    "overall_score": 100,
                    "rank": 1,
                    "failed_constraints": [],
                    "risk_factors": [],
                    "recommendation": "Suitable in this synthetic test."
                },
                {
                    "site_id": "MALAPERT_MASSIF",
                    "site_name": "Malapert Massif",
                    "feasibility": "NOT_FEASIBLE",
                    "overall_score": 80,
                    "rank": None,
                    "failed_constraints": [
                        "Minimum sunlight requirement failed."
                    ],
                    "risk_factors": [],
                    "recommendation": "Review failed requirements."
                }
            ]
        }

    monkeypatch.setattr(
        agent,
        "execute_tool",
        fake_execute_tool
    )

    result = agent.ask_copilot(
        "Compare Shackleton Rim and Malapert Massif for rover exploration."
    )

    assert result["success"] is True
    assert "compare_landing_sites" in result["tools_used"]
    assert "MISSION SITE COMPARISON" in result["answer"]
    assert "Shackleton Rim" in result["answer"]
    assert "Malapert Massif" in result["answer"]
