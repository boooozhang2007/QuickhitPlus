import os
import socket
import sys
import threading
from collections import deque

# server.py 在 server/ 目录下，把 shared/ 加进搜索路径才能 import 到 protocol.py
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "shared"))

from protocol import send_msg, recv_msg
from auth import UserManager


HOST = "0.0.0.0"   # 监听所有网卡
PORT = 8888


class Client:
    """一个已连接的客户端：socket + 发送锁 + 登录后的用户名"""

    def __init__(self, conn, address):
        self.conn = conn
        self.address = address
        self.username = None
        # 多个线程可能同时给同一个客户端发消息（比如广播在线人数），
        # 不加锁的话两条消息的字节会交错在一起，对端就解析不了
        self.send_lock = threading.Lock()

    def send(self, obj):
        with self.send_lock:
            send_msg(self.conn, obj)

    def close(self):
        try:
            self.conn.close()
        except OSError:
            pass


class Battle:
    """一场匹配对战：记录双方用户名和各自上报的分数

    双方匹配成功后各在本地打完一局无限模式，把分数上报给服务器；
    两边都上报后由服务器比大小判定胜负。
    """

    def __init__(self, a, b):
        self.usernames = (a, b)
        self.scores = {}          # 用户名 -> 上报的分数

    def report(self, username, score):
        """记录一次上报，返回双方是否都已上报"""
        self.scores[username] = score
        return len(self.scores) == 2

    def opponent_of(self, username):
        a, b = self.usernames
        return b if username == a else a

    def winner(self):
        """返回获胜者用户名；双方分数相同则返回 None（平局）"""
        a, b = self.usernames
        if self.scores[a] == self.scores[b]:
            return None
        return a if self.scores[a] > self.scores[b] else b


class Server:
    def __init__(self):
        self.users = UserManager()   # 复用 client/auth.py 的哈希表 + 账号逻辑
        self.users_lock = threading.Lock()   # HashTable 本身不是线程安全的

        # ---- 下面三块共享状态都由 self.lock 保护 ----
        self.online = {}          # 用户名 -> Client，用哈希表做在线表
        self.waiting = deque()    # 等待匹配的 Client，FIFO 队列
        self.battles = {}         # 用户名 -> Battle，进行中的对战
        self.lock = threading.Lock()

    # ---------- 启动 ----------
    def create_socket_server(self):
        server = socket.socket()
        # 服务器重启后端口能立刻复用，否则会报 Address already in use
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen(100)   # 最大等待连接数 100
        print(f"[INFO] 服务器已启动，监听 {HOST}:{PORT}")

        try:
            while True:
                conn, address = server.accept()
                print(f"[INFO] 服务器已收到 {address[0]}:{address[1]} 链接")

                client = Client(conn, address)
                # daemon=True：主线程退出时这些线程不会被卡住
                t = threading.Thread(target=self.handler_client,
                                     args=(client,), daemon=True)
                t.start()
        except KeyboardInterrupt:
            print("\n[INFO] 服务器关闭")
        finally:
            server.close()

    # ---------- 单个连接的处理循环 ----------
    def handler_client(self, client):
        # 请求类型 -> 处理函数
        handlers = {
            "register": self.do_register,
            "login": self.do_login,
            "online": self.do_online,
            "rank": self.do_rank,
            "match": self.do_match,
            "cancel_match": self.do_cancel_match,
            "battle_result": self.do_battle_result,
            "score": self.do_score,
            "analyse": self.do_analyse,
        }

        try:
            while True:
                msg = recv_msg(client.conn)   # 对端正常关闭时返回 None
                if msg is None:
                    break

                handler = handlers.get(msg.get("type"))
                if handler is None:
                    client.send({"type": "error",
                                 "msg": "未知请求: %s" % msg.get("type")})
                    continue

                handler(client, msg)
        except (ConnectionError, OSError) as e:
            print(f"[WARN] {client.address} 连接中断: {e}")
        except Exception as e:
            print(f"[ERROR] 处理 {client.address} 出错: {type(e).__name__}: {e}")
        finally:
            self.remove_client(client)

    def remove_client(self, client):
        """客户端断开：从在线表、匹配队列和对战里都摘掉"""
        opponent = None
        with self.lock:
            # 只有「当前在线的还是这个连接」才删，避免把顶替上来的新连接误删
            if client.username and self.online.get(client.username) is client:
                del self.online[client.username]
                print(f"[INFO] {client.username} 下线，当前在线 {len(self.online)} 人")
            if client in self.waiting:
                self.waiting.remove(client)

            # 对战中途掉线：结束这场对战并通知对手，别让对手一直干等
            battle = self.battles.get(client.username) if client.username else None
            if battle is not None:
                opp_name = battle.opponent_of(client.username)
                for u in battle.usernames:
                    self.battles.pop(u, None)
                opponent = self.online.get(opp_name)

        client.close()
        if opponent is not None:
            try:
                opponent.send({"type": "battle_over", "aborted": True,
                               "msg": f"对手 {client.username} 已离开，对战结束"})
            except OSError:
                pass    # 这个对手也断了，它自己的线程会负责清理
        self.broadcast_online_count()

    # ---------- 各请求的处理 ----------
    def do_register(self, client, msg):
        with self.users_lock:
            ok, text = self.users.register(msg.get("username", ""),
                                           msg.get("password", ""))
        client.send({"type": "register_result", "ok": ok, "msg": text})

    def do_login(self, client, msg):
        with self.users_lock:
            ok, acc, text = self.users.login(msg.get("username", ""),
                                             msg.get("password", ""))
        if not ok:
            client.send({"type": "login_result", "ok": False, "msg": text})
            return

        with self.lock:
            old = self.online.get(acc.username)
            # old is client：同一条连接重登（客户端「返回账号菜单」后会再登一次），
            # 关它就等于关掉正在处理这条请求的 socket
            if old is not None and old is not client:   # 同账号在别处登录，踢掉旧连接
                try:
                    old.send({"type": "kicked", "msg": "你的账号在别处登录了"})
                except OSError:
                    pass
                old.close()
            self.online[acc.username] = client
            client.username = acc.username
            count = len(self.online)

        client.send({"type": "login_result", "ok": True, "msg": text,
                     "username": acc.username,
                     "high_score": acc.high_score,
                     "online": count})
        self.broadcast_online_count()

    def do_online(self, client, msg):
        with self.lock:
            users = sorted(self.online.keys())
        client.send({"type": "online_result",
                     "count": len(users), "users": users})

    def do_rank(self, client, msg):
        client.send({"type": "rank_result", "board": self.get_board(msg.get("n", 10))})

    def do_match(self, client, msg):
        if client.username is None:
            client.send({"type": "match_result", "ok": False, "msg": "请先登录"})
            return

        pair = self.queue_pair(client)
        if pair is None:
            client.send({"type": "match_result", "ok": True,
                         "msg": "已进入匹配队列，等待对手…"})
            return

        a, b = pair
        # 配对成功：登记一场对战，等双方各自打完上报成绩后判定胜负
        with self.lock:
            battle = Battle(a.username, b.username)
            self.battles[a.username] = battle
            self.battles[b.username] = battle

        # 两边都要通知，各自看到对方的用户名
        for me, other in ((a, b), (b, a)):
            me.send({"type": "match_result", "ok": True, "matched": True,
                     "opponent": other.username,
                     "msg": f"匹配成功，对手是 {other.username}"})

    def do_battle_result(self, client, msg):
        """接收对战成绩：双方都上报后判定胜负，并把结果推给双方"""
        if client.username is None:
            client.send({"type": "error", "msg": "请先登录"})
            return

        score = int(msg.get("score", 0))
        results = None
        targets = None

        with self.lock:
            battle = self.battles.get(client.username)
            if battle is None:
                status = "none"
            elif not battle.report(client.username, score):
                status = "waiting"
            else:
                status = "done"
                # 双方都上报了：算出双方视角的结果，并从对战表里摘掉
                results = {}
                for u in battle.usernames:
                    opp = battle.opponent_of(u)
                    results[u] = {"my_score": battle.scores[u],
                                  "opp_score": battle.scores[opp],
                                  "opponent": opp,
                                  "winner": battle.winner()}
                targets = [(u, self.online.get(u)) for u in battle.usernames]
                for u in battle.usernames:
                    del self.battles[u]

        if status == "none":
            client.send({"type": "battle_ack", "ok": False,
                         "msg": "当前没有进行中的对战"})
            return
        if status == "waiting":
            client.send({"type": "battle_ack", "ok": True, "waiting": True,
                         "msg": "成绩已上报，等待对手完成…"})
            return

        # 对战成绩也计入各自的历史记录与最高分，和单机模式共享排行榜
        with self.users_lock:
            for u in results:
                self.users.update_score(u, results[u]["my_score"])
            for u in results:
                acc = self.users.ht.get(u)
                results[u]["high_score"] = acc.high_score
                results[u]["rank"] = self.users.total_ranking(acc.high_score)

        # 先给上报者回执，让它的请求能返回；再把最终结果推给双方
        client.send({"type": "battle_ack", "ok": True, "waiting": False,
                     "msg": "成绩已上报"})
        for u, c in targets:
            if c is None:      # 可能有一方在等待期间掉线了
                continue
            c.send({"type": "battle_over", "msg": "对战结束", **results[u]})

    def do_cancel_match(self, client, msg):
        removed = self.dequeue(client)
        # ok=False 一般是取消晚了：等待期间正好被别人配对走了
        client.send({"type": "cancel_match_result", "ok": removed,
                     "msg": "已取消匹配" if removed else "已不在匹配队列中"})

    def do_score(self, client, msg):
        if client.username is None:
            client.send({"type": "error", "msg": "请先登录"})
            return

        score = int(msg.get("score", 0))
        with self.users_lock:
            acc = self.users.ht.get(client.username)
            self.users.update_score(client.username, score)
            new_high = acc.high_score
            rank = self.users.total_ranking(new_high)

        client.send({"type": "score_result", "ok": True, "score": score,
                     "high_score": new_high, "rank": rank})

    def do_analyse(self, client, msg):
        if client.username is None:
            client.send({"type": "error", "msg": "请先登录"})
            return
        with self.users_lock:
            stats = self.users.analyse(client.username)
        if stats is None:
            client.send({"type": "analyse_result", "ok": False, "msg": "暂无游戏记录"})
        else:
            client.send({"type": "analyse_result", "ok": True, **stats})

    # ---------- 三个数据结构功能 ----------
    def online_people(self):
        """在线人数：online 是哈希表，取大小是 O(1)"""
        with self.lock:
            return len(self.online)

    def queue_pair(self, client):
        """队列匹配：FIFO。凑够两人就配对弹出，否则入队等待

        返回 (clientA, clientB) 表示配对成功；返回 None 表示还在排队。
        """
        with self.lock:
            if client in self.waiting:
                return None                     # 已经在队列里，别重复入队

            self.waiting.append(client)         # 入队 O(1)
            if len(self.waiting) < 2:
                return None

            a = self.waiting.popleft()          # 出队 O(1)
            b = self.waiting.popleft()
            return (a, b)

    def dequeue(self, client):
        """取消匹配：把自己从等待队列里摘掉，返回是否真的在队列里"""
        with self.lock:
            if client not in self.waiting:
                return False
            self.waiting.remove(client)
            return True

    def get_board(self, n=10):
        """实时排行榜：取所有玩家按最高分降序排列，返回前 N 名"""
        with self.users_lock:
            top = self.users.top_players(n)
        board = []
        for i, acc in enumerate(top, 1):
            board.append({"username": acc.username,
                          "high_score": acc.high_score, "rank": i})
        return board

    # ---------- 广播 ----------
    def broadcast_online_count(self):
        """在线人数变了，通知所有在线客户端刷新"""
        with self.lock:
            targets = list(self.online.values())
            count = len(self.online)

        for c in targets:
            try:
                c.send({"type": "online_count", "count": count})
            except OSError:
                pass    # 这个客户端已经断了，它自己的线程会负责清理


if __name__ == '__main__':
    server = Server()
    server.create_socket_server()