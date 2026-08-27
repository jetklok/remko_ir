import pytest

from custom_components.remko_ir.protocol import (
    RemkoFanMode,
    RemkoIREncoder,
    RemkoMode,
    RemkoPower,
    RemkoProtocol,
    RemkoState,
    RemkoSwingMode,
    ZosungCodec,
)


def decode_zosung_independently(data: bytes) -> bytes:
    """Decode Zosung blocks independently from ZosungCodec."""
    output = bytearray()
    position = 0

    while position < len(data):
        header = data[position]
        position += 1
        block_type = header >> 5

        if block_type == 0:
            length = (header & 0x1F) + 1
            output.extend(data[position : position + length])
            position += length
            continue

        length = block_type + 2
        if length == 9:
            while data[position] == 0xFF:
                length += 255
                position += 1
            length += data[position]
            position += 1

        distance = ((header & 0x1F) << 8) | data[position]
        position += 1
        offset = distance + 1

        for _ in range(length):
            output.append(output[-offset])

    return bytes(output)


def test_timings_to_bytes_uses_unsigned_little_endian() -> None:
    assert ZosungCodec.timings_to_bytes([473, -3591]) == bytes([0xD9, 0x01, 0x07, 0x0E])


def test_bytes_to_timings_restores_alternating_signs() -> None:
    raw = ZosungCodec.timings_to_bytes([473, -3591, 546, -1583])

    assert ZosungCodec.bytes_to_timings(raw) == [473, -3591, 546, -1583]


@pytest.mark.parametrize(
    "raw",
    [b"abc", b"abcabc", b"abcabcabcabc", bytes(range(64))],
)
def test_compression_round_trip(raw: bytes) -> None:
    compressed = ZosungCodec.compress(raw)

    assert decode_zosung_independently(compressed) == raw
    assert ZosungCodec.decompress(compressed) == raw


def test_compression_uses_literal_and_back_reference() -> None:
    assert ZosungCodec.compress(b"abcabc") == bytes.fromhex("026162632002")


def test_extended_back_reference_round_trip() -> None:
    raw = b"abc" * 100

    compressed = ZosungCodec.compress(raw)

    assert decode_zosung_independently(compressed) == raw


def test_odd_length_timing_data_is_rejected() -> None:
    with pytest.raises(ValueError, match="complete uint16"):
        ZosungCodec.bytes_to_timings(b"\x00")


def test_invalid_timing_is_rejected() -> None:
    with pytest.raises(ValueError, match="uint16"):
        ZosungCodec.timings_to_bytes([0x10000])


def test_invalid_back_reference_is_rejected() -> None:
    with pytest.raises(ValueError, match="back-reference"):
        ZosungCodec.decompress(bytes.fromhex("2000"))


def test_zosung_base64_round_trip() -> None:
    timings = [473, -3591, 473, -546]

    assert ZosungCodec.decode(ZosungCodec.encode(timings)) == timings


def test_remko_ir_code_round_trips_through_zosung_codec() -> None:
    state = RemkoState(
        power=RemkoPower.ON,
        mode=RemkoMode.DRY,
        fan=RemkoFanMode.MEDIUM,
        swing=RemkoSwingMode.ON,
        temperature=28,
        timer=12,
    )

    assert ZosungCodec.decode(
        RemkoIREncoder.encode(state)
    ) == RemkoProtocol.encode_timings(state)
