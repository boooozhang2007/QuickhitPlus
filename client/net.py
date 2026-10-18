import os
import queue
import socket
import sys
import threading
import time

# net.py 在 client/ 下，把 shared/ 加进搜索路径才能 import 到 protocol.py
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "shared"))

from protocol import send_msg, recv_msg


class NetClient:
    """和服务器的连接

    为什么要有后台收消息的线程：
    服务器会主动推消息（别人上线了要广播在线人数、匹配成功要通知双方），
    这些消息和「我请求的回复」混在同一个 socket 上。
    如果主线程发一条读一条，推送就会把回复的位置顶掉。
    所以用一个线程专门收，收到的都丢进队列，主线程按类型去队列里挑。
    """

    def __init__(self, host="127.0.0.1", port=8888):
        self.host = host
        self.port = port
        self.sock = None
        self.inbox = queue.Queue()   # 收到还没被取走的消息
        self.pending = []            # 等待期间收到的推送，先存着
        self.online_count = 0        # 服务器广播的在线人数
        self.connected = False
        self._reader = None

    # ---------- 连接 ----------
    def connect(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=5)
        self.sock.settimeout(None)   # 之后靠 recv 阻塞，不用超时
        self.connected = True

        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self):
        """后台线程：不停地收消息，塞进队列"""
        try:
            while self.connected:
                msg = recv_msg(self.sock)
                if msg is None:          # 服务器关闭了连接
                    break
                if self._absorb(msg):
                    continue             # 广播类消息就地消化，不进队列
                self.inbox.put(msg)
        except OSError:
            pass
        finally:
            self.connected = False
            self.inbox.put(None)    # 哨兵：让还在等的线程知道连接没了

    def _absorb(self, msg):
        """消化掉不需要交给上层的消息，返回 True 表示已处理

        在线人数是服务器广播的，随时可能来，调用方并不「等」它，
        所以就地更新到 self.online_count，不要污染请求/回复的配对。
        """
        if msg.get("type") == "online_count":
            self.online_count = msg["count"]
            return True
        return False

    def close(self):
        self.connected = False
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass

    # ---------- 收发 ----------
    def request(self, obj, expect, timeout=10):
        """发一条请求，等指定类型的回复

        等待期间收到的推送（不是我要的类型）先存进 self.pending，
        之后可以用 poll() 取出来。
        """
        if not self.connected:
            return None

        send_msg(self.sock, obj)

        deadline = time.monotonic() + timeout
        while True:
            remain = deadline - time.monotonic()
            if remain <= 0:
                return None                      # 超时
            try:
                msg = self.inbox.get(timeout=remain)
            except queue.Empty:
                return None
            if msg is None:
                return None                      # 连接断了
            if msg.get("type") == expect:
                return msg
            self.pending.append(msg)             # 不是我要的，先存着

    def poll(self, timeout=0):
        """取一条推送消息；没有就返回 None

        先看之前存下来的，再看队列。timeout=0 表示不等待。
        在线人数这类广播已经被 _absorb 就地消化，不会出现在这里。
        """
        if self.pending:
            return self.pending.pop(0)

        try:
            msg = self.inbox.get(timeout=timeout)
        except queue.Empty:
            return None

        if msg is None:      # 连接断了
            self.connected = False
            return None
        return msg

    # ---------- 业务请求 ----------
    def register(self, username, password):
        return self.request(
            {"type": "register", "username": username, "password": password},
            "register_result")

    def login(self, username, password):
        return self.request(
            {"type": "login", "username": username, "password": password},
            "login_result")

    def online(self):
        return self.request({"type": "online"}, "online_result")

    def rank(self, n=10):
        return self.request({"type": "rank", "n": n}, "rank_result")

    def submit_score(self, score):
        return self.request({"type": "score", "score": score}, "score_result")

    def match(self):
        return self.request({"type": "match"}, "match_result")

    def cancel_match(self):
        return self.request({"type": "cancel_match"}, "cancel_match_result")

    def submit_battle(self, score):
        """上报对战胜负局分数；双方都上报后服务器会推送 battle_over"""
        return self.request({"type": "battle_result", "score": score},
                            "battle_ack")

    def analyse(self):
        return self.request({"type": "analyse"}, "analyse_result")


if __name__ == "__main__":
    # 自测：需要先在本机把 server/server.py 跑起来
    c = NetClient()
    c.connect()
    print("已连接", c.host, c.port)
    print("在线:", c.online())
    print("排行:", c.rank(5))
    c.close()