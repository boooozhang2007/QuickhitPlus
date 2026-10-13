import time

from game import Game
from level import Level
from level_params import LevelParams


class Player:
    """玩家：保存玩家的分数和状态，并负责整个游戏主循环"""

    def __init__(self):
        self.level_no = 1     # 当前关卡号
        self.start_time = 0   # 游戏开始时间（毫秒）
        self.elpsed_time = 0  # 游戏总用时（毫秒）
        self.score = 0        # 总分

    def play(self):
        """开始游戏：依次进行三关"""
        game = Game(self)
        self.start_time = self._now_millis()

        configs = [
            LevelParams(1, 4, 10000, 100),
            LevelParams(2, 6, 8000, 200),
            LevelParams(3, 8, 6000, 300),
        ]

        print("====== 打字游戏开始 ======")

        for p in configs:
            level = Level(p)  # 当前关卡的状态

            self.level_no = level.get_level_no()
            print("\n--- 第%d关 ---" % self.level_no)
            print("时限: %d秒" % (level.get_time_limit() // 1000))

            target = game.gen_string(level.get_str_length())
            print("请输入:", target)

            t1 = self._now_millis()
            user_input = input()
            t2 = self._now_millis()

            if user_input == target and (t2 - t1) <= p.get_time_limit():
                gained = p.get_base_score()
                level.set_score(gained)
                self.score += gained
                print("正确! 本关得分:", gained)
            else:
                print("失败!")
                break

        self.elpsed_time = self._now_millis() - self.start_time
        game.print_result()

    def _now_millis(self):
        """返回当前时间的毫秒数（整数）"""
        return int(time.monotonic() * 1000)

    def get_level_no(self):
        return self.level_no

    def get_start_time(self):
        return self.start_time

    def get_elpsed_time(self):
        return self.elpsed_time

    def get_score(self):
        return self.score
