"""cTrader Open API wire format: Protobuf messages over TLS, each one length-prefixed.

Facts (docs/ctrader_api_notes.md says which were seen on the wire):
- Every message on the connection is a ProtoMessage {payloadType, payload, clientMsgId}.
  payload is the serialized inner message (ProtoOAApplicationAuthReq, ...), payloadType
  says which one it is, clientMsgId is ours and comes back on the reply.
- On TCP each ProtoMessage is preceded by its length: 4 bytes, big-endian, not counting
  the 4 bytes themselves (help.ctrader.com "Send and receive Protobuf messages": read
  four bytes, reverse them on a little-endian machine, read that many bytes; Spotware's
  own Python SDK uses Twisted's Int32StringReceiver, which is the same thing).
"""

from __future__ import annotations

import asyncio
import struct
from dataclasses import dataclass
from typing import Any

from google.protobuf.message import DecodeError, Message

from fxbot.ctrader.proto import OpenApiCommonMessages_pb2 as common
from fxbot.ctrader.proto import OpenApiCommonModelMessages_pb2 as common_model
from fxbot.ctrader.proto import OpenApiMessages_pb2 as oa
from fxbot.ctrader.proto import OpenApiModelMessages_pb2 as model

MAX_FRAME = 16 * 1024 * 1024        # far above any reply we ask for; protects against a garbage length
_LEN = struct.Struct(">I")


def _payload_types() -> dict[str, int]:
    names: dict[str, int] = {}
    for enum in (model.ProtoOAPayloadType, common_model.ProtoPayloadType):
        for v in enum.DESCRIPTOR.values:
            names[v.name] = v.number
    return names


PT = _payload_types()                 # "PROTO_OA_APPLICATION_AUTH_REQ" -> 2100, "HEARTBEAT_EVENT" -> 51, ...
PT_NAME = {v: k for k, v in PT.items()}


def _registry() -> dict[int, type[Message]]:
    """payloadType -> message class, read from each message's payloadType default."""
    out: dict[int, type[Message]] = {}
    for module in (oa, common):
        for name, desc in module.DESCRIPTOR.message_types_by_name.items():
            field = desc.fields_by_name.get("payloadType")
            if field is None or not field.has_default_value:
                continue
            out[field.default_value] = getattr(module, name)
    return out


MESSAGES = _registry()


def payload_type_of(msg: Message) -> int:
    return msg.DESCRIPTOR.fields_by_name["payloadType"].default_value


@dataclass
class Envelope:
    payload_type: int
    client_msg_id: str | None
    message: Message | None           # None when the payloadType is unknown to these definitions

    @property
    def name(self) -> str:
        return PT_NAME.get(self.payload_type, str(self.payload_type))


def encode(msg: Message, client_msg_id: str | None = None) -> bytes:
    """One framed ProtoMessage ready to write to the socket."""
    wrapper = common.ProtoMessage(payloadType=payload_type_of(msg), payload=msg.SerializeToString())
    if client_msg_id is not None:
        wrapper.clientMsgId = client_msg_id
    body = wrapper.SerializeToString()
    return _LEN.pack(len(body)) + body


def decode(body: bytes) -> Envelope:
    """A ProtoMessage body (without the length prefix) -> Envelope with the inner message parsed."""
    wrapper = common.ProtoMessage()
    wrapper.ParseFromString(body)
    cls = MESSAGES.get(wrapper.payloadType)
    inner = None
    if cls is not None:
        inner = cls()
        inner.ParseFromString(wrapper.payload)
    cid = wrapper.clientMsgId if wrapper.HasField("clientMsgId") else None
    return Envelope(wrapper.payloadType, cid, inner)


class FrameError(ConnectionError):
    """The byte stream does not look like cTrader framing."""


async def read_frame(reader: asyncio.StreamReader) -> bytes:
    """Read one length-prefixed body. Raises asyncio.IncompleteReadError at end of stream."""
    head = await reader.readexactly(4)
    (length,) = _LEN.unpack(head)
    if length > MAX_FRAME:
        raise FrameError(f"frame of {length} bytes is larger than the {MAX_FRAME} limit")
    return await reader.readexactly(length)


def split_frames(data: bytes) -> tuple[list[bytes], bytes]:
    """Synchronous helper (tests, probes): complete bodies in data, and the leftover bytes."""
    out = []
    while len(data) >= 4:
        (length,) = _LEN.unpack(data[:4])
        if len(data) < 4 + length:
            break
        out.append(data[4:4 + length])
        data = data[4 + length:]
    return out, data


def to_dict(msg: Message) -> dict[str, Any]:
    """Message -> plain dict (field names as in the .proto, enums as names). For logs and Quote.raw;
    never call it on messages that carry an access token without redacting (see redact)."""
    from google.protobuf.json_format import MessageToDict
    return MessageToDict(msg, preserving_proto_field_name=True)


SECRET_FIELDS = ("clientSecret", "accessToken", "refreshToken")


def redact(d: dict[str, Any]) -> dict[str, Any]:
    """Copy of a to_dict() result with secrets replaced by '***'."""
    out = {}
    for k, v in d.items():
        if k in SECRET_FIELDS:
            out[k] = "***"
        elif isinstance(v, dict):
            out[k] = redact(v)
        else:
            out[k] = v
    return out


__all__ = ["PT", "PT_NAME", "MESSAGES", "Envelope", "encode", "decode", "read_frame", "split_frames",
           "FrameError", "to_dict", "redact", "oa", "model", "common", "DecodeError"]
