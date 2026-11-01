"""TCP Chat Lab Project - multiclient chat server.

Uses only Python's standard library. Run: python server.py
For LAN demos: python server.py --host 0.0.0.0
"""

import argparse
import json
import re
import socketserver
import threading
from datetime import datetime

MAX_PACKET_BYTES = 4096
MAX_MESSAGE_LENGTH = 500


def timestamp():
    return datetime.now().strftime("%H:%M:%S")


class ChatServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address):
        super().__init__(address, ChatHandler)
        self.users = {}  # Maps each connected handler to a username
        self.users_lock = threading.Lock()

    def register(self, handler, name):
        with self.users_lock:
            if any(existing.casefold() == name.casefold() for existing in self.users.values()):
                return False
            self.users[handler] = name
            return True

    def unregister(self, handler):
        with self.users_lock:
            name = self.users.pop(handler, None)
        if name:
            print(f"[{timestamp()}] {name} disconnected", flush=True)
            self.broadcast({"type": "system", "text": f"{name} left the chat.", "time": timestamp()})
            self.publish_user_list()

    def broadcast(self, packet):
        with self.users_lock:
            recipients = list(self.users)
        for recipient in recipients:
            try:
                recipient.send_packet(packet)
            except OSError:
                # The recipient's own handler will remove it when the socket closes.
                pass

    def publish_user_list(self):
        with self.users_lock:
            names = sorted(self.users.values(), key=str.casefold)
        self.broadcast({"type": "users", "names": names})


class ChatHandler(socketserver.StreamRequestHandler):
    def setup(self):
        super().setup()
        self.send_lock = threading.Lock()
        self.username = None

    def send_packet(self, packet):
        encoded = (json.dumps(packet, ensure_ascii=False) + "\n").encode("utf-8")
        with self.send_lock:
            self.wfile.write(encoded)
            self.wfile.flush()

    def read_packet(self):
        line = self.rfile.readline(MAX_PACKET_BYTES + 1)
        if not line:
            return None
        if len(line) > MAX_PACKET_BYTES:
            raise ValueError("Packet too large")
        try:
            packet = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise ValueError("Invalid message format") from exc
        if not isinstance(packet, dict):
            raise ValueError("Invalid message format")
        return packet

    def handle(self):
        peer = self.client_address[0]
        try:
            first = self.read_packet()
            if first is None:
                return
            if first.get("type") != "join":
                self.send_packet({"type": "error", "text": "First packet must be a join request."})
                return

            username = first.get("name", "")
            if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_ ]{2,20}", username) or username.strip() != username:
                self.send_packet({"type": "error", "text": "Username must be 2-20 letters, numbers, spaces or underscores."})
                return
            if not self.server.register(self, username):
                self.send_packet({"type": "error", "text": "That username is already being used."})
                return

            self.username = username
            self.send_packet({"type": "welcome", "text": f"Connected to chat server as {username}."})
            print(f"[{timestamp()}] {username} connected from {peer}", flush=True)
            self.server.broadcast({"type": "system", "text": f"{username} joined the chat.", "time": timestamp()})
            self.server.publish_user_list()

            while True:
                packet = self.read_packet()
                if packet is None:
                    return
                if packet.get("type") == "leave":
                    return
                if packet.get("type") != "chat":
                    self.send_packet({"type": "error", "text": "Unsupported message type."})
                    continue
                text = packet.get("text")
                if not isinstance(text, str):
                    self.send_packet({"type": "error", "text": "Message must be text."})
                    continue
                text = text.replace("\r", " ").replace("\n", " ").strip()
                if not text or len(text) > MAX_MESSAGE_LENGTH:
                    self.send_packet({"type": "error", "text": "Message must contain 1-500 characters."})
                    continue
                self.server.broadcast({"type": "chat", "name": username, "text": text, "time": timestamp()})
                print(f"[{timestamp()}] {username}: {text}", flush=True)

        except (ConnectionError, BrokenPipeError, OSError):
            pass  # The client disconnected or lost its connection.
        except ValueError as exc:
            try:
                self.send_packet({"type": "error", "text": str(exc)})
            except OSError:
                pass
        finally:
            self.server.unregister(self)


def main():
    parser = argparse.ArgumentParser(description="Multiclient TCP chat server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="TCP port (default: 5000)")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")

    try:
        with ChatServer((args.host, args.port)) as server:
            host, port = server.server_address
            print("=" * 52)
            print("       COMPUTER NETWORKS: TCP CHAT SERVER")
            print("=" * 52)
            print(f"Listening on {host}:{port}")
            print("Open client.py twice to demonstrate communication.")
            print("Press Ctrl+C to stop the server.")
            print("=" * 52, flush=True)
            try:
                server.serve_forever(poll_interval=0.2)
            except KeyboardInterrupt:
                print("\nServer stopped.")
    except OSError as exc:
        print(f"Could not start server: {exc}")
        print("Try another port: python server.py --port 5001")


if __name__ == "__main__":
    main()
