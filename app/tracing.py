"""Small W3C Trace Context helper for log and response correlation."""

from __future__ import annotations

import re
import secrets

HEX16 = re.compile(r"^[0-9a-f]{16}$")
HEX32 = re.compile(r"^[0-9a-f]{32}$")


class TraceContext:
    __slots__ = ("trace_id", "span_id", "sampled")

    def __init__(self, trace_id: str, span_id: str, sampled: bool = True) -> None:
        self.trace_id = trace_id
        self.span_id = span_id
        self.sampled = sampled

    @classmethod
    def from_traceparent(cls, header: str | None) -> TraceContext:
        if header:
            parts = header.strip().split("-")
            if (
                len(parts) == 4
                and parts[0] == "00"
                and HEX32.match(parts[1])
                and HEX16.match(parts[2])
                and parts[1] != "0" * 32
                and parts[2] != "0" * 16
            ):
                return cls(parts[1], secrets.token_hex(8), parts[3] == "01")
        return cls(secrets.token_hex(16), secrets.token_hex(8))

    @property
    def traceparent(self) -> str:
        flag = "01" if self.sampled else "00"
        return f"00-{self.trace_id}-{self.span_id}-{flag}"

    @property
    def request_id(self) -> str:
        return self.span_id
