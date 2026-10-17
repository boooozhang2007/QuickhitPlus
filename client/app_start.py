import getpass
import sys
import threading

from net import NetClient
from player import Player
from infinite_game import infinite_game

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8888


# ---------- 登录 / 注册 ----------
def login_or_register(net):
    """返回登录成功的用户名；用户选择退出则返回 None"""
    while True:
        print("\n===== QuickHit 账号系统 =====")
        print("1. 登录")
        print("2. 注册")
        print("3. 查看排行榜")
        print("4. 退出")
        choice = input("请选择 (1/2/3/4): ").strip()

        if choice == '1':
            username = input("用户名: ").strip()
            password = getpass.getpass("密码: ")
            r = net.login(username, password)
            if r is None:
                print("服务器没有响应，请重试")
                continue
            if r["ok"]:
                print(f"登录成功，欢迎回来，{r['username']}！"
                      f"（历史最高 {r['high_score']}，当前在线 {r['online']} 人）")
                return r["username"]
            print(r["msg"])

        elif choice == '2':
            username = input("用户名: ").strip()
            password = getpass.getpass("密码: ")
            confirm = getpass.getpass("确认密码: ")
            if password != confirm:
                print("两次密码不一致")
                continue
            r = net.register(username, password)
            if r is None:
                print("服务器没有响应，请重试")
                continue
            print(r["msg"])
            if r["ok"]:
                # 注册成功直接登录
                r2 = net.login(username, password)
                if r2 and r2["ok"]:
                    return r2["username"]

        elif choice == '3':
            show_rank(net)

        elif choice == '4':
            return None
        else:
            print("无效选择，请重新输入。")


# ---------- 几个展示函数 ----------
def show_rank(net):
    r = net.rank(10)
    if r is None:
        print("获取排行榜失败")
        return
    board = r["board"]
    if not board:
        print("暂无玩家记录")
        return
    print("\n--- 排行榜 TOP 10 ---")
    for row in board:
        print(f"{row['rank']:>2}. {row['username']:<12} 最高分: {row['high_score']}")


def show_online(net):
    r = net.online()
    if r is None:
        print("获取在线列表失败")
        return
    print(f"\n当前在线 {r['count']} 人：{', '.join(r['users']) or '（无）'}")


def show_analyse(net, username):
    r = net.analyse()
    if r is None:
        print("获取统计信息失败（服务器无响应）")
        return
    if not r["ok"]:
        print(r.get("msg", "暂无游戏记录"))
        return
    print(f"\n--- {username} 的个人统计 ---")
    print(f"总局数: {r['total']}")
    print(f"最高分: {r['max_score']}")
    print(f"最低分: {r['min_score']}")
    print(f"平均分: {r['avg_score']:.1f}")
    print(f"全服排名: 第 {r['rank']} 名")


def do_match(net, username):
    """发起匹配：先等服务器确认入队，再等对手出现的推送

    等待期间敲回车可以取消。主线程短轮询消息、另开一个线程读输入，
    否则主线程卡在 input() 上就收不到「匹配成功」的推送了。
    """
    r = net.match()
    if r is None:
        print("匹配请求失败")
        return
    if not r["ok"]:
        print(r["msg"])
        return
    if r.get("matched"):
        print(r["msg"])
        return

    print(r["msg"])
    print("（等待对手中，敲回车可取消匹配）")

    typed = [None]

    def _read():
        try:
            typed[0] = input()
        except EOFError:
            typed[0] = ""

    threading.Thread(target=_read, daemon=True).start()

    while True:
        push = net.poll(timeout=0.2)
        if push is None:
            if typed[0] is not None:          # 敲了回车（直接回车也算）
                cancel_match(net)
                return
            if not net.connected:
                print("与服务器断开连接，匹配结束")
                return
            continue
        if push.get("matched"):
            print(push["msg"])
            return
        print("收到未知消息:", push)


def cancel_match(net):
    """通知服务端把自己从队列里摘掉

    不取消就回主菜单的话，人已经不在等着了，下次别人匹配却会把我们配给他。
    """
    r = net.cancel_match()
    if r is None:
        print("取消匹配失败（服务器无响应）")
    else:
        print(r["msg"])


# ---------- 主流程 ----------
def main():
    host = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PORT

    net = NetClient(host, port)
    try:
        net.connect()
    except OSError as e:
        print(f"连接服务器 {host}:{port} 失败：{e}")
        print("请确认服务端已启动，且地址和端口正确。")
        return

    print(f"已连接服务器 {host}:{port}")

    try:
        while True:
            username = login_or_register(net)
            if username is None:
                print("退出游戏")
                return

            while True:
                print(f"\n欢迎，{username}！开始打字游戏吧。")
                print(f"（当前在线 {net.online_count} 人）")
                print("请你选择一个游戏模式：")
                print("1. 闯关模式")
                print("2. 无限模式")
                print("3. 查看在线玩家")
                print("4. 查看排行榜")
                print("5. 匹配对战")
                print("6. 个人统计")
                print("7. 退出游戏")
                mode = input("请选择 (1/2/3/4/5/6/7): ").strip()

                if mode == '1':
                    player = Player(account=username)
                elif mode == '2':
                    player = infinite_game(account=username)
                elif mode == '3':
                    show_online(net)
                    continue
                elif mode == '4':
                    show_rank(net)
                    continue
                elif mode == '5':
                    do_match(net, username)
                    continue
                elif mode == '6':
                    show_analyse(net, username)
                    continue
                elif mode == '7':
                    print("再见！")
                    return
                else:
                    print("无效选择")
                    continue

                final_score = player.start()

                # 把分数交给服务器保存，顺便拿回最高分和全服排名
                if final_score is not None:
                    r = net.submit_score(final_score)
                    if r is None:
                        print("分数上传失败（服务器无响应）")
                    else:
                        print(f"本次得分：{r['score']}，"
                              f"历史最高：{r['high_score']}，"
                              f"全服排名：第 {r['rank']} 名")

                # 玩完一局，看看有没有错过的推送
                push = net.poll()
                if push and push.get("matched"):
                    print("提示：", push["msg"])

                print("\n1. 返回游戏模式选择")
                print("2. 返回账号菜单")
                print("0. 退出程序")
                choice = input("请选择 (0/1/2): ").strip()
                if choice == '2':
                    break            # 回登录菜单
                elif choice == '0':
                    print("再见！")
                    return
                elif choice != '1':
                    print("无效选择，返回游戏模式选择")
                # 其他情况（含直接回车）都当"再玩一局"
    finally:
        net.close()


if __name__ == '__main__':
    main()