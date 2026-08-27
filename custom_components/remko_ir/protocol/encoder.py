"""Public encoder for Remko state to Zigbee2MQTT IR codes."""

from .models import RemkoState
from .remko import RemkoProtocol
from .zosung import ZosungCodec


class RemkoIREncoder:
    """Encode a Remko state in the Zosung format expected by Zigbee2MQTT."""

    @staticmethod
    def encode(state: RemkoState) -> str:
        """Return a base64-encoded Zosung IR code."""
        return ZosungCodec.encode(RemkoProtocol.encode_timings(state))
