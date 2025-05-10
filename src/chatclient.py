
from __future__ import annotations
from dataclasses import dataclass, field
from sys import argv
from threading import Thread
from re import match
import sys
import struct
from events import _Event, MessageEvent,QuitEvent,WhisperEvent,ShutdownEvent,KickEvent,MuteEvent,EmptyEvent,SendEvent,ListEvent,SwitchEvent,JoinEvent,Event
from socket import AF_INET, SOCK_STREAM, socket

def print_usage_and_exit():
    print("Usage: chatclient port_number client_username", file=sys.stderr, flush=True)
    sys.exit(3)
    
def port_exit():
    print(f"Error: Unable to connect to port {argv[1]}.", file=sys.stderr, flush=True)
    sys.exit(3)

def check_args():
    if len(sys.argv) != 3:
        print_usage_and_exit()

    try:
        port_number = int(sys.argv[1])
        if not (1024 <= port_number <= 65535):
            port_exit()
    except ValueError:
        port_exit()

    client_username = sys.argv[2]
    if not client_username:
        print_usage_and_exit()


@dataclass
class ChatClient:
    socket: socket = field(init=False)
    name: str
    
    def __post_init__(self):
        port = int(argv[1])
        self.socket = socket(AF_INET, SOCK_STREAM)
        try:
            self.socket.connect(('localhost', port))
            self.socket.send(self.name.encode())
        except:
            port_exit()  
        print(f"Welcome to chatclient, {self.name}.")  
        receive_thread = Thread(target=self.receive_handler, daemon=True)
        receive_thread.start()

    
    def interact(self):
        while True:
            message = input().strip()
            event = MessageEvent(name=self.name, message=message)
            self.send(event)
                
    def send(self,event:Event):
        message = _Event.serialise(event)
        length = len(message)
        self.socket.send(struct.pack(f"!I", length) + message)
                 
            #probably a match check to see what stuff it wants to send. ie. a message or a command and send that to a method that makes an Event and sends it?
    
    def receive_handler(self):
        while True:
                # get the first 4 bytes determining message length L
                # get L bytes and process via `self.receive`
            message_length_b = self.socket.recv(4)
            if not message_length_b:
                break
            message_length: int = struct.unpack("!I",message_length_b)[0]
            message = self.socket.recv(message_length)
            self.receive(message)
    
    def receive(self, message:bytes):
        event = _Event.deserialise(message)
        
        match event:
            case MessageEvent(name = n, message = m):
                print(f"[{n}] {m}", flush=True)
            case ShutdownEvent():
                print("shutting down client", flush=True)
                print("Error: server connection closed.", file=sys.stderr, flush=True)
                self.socket.close()
                exit(8)
            case JoinEvent(channel=c):
                print(f'[Server Message] You have joined the channel "{c}".', flush=True)
    

check_args()    

client = ChatClient(name=sys.argv[2])
client.interact()
