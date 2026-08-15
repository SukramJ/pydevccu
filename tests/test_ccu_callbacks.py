"""
Tests for the two callback-path behaviours a real CCU exhibits.

A CCU answers a ping with a CENTRAL/PONG event so the client can match
its own request, and it keeps delivering to a client that replied with a
fault — only a transport error means the client is gone.
"""

from __future__ import annotations

from typing import Any

import pytest

from pydevccu import const
from pydevccu.ccu import RPCFunctions


class RecordingProxy:
    """A callback receiver that records every event it is handed."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str, str, Any]] = []

    def event(self, interface_id: str, address: str, value_key: str, value: Any) -> None:
        """Record an event callback."""
        self.events.append((interface_id, address, value_key, value))


class FaultingProxy(RecordingProxy):
    """A receiver whose handler raises an application-level error."""

    def event(self, interface_id: str, address: str, value_key: str, value: Any) -> None:
        """Record the event, then fail the way a client-side fault does."""
        super().event(interface_id, address, value_key, value)
        raise RuntimeError("client-side handler failed")


class DeadProxy(RecordingProxy):
    """A receiver that is no longer reachable."""

    def event(self, interface_id: str, address: str, value_key: str, value: Any) -> None:
        """Fail the way an unreachable host does."""
        raise ConnectionError("connection refused")


@pytest.fixture
def rpc() -> RPCFunctions:
    """Create RPCFunctions with a single device type loaded."""
    return RPCFunctions(devices=["HmIP-SWSD"], persistence=False, logic=False)


class TestPingPong:
    """ping must answer with a CENTRAL/PONG event."""

    def test_ping_fires_pong_carrying_the_caller_id(self, rpc: RPCFunctions) -> None:
        """The client matches the event against the token it sent."""
        proxy = RecordingProxy()
        interface_id = "ccu-test"
        rpc.remotes[interface_id] = proxy  # type: ignore[assignment]

        caller_id = f"{interface_id}#2026-08-15 12:00:00.000"
        assert rpc.ping(caller_id) is True

        assert proxy.events == [(interface_id, const.CENTRAL_ADDRESS, const.ATTR_PONG, caller_id)], (
            "no CENTRAL/PONG event carrying the caller id"
        )

    def test_ping_without_caller_id_is_silent(self, rpc: RPCFunctions) -> None:
        """The plain liveness probe must not generate an event."""
        proxy = RecordingProxy()
        rpc.remotes["ccu-test"] = proxy  # type: ignore[assignment]

        assert rpc.ping() is True
        assert rpc.ping(None) is True

        assert proxy.events == []

    def test_pong_goes_only_to_the_pinging_interface(self, rpc: RPCFunctions) -> None:
        """A CCU answers towards the interface that sent the ping."""
        pinger = RecordingProxy()
        bystander = RecordingProxy()
        rpc.remotes["pinger"] = pinger  # type: ignore[assignment]
        rpc.remotes["bystander"] = bystander  # type: ignore[assignment]

        rpc.ping("pinger#token")

        assert len(pinger.events) == 1
        assert bystander.events == [], "PONG leaked to an unrelated client"


class TestCallbackRobustness:
    """A fault is the client answering, not the client disappearing."""

    def test_fault_keeps_the_client_registered(self, rpc: RPCFunctions) -> None:
        """
        Delivery must continue after an application-level error.

        Dropping the remote on the first fault silently ends event
        delivery for the rest of the session.
        """
        proxy = FaultingProxy()
        interface_id = "faulty-client"
        rpc.remotes[interface_id] = proxy  # type: ignore[assignment]

        rpc._fire_event(interface_id, "VCU0000001:1", "STATE", True)

        assert interface_id in rpc.remotes, "client was deregistered after a fault"

        rpc._fire_event(interface_id, "VCU0000001:1", "STATE", False)
        assert len(proxy.events) == 2, "no further event delivered after the fault"

    def test_fault_does_not_abort_delivery_to_other_clients(self, rpc: RPCFunctions) -> None:
        """One failing receiver must not starve the others."""
        faulty = FaultingProxy()
        healthy = RecordingProxy()
        # Insertion order decides who is called first; the faulty one
        # goes first so its failure would shadow the healthy one.
        rpc.remotes["faulty"] = faulty  # type: ignore[assignment]
        rpc.remotes["healthy"] = healthy  # type: ignore[assignment]

        rpc._fire_event("faulty", "VCU0000001:1", "STATE", True)

        assert len(healthy.events) == 1, "a fault aborted delivery to the remaining clients"

    def test_transport_error_deregisters_the_client(self, rpc: RPCFunctions) -> None:
        """An unreachable client is gone and must be dropped."""
        rpc.remotes["dead-client"] = DeadProxy()  # type: ignore[assignment]

        rpc._fire_event("dead-client", "VCU0000001:1", "STATE", True)

        assert "dead-client" not in rpc.remotes, "unreachable client stayed registered"
