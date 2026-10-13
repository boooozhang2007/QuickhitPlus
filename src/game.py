import random

CHARS = "abcdefghijklmnopqrstuvwxyz"


class Game:
    """游戏逻辑：负责生成随机字符串、输出结算结果"""

    def __init__(self, player):
        self.player = player  # 指向所属玩家，用于读取分数等信息

    def gen_string(self, length):
        """生成长度为 length 的随机小写字母串"""
        result = ""
        for _ in range(length):
            result += random.choice(CHARS)
        return result

    def print_result(self):
        """打印最终结果"""
        print("========== 结果 ==========")
        print("关卡:", self.player.get_level_no())
        print("总分:", self.player.get_score())
        print("==========================")
