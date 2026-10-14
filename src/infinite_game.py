import threading
import time

from game import Game
from level import Level
from level_params import LevelParams


class infinite_game:
    """玩家：保存玩家的分数和状态，并负责整个游戏主循环"""

    def __init__(self, account=None):
        self.account = account
        self.level_no = 0     # 当前关卡号
        self.start_time = 0   # 游戏开始时间（毫秒）
        self.elpsed_time = 0  # 游戏总用时（毫秒）
        self.score = 0        # 总分
        self.is_failed = 0 # 游戏是否失败，0表示未失败，1表示失败
        self.Score_weight=1.0
        



    def start(self):
        """开始游戏：游戏将持续进行，直到玩家失败，返回最终得分"""
        while(self.is_failed==0):
            game = Game(self)
            self.start_time = self._now_millis()
            self.level_no += 1

            configs = [
            LevelParams(self.level_no, min(2+self.level_no*2,14), max(10-self.level_no,5)*1000, min(100*self.level_no,500)),
            ]

            print("====== 打字游戏开始 ======")

            for p in configs:
                level = Level(p)

                self.level_no = level.get_level_no()
                print("\n--- 第%d关 ---" % self.level_no)
                print("时限: %d秒" % (level.get_time_limit() // 1000))

                target = game.gen_string(level.get_str_length())
                print("请输入:", target)

                t1 = self._now_millis()
                # 在时限内读取玩家输入，超时返回 None
                user_input = self._input_with_timeout(level.get_time_limit() / 1000)
                t2 = self._now_millis()

                if user_input is None:
                    self.is_failed = 1
                    print("失败! 超时（限时 %d秒）" % (level.get_time_limit() // 1000))
                    break

                if user_input == target and (t2 - t1) <= p.get_time_limit():
                    self.Score_weight=min(1.0,2**((10-self.level_no)/10))
                    # 权重是 float，乘完会把分数变成小数；线段树的叶子下标必须是整数，
                    # 所以这里就地取整，保证全程分数都是 int
                    gained = int((p.get_base_score() + ((p.get_time_limit()- (t2 - t1))//1000 ) * 10)*self.Score_weight)
                    level.set_score(gained)
                    self.score += gained
                    print("正确! 本关得分:", gained)
                else:
                    self.is_failed = 1
                    print("失败!")
                    break

            self.elpsed_time = self._now_millis() - self.start_time
            game.print_result()
        return self.score

    def _input_with_timeout(self, timeout_sec):
        """在 timeout_sec 秒内读取一行输入；超时则返回 None"""
        box = [None]

        def _read():
            try:
                box[0] = input()
            except EOFError:
                box[0] = ""

        reader = threading.Thread(target=_read, daemon=True)
        reader.start()
        reader.join(timeout_sec)

        if reader.is_alive():
            # 超时：读取线程还卡在 input() 上，主线程先走
            print()
            return None
        return box[0]

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