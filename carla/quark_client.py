"""quark_client.py —— Quark runtime 协议客户端（真·量子推理桥接）

通过 Quark daemon（localhost:50052）的 TCP 帧协议，加载 Chimera 驾驶推理模块
（.mmi 加密模块）并逐帧调用其导出的量子函数。

协议（与 server/src/protocol.ts 对齐）：
  请求帧：[4 字节大端长度][命令字节][payload]
  响应帧：[4 字节大端长度][纯文本 payload]

命令：
  HELLO      = 0x00  握手（payload = "QUARK_PROTO_V1"）
  LOAD_MMI   = 0x05  加载 .mmi 模块（payload = 路径，响应 "MMI_LOADED <id>"）
  MMI_INVOKE = 0x06  调用导出函数（payload = "<id> <func> <args_json>"，响应 JSON 标量）
  EXIT       = 0xff  关闭

这样 autopilot.py 的「量子大脑」真正由 Quark runtime的 QVM 后端执行量子门操作（混沌意识核漂移、情绪软测量、情绪调制决策）。
"""
import json
import socket
import struct


class QuarkRuntimeClient:
    """Quark daemon 客户端：加载 .mmi 模块并逐帧 invoke 导出函数"""

    def __init__(self, host="127.0.0.1", port=50052, timeout=15.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock = None
        self.mmi_id = None

    # ── 连接与握手 ──
    def connect(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self._send_frame(0x00, "QUARK_PROTO_V1")   # HELLO

    # ── 加载 .mmi 模块，返回模块 id ──
    def load_mmi(self, path):
        self._send_frame(0x05, path)               # LOAD_MMI
        resp = self._recv_frame()
        for tok in resp.split():
            if tok.isdigit():
                self.mmi_id = int(tok)
                return self.mmi_id
        raise RuntimeError(f"MMI 加载失败: {resp}")

    # ── 调用导出函数，返回标量（double/int）；mmi_id 缺省用最近一次 load_mmi ──
    def invoke(self, func_name, args, mmi_id=None):
        mid = mmi_id if mmi_id is not None else self.mmi_id
        if mid is None:
            raise RuntimeError("尚未加载 MMI 模块")
        args_json = json.dumps(args)
        self._send_frame(0x06, f"{mid} {func_name} {args_json}")
        resp = self._recv_frame()
        if resp.startswith("RESPONSE: ERROR"):
            raise RuntimeError(f"invoke 失败: {resp}")
        return json.loads(resp)

    # ── 关闭连接 ──
    def close(self):
        if self.sock is None:
            return
        try:
            self._send_frame(0xff)                 # EXIT
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass
        self.sock = None

    # ── 帧编解码 ──
    def _send_frame(self, cmd, payload=""):
        body = bytes([cmd]) + payload.encode("utf-8")
        self.sock.sendall(struct.pack(">I", len(body)) + body)

    def _recv_frame(self):
        header = self._recv_exact(4)
        n = struct.unpack(">I", header)[0]
        return self._recv_exact(n).decode("utf-8")

    def _recv_exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise EOFError("daemon 连接被关闭")
            buf += chunk
        return buf

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.close()