from __future__ import annotations
from dataclasses import dataclass, field
from re import match
from queue import Queue
from socket import *
import sys
from threading import Thread,Event as threading_Event
import threading
from enum import IntEnum, auto
from typing import Literal, ClassVar, Type
from abc import ABC, abstractmethod
import struct
from events import _Event, MessageEvent,QuitEvent,WhisperEvent,ShutdownEvent,KickEvent,MuteEvent,EmptyEvent,SendEvent,ListEvent,SwitchEvent,JoinEvent,Event
from collections.abc import Sequence

def print_usage_and_exit():
    print("Usage: chatserver [afk_time] config_file", file=sys.stderr, flush=True)
    sys.exit(4)

def check_args():
    if len(sys.argv) == 2:
        pass
    elif len(sys.argv) == 3:
        try:
            afk_timer = int(sys.argv[1])
            if not (1<= afk_timer <=1000):
                print_usage_and_exit()
        except ValueError:
            print_usage_and_exit()
    else:
        print_usage_and_exit()



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
                    print(f"Error: Invalid configuration file.", file=sys.stderr, flush=True)
                    sys.exit(5)
                    
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
    
    _channels: list[ChannelServer] = field(default_factory=list, init=False) # changed this from = []

    def __post_init__(self) -> None:
        for c in self.channel_configs:
            self._channels.append(
                ChannelServer(config=c, server=self),
            )
        print("Welcome to chatserver.", flush=True)
    
    
    def start(self):    
        while True:
            command = input().split()
            #would this be how to wait for commands for server? should i send events to channels and if so, how do i prioritise them perhaps
            try:
                match command[0]: #this but the first word only. trying to do it 
                    case "/shutdown":
                        print("shutting down...", flush=True)
                        self.shutdown()
                        print("shutdown channels...", flush=True)
                        #sys.exit() # shutdown server
                    case "/kick":
                        ...
                    case "/mute":
                        ...
                    case "/empty":
                        ...
            except:
                continue
                    
    def shutdown(self):
        for channel in self._channels:
            channel.broadcast(ShutdownEvent())
        #should also send a shutdown event to the client (who cannot send one back) to trigger a client shutdown
            
            
    # Should handle server commands -> Create even in respective ChannelServer
    
    

@dataclass(kw_only=True)
class ChannelServer:
    config: ChannelConfig
    server: ChatServer

    _clients: dict[str, ChannelClientHandler] = field(default_factory=dict, init=False)

    _waitlist: list[ChannelClientHandler] = field(default_factory=list, init=False)
    
    sock: socket = field(init=False)
    # need to store metadata on the event, e.g., the socket
    _events: Queue[Event] = field(default_factory=Queue, init=False)
    
    @property
    def client_names(self) -> Sequence[str]:
        return (*self._clients.keys(), *(c.name for c in self._waitlist))

    def __post_init__(self) -> None:
        # TODO: spin up a thread listening on our port
        self.sock = socket(AF_INET, SOCK_STREAM)
        try:
            self.sock.bind(("", self.config.port))
            self.sock.listen()
        except:
            print(f"Error: unable to listen on port {self.config.port}.", file=sys.stderr, flush=True)
            sys.exit(6)
        print(f'Channel "{self.config.name}" is created on port {self.config.port}, with a capacity of {self.config.capacity}.', flush=True)
        
        listen = threading.Thread(target=self._listen, daemon=True)
        handle = threading.Thread(target=self._handler, daemon=True)
        listen.start()
        handle.start()

    def _listen(self) -> None:
        # this should run in a thread listening on `self.port`
        # when a client joins, queue a join event to `_events`
        

        while True:
            client_sock, addr = self.sock.accept()
            client_handler = ChannelClientHandler(socket=client_sock, channel=self)
            if len(self._clients) >= self.config.capacity:
                client_handler.send(_Event.serialise(MessageEvent(name="Server Message", message=f"You are in the waiting queue and there are {len(self._waitlist)} user(s) ahead of you.")))
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
                        for idx, client in enumerate(self._waitlist):
                            client.send(_Event.serialise(MessageEvent(name="Server Message" ,message=f"You are in the waiting queue and there are {idx} user(s) ahead of you.")))


    def _join(self, client: ChannelClientHandler) -> None:
        self._clients[client.name] = client
        print(f'[Server Message] {client.name} has joined the channel "{self.config.name}".', flush=True)      
        client.join()
        # notify user/server

    def _quit(self, name) -> None:
        # if a user runs `/quit`
        # print any notices that the user has left
        self._clients.pop(name)
        
    def broadcast(self, event: Event) -> None:
        for client in self._clients.values():
            client.send(_Event.serialise(event)) #check to see if this is ok? maybe _Event.serialise?
                

@dataclass(kw_only=True)
class ChannelClientHandler:
    socket: socket
    channel: ChannelServer

    name: str = field(init=False)
    
    muted: bool = False
    joined: bool = False

    def __post_init__(self) -> None:
        #get name from client
        self.name = self.socket.recv(1024).decode()

        channel_client_names = self.channel.client_names
        if self.name in channel_client_names:
            # reject! (not sure how to reject because you need to take it out. not let it join the waitlist or clients)
            ...
            
        receive_thread = Thread(target=self.receive_handler, daemon=True)
        receive_thread.start()
    
    def join(self) -> None:
        # TODO: spin up a running our handler
        self.joined = True
        self.send(_Event.serialise(JoinEvent(channel=self.channel.config.name)))

        
    # method to send message to user
    def message(self,message: str):
        message_event = MessageEvent(name="server", message=message)
        self.socket.send(message_event._serialise())        
            
    def send(self,message:bytes):
        length = len(message)
        self.socket.send(struct.pack(f"!I", length) + message)
            
            #probably a match check to see what stuff it wants to send. ie. a message or a command and send that to a method that makes an Event and sends it?
    
    def receive_handler(self):
        while True:
            message_length_b = self.socket.recv(4)
            if not message_length_b:
                break
            message_length: int = struct.unpack("!I",message_length_b)[0]
            message = self.socket.recv(message_length)
            self.receive(message)
                
    
    def receive(self, message:bytes):
        event = _Event.deserialise(message)
        
        match event:
                case MessageEvent(name=n, message=m):
                    if self.joined and not self.muted:
                        assert self.name == n
                        print(f"[{n}] {m}", flush=True)
                        self.channel.broadcast(event)
                case QuitEvent():
                    ...
                case SendEvent():
                    ...
                case WhisperEvent():
                    ...
                case ListEvent():
                    ...
                case SwitchEvent():
                    ...


check_args()
#start the server here?
if len(sys.argv) == 3:
    channel_configs = load_channel_configs(sys.argv[2])
else:
    channel_configs = load_channel_configs(sys.argv[1])


server = ChatServer(channel_configs=channel_configs)
server.start()