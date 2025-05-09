from __future__ import annotations
from dataclasses import dataclass, field
from re import match
from queue import Queue
from socket import *
import sys
from threading import Thread
import threading
from enum import IntEnum, auto
from typing import Literal, ClassVar, Type
from abc import ABC, abstractmethod
import struct
from events import _Event, MessageEvent,QuitEvent,WhisperEvent,ShutdownEvent,KickEvent,MuteEvent,EmptyEvent,SendEvent,ListEvent,SwitchEvent,Event
from collections.abc import Sequence


def load_channel_configs(filename: str) -> list[ChannelConfig]:
        configs = []
        with open(filename, 'r') as file:
            for line in file:
                parts = line.strip().split()
                try:
                    _, name, port_str, capacity_str = parts
                    config = ChannelConfig(
                        name=name,
                        port=int(port_str),
                        capacity=int(capacity_str)
                    )
                    configs.append(config)
                except (ValueError, AssertionError):
                    print(f"Invalid channel config line: {line.strip()}", file=sys.stderr)
        return configs
    
    
@dataclass(kw_only=True)
class ChannelConfig:
    name: str
    port: int
    capacity: int

    def __post_init__(self) -> None:
        assert match(r"^[a-zA-Z0-9_]+$", self.name)
        assert 1024 <= self.port <= 65535
        assert 1 <= self.capacity <= 8
        

#need to actually implement a "read" from the config file
# SERVER_CONFIG: list[ChannelConfig] = [
#     ChannelConfig(name="core", port=2000, capacity=5),
#     ChannelConfig(name="future", port=2030, capacity=2),
# ]

# assert len(set(c.name for c in SERVER_CONFIG)) == len(SERVER_CONFIG)


@dataclass(kw_only=True)
class ChatServer:
    channel_configs: list[ChannelConfig]

    _channels: list[ChannelServer] = field(default_factory=list) # changed this from = []

    def __post_init__(self) -> None:
        for c in self.channel_configs:
            self._channels.append(
                ChannelServer(config=c, server=self),
            )
        
        while True:
            command = input().split()
            #would this be how to wait for commands for server? should i send events to channels and if so, how do i prioritise them perhaps
            
            match command[0]: #this but the first word only. trying to do it 
                case "/shutdown":
                    ... # shutdown server
                case "/kick":
                    ...
                case "/mute":
                    ...
                case "/empty":
                    ...
                

    # Should handle server commands -> Create even in respective ChannelServer
    


@dataclass(kw_only=True)
class ChannelServer:
    config: ChannelConfig
    server: ChatServer

    _clients: dict[str, ChannelClientHandler] = field(default_factory=dict, init=False)

    _waitlist: list[ChannelClientHandler] = field(default_factory=list, init=False)

    # need to store metadata on the event, e.g., the socket
    _events: Queue[Event] = field(default_factory=Queue, init=False)
    
    @property
    def client_names(self) -> Sequence[str]:
        return (*self._clients.keys(), *(c.name for c in self._waitlist))

    def __post_init__(self) -> None:
        # TODO: spin up a thread listening on our port
        listen = threading.Thread(target=self._listen)
        handle = threading.Thread(target=self._handler)
        listen.start()
        handle.start()

    def _listen(self) -> None:
        # this should run in a thread listening on `self.port`
        # when a client joins, queue a join event to `_events`
        sock = socket(AF_INET, SOCK_STREAM)
        sock.bind(("", self.config.port))
        sock.listen()

        while True:
            client_sock, addr = sock.accept()
            client_handler = ChannelClientHandler(socket=client_sock, channel=self)
            if len(self._clients) >= self.config.capacity:
                self._waitlist.append(client_handler)
                # notify how many in front of queue
            else:
                self._join(client_handler)

    def _handler(self) -> None:
        # runs in a thread, processing from `_events`
        # iterates events
        # if join: if capacity, add client via `_join`; else queue on `_waitlist` and notify
        # if leave: remove client from `_clients`; permit from `_waitlist`
        while True:
            event = self._events.get()
            match event:
                case KickEvent():
                    ...
                case ShutdownEvent():
                    ...
                case MuteEvent():
                    ...
                case EmptyEvent():
                    ...
                case QuitEvent(name=name): #im confused will this even reach queue? should this not be handled in ChannelClientHandler's _handler method?
                    # remove client from _clients
                    self._quit(name)
                    if self._waitlist:
                        self._join(self._waitlist.pop(0))

    def _join(self, client: ChannelClientHandler) -> None:
        self._clients[client.name] = client
        client.start()
        # notify user/server

    def _quit(self, name) -> None:
        # if a user runs `/quit`
        # print any notices that the user has left
        self._clients.pop(name)
        
    def broadcast(self, message: str) -> None:
        message_event = MessageEvent(name="server", message=message)
        for client in self._clients.values():
            client.socket.send(message_event._serialise()) #check to see if this is ok? maybe _Event.serialise?


@dataclass(kw_only=True)
class ChannelClientHandler:
    socket: socket
    channel: ChannelServer
    
    name: str = field(init=False)
    
    muted: bool = False

    def __post_init__(self) -> None:
        #get name from client
        self.name = self.socket.recv(1024).decode()

        channel_client_names = self.channel.client_names
        if self.name in channel_client_names:
            # reject! (not sure how to reject because you need to take it out. not let it join the waitlist or clients)
            ...
        
        
    
    
    def start(self) -> None:
        # TODO: spin up a running our handler
        send_thread = Thread(target=self.send_handler)
        receive_thread = Thread(target=self.receive_handler)
        
        send_thread.start()
        receive_thread.start()


    # def _handler(self) -> None:
    #     # handles receiving messages/comments from client (should this handle ALL non join or non serverside events (aka. quit))
    #     while True:
    #         event = _Event.deserialise(self.socket.recv(8000))
    #          # is this correct?
            
    #         match event:
    #             case MessageEvent():
    #                 ...
    #             case QuitEvent():
    #                 ...
    #             case SendEvent():
    #                 ...
    #             case WhisperEvent():
    #                 ...
    #             case ListEvent():
    #                 ...
    #             case SwitchEvent():
    #                 ...
    #             #can deal with the right format in the client 
        
        
    # method to send message to user
    def message(self,message: str):
        message_event = MessageEvent(name="server", message=message)
        self.socket.send(message_event._serialise())
        
    def broadcast(self,message: str):
        ...
        

    def send_handler(self):
        while True:
            message = input().encode()
            self.send(message)
           
            
    def send(self,message:bytes):

        self.socket.send(message)
        self.socket.send(b'\x00')
            
            #probably a match check to see what stuff it wants to send. ie. a message or a command and send that to a method that makes an Event and sends it?
    
    
    def receive_handler(self):
        buffer = b''
        while True:
            data = self.socket.recv(1024)
            if not data:
                break
            buffer += data
            while b'\x00' in buffer:
                message, buffer = buffer.split(b'\x00', 1)
                self.receive(message)
        
    
    def receive(self, message:bytes):
        print(message.decode())



#start the server here?
channel_configs = load_channel_configs(sys.argv[2])

ChatServer(channel_configs=channel_configs)