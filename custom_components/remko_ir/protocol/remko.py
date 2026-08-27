from __future__ import annotations

from typing import ClassVar

from ..const import MIN_TIMER, TEMPERATURE_BASE
from .models import RemkoFanMode, RemkoMode, RemkoPower, RemkoState, RemkoSwingMode


class RemkoProtocol:
    """Encode Remko RKL 495 state as an IR frame and timings."""

    IR_MARK: ClassVar[int] = 473
    IR_ZERO_SPACE: ClassVar[int] = 546
    IR_ONE_SPACE: ClassVar[int] = 1583
    IR_HEADER_SPACE: ClassVar[int] = 3591
    IR_TRAILER_SPACE: ClassVar[int] = 3591

    _COOL_MODE_NIBBLES: ClassVar[dict[RemkoFanMode, int]] = {
        RemkoFanMode.AUTO: 0x0,
        RemkoFanMode.MEDIUM: 0x1,
        RemkoFanMode.LOW: 0x2,
        RemkoFanMode.HIGH: 0x8,
    }
    _FIXED_MODE_NIBBLES: ClassVar[dict[RemkoMode, int]] = {
        RemkoMode.DRY: 0x4,
        RemkoMode.FAN_ONLY: 0x3,
    }

    @classmethod
    def encode_frame(cls, state: RemkoState) -> bytes:
        """Build the six-byte frame and its four-bit checksum."""
        payload = bytearray(
            [
                0x83 if state.power == RemkoPower.ON else 0x80,
                cls._build_byte_2(state),
                0x00,
                0x00,
                cls._build_byte_5(state),
                cls._build_byte_6(state),
            ]
        )
        payload.append(cls._get_payload_checksum(payload))
        return bytes(payload)

    @classmethod
    def encode_bits(cls, state: RemkoState) -> str:
        """Return the 52-bit Remko frame representation."""
        payload = cls.encode_frame(state)
        return "".join(f"{byte:08b}" for byte in payload[:6]) + f"{payload[6]:04b}"

    @classmethod
    def encode_timings(cls, state: RemkoState) -> list[int]:
        """Return the signed mark/space timings for the Remko frame."""
        return cls._bits_to_timings(cls.encode_bits(state))

    @staticmethod
    def _build_byte_2(state: RemkoState) -> int:
        return 0x00 if state.timer == MIN_TIMER else 0x80 | (state.timer * 4)

    @staticmethod
    def _build_byte_5(state: RemkoState) -> int:
        swing_bit = 0x00 if state.swing == RemkoSwingMode.ON else 0x20
        lower_nibble = {
            RemkoFanMode.AUTO: 0x8,
            RemkoFanMode.HIGH: 0x8,
            RemkoFanMode.MEDIUM: 0x9,
            RemkoFanMode.LOW: 0xA,
        }[state.fan]
        return (0x70 & ~0x20) | swing_bit | lower_nibble

    @classmethod
    def _build_byte_6(cls, state: RemkoState) -> int:
        if state.mode == RemkoMode.COOL:
            upper_nibble = cls._COOL_MODE_NIBBLES[state.fan]
        else:
            upper_nibble = cls._FIXED_MODE_NIBBLES.get(state.mode)
        if upper_nibble is None:
            raise ValueError(f"Unsupported mode: {state.mode}")
        return (upper_nibble << 4) | (state.temperature - TEMPERATURE_BASE)

    @staticmethod
    def _get_payload_checksum(payload: bytearray) -> int:
        nibble_sum = sum((byte >> 4) + (byte & 0x0F) for byte in payload)
        return (15 - (nibble_sum % 16)) & 0x0F

    @classmethod
    def _bits_to_timings(cls, bits: str) -> list[int]:
        if len(bits) != 52:
            raise ValueError(f"Expected 52 bits, got {len(bits)}")
        if any(bit not in "01" for bit in bits):
            raise ValueError("Bitstream contains characters other than 0/1")

        timings = [cls.IR_MARK, -cls.IR_HEADER_SPACE]
        for bit in bits:
            timings.extend(
                [
                    cls.IR_MARK,
                    -cls.IR_ONE_SPACE if bit == "1" else -cls.IR_ZERO_SPACE,
                ]
            )
        timings.extend([cls.IR_MARK, -cls.IR_TRAILER_SPACE, cls.IR_MARK])
        return timings
