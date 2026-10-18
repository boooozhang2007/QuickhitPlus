import threading
import time

from game import Game
from level import Level
from level_params import LevelParams
from stack import Stack


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
        



    MAX_UNDO = 3

    def start(self):
        """开始游戏：游戏将持续进行，直到玩家失败，返回最终得分

        失败时可撤销（弹出栈顶快照）回到本关开头重试，
        最多撤销 MAX_UNDO 次。
        """
        undo_stack = Stack()
        undo_count = 0

        print("====== 打字游戏开始 ======")
        print("（失败时可撤销重试，最多 %d 次）" % self.MAX_UNDO)

        self.start_time = self._now_millis()   # 只在开局记录一次，统计的是整局总用时
        while(self.is_failed==0):
            game = Game(self)
            self.level_no += 1

            undo_stack.push({'score': self.score, 'level_no': self.level_no})

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
                user_input = self._input_with_timeout(level.get_time_limit() / 1000)
                t2 = self._now_millis()

                if user_input is None:
                    self.is_failed = 1
                    print("失败! 超时（限时 %d秒）" % (level.get_time_limit() // 1000))
                elif user_input == target and (t2 - t1) <= p.get_time_limit():
                    self.Score_weight=min(1.0,2**((10-self.level_no)/10))
                    gained = int((p.get_base_score() + ((p.get_time_limit()- (t2 - t1))//1000 ) * 10)*self.Score_weight)
                    level.set_score(gained)
                    self.score += gained
                    print("正确! 本关得分:", gained)
                else:
                    self.is_failed = 1
                    print("失败!")

            self.elpsed_time = self._now_millis() - self.start_time
            game.print_result()

            if self.is_failed and undo_count < self.MAX_UNDO and not undo_stack.is_empty():
                print("撤销机会剩余: %d 次" % (self.MAX_UNDO - undo_count))
                choice = input("是否撤销重试？(y/n): ").strip().lower()
                if choice == 'y':
                    state = undo_stack.pop()
                    self.score = state['score']
                    self.level_no = state['level_no'] - 1
                    self.is_failed = 0
                    undo_count += 1
                    print("已撤销，重新挑战本关！")

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