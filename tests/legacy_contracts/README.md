# Legacy API Contracts

This directory preserves tests for retired API contracts.

## Mission API contract

`mission_api_contract.py` documents the former endpoints:

- `POST /api/v1/mission/assess`
- `POST /api/v1/mission/compare`

These endpoints used the earlier mock-data mission assessment engine.
The current application uses the native-data-backed Mission Intelligence
API under `/terrain/explorer/mission-intelligence`.

The legacy tests are retained for historical reference and are not part
of the active pytest regression suite. Their expectations must not be
treated as current application behavior.
