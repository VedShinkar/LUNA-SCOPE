# LUNA-SCOPE AI Mission Copilot

## 1. Overview

The AI Mission Copilot is a decision-support component of the LUNA-SCOPE lunar mission planning platform.

It accepts natural-language mission questions, identifies the relevant lunar landing sites, invokes existing Mission Intelligence tools, and presents their results in a readable format.

The Copilot helps users investigate lunar landing-site feasibility, compare candidate locations, and understand mission constraints.

The current implementation uses a local deterministic question-routing system. It does not require an external LLM API or paid API credits.

## 2. Key Features

- Natural-language mission question handling.
- Lunar landing-site identification.
- Single-site mission assessment.
- Comparison of multiple lunar landing sites.
- Terrain information retrieval.
- Mission feasibility and constraint analysis through existing scientific services.
- Session-based context for follow-up questions.
- Evidence-based responses using existing LUNA-SCOPE tools.
- Scientific data provenance and limitation warnings.

## 3. Supported Landing Sites

The current Mission Intelligence test fixtures include:

1. Shackleton Rim
2. Malapert Massif
3. de Gerlache Rim

These locations are represented using synthetic test data.

## 4. System Architecture

The AI Mission Copilot consists of the following components:

| Component | File | Responsibility |
|---|---|---|
| Agent | `agent.py` | Processes questions and routes them to tools |
| Tools | `tools.py` | Connects the Copilot to Mission Intelligence functions |
| Schemas | `schemas.py` | Defines API request and response structures |
| Routes | `routes.py` | Exposes the Copilot API endpoint |
| Configuration | `config.py` | Contains optional API configuration |

### Processing Workflow

1. User submits a mission-related question.
2. The Copilot identifies the lunar site mentioned.
3. It determines whether the user needs an assessment, terrain information, or site comparison.
4. The appropriate scientific tool is executed.
5. The returned results are formatted into a readable explanation.
6. The response includes scientific data limitations and provenance warnings.

## 5. Integrated Scientific Tools

The Copilot connects to the existing Mission Intelligence functions.

| Tool | Purpose |
|---|---|
| `mission_feasibility` | Checks mission feasibility against configured requirements |
| `site_assessment` | Evaluates an individual landing site |
| `compare_landing_sites` | Compares multiple candidate locations |
| `terrain_information` | Retrieves available terrain information |

These functions reuse existing LUNA-SCOPE scientific services instead of independently inventing scientific measurements.

## 6. API Endpoint

**Endpoint:**

`POST /api/v1/copilot/chat`

**Local development URL:**

`http://127.0.0.1:8000/api/v1/copilot/chat`

### Example Request

```json
{
  "question": "Compare Shackleton Rim and Malapert Massif for rover exploration."
}
```

### Example Questions

- Is Shackleton Rim suitable for rover exploration?
- Compare Shackleton Rim and Malapert Massif.
- What are the terrain characteristics of Shackleton Rim?
- Which landing site satisfies the rover mission requirements?
- What are the risks associated with Malapert Massif?

## 7. Mission Profile

The current default mission profile is:

`ROVER_EXPLORATION_V1`

It evaluates sites against configured requirements, including:

- Minimum sunlight hours.
- Minimum Earth visibility hours.
- Minimum solar energy.
- Maximum terrain slope.
- Maximum terrain hazard score.

The profile also uses weighted criteria for scoring and comparison.

## 8. Session Management

The Copilot maintains lightweight session context.

It can retain previously identified landing sites and use them to interpret certain follow-up questions.

Session history is stored in application memory and is not persistent across server restarts.

## 9. Installation and Execution

Run these commands from the root directory of the LUNA-SCOPE repository.

Activate the virtual environment:

```powershell
.venv\Scripts\Activate.ps1
```

Set the backend Python path:

```powershell
$env:PYTHONPATH = "$PWD\backend"
```

Start the FastAPI application:

```powershell
python -m uvicorn app.main:app --reload --app-dir backend
```

Open the API documentation:

`http://127.0.0.1:8000/docs`

Find the AI Mission Copilot endpoint and use the interactive Swagger interface to submit questions.

## 10. Testing

Automated tests are available in:

`tests/test_ai_copilot.py`

Run the tests from the repository root:

```powershell
$env:PYTHONPATH = "$PWD\backend"
python -m pytest tests/test_ai_copilot.py -v
```

The tests cover:

- Empty-question validation.
- Missing-site clarification.
- Single-site assessment tool routing.
- Multi-site comparison tool routing.

## 11. Scientific Data Limitations

**Important: The current Mission Intelligence site fixtures and mission profile are marked `SYNTHETIC_EXAMPLE`.**

Their values are illustrative software-testing data and are not verified NASA measurements.

They must not be used for real lunar mission planning or operational decisions.

Terrain information is returned only when the corresponding terrain dataset and service are available.

## 12. Current Implementation Limitations

- Question interpretation uses deterministic keyword-based routing rather than a live LLM.
- Session information is stored in application memory.
- Scientific outputs depend on the existing LUNA-SCOPE services and available datasets.
- The current synthetic fixtures are intended for software demonstration and testing.

## 13. Future Improvements

- Integrate an optional LLM for more flexible natural-language interpretation.
- Improve conversational context and follow-up question handling.
- Connect additional verified lunar datasets.
- Expand terrain, illumination, thermal, and communication analysis.
- Add richer visual explanations and mission comparison dashboards.

---

**LUNA-SCOPE AI Mission Copilot**  
An intelligent decision-support component for lunar exploration planning.