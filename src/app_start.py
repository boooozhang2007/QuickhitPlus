from auth import UserManager, login_or_register
from player import Player
from infinite_game import infinite_game
from Stats import Leaderboard, render_histogram


def show_leaderboard(lb, account):
    """打印全服排行榜：我的排名 + 分数段分布 + TOP 10"""
    print("\n========== 全服排行榜 ==========")

    total = lb.tree.total()
    if total == 0:
        print("还没有任何玩家记录。")
        return

    rank = lb.my_rank(account.username)
    pct = lb.percentile(account.username)
    print(f"全服玩家：{total} 人")
    print(f"我的排名：第 {rank} 名（超过了 {pct:.1f}% 的玩家）")

    print("\n--- 分数段分布 ---")
    for line in render_histogram(lb.distribution(8)):
        print(line)

    print("\n--- TOP 10 ---")
    rank = 1
    for score, names in lb.top_n(10):
        shown = "、".join(names[:3])
        if len(names) > 3:
            shown += f" 等 {len(names)} 人"
        print(f"{rank:>2}. {score:>10}  {shown}")
        rank += len(names)          # 同分的并列，跳过整组
    print("================================")


def main():
    um = UserManager()
    lb = Leaderboard(um)            # 全服排行榜：值域线段树，随分数变化增量维护

    while True:
        # 1. 登录 / 注册
        account = login_or_register(um)
        if account is None:
            print("退出游戏")
            return

        # 2. 进入游戏循环：可以连续玩多局
        while True:
            print(f"\n欢迎，{account.username}！开始打字游戏吧。\n")
            print("请你选择一个游戏模式：\n1. 闯关模式\n2.无限模式\n3. 全服排行榜\n4. 退出游戏")
            mode = input("请选择 (1/2/3/4): ").strip()
            if mode == '1':
                player = Player(account=account)
            elif mode == '2':
                player = infinite_game(account=account)
            elif mode == '3':
                show_leaderboard(lb, account)
                continue
            elif mode == '4':
                print("再见！")
                return
            else:
                print("无效选择，请重新输入")
                continue
            final_score = player.start()

            # 3. 更新分数
            if final_score is not None:
                old_high = um.ht.get(account.username).high_score
                um.update_score(account.username, final_score)
                acc = um.ht.get(account.username)
                if acc.high_score != old_high:
                    # 最高分变了：排行榜线段树做一次 O(log V) 点修改
                    lb.update_player(account.username, old_high, acc.high_score)
                print(f"本次得分：{final_score}，历史最高：{acc.high_score}")

            # 4. 一局结束后，询问下一步
            print("\n1. 再玩一局")
            print("2. 返回账号菜单")
            print("3.我的统计")
            print("0. 退出程序")
            choice = input("请选择 (0/1/2/3): ").strip()

            if choice == '1':
                continue
            elif choice == '2':
                break        # 跳出内层循环，回到登录菜单
            elif choice == '3':
                info = um.analyse(account.username)
                if not info:
                    print("还没有游戏记录，先玩一局吧！")
                    continue
                    
                print(f'''
                统计信息：
                最高分：{info['max_score']}
                最低分：{info['min_score']}
                平均分：{info['avg_score']:.1f}
                排名：{info['rank']}
                ''')
            elif choice == '0':
                print("再见！")
                return
            else:
                print("无效选择，默认再玩一局")
                continue


if __name__ == '__main__':
    main()