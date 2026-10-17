"""全服排行榜统计模块

用「值域线段树」维护每个分数有多少玩家，支持：
    - 我的排名                 O(log V)
    - 任意分数段有多少人        O(log V)
    - 第 K 名是谁              O(log V)

选它而不是排序数组 / 前缀和，是因为排行榜的数据会变（破纪录时 high_score 更新）：
点修改 O(log V)，而前缀和要 O(V) 重算后面全部。

值域是有界的：无限模式每关得分权重按 r = 2^(-0.1) 等比衰减，所以关卡数无限、
分数级数依然收敛，总分上限约 12263。值域有界才谈得上静态数组（内存 = O(值域
大小)），不必上动态开点 / 坐标压缩。
"""

MAX_SCORE = 16383


class ScoreSegmentTree:
    """值域线段树：横轴是「分数」，叶子存该分数的玩家数

    内部用自底向上的完全二叉树（不用递归，省掉函数调用开销）：
        tree[i]  节点 i 覆盖的分数区间内的玩家总数，tree[1] 即总人数
        size     2 的幂且 > max_score，叶子 s 存放在 tree[s + size]
    """

    def __init__(self, max_score=MAX_SCORE):
        self.max_score = int(max_score)

        size = 1
        while size <= self.max_score:
            size *= 2
        self.size = size
        self.tree = [0] * (2 * size)

    def add(self, score, delta=1):
        """点修改：把分数 score 的玩家数加上 delta（delta 可为负）—— O(log V)"""
        if not isinstance(score, int) or not 0 <= score <= self.max_score:
            raise ValueError(
                '分数 %r 必须是 [0, %d] 内的整数；'
                '若来自旧数据请清洗 users.json，若公式已改请同步 MAX_SCORE'
                % (score, self.max_score))

        i = score + self.size
        self.tree[i] += delta
        i //= 2
        while i:
            self.tree[i] = self.tree[2 * i] + self.tree[2 * i + 1]
            i //= 2

    def count_between(self, lo, hi):
        """分数落在闭区间 [lo, hi] 里的玩家数 —— O(log V)"""
        if hi < lo:
            return 0
        lo = max(lo, 0)
        hi = min(hi, self.max_score)
        if hi < lo:
            return 0

        l = lo + self.size
        r = hi + 1 + self.size
        total = 0
        while l < r:
            if l & 1:
                total += self.tree[l]
                l += 1
            if r & 1:
                r -= 1
                total += self.tree[r]
            l //= 2
            r //= 2
        return total

    def count_greater(self, score):
        """分数严格大于 score 的玩家数 —— O(log V)"""
        return self.count_between(score + 1, self.max_score)

    def rank_of(self, score):
        """分数 score 的名次（并列同名次）= 比我高的人数 + 1 —— O(log V)"""
        return self.count_greater(score) + 1

    def kth_largest(self, k):
        """第 k 名的分数（k = 1 即最高分）；越界返回 None —— O(log V)"""
        if k < 1 or k > self.tree[1]:
            return None
        i = 1
        while i < self.size:
            right = 2 * i + 1
            if self.tree[right] >= k:
                i = right
            else:
                k -= self.tree[right]
                i = 2 * i
        return i - self.size

    def total(self):
        """树里的玩家总数 —— O(1)"""
        return self.tree[1]


class Leaderboard:
    """把 UserManager（auth.py）的账号数据接进值域线段树

    只用 Account 上已有的两个字段：username 和 high_score。
    """

    def __init__(self, user_manager, max_score=MAX_SCORE):
        self.um = user_manager
        self.max_score = max_score
        self.by_score = {}
        self.tree = ScoreSegmentTree(max_score)
        self.rebuild()

    def rebuild(self):
        """从 UserManager 现有账号整棵重建"""
        self.by_score = {}
        self.tree = ScoreSegmentTree(self.max_score)
        for username, acc in self.um.ht.items():
            self.tree.add(acc.high_score, 1)
            self.by_score.setdefault(acc.high_score, []).append(username)
        return self.tree.total()

    def add_player(self, username, score):
        """新用户注册时加入线段树"""
        self.tree.add(score, 1)
        self.by_score.setdefault(score, []).append(username)

    def update_player(self, username, old_high, new_high):
        """某个玩家的最高分变了 —— 两次点修改，O(log V)"""
        if old_high == new_high:
            return
        self.tree.add(old_high, -1)
        self.tree.add(new_high, 1)

        names = self.by_score.get(old_high)
        if names and username in names:
            names.remove(username)
            if not names:
                del self.by_score[old_high]
        self.by_score.setdefault(new_high, []).append(username)

    def my_rank(self, username):
        """某个用户的全服名次；查无此人返回 None"""
        acc = self.um.ht.get(username)
        if acc is None:
            return None
        return self.tree.rank_of(acc.high_score)

    def percentile(self, username):
        """超过了百分之多少的玩家；查无此人返回 None"""
        acc = self.um.ht.get(username)
        if acc is None:
            return None
        total = self.tree.total()
        if total <= 1:
            return 100.0
        lower = self.tree.count_between(0, acc.high_score - 1)
        return lower / (total - 1) * 100.0

    def distribution(self, buckets=8):
        """把 [0, 全服最高分] 等分成 buckets 段

        返回 [(下界, 上界, 人数), ...]，按分数升序排列。没有玩家时返回 []。
        """
        top = self.tree.kth_largest(1)
        if top is None:
            return []
        buckets = max(1, min(buckets, top + 1))

        rows = []
        for b in range(buckets):
            lo = b * (top + 1) // buckets
            hi = (b + 1) * (top + 1) // buckets - 1
            rows.append((lo, hi, self.tree.count_between(lo, hi)))
        return rows

    def top_n(self, n=10):
        """前 n 名，返回 [(分数, [同分的用户名...]), ...]，按分数降序"""
        result = []
        k = 1
        total = self.tree.total()
        while k <= total and len(result) < n:
            score = self.tree.kth_largest(k)
            names = self.by_score.get(score, [])
            result.append((score, sorted(names)))
            k += max(len(names), 1)
        return result


BAR_CHAR = '█'


def render_histogram(rows, bar_width=36):
    """把 distribution() 的结果渲染成控制台文本直方图"""
    if not rows:
        return []
    peak = max([c for _, _, c in rows] + [1])

    lines = []
    for lo, hi, count in rows:
        label = '%6d' % lo if lo == hi else '%5d-%d' % (lo, hi)
        filled = int(round(count / peak * bar_width))
        if count and filled == 0:
            filled = 1
        bar = BAR_CHAR * filled
        lines.append('%s |%-*s %d' % (label, bar_width, bar, count))
    return lines