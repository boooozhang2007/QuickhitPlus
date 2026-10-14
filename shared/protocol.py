import json
import struct

HEADER_SIZE = 4

# 单条消息的最大长度，防止对端发个假长度把内存撑爆（16MB）
MAX_MSG_SIZE = 16 * 1024 * 1024


def send_msg(sock, obj):
    """把 obj 序列化成 JSON，前面加 4 字节长度头，整条发出去"""
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    header = struct.pack(">I", len(body))   # >I = 大端无符号 4 字节整数
    sock.sendall(header + body)


def _recv_exactly(sock, n):
    """从 sock 上精确读满 n 个字节

    recv 不保证一次给你 n 个字节，可能只给一部分，所以要循环读到够为止。
    对端在读到一半时关闭，返回 None。
    """
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:          # 空字节 = 对端关闭了连接
            return None
        data += chunk
    return data


def recv_msg(sock):
    """读一条完整消息并解析成 Python 对象

    对端在消息边界正常关闭时返回 None（可以当作退出循环的信号）；
    读到一半断线则抛 ConnectionError。
    """
    header = _recv_exactly(sock, HEADER_SIZE)
    if header is None:
        return None            # 正常关闭，没有下一条消息了

    msg_len = struct.unpack(">I", header)[0]
    if msg_len > MAX_MSG_SIZE:
        raise ValueError("消息长度 %d 超出上限" % msg_len)

    body = _recv_exactly(sock, msg_len)
    if body is None:
        raise ConnectionError("接收中途连接断开")

    return json.loads(body.decode("utf-8"))


if __name__ == "__main__":
    # 用 socketpair 自测：不占端口，两个 socket 直连
    import socket

    a, b = socket.socketpair()

    # 1. 普通收发
    send_msg(a, {"type": "login", "user": "alice"})
    print("1. 单条:", recv_msg(b))

    # 2. 连发多条，确认不会粘在一起
    send_msg(a, {"type": "play", "n": 1})
    send_msg(a, {"type": "play", "n": 2})
    print("2. 连续两条:", recv_msg(b), recv_msg(b))

    # 3. 中文不会被转义成 \uXXXX
    send_msg(a, {"msg": "登录成功"})
    print("3. 中文:", recv_msg(b))

    # 4. 对端关闭 -> None
    a.close()
    print("4. 对端关闭:", recv_msg(b))

    b.close()
    print("全部通过")
