from __future__ import annotations
from dataclasses import dataclass, field
import os
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
        try:
            with open(filename, 'r') as file:
                for line in file:
                    parts = line.strip().split()
                    try:
                        channel, name, port_str, capacity_str = parts
                        if channel != "channel":
                            print("Error: Invalid configuration file.", file=sys.stderr, flush=True)
                            sys.exit(5)
                        config = ChannelConfig(
                            name=name,
                            port=int(port_str),
                            capacity=int(capacity_str)
                        )
                        configs.append(config)
                    except (ValueError, AssertionError):
                        print(f"Error: Invalid configuration file.", file=sys.stderr, flush=True)
                        sys.exit(5)
        except FileNotFoundError:
            print_usage_and_exit()
        except:
            sys.exit(5)
        if len(configs) == 0:
            print("Error: Invalid configuration file.", file=sys.stderr, flush=True)
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
        

@dataclass(kw_only=True)
class ChatServer:
    channel_configs: list[ChannelConfig]
    _channels: list[ChannelServer] = field(default_factory=list, init=False)
    _server_thread: Thread = field(init=False)
    running: bool = True

    def __post_init__(self) -> None:
        for c in self.channel_configs:
            self._channels.append(
                ChannelServer(config=c, server=self),
            )
        print("Welcome to chatserver.", flush=True)
        self._server_thread = Thread(target=self.start)
        self._server_thread.start()
    
    def start(self):    
        while self.running:
            try:
                message = input()
            except:
                message = "/shutdown"
            command = message.split()
            try:
                match command[0]:
                    case "/shutdown":
                        if message != message.strip() or len(command) != 1:
                            print("Usage: /shutdown", flush=True)
                        else:
                            self.shutdown()
                            print("[Server Message] Server shuts down.", flush=True)
                            break
                    case "/kick":
                        if message != message.strip() or len(command) != 3:
                            print("Usage: /kick channel_name client_username", flush=True)
                        else:
                            for channel in self._channels:
                                if channel.config.name == command[1]:
                                    channel._events.put(KickEvent(target=command[2]))
                                    break
                            else:
                                print(f'[Server Message] Channel "{command[1]}" does not exist.', flush=True)                                
                    case "/mute":
                        ...
                    case "/empty":
                        if message != message.strip() or len(command) != 2:
                            print("Usage: /empty channel_name", flush=True)
                        else:
                            for channel in self._channels:
                                if channel.config.name == command[1]:
                                    channel._events.put(EmptyEvent())
                                    break
                            else:
                                print(f'[Server Message] Channel "{command[1]}" does not exist.', flush=True)  
            except:
                continue
                    
    def shutdown(self):
        for channel in self._channels:
            channel.shutdown()
            channel._events.put(ShutdownEvent())
        self.running = False


@dataclass(kw_only=True)
class ChannelServer:
    config: ChannelConfig
    server: ChatServer
    _clients: dict[str, ChannelClientHandler] = field(default_factory=dict, init=False)
    _waitlist: list[ChannelClientHandler] = field(default_factory=list, init=False)
    sock: socket = field(init=False)
    _events: Queue[Event] = field(default_factory=Queue, init=False)
    running: bool = True
    _listen_thread: Thread = field(init=False)
    _handle_thread: Thread = field(init=False)
    
    @property
    def client_names(self) -> Sequence[str]:
        return (*self._clients.keys(), *(c.name for c in self._waitlist))

    def __post_init__(self) -> None:
        # TODO: spin up a thread listening on our port
        self.sock = socket(AF_INET, SOCK_STREAM)
        try:
            self.sock.bind(("", self.config.port))
            self.sock.listen()
            self.sock.settimeout(1.0)
        except:
            print(f"Error: unable to listen on port {self.config.port}.", file=sys.stderr, flush=True)
            sys.exit(6)
        print(f'Channel "{self.config.name}" is created on port {self.config.port}, with a capacity of {self.config.capacity}.', flush=True)
        
        self._listen_thread = threading.Thread(target=self._listen)
        self._handle_thread = threading.Thread(target=self._handler)
        self._listen_thread.start()
        self._handle_thread.start()

    def _listen(self) -> None:
        while self.running:
            try:
                client_sock, addr = self.sock.accept()
            except:
                continue
            client_handler = ChannelClientHandler(socket=client_sock, channel=self)
            if client_handler.name not in self.client_names:
                if len(self._clients) >= self.config.capacity:
                    client_handler.send(_Event.serialise(MessageEvent(name="Server Message", message=f"You are in the waiting queue and there are {len(self._waitlist)} user(s) ahead of you.")))
                    self._waitlist.append(client_handler)
                else:
                    self._join(client_handler)

    def _handler(self) -> None:
        while self.running:
            try:
                event = self._events.get(timeout=1)
            except:
                continue
            match event:
                case KickEvent(target=t):
                    for all in list(self._clients.values()) + self._waitlist:
                        if all.name == t:
                            self._quit(t)
                            all.send(_Event.serialise(KickEvent(target=t)))
                            all.joined = False
                            print(f"[Server Message] Kicked {t}.", flush=True)
                            for client in self._clients:
                                if client != t and client not in self._waitlist:
                                    client_handler = self._clients.get(client)
                                    if client_handler != None:
                                        client_handler.send(_Event.serialise(MessageEvent(name="Server Message",message=f"{t} has left the channel.")))
                                else:
                                    pass
                            if len(self._waitlist):
                                self._join(self._waitlist.pop(0))
                                for idx, c in enumerate(self._waitlist):
                                    c.send(_Event.serialise(MessageEvent(name="Server Message" ,message=f"You are in the waiting queue and there are {idx} user(s) ahead of you.")))
                            break
                    else:
                        print(f'[Server Message] {t} is not in the channel.', flush=True)
                case ShutdownEvent():
                    self.running = False
                case MuteEvent():
                    ...
                case EmptyEvent():
                    print(f'[Server Message] "{self.config.name}" has been emptied.', flush=True)
                    for c in list(self._clients.values()):
                        self._quit(c.name)
                        c.send(_Event.serialise(KickEvent(target=c.name)))
                        c.joined = False        
                        if len(self._waitlist):
                            self._join(self._waitlist.pop(0))
                            for idx, c in enumerate(self._waitlist):
                                c.send(_Event.serialise(MessageEvent(name="Server Message" ,message=f"You are in the waiting queue and there are {idx} user(s) ahead of you.")))

                    

    def _join(self, client: ChannelClientHandler) -> None:
        self._clients[client.name] = client
        print(f'[Server Message] {client.name} has joined the channel "{self.config.name}".', flush=True)      
        client.join()

    def _quit(self, name) -> None:
        self._clients.pop(name)
        
    def broadcast(self, event: Event) -> None:
        for client in self._clients.values():
            client.send(_Event.serialise(event))
    
    def all_broadcast(self, event: Event) -> None:
        for all in list(self._clients.values()) + self._waitlist:
            all.send(_Event.serialise(event))
    
    def shutdown(self):
        self.running = False
        self.all_broadcast(ShutdownEvent())
        self._listen_thread.join()
        self._handle_thread.join()
                

@dataclass(kw_only=True)
class ChannelClientHandler:
    socket: socket
    channel: ChannelServer
    name: str = field(init=False)
    muted: bool = False
    joined: bool = False
    running: bool = True

    def __post_init__(self) -> None:
        self.name = self.socket.recv(1024).decode()
        channel_client_names = self.channel.client_names
        self.socket.settimeout(1)
        if self.name in channel_client_names:
            self.socket.send(self.channel.config.name.encode())
            self.running = False
        else:
            self.socket.send(b"Y")
            receive_thread = Thread(target=self.receive_handler)
            receive_thread.start()
    
    def join(self) -> None:
        self.joined = True
        self.send(_Event.serialise(JoinEvent(channel=self.channel.config.name)))

    def message(self,message: str):
        message_event = MessageEvent(name="server", message=message)
        self.socket.send(message_event._serialise())        
            
    def send(self,message:bytes):
        length = len(message)
        self.socket.send(struct.pack(f"!I", length) + message)
                
    def receive_handler(self):
        while self.running:
            try:
                message_length_b = self.socket.recv(4)
            except TimeoutError:
                continue
            # if message_length_b == b'':
            #     self.running = False
            #     self.channel._quit(self.name)
            #     self.joined = False
            #     print(f"[Server Message] {self.name} has left the channel.", flush=True)
            #     for client in self.channel._clients:
            #         if client != self.name and client not in self.channel._waitlist:
            #             client_handler = self.channel._clients.get(client)
            #             if client_handler != None:
            #                 client_handler.send(_Event.serialise(MessageEvent(name="Server Message",message=f"{self.name} has left the channel.")))
            #         else:
            #             pass
            #     if len(self.channel._waitlist):
            #         self.channel._join(self.channel._waitlist.pop(0))
            #         for idx, c in enumerate(self.channel._waitlist):
            #             c.send(_Event.serialise(MessageEvent(name="Server Message" ,message=f"You are in the waiting queue and there are {idx} user(s) ahead of you.")))
            #else:   
            if not message_length_b:
                break
            message_length = struct.unpack("!I",message_length_b)[0]
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
                case QuitEvent(name=name):
                    self.channel._quit(name)
                    self.send(_Event.serialise(QuitEvent(name=name)))
                    self.joined = False
                    print(f"[Server Message] {name} has left the channel.", flush=True)
                    for client in self.channel._clients:
                        if client != name and client not in self.channel._waitlist:
                            client_handler = self.channel._clients.get(client)
                            if client_handler != None:
                                client_handler.send(_Event.serialise(MessageEvent(name="Server Message",message=f"{name} has left the channel.")))
                        else:
                            pass
                    if len(self.channel._waitlist):
                        self.channel._join(self.channel._waitlist.pop(0))
                        for idx, c in enumerate(self.channel._waitlist):
                            c.send(_Event.serialise(MessageEvent(name="Server Message" ,message=f"You are in the waiting queue and there are {idx} user(s) ahead of you.")))
                case SendEvent():
                    ...
                case WhisperEvent(name=sender, target=receiver, message=msg):
                    r = self.channel._clients.get(receiver)
                    if r != None:
                        self.channel._events.put(event)
                        self.send(_Event.serialise(MessageEvent(name=f"{self.name} whispers to {receiver}", message=msg)))
                        r.send(_Event.serialise(MessageEvent(name=f"{sender} whispers to you", message=msg)))
                        print(f"[{sender} whispers to {receiver}] {msg}", flush=True)
                    else:
                        self.send(_Event.serialise(MessageEvent(name="Server Message", message=f"{receiver} is not in the channel.")))
                case ListEvent():
                    for channel in self.channel.server._channels:
                        self.send(_Event.serialise(MessageEvent(name="Channel", message=f"{channel.config.name} {channel.config.port} Capacity: {len(channel._clients)}/{channel.config.capacity}, Queue: {len(channel._waitlist)}")))
                case SwitchEvent(name=name, channel=channel_name):
                    original_channel = self.channel
                    for channel in self.channel.server._channels:
                        if channel.config.name == channel_name:
                            if name in channel.client_names:
                                self.send(_Event.serialise(MessageEvent(name="Server Message", message=f'Channel "{channel.config.name}" already has user {name}.')))
                                break
                            else:
                                self.channel._quit(name)
                                self.joined = False
                                print(f'[Server Message] {name} has left the channel.', flush=True)
                                original_channel.broadcast(event=MessageEvent(name="Server Message", message=f"{name} has left the channel."))
                                if len(original_channel._waitlist):
                                    original_channel._join(self.channel._waitlist.pop(0))
                                    for idx, c in enumerate(original_channel._waitlist):
                                        c.send(_Event.serialise(MessageEvent(name="Server Message" ,message=f"You are in the waiting queue and there are {idx} user(s) ahead of you.")))
                                self.send(_Event.serialise(SwitchEvent(name=name, channel=str(channel.config.port))))
                                break
                    else:
                        self.send(_Event.serialise(MessageEvent(name="Server Message", message=f'Channel "{channel_name}" does not exist.')))
                        
                    


check_args()
#start the server here?
if len(sys.argv) == 3:
    channel_configs = load_channel_configs(sys.argv[2])
else:
    channel_configs = load_channel_configs(sys.argv[1])

server = ChatServer(channel_configs=channel_configs)
sys.exit()