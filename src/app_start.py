from auth import UserManager, login_or_register
from player import Player
from infinite_game import infinite_game


def main():
    um = UserManager()

    while True:
        # 1. 登录 / 注册
        account = login_or_register(um)
        if account is None:
            print("退出游戏")
            return

        # 2. 进入游戏循环：可以连续玩多局
        while True:
            print(f"\n欢迎，{account.username}！开始打字游戏吧。\n")
            print("请你选择一个游戏模式：\n1. 闯关模式\n2.无限模式\n3. 退出游戏")
            mode = input("请选择 (1/2/3): ").strip()
            if mode == '1':
                player = Player(account=account)
            elif mode == '2':
                player = infinite_game(account=account)
            elif mode == '3':
                print("再见！")
                return
            final_score = player.start()

            # 3. 更新分数
            if final_score is not None:
                um.update_score(account.username, final_score)
                best = um.ht.get(account.username).high_score
                print(f"本次得分：{final_score}，历史最高：{best}")

            # 4. 一局结束后，询问下一步
            print("\n1. 再玩一局")
            print("2. 返回账号菜单")
            print("3. 退出程序")
            choice = input("请选择 (1/2/3): ").strip()

            if choice == '1':
                continue
            elif choice == '2':
                break        # 跳出内层循环，回到登录菜单
            elif choice == '3':
                print("再见！")
                return
            else:
                print("无效选择，默认再玩一局")
                continue


if __name__ == '__main__':
    main()