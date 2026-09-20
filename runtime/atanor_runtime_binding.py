"""
ATANOR TEP — Runtime Binding

Este archivo NO implementa Router ni Dispatch.

Su única función es enlazar explícitamente
el runtime vigente con el harness D11.

NO AUTO-DISCOVERY.
NO INFERENCE.
NO SIMULATION.

Reemplazar únicamente las dos funciones marcadas.
"""


def router_decide(request: dict) -> dict:
    """
    Ejecuta la función REAL del Router vigente.

    REEMPLAZAR EL CONTENIDO DE ESTA FUNCIÓN
    CON EL ENTRYPOINT REAL DEL ROUTER.
    """

    raise RuntimeError(
        "ROUTER_RUNTIME_BINDING_NOT_DEFINED"
    )


def dispatch_ingest(payload: dict) -> dict:
    """
    Entrega el payload EXACTAMENTE como recibido
    al entrypoint REAL de Dispatch.

    REEMPLAZAR EL CONTENIDO DE ESTA FUNCIÓN
    CON EL ENTRYPOINT REAL DE DISPATCH.
    """

    raise RuntimeError(
        "DISPATCH_RUNTIME_BINDING_NOT_DEFINED"
    )