from __future__ import annotations
from enum import IntEnum,auto
from typing import Type,ClassVar,Literal,TYPE_CHECKING
from dataclasses import dataclass,field
import struct
from abc import ABC,abstractmethod
from socket import socket
if TYPE_CHECKING: 
    from chatserver import ChannelClientHandler


class EventType(IntEnum):
    QUIT = auto()
    KICK = auto()
    SHUTDOWN = auto()
    MUTE = auto()
    EMPTY = auto()
    SEND = auto()
    WHISPER = auto()
    LIST = auto()
    SWITCH = auto()
    MESSAGE = auto()
    JOIN = auto()


@dataclass(kw_only=True)
class _Event(ABC):
    type: ClassVar[EventType]

    # struct packing spec; must match dataclass attribute order
    _event_map: ClassVar[dict[EventType, Type[_Event]]] = field(
        repr=False, default={}, init=False
    )

    def __init_subclass__(cls):
        # register a deserialise handler
        if cls.type in _Event._event_map:
            raise RuntimeError("cannot reregister event type")
        _Event._event_map[cls.type] = cls

    @classmethod
    def serialise(cls, obj) -> bytes:
        return struct.pack("!I", obj.type) + obj._serialise()

    @abstractmethod
    def _serialise(self) -> bytes: ...

    @classmethod
    def deserialise(cls, data: bytes) -> _Event:
        event_type = EventType(struct.unpack("!I", data[:4])[0])
        return cls._event_map[event_type]._deserialise(data=data[4:])

    @classmethod
    @abstractmethod
    def _deserialise(cls, data: bytes) -> _Event: ...


@dataclass(kw_only=True)
class MessageEvent(_Event):
    type: ClassVar[Literal[EventType.MESSAGE]] = EventType.MESSAGE
    name: str
    message: str

    def _serialise(self) -> bytes:
        return struct.pack(
            f"!I{len(self.name)}sI{len(self.message)}s",
            len(self.name),
            self.name.encode(),
            len(self.message),
            self.message.encode(),
        )

    @classmethod
    def _deserialise(cls, data: bytes) -> MessageEvent:
        name_length = struct.unpack("!I", data[:4])[0]
        name = struct.unpack(
            f"{name_length}s",
            data[4 : 4 + name_length],
        )[0].decode()
        message_length = struct.unpack("!I", data[4 + name_length : 8 + name_length])[0]
        message = struct.unpack(
            f"{message_length}s",
            data[8 + name_length : 8 + name_length + message_length],
        )[0].decode()

        return MessageEvent(
            name=name,
            message=message,
        )


@dataclass(kw_only=True)
class QuitEvent(_Event):
    type: ClassVar[Literal[EventType.QUIT]] = EventType.QUIT
    name: str
    
    def _serialise(self):
        return struct.pack(
            f"!I{len(self.name)}s",
            len(self.name),
            self.name.encode()
        )
    
    @classmethod
    def _deserialise(cls, data) -> QuitEvent:
        name_length = struct.unpack("!I", data[:4])[0]
        name = struct.unpack(
            f"{name_length}s",
            data[4 : 4 + name_length],
        )[0].decode()

        return QuitEvent(
            name=name,
        )


@dataclass(kw_only=True)
class KickEvent(_Event):
    type: ClassVar[Literal[EventType.KICK]] = EventType.KICK
    target: str

    def _serialise(self) -> bytes:
        raise RuntimeError("kick not serialisable")
    
    @classmethod
    def _deserialise(cls, data):
        raise RuntimeError("kick not deserialisable")


@dataclass(kw_only=True)
class ShutdownEvent(_Event):
    type: ClassVar[Literal[EventType.SHUTDOWN]] = EventType.SHUTDOWN

    def _serialise(self):
        return b''
    
    @classmethod
    def _deserialise(cls, data) -> ShutdownEvent:
        return ShutdownEvent()


@dataclass(kw_only=True)
class MuteEvent(_Event):
    type: ClassVar[Literal[EventType.MUTE]] = EventType.MUTE
    target: str

    def _serialise(self) -> bytes:
        raise RuntimeError("mute not serialisable")
    
    @classmethod
    def _deserialise(cls, data):
        raise RuntimeError("mute not deserialisable")


@dataclass(kw_only=True)
class EmptyEvent(_Event):
    type: ClassVar[Literal[EventType.EMPTY]] = EventType.EMPTY

    def _serialise(self) -> bytes:
        raise RuntimeError("empty not serialisable")
    
    @classmethod
    def _deserialise(cls, data):
        raise RuntimeError("empty not deserialisable")

@dataclass(kw_only=True)
class SendEvent(_Event):
    type: ClassVar[Literal[EventType.SEND]] = EventType.SEND
    message: str
    
    #target?
    #name?
    #file?
    
    def _serialise(self):
        ...
    
    @classmethod
    def _deserialise(cls, data):
        ...


@dataclass(kw_only=True)
class WhisperEvent(_Event):
    type: ClassVar[Literal[EventType.WHISPER]] = EventType.WHISPER
    name: str
    target: str
    message: str
    
    def _serialise(self):
        return struct.pack(
            f"!I{len(self.name)}sI{len(self.target)}sI{len(self.message)}s",
            len(self.name),
            self.name.encode(),
            len(self.target),
            self.target.encode(),
            len(self.message),
            self.message.encode(),
        )
    
    
    @classmethod
    def _deserialise(cls, data) -> WhisperEvent:
        name_length = struct.unpack("!I", data[:4])[0]
        name = struct.unpack(
            f"{name_length}s",
            data[4 : 4 + name_length],
        )[0].decode()
        target_length = struct.unpack("!I", data[4 + name_length : 8 + name_length])[0]
        target = struct.unpack(
            f"{target_length}s",
            data[8 + name_length : 8 + name_length + target_length],
        )[0].decode()
        message_length = struct.unpack("!I", data[8 + name_length + target_length : 12 + name_length + target_length])[0]
        message = struct.unpack(
            f"{message_length}s",
            data[12 + name_length + target_length: 12 + name_length + target_length + message_length],
        )[0].decode()

        return WhisperEvent(
            name=name,
            target=target,
            message=message
        )


@dataclass(kw_only=True)
class ListEvent(_Event):
    type: ClassVar[Literal[EventType.LIST]] = EventType.LIST
    name: str
    
    def _serialise(self):
        return struct.pack(
            f"!I{len(self.name)}s",
            len(self.name),
            self.name.encode()
        )
    
    @classmethod
    def _deserialise(cls, data) -> ListEvent:
        name_length = struct.unpack("!I", data[:4])[0]
        name = struct.unpack(
            f"{name_length}s",
            data[4 : 4 + name_length],
        )[0].decode()

        return ListEvent(
            name=name,
        )


@dataclass(kw_only=True)
class SwitchEvent(_Event):
    type: ClassVar[Literal[EventType.SWITCH]] = EventType.SWITCH
    name: str
    channel: str

    def _serialise(self) -> bytes:
        return struct.pack(
            f"!I{len(self.name)}sI{len(self.channel)}s",
            len(self.name),
            self.name.encode(),
            len(self.channel),
            self.channel.encode(),
        )

    @classmethod
    def _deserialise(cls, data: bytes) -> SwitchEvent:
        name_length = struct.unpack("!I", data[:4])[0]
        name = struct.unpack(
            f"{name_length}s",
            data[4 : 4 + name_length],
        )[0].decode()
        channel_length = struct.unpack("!I", data[4 + name_length : 8 + name_length])[0]
        channel = struct.unpack(
            f"{channel_length}s",
            data[8 + name_length : 8 + name_length + channel_length],
        )[0].decode()

        return SwitchEvent(
            name=name,
            channel=channel,
        )
        
        
@dataclass(kw_only=True)
class JoinEvent(_Event):
    type: ClassVar[Literal[EventType.JOIN]] = EventType.JOIN
    channel: str

    def _serialise(self):
        return struct.pack(
            f"!I{len(self.channel)}s",
            len(self.channel),
            self.channel.encode()
        )
    
    @classmethod
    def _deserialise(cls, data) -> JoinEvent:
        channel_length = struct.unpack("!I", data[:4])[0]
        channel = struct.unpack(
            f"{channel_length}s",
            data[4 : 4 + channel_length],
        )[0].decode()

        return JoinEvent(
            channel=channel
        )


Event = (
    MessageEvent
    | QuitEvent
    | KickEvent
    | ShutdownEvent
    | MuteEvent
    | EmptyEvent
    | SendEvent
    | WhisperEvent
    | ListEvent
    | SwitchEvent
    | JoinEvent
)
