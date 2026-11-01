"""Run `python test_chat.py` to verify the TCP server's core behavior."""

import json
import socket
import threading
import unittest

from server import ChatServer


class TestTCPChat(unittest.TestCase):
    def setUp(self):
        self.server = ChatServer(("127.0.0.1", 0))  # OS chooses a free TCP port
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.connections = []

    def tearDown(self):
        for sock, file_obj in self.connections:
            file_obj.close()
            sock.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def join(self, name):
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=3)
        sock.settimeout(3)
        stream = sock.makefile("rb")
        self.connections.append((sock, stream))
        self.send(sock, {"type": "join", "name": name})
        return sock, stream

    @staticmethod
    def send(sock, payload):
        sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))

    @staticmethod
    def until(stream, check, limit=14):
        for _ in range(limit):
            line = stream.readline()
            if not line:
                raise AssertionError("Connection closed before expected packet")
            packet = json.loads(line.decode("utf-8"))
            if check(packet):
                return packet
        raise AssertionError("Expected packet not observed")

    def test_join_broadcast_online_users_duplicate_and_leave(self):
        alice_sock, alice = self.join("Alice")
        welcome = self.until(alice, lambda p: p.get("type") == "welcome")
        self.assertIn("Alice", welcome["text"])

        bob_sock, bob = self.join("Bob")
        self.until(bob, lambda p: p.get("type") == "welcome")
        names = self.until(alice, lambda p: p.get("type") == "users" and len(p["names"]) == 2)
        self.assertEqual(names["names"], ["Alice", "Bob"])

        self.send(alice_sock, {"type": "chat", "text": "Hello Bob!"})
        predicate = lambda p: p.get("type") == "chat" and p.get("text") == "Hello Bob!"
        self.assertEqual(self.until(alice, predicate)["name"], "Alice")
        self.assertEqual(self.until(bob, predicate)["name"], "Alice")

        duplicate_sock, duplicate_stream = self.join("alice")
        duplicate_error = self.until(duplicate_stream, lambda p: p.get("type") == "error")
        self.assertIn("already", duplicate_error["text"])

        self.send(bob_sock, {"type": "leave"})
        updated = self.until(alice, lambda p: p.get("type") == "users" and p["names"] == ["Alice"])
        self.assertEqual(updated["names"], ["Alice"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
