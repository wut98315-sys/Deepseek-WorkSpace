# -*- coding: utf-8 -*-
"""极简 FTP 服务器(仅测试用,标准库实现)。

只实现 ftplib 被动模式上传所需的最小命令集:
USER/PASS/TYPE/PASV/STOR/SIZE/CWD/MKD/PWD/NOOP/QUIT
"""
import os
import socket
import threading

REAL_USER = "tester"
REAL_PASS = "secret"


class FakeFTPServer:
    def __init__(self, rootdir, host="127.0.0.1", port=2121, user=REAL_USER, password=REAL_PASS):
        self.root = os.path.abspath(rootdir)
        self.user = user
        self.password = password
        self._ls = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._ls.bind((host, port))
        self._ls.listen(16)
        self._alive = True
        threading.Thread(target=self._accept_loop, daemon=True).start()

    # ---------- helpers ----------
    def _abs(self, path):
        parts = []
        for seg in (path or "/").replace("\\", "/").split("/"):
            if seg in ("", "."):
                continue
            if seg == "..":
                raise FileNotFoundError(path)
            parts.append(seg)
        return os.path.join(self.root, *parts)

    @staticmethod
    def _reply(f, code, text=""):
        f.write(("%d %s\r\n" % (code, text)).encode("utf-8"))
        f.flush()

    # ---------- accept loop ----------
    def _accept_loop(self):
        while self._alive:
            try:
                conn, _ = self._ls.accept()
            except OSError:
                break
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def close(self):
        self._alive = False
        try:
            self._ls.close()
        except OSError:
            pass

    # ---------- one control connection ----------
    def _serve(self, conn):
        conn.settimeout(180)
        f = conn.makefile("rwb", buffering=0)
        logged_in = False
        username = ""
        try:
            self._reply(f, 220, "FakeFTP ready")
            passive = None  # listening data socket
            while True:
                line = f.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").strip("\r\n")
                if not text:
                    continue
                if " " in text:
                    verb, arg = text.split(" ", 1)
                else:
                    verb, arg = text, ""
                verb = verb.upper()

                if verb == "USER":
                    username = arg
                    self._reply(f, 331, "User name okay, need password")
                elif verb == "PASS":
                    if username == self.user and arg == self.password:
                        logged_in = True
                        self._reply(f, 230, "User logged in")
                    else:
                        self._reply(f, 530, "Login incorrect")
                elif verb == "QUIT":
                    self._reply(f, 221, "Goodbye")
                    break
                elif verb == "NOOP":
                    self._reply(f, 200, "OK")
                elif not logged_in:
                    self._reply(f, 530, "Please login with USER and PASS")
                elif verb == "TYPE":
                    self._reply(f, 200, "Type set")
                elif verb == "PWD":
                    self._reply(f, 257, '"/"')
                elif verb == "SYST":
                    self._reply(f, 215, "UNIX Type: L8")
                elif verb == "PASV":
                    ds = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    ds.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    ds.bind(("127.0.0.1", 0))
                    ds.listen(1)
                    ds.settimeout(30)
                    if passive:
                        try:
                            passive.close()
                        except OSError:
                            pass
                    passive = ds
                    port = ds.getsockname()[1]
                    self._reply(f, 227, "Entering Passive Mode (%s,%d,%d)" % (
                        ",".join("127.0.0.1".split(".")), port // 256, port % 256))
                elif verb == "CWD":
                    try:
                        p = self._abs(arg)
                        if os.path.isdir(p):
                            self._reply(f, 250, "CWD successful")
                        else:
                            self._reply(f, 550, "No such directory")
                    except FileNotFoundError:
                        self._reply(f, 550, "No such directory")
                elif verb == "MKD":
                    try:
                        os.makedirs(self._abs(arg), exist_ok=False)
                        self._reply(f, 257, '"%s" created' % arg)
                    except OSError:
                        self._reply(f, 550, "Create directory failed")
                elif verb == "SIZE":
                    p = self._abs(arg)
                    if os.path.isfile(p):
                        self._reply(f, 213, str(os.path.getsize(p)))
                    else:
                        self._reply(f, 550, "File not found")
                elif verb == "STOR":
                    if passive is None:
                        self._reply(f, 425, "Use PASV first")
                        continue
                    p = self._abs(arg)
                    dconn = None
                    try:
                        self._reply(f, 150, "Opening BINARY mode data connection")
                        dconn, _ = passive.accept()
                        dconn.settimeout(60)
                        os.makedirs(os.path.dirname(p), exist_ok=True)
                        with open(p, "wb") as out:
                            while True:
                                chunk = dconn.recv(65536)
                                if not chunk:
                                    break
                                out.write(chunk)
                        dconn.close()
                        dconn = None
                        self._reply(f, 226, "Transfer complete")
                    except OSError as exc:
                        if dconn:
                            try:
                                dconn.close()
                            except OSError:
                                pass
                        self._reply(f, 426, "Transfer aborted: %s" % exc)
                    finally:
                        if passive:
                            try:
                                passive.close()
                            except OSError:
                                pass
                        passive = None
                else:
                    self._reply(f, 502, "Command not implemented")
        except (OSError, socket.timeout):
            pass
        finally:
            try:
                f.close()
            except Exception:
                pass
            try:
                conn.close()
            except OSError:
                pass
