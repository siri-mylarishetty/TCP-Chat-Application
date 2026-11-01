"""TCP Chat Lab Project - graphical client (Tkinter, no extra packages).

Run twice: python client.py, then join as different usernames.
"""

import json
import queue
import socket
import threading
import tkinter as tk
from tkinter import messagebox, ttk

MAX_PACKET_BYTES = 4096
MAX_MESSAGE_LENGTH = 500
BG = "#f3f6fb"
NAVY = "#17324d"
TEAL = "#087e82"
TEXT = "#243746"
GRAY = "#627486"


class ChatApp:
    def __init__(self, root):
        self.root = root
        root.title("NetworkLab Messenger | TCP Chat")
        root.geometry("840x610")
        root.minsize(700, 510)
        root.configure(bg=BG)

        self.host_var = tk.StringVar(value="127.0.0.1")
        self.port_var = tk.StringVar(value="5000")
        self.name_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Not connected")
        self.socket = None
        self.connected = False
        self.connecting = False
        self.generation = 0
        self.events = queue.Queue()
        self.send_lock = threading.Lock()
        self._make_ui()
        self.root.after(100, self._read_events)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _make_ui(self):
        header = tk.Frame(self.root, bg=NAVY, padx=22, pady=16)
        header.pack(fill="x")
        tk.Label(header, text="NetworkLab Messenger", bg=NAVY, fg="white",
                 font=("Segoe UI", 19, "bold")).pack(anchor="w")
        tk.Label(header, text="A real-time multi-user chat built using TCP/IP socket programming",
                 bg=NAVY, fg="#c9dee6", font=("Segoe UI", 10)).pack(anchor="w", pady=(3, 0))

        connect = tk.Frame(self.root, bg="white", padx=16, pady=12,
                           highlightbackground="#dce5ec", highlightthickness=1)
        connect.pack(fill="x", padx=18, pady=(16, 12))
        for label_text, variable, width in [
            ("Server IP", self.host_var, 18),
            ("Port", self.port_var, 7),
            ("Your username", self.name_var, 17),
        ]:
            group = tk.Frame(connect, bg="white")
            group.pack(side="left", padx=(0, 12))
            tk.Label(group, text=label_text, bg="white", fg=GRAY,
                     font=("Segoe UI", 9)).pack(anchor="w")
            entry = ttk.Entry(group, textvariable=variable, width=width,
                              font=("Segoe UI", 10))
            entry.pack(pady=(4, 0), ipady=3)
            if variable is self.host_var:
                self.host_entry = entry
            elif variable is self.port_var:
                self.port_entry = entry
            else:
                self.name_entry = entry
                entry.bind("<Return>", lambda e: self._toggle_connection())
        self.connect_button = tk.Button(connect, text="Connect", command=self._toggle_connection,
                                        bg=TEAL, fg="white", activebackground="#056a6d",
                                        activeforeground="white", borderwidth=0,
                                        cursor="hand2", font=("Segoe UI", 10, "bold"),
                                        padx=21, pady=9)
        self.connect_button.pack(side="right", pady=(14, 0))

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        body.grid_columnconfigure(0, weight=4)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        conversation = tk.Frame(body, bg="white", highlightbackground="#dce5ec",
                                highlightthickness=1)
        conversation.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        tk.Label(conversation, text="Group conversation", bg="white", fg=NAVY,
                 font=("Segoe UI", 12, "bold"), padx=16, pady=12).pack(anchor="w")
        tk.Frame(conversation, bg="#e5edf3", height=1).pack(fill="x")
        compose = tk.Frame(conversation, bg="white", padx=11, pady=12)
        compose.pack(fill="x", side="bottom")
        self.message_var = tk.StringVar()
        self.message_entry = ttk.Entry(compose, textvariable=self.message_var,
                                       font=("Segoe UI", 11), state="disabled")
        self.message_entry.pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 9))
        self.message_entry.bind("<Return>", lambda event: self._send_message())
        self.send_button = tk.Button(compose, text="Send ➤", command=self._send_message,
                                     bg=TEAL, fg="white", borderwidth=0, cursor="hand2",
                                     font=("Segoe UI", 10, "bold"), padx=15, pady=10,
                                     state="disabled")
        self.send_button.pack(side="right")

        area = tk.Frame(conversation, bg="white")
        area.pack(fill="both", expand=True, padx=12, pady=7)
        scroll = ttk.Scrollbar(area)
        scroll.pack(side="right", fill="y")
        self.log = tk.Text(area, wrap="word", relief="flat", borderwidth=0,
                           bg="white", fg=TEXT, font=("Segoe UI", 10),
                           padx=6, pady=6, yscrollcommand=scroll.set,
                           state="disabled", spacing1=5, spacing3=4, height=8)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.configure(command=self.log.yview)
        self.log.tag_configure("system", foreground=GRAY, font=("Segoe UI", 9, "italic"))
        self.log.tag_configure("mine", foreground="#007d77", font=("Segoe UI", 10, "bold"))
        self.log.tag_configure("other", foreground=NAVY, font=("Segoe UI", 10, "bold"))
        self.log.tag_configure("error", foreground="#c43a43")
        self.log.tag_configure("body", foreground=TEXT, font=("Segoe UI", 10))
        tk.Frame(conversation, bg="#e5edf3", height=1).pack(fill="x")

        sidebar = tk.Frame(body, bg="white", highlightbackground="#dce5ec",
                           highlightthickness=1)
        sidebar.grid(row=0, column=1, sticky="nsew")
        tk.Label(sidebar, text="Online users", bg="white", fg=NAVY,
                 font=("Segoe UI", 11, "bold"), padx=14, pady=15).pack(anchor="w")
        tk.Frame(sidebar, bg="#e5edf3", height=1).pack(fill="x")
        self.users_list = tk.Listbox(sidebar, borderwidth=0, highlightthickness=0,
                                     activestyle="none", bg="white", fg=TEXT,
                                     font=("Segoe UI", 10), selectbackground="#c5e9e8")
        self.users_list.pack(fill="both", expand=True, padx=12, pady=12)
        tk.Label(sidebar, text="Uses TCP port 5000 by default", bg="white", fg=GRAY,
                 font=("Segoe UI", 8), wraplength=155, justify="left",
                 padx=12, pady=12).pack(anchor="w")

        footer = tk.Frame(self.root, bg=BG, padx=19, pady=5)
        footer.pack(fill="x", side="bottom")
        tk.Label(footer, textvariable=self.status_var, bg=BG, fg=GRAY,
                 font=("Segoe UI", 9)).pack(side="left")
        tk.Label(footer, text="Computer Networks Lab • TCP/IP", bg=BG, fg=GRAY,
                 font=("Segoe UI", 9)).pack(side="right")
        self._append("SYSTEM", "Start the server, enter your username, and click Connect.", "system")

    def _append(self, label, content, kind):
        self.log.configure(state="normal")
        if kind == "system":
            self.log.insert("end", f"• {content}\n", "system")
        elif kind == "error":
            self.log.insert("end", f"• {content}\n", "error")
        else:
            self.log.insert("end", label + "\n", "mine" if kind == "mine" else "other")
            self.log.insert("end", content + "\n", "body")
        self.log.configure(state="disabled")
        self.log.see("end")

    def _toggle_connection(self):
        if self.connected or self.connecting:
            self._disconnect(manual=True)
            return
        name = self.name_var.get().strip()
        host = self.host_var.get().strip()
        try:
            port = int(self.port_var.get())
        except ValueError:
            messagebox.showerror("Invalid port", "Enter a numeric port (e.g. 5000).")
            return
        if not 1 <= port <= 65535 or not host or not 2 <= len(name) <= 20 or not all(c.isascii() and (c.isalnum() or c in "_ ") for c in name):
            messagebox.showerror("Check details", "Provide a server IP, valid port and a 2-20 character username (letters/numbers/spaces/underscores).")
            return
        self.generation += 1
        generation = self.generation
        self.connecting = True
        self.connect_button.configure(text="Cancel")
        self.status_var.set("Connecting to server...")
        worker = threading.Thread(target=self._connect_worker,
                                  args=(host, port, name, generation), daemon=True)
        worker.start()

    def _connect_worker(self, host, port, name, generation):
        sock = None
        try:
            sock = socket.create_connection((host, port), timeout=4)
            sock.settimeout(None)
            packet = json.dumps({"type": "join", "name": name}, ensure_ascii=False)
            sock.sendall((packet + "\n").encode("utf-8"))
            self.events.put((generation, "socket", sock))
            with sock.makefile("rb") as stream:
                while True:
                    line = stream.readline(MAX_PACKET_BYTES + 1)
                    if not line:
                        break
                    if len(line) > MAX_PACKET_BYTES:
                        raise ValueError("Received an oversized packet")
                    packet = json.loads(line.decode("utf-8"))
                    if isinstance(packet, dict):
                        self.events.put((generation, "packet", packet))
        except (OSError, ValueError, UnicodeError) as exc:
            self.events.put((generation, "error", str(exc)))
        finally:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
            self.events.put((generation, "closed", None))

    def _read_events(self):
        try:
            while True:
                generation, event, payload = self.events.get_nowait()
                if generation != self.generation:
                    # Release an obsolete socket created by a cancelled attempt.
                    if event == "socket":
                        payload.close()
                    continue
                if event == "socket":
                    self.socket = payload
                elif event == "packet":
                    self._handle_packet(payload)
                elif event == "error":
                    self._append("ERROR", f"Network error: {payload}", "error")
                elif event == "closed":
                    self._disconnect(manual=False)
        except queue.Empty:
            pass
        self.root.after(100, self._read_events)

    def _handle_packet(self, packet):
        kind = packet.get("type")
        if kind == "welcome":
            self.connected = True
            self.connecting = False
            self.connect_button.configure(text="Disconnect", bg="#b2474e")
            self.message_entry.configure(state="normal")
            self.send_button.configure(state="normal")
            self.host_entry.configure(state="disabled")
            self.port_entry.configure(state="disabled")
            self.name_entry.configure(state="disabled")
            self.status_var.set(f"Connected as {self.name_var.get()} • TCP connection active")
            self._append("SYSTEM", packet.get("text", "Connected"), "system")
            self.message_entry.focus_set()
        elif kind == "users":
            self.users_list.delete(0, "end")
            for name in packet.get("names", []):
                self.users_list.insert("end", "●  " + str(name))
        elif kind == "chat":
            sender = str(packet.get("name", "Unknown"))
            when = str(packet.get("time", ""))
            self._append(f"{sender}  •  {when}", str(packet.get("text", "")),
                         "mine" if sender == self.name_var.get().strip() else "other")
        elif kind == "system":
            self._append("SYSTEM", str(packet.get("text", "")), "system")
        elif kind == "error":
            self._append("ERROR", str(packet.get("text", "Unexpected server error")), "error")

    def _send_message(self):
        if not self.connected or self.socket is None:
            return
        content = self.message_var.get().strip()
        if not content:
            return
        if len(content) > MAX_MESSAGE_LENGTH:
            messagebox.showwarning("Message too long", "Maximum message length is 500 characters.")
            return
        try:
            packet = json.dumps({"type": "chat", "text": content}, ensure_ascii=False) + "\n"
            with self.send_lock:
                self.socket.sendall(packet.encode("utf-8"))
            self.message_var.set("")
        except OSError as exc:
            self._append("ERROR", f"Could not send message: {exc}", "error")
            self._disconnect(manual=False)

    def _disconnect(self, manual=False):
        was_active = self.connected or self.connecting
        self.generation += 1
        sock, self.socket = self.socket, None
        if sock is not None:
            if manual and self.connected:
                try:
                    with self.send_lock:
                        sock.sendall(b'{"type":"leave"}\n')
                except OSError:
                    pass
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass
        self.connected = False
        self.connecting = False
        self.connect_button.configure(text="Connect", bg=TEAL)
        self.message_entry.configure(state="disabled")
        self.send_button.configure(state="disabled")
        self.host_entry.configure(state="normal")
        self.port_entry.configure(state="normal")
        self.name_entry.configure(state="normal")
        self.users_list.delete(0, "end")
        self.status_var.set("Not connected")
        if was_active:
            self._append("SYSTEM", "Disconnected." if manual else "Connection closed.", "system")

    def _close(self):
        self._disconnect(manual=True)
        self.root.destroy()


def main():
    root = tk.Tk()
    ChatApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
