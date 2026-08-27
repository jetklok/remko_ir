from __future__ import annotations

import base64


class ZosungCodec:
    """Encode and decode Zosung IR timing payloads."""

    MAX_DISTANCE = 8192
    MAX_LITERAL = 32

    @staticmethod
    def timings_to_bytes(timings: list[int]) -> bytes:
        """Serialize signed timings as little-endian uint16 values."""
        raw = bytearray()
        for timing in timings:
            value = abs(timing)
            if value > 0xFFFF:
                raise ValueError(f"Timing out of uint16 range: {value}")
            raw.extend(value.to_bytes(2, "little"))
        return bytes(raw)

    @staticmethod
    def bytes_to_timings(data: bytes) -> list[int]:
        """Deserialize Zosung timing bytes using alternating mark/space signs."""
        if len(data) % 2:
            raise ValueError("Timing data must contain complete uint16 values")
        return [
            int.from_bytes(data[index : index + 2], "little")
            * (1 if index % 4 == 0 else -1)
            for index in range(0, len(data), 2)
        ]

    @classmethod
    def encode(cls, timings: list[int]) -> str:
        """Encode timings as the base64 format used by Zigbee2MQTT."""
        return base64.b64encode(cls.compress(cls.timings_to_bytes(timings))).decode(
            "ascii"
        )

    @classmethod
    def decode(cls, code: str) -> list[int]:
        """Decode a Zigbee2MQTT base64 IR code into signed timings."""
        try:
            compressed = base64.b64decode(code, validate=True)
        except ValueError as err:
            raise ValueError("Invalid base64 Zosung code") from err
        return cls.bytes_to_timings(cls.decompress(compressed))

    @classmethod
    def compress(cls, data: bytes) -> bytes:
        """Compress raw timing bytes using the Zosung LZ format."""
        output = bytearray()
        literals = bytearray()

        def flush_literals() -> None:
            while literals:
                chunk = literals[: cls.MAX_LITERAL]
                del literals[: cls.MAX_LITERAL]
                output.append(len(chunk) - 1)
                output.extend(chunk)

        position = 0
        while position < len(data):
            length, distance = cls._find_best_match(data, position)
            if length < 3:
                literals.append(data[position])
                position += 1
                if len(literals) == cls.MAX_LITERAL:
                    flush_literals()
                continue

            flush_literals()
            length = min(length, 9 + (255 * 255) + 255)
            distance_minus_one = distance - 1
            high_distance = distance_minus_one >> 8
            low_distance = distance_minus_one & 0xFF

            if length <= 8:
                output.append(((length - 2) << 5) | high_distance)
            else:
                output.append((7 << 5) | high_distance)
                extra = length - 9
                full_extensions, remainder = divmod(extra, 255)
                output.extend([0xFF] * full_extensions)
                output.append(remainder)
            output.append(low_distance)
            position += length

        flush_literals()
        return bytes(output)

    @classmethod
    def decompress(cls, data: bytes) -> bytes:
        """Decompress a Zosung byte stream into raw timing bytes."""
        output = bytearray()
        position = 0

        while position < len(data):
            header = data[position]
            position += 1
            block_type = header >> 5

            if block_type == 0:
                length = (header & 0x1F) + 1
                if position + length > len(data):
                    raise ValueError("Truncated Zosung literal block")
                output.extend(data[position : position + length])
                position += length
                continue

            length = block_type + 2
            if length == 9:
                while position < len(data) and data[position] == 0xFF:
                    length += 255
                    position += 1
                if position >= len(data):
                    raise ValueError("Truncated Zosung extended length")
                length += data[position]
                position += 1

            if position >= len(data):
                raise ValueError("Truncated Zosung distance")
            distance = ((header & 0x1F) << 8) | data[position]
            position += 1
            offset = distance + 1
            if offset > len(output):
                raise ValueError("Invalid Zosung back-reference")
            for _ in range(length):
                output.append(output[-offset])

        return bytes(output)

    @classmethod
    def _find_best_match(cls, data: bytes, position: int) -> tuple[int, int]:
        """Find the longest available overlapping LZ match."""
        if position == 0:
            return 0, 0

        start = max(0, position - cls.MAX_DISTANCE)
        best_length = 0
        best_distance = 0

        for candidate in range(position - 1, start - 1, -1):
            distance = position - candidate
            if data[candidate] != data[position]:
                continue

            length = 0
            while position + length < len(data):
                expected = (
                    data[candidate + length]
                    if length < distance
                    else data[position + (length % distance)]
                )
                if expected != data[position + length]:
                    break
                length += 1

            if length > best_length:
                best_length = length
                best_distance = distance

        return best_length, best_distance
