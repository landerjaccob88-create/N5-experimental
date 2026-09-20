from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path


EVIDENCE_DIR = Path("evidence/d11")
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(filename: str, payload: dict) -> None:
    path = EVIDENCE_DIR / filename
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def fail_closed(reason: str, details: dict | None = None) -> None:
    evidence = {
        "record_type": "ATANOR_D11_RUNTIME_RESULT",
        "status": "EXECUTION_NOT_ESTABLISHED",
        "executed": False,
        "target_execution": False,
        "timestamp": utc_now(),
        "reason": reason,
        "details": details or {},
    }

    write_json("D11.RUNTIME_RESULT.json", evidence)

    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    sys.exit(2)


def load_runtime_binding():
    """
    REQUIRED CONTRACT

    The repository must contain:

        runtime/atanor_runtime_binding.py

    exposing:

        router_decide(request: dict) -> dict
        dispatch_ingest(payload: dict) -> dict

    This file deliberately does NOT guess module names,
    discover arbitrary functions, or simulate execution.
    """
    try:
        from atanor_runtime_binding import (
            router_decide,
            dispatch_ingest,
        )
    except Exception as exc:
        fail_closed(
            "RUNTIME_BINDING_NOT_AVAILABLE",
            {
                "required_module": "runtime/atanor_runtime_binding.py",
                "required_functions": [
                    "router_decide(request)",
                    "dispatch_ingest(payload)",
                ],
                "exception": repr(exc),
            },
        )

    return router_decide, dispatch_ingest


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


def run_case(router_decide, dispatch_ingest, fixture: dict, case_id: str) -> dict:
    operation_id = f"D11-{case_id}"

    # O1 — Router emission/decision observation boundary.
    router_output = router_decide(fixture)

    o1 = {
        "event_id": f"{operation_id}-O1",
        "operation_id": operation_id,
        "input_ref": fixture.get("fixture_id"),
        "output_ref": None,
        "emitted_by": "ROUTER",
        "emitted_at_layer": "ROUTER",
        "emitted_at": utc_now(),
        "trace_parent": None,
        "transition": "ROUTER_DECISION",
        "payload": router_output,
    }

    # O2 — exact raw payload received by Dispatch.
    raw_payload = router_output

    o2 = {
        "event_id": f"{operation_id}-O2",
        "operation_id": operation_id,
        "input_ref": o1["event_id"],
        "output_ref": None,
        "emitted_by": None,
        "emitted_at_layer": "DISPATCH_INGRESS_CAPTURE",
        "emitted_at": utc_now(),
        "trace_parent": o1["event_id"],
        "transition": "DISPATCH_INGRESS",
        "payload": raw_payload,
    }

    # D11 intentionally observes Dispatch behavior only.
    dispatch_output = dispatch_ingest(raw_payload)

    o3 = {
        "event_id": f"{operation_id}-O3",
        "operation_id": operation_id,
        "input_ref": o2["event_id"],
        "output_ref": None,
        "emitted_by": "DISPATCH",
        "emitted_at_layer": "DISPATCH",
        "emitted_at": utc_now(),
        "trace_parent": o2["event_id"],
        "transition": "DISPATCH_OUTPUT",
        "payload": dispatch_output,
    }

    result = {
        "record_type": "ATANOR_D11_CASE_RESULT",
        "case_id": case_id,
        "operation_id": operation_id,
        "fixture": fixture,
        "o1": o1,
        "o2": o2,
        "o3": o3,
        "target_execution": False,
        "side_effects": False,
    }

    write_json(f"D11.{case_id}.json", result)
    return result


def main() -> None:
    router_decide, dispatch_ingest = load_runtime_binding()

    cases = [
        ("A", build_fixture_ambiguous()),
        ("B", build_fixture_unresolved()),
    ]

    results = []

    try:
        for case_id, fixture in cases:
            results.append(
                run_case(
                    router_decide,
                    dispatch_ingest,
                    fixture,
                    case_id,
                )
            )

    except Exception as exc:
        failure = {
            "record_type": "ATANOR_D11_RUNTIME_RESULT",
            "status": "EXECUTION_ERROR",
            "executed": False,
            "target_execution": False,
            "timestamp": utc_now(),
            "exception": repr(exc),
            "traceback": traceback.format_exc(),
            "partial_results": results,
        }

        write_json("D11.RUNTIME_RESULT.json", failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        sys.exit(1)

    final = {
        "record_type": "ATANOR_D11_RUNTIME_RESULT",
        "status": "EXECUTED",
        "executed": True,
        "target_execution": False,
        "side_effects": False,
        "timestamp": utc_now(),
        "cases": ["D11-A", "D11-B"],
        "evidence_files": [
            "D11.A.json",
            "D11.B.json",
        ],
    }

    write_json("D11.RUNTIME_RESULT.json", final)
    print(json.dumps(final, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()