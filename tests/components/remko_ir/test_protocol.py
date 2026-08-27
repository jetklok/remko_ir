import pytest

import custom_components.remko_ir as library
from custom_components.remko_ir.protocol import (
    RemkoFanMode,
    RemkoMode,
    RemkoPower,
    RemkoProtocol,
    RemkoState,
    RemkoSwingMode,
)


def test_library_symbols_are_exported_from_package_root() -> None:
    assert library.RemkoFanMode is RemkoFanMode
    assert library.RemkoMode is RemkoMode
    assert library.RemkoPower is RemkoPower
    assert library.RemkoSwingMode is RemkoSwingMode
    assert library.RemkoProtocol is RemkoProtocol
    assert library.RemkoState is RemkoState


def test_state_is_immutable() -> None:
    state = RemkoState()

    with pytest.raises(AttributeError):
        state.temperature = 22  # type: ignore[misc]


ON_STATES = [
    pytest.param(
        RemkoMode.COOL,
        RemkoFanMode.AUTO,
        RemkoSwingMode.OFF,
        0x0,
        id="cool_auto_swing_off",
    ),
    pytest.param(
        RemkoMode.COOL,
        RemkoFanMode.AUTO,
        RemkoSwingMode.ON,
        0x0,
        id="cool_auto_swing_on",
    ),
    pytest.param(
        RemkoMode.COOL,
        RemkoFanMode.HIGH,
        RemkoSwingMode.OFF,
        0x8,
        id="cool_high_swing_off",
    ),
    pytest.param(
        RemkoMode.COOL,
        RemkoFanMode.HIGH,
        RemkoSwingMode.ON,
        0x8,
        id="cool_high_swing_on",
    ),
    pytest.param(
        RemkoMode.COOL,
        RemkoFanMode.MEDIUM,
        RemkoSwingMode.OFF,
        0x1,
        id="cool_medium_swing_off",
    ),
    pytest.param(
        RemkoMode.COOL,
        RemkoFanMode.MEDIUM,
        RemkoSwingMode.ON,
        0x1,
        id="cool_medium_swing_on",
    ),
    pytest.param(
        RemkoMode.COOL,
        RemkoFanMode.LOW,
        RemkoSwingMode.OFF,
        0x2,
        id="cool_low_swing_off",
    ),
    pytest.param(
        RemkoMode.COOL,
        RemkoFanMode.LOW,
        RemkoSwingMode.ON,
        0x2,
        id="cool_low_swing_on",
    ),
    pytest.param(
        RemkoMode.DRY,
        RemkoFanMode.AUTO,
        RemkoSwingMode.OFF,
        0x4,
        id="dry_swing_off",
    ),
    pytest.param(
        RemkoMode.DRY,
        RemkoFanMode.AUTO,
        RemkoSwingMode.ON,
        0x4,
        id="dry_swing_on",
    ),
    pytest.param(
        RemkoMode.FAN_ONLY,
        RemkoFanMode.AUTO,
        RemkoSwingMode.OFF,
        0x3,
        id="fan_only_swing_off",
    ),
    pytest.param(
        RemkoMode.FAN_ONLY,
        RemkoFanMode.AUTO,
        RemkoSwingMode.ON,
        0x3,
        id="fan_only_swing_on",
    ),
]


@pytest.mark.parametrize("mode, fan, swing, mode_nibble", ON_STATES)
@pytest.mark.parametrize("temperature", [16, 30])
def test_build_bytes_covers_all_on_states(
    mode: RemkoMode,
    fan: RemkoFanMode,
    swing: RemkoSwingMode,
    mode_nibble: int,
    temperature: int,
) -> None:
    state = RemkoState(
        power=RemkoPower.ON,
        mode=mode,
        fan=fan,
        swing=swing,
        temperature=temperature,
    )

    expected_swing_bit = 0x20 if swing == RemkoSwingMode.OFF else 0x00
    expected_fan_nibble = {
        RemkoFanMode.AUTO: 0x8,
        RemkoFanMode.HIGH: 0x8,
        RemkoFanMode.MEDIUM: 0x9,
        RemkoFanMode.LOW: 0xA,
    }[fan]
    expected = bytearray(
        [
            0x83,
            0x00,
            0x00,
            0x00,
            (0x70 & ~0x20) | expected_swing_bit | expected_fan_nibble,
            (mode_nibble << 4) | (temperature - 16),
        ]
    )
    expected.append(
        (15 - sum((byte >> 4) + (byte & 0x0F) for byte in expected) % 16) & 0x0F
    )

    assert RemkoProtocol.encode_frame(state) == bytes(expected)


def test_build_bytes_default_state() -> None:
    assert RemkoProtocol.encode_frame(RemkoState()) == bytes.fromhex("80000000780800")


def test_checksum_completes_nibble_sum() -> None:
    payload = RemkoProtocol.encode_frame(RemkoState())

    assert sum((byte >> 4) + (byte & 0x0F) for byte in payload) % 16 == 15


def test_swing_changes_the_encoded_frame() -> None:
    swing_off = RemkoProtocol.encode_frame(
        RemkoState(power=RemkoPower.ON, swing=RemkoSwingMode.OFF)
    )
    swing_on = RemkoProtocol.encode_frame(
        RemkoState(power=RemkoPower.ON, swing=RemkoSwingMode.ON)
    )

    assert swing_off[4] == 0x78
    assert swing_on[4] == 0x58
    assert swing_off != swing_on


@pytest.mark.parametrize("temperature", [15, 31, 24.5, True])
def test_temperature_out_of_range(temperature: object) -> None:
    with pytest.raises(ValueError, match="Temperature"):
        RemkoState(temperature=temperature)  # type: ignore[arg-type]


def test_timer_out_of_range() -> None:
    with pytest.raises(ValueError, match="Timer"):
        RemkoState(timer=25)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("power", "on"),
        ("mode", "cool"),
        ("fan", "auto"),
        ("swing", "off"),
        ("timer", 1.5),
    ],
)
def test_invalid_state_values_are_rejected(field: str, value: object) -> None:
    with pytest.raises(ValueError, match=f"Invalid {field}|must be an integer"):
        RemkoState(**{field: value})  # type: ignore[arg-type]


def test_timings_encode_all_bits() -> None:
    timings = RemkoProtocol._bits_to_timings("01" * 26)

    assert len(timings) == 109
    assert timings[:2] == [473, -3591]
    assert timings[2:6] == [473, -546, 473, -1583]
    assert timings[-3:] == [473, -3591, 473]


def test_default_ir_frame_regression_vector() -> None:
    state = RemkoState(power=RemkoPower.ON)

    assert RemkoProtocol.encode_frame(state) == bytes.fromhex("8300000078080d")
