"""Tests for device response mappings."""

from __future__ import annotations

from pydevccu.device_responses import compute_response_events, get_response_mapping


class TestGetResponseMapping:
    """Test response mapping lookup."""

    def test_exact_match(self) -> None:
        """Test exact device type match."""
        response = get_response_mapping("HmIP-PSM", "STATE")
        assert response is not None
        assert response.trigger_param == "STATE"

    def test_prefix_match(self) -> None:
        """Test prefix-based device type match."""
        # HmIP-PSM-2 should match HmIP-PSM prefix
        response = get_response_mapping("HmIP-PSM-2", "STATE")
        assert response is not None
        assert response.trigger_param == "STATE"

    def test_no_match_device(self) -> None:
        """Test unknown device type returns None."""
        response = get_response_mapping("UNKNOWN-DEVICE", "STATE")
        assert response is None

    def test_no_match_param(self) -> None:
        """Test unknown parameter returns None."""
        response = get_response_mapping("HmIP-PSM", "UNKNOWN_PARAM")
        assert response is None


class TestComputeResponseEvents:
    """Test response event computation."""

    def test_switch_state_response(self) -> None:
        """Test switch STATE triggers STATE and WORKING response."""
        events = compute_response_events(
            device_type="HmIP-PSM",
            param="STATE",
            value=True,
            current_values={},
        )

        assert "STATE" in events
        assert events["STATE"] is True
        assert "WORKING" in events
        assert events["WORKING"] is False

    def test_dimmer_level_response(self) -> None:
        """Test dimmer LEVEL triggers LEVEL and ACTIVITY_STATE response."""
        events = compute_response_events(
            device_type="HmIP-BDT",
            param="LEVEL",
            value=0.5,
            current_values={},
        )

        assert "LEVEL" in events
        assert events["LEVEL"] == 0.5
        assert "ACTIVITY_STATE" in events
        assert events["ACTIVITY_STATE"] == 2  # down/active

    def test_dimmer_level_zero_response(self) -> None:
        """Test dimmer LEVEL=0 sets ACTIVITY_STATE to 0."""
        events = compute_response_events(
            device_type="HmIP-BDT",
            param="LEVEL",
            value=0,
            current_values={},
        )

        assert events["LEVEL"] == 0
        assert events["ACTIVITY_STATE"] == 0  # unknown/off

    def test_blind_level_preserves_level2(self) -> None:
        """Test blind LEVEL preserves existing LEVEL_2."""
        events = compute_response_events(
            device_type="HmIP-BROLL",
            param="LEVEL",
            value=0.8,
            current_values={"LEVEL_2": 0.3},
        )

        assert events["LEVEL"] == 0.8
        assert events["LEVEL_2"] == 0.3

    def test_thermostat_setpoint_response(self) -> None:
        """Test thermostat SET_POINT_TEMPERATURE response."""
        events = compute_response_events(
            device_type="HmIP-eTRV",
            param="SET_POINT_TEMPERATURE",
            value=21.5,
            current_values={"CONTROL_MODE": 1},
        )

        assert events["SET_POINT_TEMPERATURE"] == 21.5
        assert events["CONTROL_MODE"] == 1

    def test_unknown_device_echoes_param(self) -> None:
        """Test unknown device echoes the parameter back."""
        events = compute_response_events(
            device_type="UNKNOWN-DEVICE",
            param="SOME_PARAM",
            value=42,
            current_values={},
        )

        assert events == {"SOME_PARAM": 42}

    def test_lock_target_level_response(self) -> None:
        """Test lock LOCK_TARGET_LEVEL triggers LOCK_STATE response."""
        # Lock (target=0)
        events = compute_response_events(
            device_type="HmIP-DLD",
            param="LOCK_TARGET_LEVEL",
            value=0,
            current_values={},
        )
        assert events["LOCK_STATE"] == 1  # locked

        # Unlock (target=1)
        events = compute_response_events(
            device_type="HmIP-DLD",
            param="LOCK_TARGET_LEVEL",
            value=1,
            current_values={},
        )
        assert events["LOCK_STATE"] == 2  # unlocked
