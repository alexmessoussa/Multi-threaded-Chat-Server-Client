
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
    
    def __post_init__(self):
        port = int(argv[1])
        self.socket = socket(AF_INET, SOCK_STREAM)
        self.socket.connect(('localhost', port))
        
        self.socket.send(argv[2].encode())
        
        send_thread = Thread(target=self.send_handler)
        receive_thread = Thread(target=self.receive_handler)
        
        send_thread.start()
        receive_thread.start()
        

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
    
    
ChatClient()