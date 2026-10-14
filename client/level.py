class Level:
    """关卡状态：保存当前这一关的运行时数据"""

    def __init__(self, params):
        self.level_no = params.get_level_no()      # 关卡号
        self.str_length = params.get_str_length()  # 本关随机字符串的长度
        self.time_limit = params.get_time_limit()  # 时间限制（毫秒）
        self.score = 0                             # 本关已得分数

    def get_level_no(self):
        return self.level_no

    def get_str_length(self):
        return self.str_length

    def get_time_limit(self):
        return self.time_limit

    def get_score(self):
        return self.score

    def set_score(self, score):
        self.score = score
