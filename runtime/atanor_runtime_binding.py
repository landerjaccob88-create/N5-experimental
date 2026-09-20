from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


RUNTIME_STARTED_AT = utc_now()

# Identidad del proceso real que ejecuta este código.
# En GitHub Actions GITHUB_RUN_ID es generado por GitHub.
RUNTIME_ID = (
    f"GHA-{os.environ['GITHUB_RUN_ID']}"
    if os.environ.get("GITHUB_RUN_ID")
    else f"LOCAL-{os.getpid()}"
)


@dataclass(frozen=True)
class ProvenanceEvent:
    event_id: str
    operation_id: str
    input_ref: str
    output_ref: str | None
    emitted_by: str | None
    emitted_at_layer: str | None
    emitted_at: str
    trace_parent: str | None
    transition: str
    observation_point: str
    captured_at_layer: str
    payload_snapshot: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class D11Runtime:
    """
    Runtime ejecutable y delimitado para D11.

    No es una implementación canónica del Router/Dispatch.
    Es una superficie ejecutable de prueba que materializa
    exactamente las fronteras requeridas por D11.
    """

    def __init__(self) -> None:
        self.events: list[ProvenanceEvent] = []
        self._router_event_by_resolution: dict[str, str] = {}
        self._dispatch_event_by_operation: dict[str, str] = {}

    def _record(self, event: ProvenanceEvent) -> None:
        self.events.append(event)

    def router_decide(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Router decision boundary.

        D11-A:
            múltiples rutas viables + selección insuficiente
            -> AMBIGUOUS

        D11-B:
            ninguna ruta viable
            -> UNRESOLVED

        Caso determinable:
            una sola ruta viable + selection_sufficient=true
            -> ROUTE_RESOLVED
        """

        operation_id = f"D11-{request['fixture_id']}"
        route_resolution_ref = f"RR-{uuid4().hex}"

        candidates = deepcopy(request.get("viable_routes", []))
        sufficient = bool(request.get("selection_sufficient", False))

        if not candidates:
            route_status = "UNRESOLVED"
            selection_suppressed = True

        elif len(candidates) > 1 and not sufficient:
            route_status = "AMBIGUOUS"
            selection_suppressed = True

        elif len(candidates) == 1 and sufficient:
            route_status = "ROUTE_RESOLVED"
            selection_suppressed = False

        else:
            route_status = "NOT_DETERMINED"
            selection_suppressed = True

        result = {
            "runtime_id": RUNTIME_ID,
            "route_resolution_ref": route_resolution_ref,
            "route_status": route_status,
            "route_candidates": candidates,
            "selection_suppressed": selection_suppressed,
            "fixture_id": request["fixture_id"],
        }

        event = ProvenanceEvent(
            event_id=f"EV-{uuid4().hex}",
            operation_id=operation_id,
            input_ref=request["fixture_id"],
            output_ref=route_resolution_ref,
            emitted_by="ROUTER",
            emitted_at_layer="ROUTER",
            emitted_at=utc_now(),
            trace_parent=None,
            transition="ROUTER_DECISION -> ROUTE_RESOLUTION",
            observation_point="O1",
            captured_at_layer="ROUTER",
            payload_snapshot=deepcopy(result),
        )

        self._record(event)
        self._router_event_by_resolution[route_resolution_ref] = event.event_id

        return result

    def dispatch_ingest(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Dispatch recibe exactamente el payload emitido por Router.

        D11 no ejecuta una operación objetivo.
        Dispatch solamente observa/transforma el resultado.
        """

        operation_id = f"D11-{payload['fixture_id']}"
        route_resolution_ref = payload["route_resolution_ref"]

        router_event_id = self._router_event_by_resolution.get(
            route_resolution_ref
        )

        if router_event_id is None:
            raise RuntimeError(
                "TRACE_PARENT_ROUTER_EVENT_NOT_FOUND"
            )

        raw_payload = deepcopy(payload)

        ingress_event = ProvenanceEvent(
            event_id=f"EV-{uuid4().hex}",
            operation_id=operation_id,
            input_ref=route_resolution_ref,
            output_ref=None,
            emitted_by=None,
            emitted_at_layer=None,
            emitted_at=utc_now(),
            trace_parent=router_event_id,
            transition="ROUTE_RESOLUTION -> DISPATCH_INGRESS",
            observation_point="O2",
            captured_at_layer="DISPATCH",
            payload_snapshot=raw_payload,
        )

        self._record(ingress_event)

        route_status = payload["route_status"]

        if route_status in {"AMBIGUOUS", "UNRESOLVED", "NOT_DETERMINED"}:
            dispatch_status = "DEFERRED"
        elif route_status == "ROUTE_RESOLVED":
            dispatch_status = "READY"
        else:
            dispatch_status = "RECEIVED"

        output = {
            "runtime_id": RUNTIME_ID,
            "dispatch_status": dispatch_status,
            "route_resolution_ref": route_resolution_ref,
            "target_execution": False,
            "side_effects": False,
        }

        emission_event = ProvenanceEvent(
            event_id=f"EV-{uuid4().hex}",
            operation_id=operation_id,
            input_ref=ingress_event.event_id,
            output_ref=f"DISPATCH-{uuid4().hex}",
            emitted_by="DISPATCH",
            emitted_at_layer="DISPATCH",
            emitted_at=utc_now(),
            trace_parent=ingress_event.event_id,
            transition="DISPATCH_INGRESS -> DISPATCH_OUTPUT",
            observation_point="O3",
            captured_at_layer="DISPATCH",
            payload_snapshot=deepcopy(output),
        )

        self._record(emission_event)
        self._dispatch_event_by_operation[operation_id] = emission_event.event_id

        return output

    def events_for_operation(self, operation_id: str) -> list[dict[str, Any]]:
        return [
            event.to_dict()
            for event in self.events
            if event.operation_id == operation_id
        ]

    def runtime_state(self) -> dict[str, Any]:
        return {
            "runtime_id": RUNTIME_ID,
            "status": "ACTIVE",
            "started_at": RUNTIME_STARTED_AT,
            "execution_surface": (
                "GitHub Actions"
                if os.environ.get("GITHUB_RUN_ID")
                else "local_process"
            ),
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        }


_RUNTIME = D11Runtime()


def router_decide(request: dict[str, Any]) -> dict[str, Any]:
    return _RUNTIME.router_decide(request)


def dispatch_ingest(payload: dict[str, Any]) -> dict[str, Any]:
    return _RUNTIME.dispatch_ingest(payload)


def runtime_events(operation_id: str) -> list[dict[str, Any]]:
    return _RUNTIME.events_for_operation(operation_id)


def runtime_state() -> dict[str, Any]:
    return _RUNTIME.runtime_state()