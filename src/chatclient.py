from __future__ import annotations
from dataclasses import dataclass, field
from sys import argv
from threading import Thread
from re import match
import sys
import struct
import threading
from events import _Event, MessageEvent,QuitEvent,WhisperEvent,ShutdownEvent,KickEvent,MuteEvent,EmptyEvent,SendEvent,ListEvent,SwitchEvent,JoinEvent,Event
from socket import AF_INET, SOCK_STREAM, socket
import select


def print_usage_and_exit():
    print("Usage: chatclient port_number client_username", file=sys.stderr, flush=True)
    sys.exit(3)
    
def port_exit():
    print(f"Error: Unable to connect to port {argv[1]}.", file=sys.stderr, flush=True)
    sys.exit(7)

def check_args():
    if len(sys.argv) != 3 or " " in argv[2]:
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
    _receive_thread: Thread = field(init=False)
    running: bool = True
    
    def __post_init__(self):
        port = int(argv[1])
        self.socket = socket(AF_INET, SOCK_STREAM)
        try:
            self.socket.connect(('localhost', port))
            self.socket.send(self.name.encode())
        except:
            port_exit()  
        self.socket.settimeout(1)
        allowed = self.socket.recv(1024).decode()
        if allowed != "Y":
            print(f'[Server Message] Channel "{allowed}" already has user {sys.argv[2]}.', flush=True)
            sys.exit(2)
        print(f"Welcome to chatclient, {self.name}.")  
        self._receive_thread = Thread(target=self.receive_handler)
        self._receive_thread.start()

    def interact(self):
        while self.running:
            ready, _, _ = select.select([sys.stdin], [], [], 0.5)
            if ready:
                message = sys.stdin.readline().strip('\n')
                if not message:
                    continue
                if not message.startswith("/"):
                    event = MessageEvent(name=self.name, message=message)
                    self.send(event)
                    continue
                try:
                    match message.split()[0]:
                        case "/send":
                            if len(message.split()) != 3 or message != message.strip():
                                print("[Server Message] Usage: /send target_client_username file_path", flush=True)
                            elif message.split()[1] == self.name:
                                print("[Server Message] Cannot send file to yourself.", flush=True)
                            else:
                                event = SendEvent(name=self.name, target=message.split()[1], file=message.split()[2])
                                self.send(event)
                        case "/quit":
                            if len(message.split()) != 1 or message != message.strip():
                                print("[Server Message] Usage: /quit", flush=True)
                            else:
                                event = QuitEvent(name=self.name)
                                self.send(event)
                        case "/list":
                            if len(message.split()) != 1 or message != message.strip():
                                print("[Server Message] Usage: /list", flush=True)
                            else:
                                event = ListEvent(name=self.name)
                                self.send(event)
                        case "/whisper":
                            parts = message.split(maxsplit=2)
                            if len(parts) < 3 or message != message.strip():
                                print("[Server Message] Usage: /whisper receiver_client_username chat_message", flush=True)
                            else:
                                _, target, msg = parts
                                event = WhisperEvent(name=self.name, target=target, message=msg)
                                self.send(event)
                        case "/switch":
                            if len(message.split()) != 2 or message != message.strip():
                                print("[Server Message] Usage: /switch channel_name", flush=True)
                            else:    
                                event = SwitchEvent(name=self.name, channel=message.split()[1])
                                self.send(event)
                        case _:
                            event = MessageEvent(name=self.name, message=message)
                            self.send(event)
                except:
                    pass
  
    def send(self,event:Event):
        message = _Event.serialise(event)
        length = len(message)
        self.socket.send(struct.pack(f"!I", length) + message)
                     
    def receive_handler(self):
        while self.running:
            try:
                message_length_b = self.socket.recv(4)
            except KeyboardInterrupt as e:
                self.shutdown()
                break
            except:
                continue
            if not message_length_b:
                break
            message_length = struct.unpack("!I",message_length_b)[0]
            message = self.socket.recv(message_length)
            self.receive(message)

    def receive(self, message:bytes):
        event = _Event.deserialise(message)

        match event:
            case MessageEvent(name = n, message = m):
                print(f"[{n}] {m}", flush=True)
            case ShutdownEvent():
                print("Error: server connection closed.", file=sys.stderr, flush=True)
                self.shutdown()
                print("\n", file=sys.stdin, flush=True)
            case JoinEvent(channel=c):
                print(f'[Server Message] You have joined the channel "{c}".', flush=True)
            case QuitEvent(name=name):
                self.socket.close()
                self.shutdown()
            case KickEvent(target=t):
                print(f'[Server Message] You are removed from the channel.', flush=True)
                self.socket.close()
                self.shutdown()
            case SwitchEvent(name=name, channel=channel_port):
                self.socket.close()
                port = int(channel_port)
                self.socket = socket(AF_INET, SOCK_STREAM)
                try:
                    self.socket.connect(('localhost', port))
                    self.socket.send(name.encode())
                except:
                    self.shutdown()
                self.socket.settimeout(1)
                allowed = self.socket.recv(1024).decode()
                if allowed != "Y":
                    print(f'[Server Message] Channel "{allowed}" already has user {sys.argv[2]}.', flush=True)
                    sys.exit(2)
                print(f"Welcome to chatclient, {self.name}.")
            case SendEvent(name=n, target=t, file=f):
                print("should not print", flush=True)
                
    def shutdown(self):
        self.running = False
        self.socket.close()
        if threading.current_thread() is not self._receive_thread:
            self._receive_thread.join()
        sys.exit(0)

 

check_args()    
client = ChatClient(name=sys.argv[2])
try:
    client.interact()
except:
    client.send(QuitEvent(name=client.name))
    client.shutdown()