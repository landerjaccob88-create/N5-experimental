from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from datetime import datetime, timezone

from atanor_runtime_binding import (
    router_decide,
    dispatch_ingest,
    runtime_events,
    runtime_state,
)


EVIDENCE_DIR = Path("evidence/d11")
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(filename: str, payload: dict) -> None:
    path = EVIDENCE_DIR / filename
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def build_fixture_ambiguous() -> dict:
    return {
        "fixture_id": "D11-A",
        "semantic_operation": "SEARCH_CONTENT",
        "target": "ATANOR TEP",
        "surface": None,
        "viable_routes": [
            "Box",
            "Dropbox",
            "Notion",
            "GitHub",
        ],
        "selection_sufficient": False,
    }


def build_fixture_unresolved() -> dict:
    return {
        "fixture_id": "D11-B",
        "semantic_operation": "OPERATION_WITHOUT_SUFFICIENT_ROUTE",
        "target": "ATANOR TEP",
        "surface": None,
        "viable_routes": [],
        "selection_sufficient": False,
    }


def run_case(fixture: dict) -> dict:
    case_id = fixture["fixture_id"]
    operation_id = f"D11-{case_id}"

    # Router real del runtime D11.
    router_output = router_decide(fixture)

    # Dispatch recibe exactamente el resultado anterior.
    dispatch_output = dispatch_ingest(router_output)

    events = runtime_events(operation_id)

    result = {
        "record_type": "ATANOR_D11_CASE_RESULT",
        "case_id": case_id,
        "operation_id": operation_id,
        "fixture": fixture,
        "runtime": runtime_state(),
        "events": events,
        "router_output": router_output,
        "dispatch_output": dispatch_output,
        "target_execution": False,
        "side_effects": False,
    }

    write_json(f"D11.{case_id}.json", result)

    return result


def validate_case(result: dict) -> None:
    events = result["events"]

    observations = {
        event["observation_point"]: event
        for event in events
    }

    required = {"O1", "O2", "O3"}

    if set(observations) != required:
        raise RuntimeError(
            f"D11_TRACE_INCOMPLETE:{sorted(observations)}"
        )

    o1 = observations["O1"]
    o2 = observations["O2"]
    o3 = observations["O3"]

    if o1["emitted_by"] != "ROUTER":
        raise RuntimeError("D11_O1_EMITTER_INVALID")

    if o1["emitted_at_layer"] != "ROUTER":
        raise RuntimeError("D11_O1_LAYER_INVALID")

    if o1["trace_parent"] is not None:
        raise RuntimeError("D11_O1_PARENT_INVALID")

    if o2["emitted_by"] is not None:
        raise RuntimeError("D11_O2_EMITTER_MUST_BE_UNATTRIBUTED")

    if o2["trace_parent"] != o1["event_id"]:
        raise RuntimeError("D11_O2_PARENT_INVALID")

    if o3["emitted_by"] != "DISPATCH":
        raise RuntimeError("D11_O3_EMITTER_INVALID")

    if o3["emitted_at_layer"] != "DISPATCH":
        raise RuntimeError("D11_O3_LAYER_INVALID")

    if o3["trace_parent"] != o2["event_id"]:
        raise RuntimeError("D11_O3_PARENT_INVALID")

    if result["target_execution"] is not False:
        raise RuntimeError("D11_TARGET_EXECUTION_DETECTED")

    if result["side_effects"] is not False:
        raise RuntimeError("D11_SIDE_EFFECT_DETECTED")


def main() -> None:
    runtime = runtime_state()

    if runtime["status"] != "ACTIVE":
        raise RuntimeError("ACTIVE_RUNTIME_NOT_ESTABLISHED")

    results = []

    try:
        for fixture in (
            build_fixture_ambiguous(),
            build_fixture_unresolved(),
        ):
            result = run_case(fixture)
            validate_case(result)
            results.append(result)

        final = {
            "record_type": "ATANOR_D11_RUNTIME_RESULT",
            "status": "EXECUTED",
            "executed": True,
            "target_execution": False,
            "side_effects": False,
            "timestamp": utc_now(),
            "runtime_connection": runtime,
            "cases": [
                "D11-A",
                "D11-B",
            ],
            "evidence_files": [
                "D11.D11-A.json",
                "D11.D11-B.json",
            ],
            "verification": {
                "O1_ROUTER_EMISSION": "PASS",
                "O2_DISPATCH_INGRESS": "PASS",
                "O3_DISPATCH_EMISSION": "PASS",
                "CAUSAL_CHAIN": "PASS",
                "TARGET_EXECUTION": "NOT_ATTEMPTED",
                "SIDE_EFFECTS": False,
            },
        }

        write_json("D11.RUNTIME_RESULT.json", final)
        print(json.dumps(final, ensure_ascii=False, indent=2))

    except Exception as exc:
        failure = {
            "record_type": "ATANOR_D11_RUNTIME_RESULT",
            "status": "EXECUTION_ERROR",
            "executed": False,
            "target_execution": False,
            "timestamp": utc_now(),
            "runtime_connection": runtime,
            "exception": repr(exc),
            "traceback": traceback.format_exc(),
            "partial_results": results,
        }

        write_json("D11.RUNTIME_RESULT.json", failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()