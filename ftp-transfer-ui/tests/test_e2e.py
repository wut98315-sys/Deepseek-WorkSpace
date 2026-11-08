# -*- coding: utf-8 -*-
"""端到端测试:真实 FTP 服务器(pyftpdlib) + server.py + HTTP 上传"""
import base64
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = "127.0.0.1"
UI_PORT = 8799
FTP_PORT = 2121

FTP_USER = "tester"
FTP_PASS = "secret"


def b64(s):
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def http_request(method, path, body=None, headers=None):
    conn = http.client.HTTPConnection(HOST, UI_PORT, timeout=60)
    conn.request(method, path, body=body, headers=headers or {})
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return resp.status, data


def probe(cfg):
    st, data = http_request("POST", "/api/probe", body=json.dumps(cfg).encode("utf-8"),
                            headers={"Content-Type": "application/json"})
    return json.loads(data.decode("utf-8"))


def upload(rel, content, remote_dir="/upload/folder", overwrite=True, user=FTP_USER, password=FTP_PASS):
    cfg = {"host": HOST, "port": FTP_PORT, "user": user, "password": password,
           "remote_dir": remote_dir, "create_missing": True, "overwrite": overwrite}
    headers = {"Content-Type": "application/octet-stream",
               "X-Ftp-Cfg": b64(json.dumps(cfg)), "X-Ftp-Rel": b64(rel)}
    st, data = http_request("POST", "/api/upload", body=content, headers=headers)
    return st, json.loads(data.decode("utf-8"))


def wait_port(port, timeout=15):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            s = socket.create_connection((HOST, port), timeout=1)
            s.close()
            return True
        except OSError:
            time.sleep(0.25)
    return False


def start_ftp_server(rootdir):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from fake_ftp import FakeFTPServer

    server = FakeFTPServer(rootdir, HOST, FTP_PORT, user=FTP_USER, password=FTP_PASS)
    return server


results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond)))
    print(("PASS | " if cond else "FAIL | ") + name + ((" | " + str(extra)) if extra else ""))


def main():
    rootdir = tempfile.mkdtemp(prefix="ftp_ui_e2e_")
    ui_log = os.path.join(ROOT, "ui_test.log")
    if os.path.exists(ui_log):
        os.remove(ui_log)
    ftp = None
    ui = None
    try:
        ftp = start_ftp_server(rootdir)
        check("FTP server listening", wait_port(FTP_PORT))

        ui = subprocess.Popen(
            [sys.executable, os.path.join(ROOT, "server.py"), "--no-open",
             "--host", HOST, "--port", str(UI_PORT)],
            cwd=ROOT, stdout=open(ui_log, "w"), stderr=subprocess.STDOUT)
        check("UI server listening", wait_port(UI_PORT))

        # --- basic static & health ---
        st, data = http_request("GET", "/api/health")
        check("health ok", st == 200 and json.loads(data)["ok"])
        st, body = http_request("GET", "/")
        check("index served", st == 200 and "FTP 远程文件传输".encode("utf-8") in body)
        st, body = http_request("GET", "/app.js")
        check("app.js served", st == 200 and b"runQueue" in body)
        st, body = http_request("GET", "/style.css")
        check("style.css served", st == 200)

        base_cfg = {"host": HOST, "port": FTP_PORT, "user": FTP_USER, "password": FTP_PASS,
                    "remote_dir": "/upload/folder", "create_missing": True}

        # --- probe ---
        r = probe(dict(base_cfg, password="wrong-pass"))
        check("probe rejects wrong password", r["ok"] is False and "登录" in r["error"], r)

        r = probe(dict(base_cfg, port=FTP_PORT + 1))
        check("probe reports connection refused", r["ok"] is False and "拒绝" in r["error"], r)

        r = probe(dict(base_cfg, remote_dir="/no-such-dir", create_missing=False))
        check("probe detects missing dir", r["ok"] is False and "不存在" in r["error"], r)

        r = probe(dict(base_cfg, remote_dir="/a/b/c"))
        check("probe auto-creates missing dir", r["ok"] is True, r)

        # --- uploads ---
        content_a = "你好, hello world!".encode("utf-8")
        st, r = upload("hello.txt", content_a)
        p = os.path.join(rootdir, "upload", "folder", "hello.txt")
        check("upload single file", r["ok"] and r["action"] == "uploaded" and os.path.isfile(p), r)
        check("upload content intact", open(p, "rb").read() == content_a)

        content_b = b"second payload \x00\x01\x02"
        st, r = upload("a/b/c.bin", content_b)
        p = os.path.join(rootdir, "upload", "folder", "a", "b", "c.bin")
        check("upload nested dirs", r["ok"] and os.path.isfile(p), r)
        check("nested content intact", open(p, "rb").read() == content_b)

        p = os.path.join(rootdir, "upload", "folder", "hello.txt")
        st, r = upload("hello.txt", b"NEW-CONTENT", overwrite=False)
        check("overwrite=false skips existing", r["ok"] and r["action"] == "skipped"
              and open(p, "rb").read() == content_a, r)

        st, r = upload("hello.txt", b"NEW-CONTENT", overwrite=True)
        check("overwrite=true replaces", r["ok"] and r["action"] == "uploaded"
              and open(p, "rb").read() == b"NEW-CONTENT", r)

        zh_rel = "中文目录/子 目录/报告-文件.txt"
        zh_content = "中文内容测试 UTF-8 ☺".encode("utf-8")
        st, r = upload(zh_rel, zh_content)
        p = os.path.join(rootdir, "upload", "folder", "中文目录", "子 目录", "报告-文件.txt")
        check("upload chinese/spaces path", r["ok"] and os.path.isfile(p), r)
        check("chinese content intact", open(p, "rb").read() == zh_content)

        st, r = upload("top.txt", b"at root", remote_dir="/")
        p = os.path.join(rootdir, "top.txt")
        check("upload to remote /", r["ok"] and os.path.isfile(p) and open(p, "rb").read() == b"at root", r)

        st, r = upload("empty.txt", b"")
        p = os.path.join(rootdir, "upload", "folder", "empty.txt")
        check("upload zero-byte file", r["ok"] and r["action"] == "uploaded" and os.path.isfile(p)
              and os.path.getsize(p) == 0, r)

        # --- missing config ---
        conn = http.client.HTTPConnection(HOST, UI_PORT, timeout=10)
        conn.request("POST", "/api/upload", body=b"x")
        resp = conn.getresponse()
        resp.read()
        conn.close()
        check("upload missing cfg header -> 400", resp.status == 400)

        # folder of files: multiple files under same new tree
        files = [("tree/d1/f1.txt", b"1"), ("tree/d1/f2.txt", b"22"), ("tree/d2/f3.txt", b"333")]
        all_ok = True
        for rel, c in files:
            st, r = upload(rel, c, remote_dir="/treebase")
            all_ok = all_ok and r.get("ok") and os.path.isfile(os.path.join(rootdir, "treebase", rel.replace("/", os.sep)))
        check("folder-tree upload keeps structure", all_ok)

    finally:
        if ui is not None:
            ui.terminate()
            try:
                ui.wait(timeout=5)
            except Exception:
                ui.kill()
        if ftp is not None:
            ftp.close()
        try:
            shutil.rmtree(rootdir, ignore_errors=True)
        except Exception:
            pass

    failed = [n for n, c in results if not c]
    print("-" * 50)
    print("TOTAL: %d passed / %d failed / %d cases" % (len(results) - len(failed), len(failed), len(results)))
    if failed:
        print("FAILED CASES:", failed)
        try:
            print(open(ui_log, encoding="utf-8", errors="replace").read()[-2000:])
        except Exception:
            pass
        code = 1
    else:
        code = 0
    try:
        os.remove(ui_log)
    except OSError:
        pass
    return code


if __name__ == "__main__":
    sys.exit(main())
