class LevelParams:
    """关卡参数配置：记录每一关的关卡号、字符长度、时间限制和基础分"""

    def __init__(self, level_no, str_length, time_limit, base_score):
        self.level_no = level_no        # 关卡号
        self.str_length = str_length    # 本关随机字符串的长度
        self.time_limit = time_limit    # 时间限制（毫秒）
        self.base_score = base_score    # 本关通过后的基础分

    def get_level_no(self):
        return self.level_no

    def get_str_length(self):
        return self.str_length

    def get_time_limit(self):
        return self.time_limit

    def get_base_score(self):
        return self.base_score
