#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FTP 远程文件传输工具 —— 本地 Web 后端(仅使用 Python 标准库)。

浏览器无法直接使用 FTP 协议,因此由本服务作为桥接:
  浏览器 (HTTP)  ->  本服务 (ftplib)  ->  目标 FTP 服务器(通过 IP)

启动:
    python server.py
    然后浏览器打开 http://127.0.0.1:8765

可选参数:
    --host 0.0.0.0   允许局域网其他设备访问本界面(注意:无鉴权,请谨慎)
    --port 9000      修改界面端口
    --no-open        不自动打开浏览器
"""

import argparse
import base64
import json
import mimetypes
import os
import socket
import sys
import threading
import time
import webbrowser
from ftplib import FTP, error_perm
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# 每个连接的 FTP 会话都会被复用;为保证一个会话同时只被一个线程使用,传输加全局锁
_io_lock = threading.Lock()
_conn_lock = threading.Lock()
_conns = {}  # key -> FTP 实例
FTP_TIMEOUT = 120

MAX_PROBE_BODY = 65536


# --------------------------------------------------------------------------
# 路径处理(防目录穿越 / 非法路径)
# --------------------------------------------------------------------------
def norm_remote_dir(value):
    """规范化远程目录,如 '' '/' '/a/b/' -> ''|'/'|'/a/b'"""
    if not value:
        return ""
    s = value.replace("\\", "/").strip()
    if not s:
        return ""
    absolute = s.startswith("/")
    parts = []
    for seg in s.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            raise ValueError("远程路径中不允许出现 '..'")
        parts.append(seg)
    prefix = "/" if absolute else ""
    return prefix + "/".join(parts) if parts else (prefix if absolute else "")


def norm_rel_path(value):
    """规范化待上传的相对路径(来自浏览器),拒绝绝对路径与 '..'"""
    s = (value or "").replace("\\", "/").strip()
    parts = []
    for seg in s.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            raise ValueError("文件路径中不允许出现 '..'")
        parts.append(seg)
    if not parts:
        raise ValueError("空路径")
    return "/".join(parts)


def remote_abs_path(remote_dir, rel):
    """拼出绝对远程路径,如 ('/a', 'b/c.txt') -> '/a/b/c.txt'"""
    base = norm_remote_dir(remote_dir)
    rel = norm_rel_path(rel)
    if base in ("", "/"):
        return "/" + rel
    return base.rstrip("/") + "/" + rel


# --------------------------------------------------------------------------
# FTP 连接管理
# --------------------------------------------------------------------------
def _conn_key(cfg):
    return (cfg["host"], cfg.get("port", 21), cfg.get("user", ""), cfg.get("password", ""))


def _login(cfg):
    ftp = FTP()
    ftp.encoding = "utf-8"
    ftp.connect(cfg["host"], int(cfg.get("port", 21)), timeout=FTP_TIMEOUT)
    user = cfg.get("user", "") or "anonymous"
    pwd = cfg.get("password", "")
    if user == "anonymous":
        ftp.login()
    else:
        ftp.login(user, pwd)
    return ftp


def _get_conn(cfg):
    """取一个已登录连接;若无效则重建"""
    key = _conn_key(cfg)
    with _conn_lock:
        conn = _conns.get(key)
        if conn is None:
            conn = _login(cfg)
            _conns[key] = conn
        return conn


def _drop_conn(cfg):
    key = _conn_key(cfg)
    with _conn_lock:
        conn = _conns.pop(key, None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass


def _ensure_remote_dirs(conn, abs_dir, create_missing=True):
    """确保绝对远程目录 abs_dir(及各级父目录)存在。create_missing=False 时只检查不创建。"""
    if abs_dir in ("", "/"):
        return
    parts = [p for p in abs_dir.split("/") if p not in ("", ".")]
    cur = ""
    for p in parts:
        cur += "/" + p
        try:
            conn.cwd(cur)
        except error_perm:
            if not create_missing:
                raise ValueError("远程目录不存在: %s(未勾选“自动创建目录”)" % cur)
            try:
                conn.mkd(cur)
            except error_perm:
                # 可能刚刚被创建,再确认一次
                conn.cwd(cur)


def _remote_exists(conn, abs_file):
    try:
        conn.size(abs_file)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------
# 流式上传:把浏览器 POST 过来的请求体直接写给 FTP,不落盘
# --------------------------------------------------------------------------
class _BodyReader:
    """把 http 请求体包装成 file-like 对象喂给 ftplib.storbinary"""

    def __init__(self, rfile, total):
        self._rfile = rfile
        self.total = total
        self.remaining = total

    def read(self, n=-1):
        if self.remaining <= 0:
            return b""
        take = n if 0 < n < self.remaining else self.remaining
        chunk = self._rfile.read(take)
        if not chunk:
            return b""
        self.remaining -= len(chunk)
        return chunk


def upload_stream(cfg, rel_path, reader, overwrite):
    """执行一次上传。返回 {'action':'uploaded'|'skipped', 'bytes': n}

    注意:网络中断时由前端整体重发文件(重新走完整请求体),
    因此这里不做断点续传,避免把「半截数据」当作新文件开头写入远程。
    """
    rel = norm_rel_path(rel_path)
    full = remote_abs_path(cfg.get("remote_dir", ""), rel)
    parent = "/".join(full.split("/")[:-1]) or "/"

    with _io_lock:
        conn = _get_conn(cfg)
        try:
            if not overwrite and _remote_exists(conn, full):
                return {"action": "skipped", "bytes": 0}
            _ensure_remote_dirs(conn, parent, create_missing=bool(cfg.get("create_missing", True)))
            conn.storbinary("STOR " + full, reader, blocksize=65536)
            if reader.remaining != 0:
                raise ConnectionError("传输中断:数据不完整")
            return {"action": "uploaded", "bytes": reader.total - reader.remaining}
        except (socket.error, EOFError, OSError, ConnectionError) as exc:
            _drop_conn(cfg)  # 会话已坏,丢弃以便下次重建
            raise ConnectionError("与 FTP 服务器的连接中断: %s(前端将自动重试)" % exc)
        except error_perm as exc:
            raise ValueError("FTP 服务器拒绝操作: %s" % exc)


# --------------------------------------------------------------------------
# HTTP Handler
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "FTPWebUI/1.0"

    # ---------- 工具 ----------
    def _send_json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, socket.error):
            pass

    def _read_body(self, limit=64 * 1024 * 1024):
        length = self.headers.get("Content-Length")
        if length is None:
            return None, "缺少 Content-Length"
        try:
            length = int(length)
        except ValueError:
            return None, "Content-Length 无效"
        if length > limit:
            return None, "请求体过大"
        if length == 0:
            return b"", None
        return self.rfile.read(length), None

    def _b64_header(self, name):
        raw = self.headers.get(name)
        if not raw:
            return None
        try:
            return base64.b64decode(raw).decode("utf-8")
        except Exception:
            return None

    def _parse_cfg(self):
        raw = self._b64_header("X-Ftp-Cfg")
        if raw is None:
            raise ValueError("缺少连接配置头 X-Ftp-Cfg")
        cfg = json.loads(raw)
        if not cfg.get("host"):
            raise ValueError("未填写主机 IP")
        cfg["user"] = cfg.get("user", "") or ""
        cfg["password"] = cfg.get("password", "") or ""
        return cfg

    # ---------- 日志 ----------
    def log_message(self, fmt, *args):
        sys.stderr.write("[ui-server] %s\n" % (fmt % args))

    # ---------- GET:静态资源 ----------
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            self._send_json({"ok": True, "name": "ftp-transfer-ui"})
            return
        if path in ("/", "/index.html"):
            rel = "index.html"
        else:
            rel = path.lstrip("/")
        real_root = os.path.realpath(STATIC_DIR)
        target = os.path.realpath(os.path.join(real_root, rel))
        if not target.startswith(real_root + os.sep) or not os.path.isfile(target):
            self._send_json({"ok": False, "error": "404 Not Found"}, 404)
            return
        ctype, _ = mimetypes.guess_type(target)
        if ctype is None:
            ctype = "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        try:
            with open(target, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, socket.error):
            pass

    # ---------- POST ----------
    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/probe":
                self._api_probe()
            elif path == "/api/upload":
                self._api_upload()
            else:
                self._send_json({"ok": False, "error": "404 Not Found"}, 404)
        except Exception as exc:  # 兜底
            try:
                self._send_json({"ok": False, "error": "服务器错误: %s" % exc}, 500)
            except Exception:
                pass

    def _api_probe(self):
        """测试 FTP 连接:登录 + 检查/创建远程目标目录"""
        body, err = self._read_body(MAX_PROBE_BODY)
        if err:
            self._send_json({"ok": False, "error": err}, 400)
            return
        try:
            cfg = json.loads(body.decode("utf-8"))
        except Exception:
            self._send_json({"ok": False, "error": "请求格式错误"}, 400)
            return
        host = (cfg.get("host") or "").strip()
        if not host:
            self._send_json({"ok": False, "error": "未填写主机 IP"})
            return
        port = int(cfg.get("port") or 21)
        user = (cfg.get("user") or "").strip()
        password = cfg.get("password") or ""
        remote_dir = cfg.get("remote_dir") or ""
        create_missing = bool(cfg.get("create_missing", True))
        ftp = None
        try:
            ftp = FTP()
            ftp.encoding = "utf-8"
            ftp.connect(host, port, timeout=15)
            if user and user != "anonymous":
                ftp.login(user, password)
            else:
                ftp.login()
            dir_state = "ok"
            base = norm_remote_dir(remote_dir)
            if base:
                try:
                    _ensure_remote_dirs(ftp, base, create_missing=create_missing)
                    dir_state = "created" if create_missing else "ok"
                except error_perm:
                    dir_state = "missing"
                    raise ValueError("远程目标目录不存在或无权访问: %s(可勾选“自动创建目录”)" % base)
                except ValueError:
                    dir_state = "missing"
                    raise
            self._send_json({
                "ok": True,
                "message": "连接成功: %s:%s,目录状态: %s" % (host, port, dir_state),
                "dir_state": dir_state,
            })
        except ValueError as exc:
            self._send_json({"ok": False, "error": str(exc)})
        except socket.gaierror:
            self._send_json({"ok": False, "error": "无法解析主机地址: %s" % host})
        except socket.timeout:
            self._send_json({"ok": False, "error": "连接超时,请检查 IP / 端口 / 网络"})
        except ConnectionRefusedError:
            self._send_json({"ok": False, "error": "连接被拒绝,请确认 FTP 服务已开启且端口正确(默认 21)"})
        except error_perm as exc:
            self._send_json({"ok": False, "error": "登录失败(账号或权限问题): %s" % exc})
        except Exception as exc:
            self._send_json({"ok": False, "error": "连接失败: %s" % exc})
        finally:
            if ftp is not None:
                try:
                    ftp.close()
                except Exception:
                    pass

    def _api_upload(self):
        """上传单个文件:配置与相对路径放请求头(ASCII 安全),请求体为文件原始字节流"""
        try:
            cfg = self._parse_cfg()
        except Exception as exc:
            self._send_json({"ok": False, "error": "配置无效: %s" % exc}, 400)
            return
        rel_raw = self._b64_header("X-Ftp-Rel")
        if rel_raw is None:
            self._send_json({"ok": False, "error": "缺少文件路径头 X-Ftp-Rel"}, 400)
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._send_json({"ok": False, "error": "Content-Length 无效"}, 400)
            return
        if length < 0:
            self._send_json({"ok": False, "error": "Content-Length 无效"}, 400)
            return

        reader = _BodyReader(self.rfile, length)
        overwrite = str(cfg.get("overwrite", True)).lower() not in ("false", "0")
        try:
            result = upload_stream(cfg, rel_raw, reader, overwrite)
            self._send_json({"ok": True, **result, "rel": rel_raw})
        except ConnectionError as exc:
            self._send_json({"ok": False, "retryable": True, "error": str(exc)})
        except ValueError as exc:
            self._send_json({"ok": False, "retryable": False, "error": str(exc)})
        except Exception as exc:
            self._send_json({"ok": False, "retryable": False, "error": "上传失败: %s" % exc})


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="FTP 远程文件传输工具(本地 Web 服务)")
    parser.add_argument("--host", default="127.0.0.1", help="界面监听地址(默认 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="界面端口(默认 8765)")
    parser.add_argument("--no-open", action="store_true", help="启动后不自动打开浏览器")
    args = parser.parse_args()

    if not os.path.isdir(STATIC_DIR):
        print("错误:找不到 static 目录: %s" % STATIC_DIR)
        sys.exit(1)

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    httpd.daemon_threads = True

    url = "http://127.0.0.1:%d" % args.port if args.host in ("127.0.0.1", "localhost", "::1") \
        else "http://%s:%d" % (args.host, args.port)
    print("FTP Transfer UI is running: %s" % url)
    print("Press Ctrl+C to stop.")

    if not args.no_open:
        def _open():
            time.sleep(0.6)
            try:
                webbrowser.open(url)
            except Exception:
                pass
        threading.Thread(target=_open, daemon=True).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        httpd.server_close()
        with _conn_lock:
            for conn in _conns.values():
                try:
                    conn.close()
                except Exception:
                    pass
            _conns.clear()


if __name__ == "__main__":
    main()
