
from __future__ import annotations
from dataclasses import dataclass, field
from sys import argv
from threading import Thread
from re import match
import sys
from events import _Event, MessageEvent,QuitEvent,WhisperEvent,ShutdownEvent,KickEvent,MuteEvent,EmptyEvent,SendEvent,ListEvent,SwitchEvent,Event
from socket import AF_INET, SOCK_STREAM, socket




@dataclass
class ChatClient:
    socket: socket = field(init=False)
    name: str = argv[2]
    
    def __post_init__(self):
        port = int(argv[1])
        self.socket = socket(AF_INET, SOCK_STREAM)
        self.socket.connect(('localhost', port))
        
        self.socket.send(self.name.encode())
        
        receive_thread = Thread(target=self.receive_handler, daemon=True)
        
        receive_thread.start()
    
    def interact(self):
        while True:
            message = input().strip()
            event = MessageEvent(name=self.name, message=message)
            self.send(event)
            
    def send(self,event:Event):
        message = _Event.serialise(event)
        self.socket.send(message + b'\n')            
            #probably a match check to see what stuff it wants to send. ie. a message or a command and send that to a method that makes an Event and sends it?
    
    def receive_handler(self):
        buffer = b''
        while True:
            data = self.socket.recv(1024)
            if not data:
                break
            buffer += data
            while b'\n' in buffer:
                message, buffer = buffer.split(b'\n', 1)
                self.receive(message)
    
    def receive(self, message:bytes):
        event = _Event.deserialise(message)
        
        match event:
            case MessageEvent(name = n, message = m):
                print(f"[{n}] {m}")
    
    
    
client = ChatClient()
client.interact()