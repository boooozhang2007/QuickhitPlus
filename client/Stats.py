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

# 值域上界 = 游戏理论最高分（约 12263），取 2^14 - 1 留余量。
#
# 注意是 16383 而不是 16384：size 必须「严格大于 max_score」才会取到 2^14，
# 写成 16384 会让 size 翻到 32768，内存凭空多一倍。
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
        while size <= self.max_score:   # 严格大于：叶子 s+size 要落在 [size, 2*size)
            size *= 2
        self.size = size
        self.tree = [0] * (2 * size)

    # ---------------- 对外 ----------------

    def add(self, score, delta=1):
        """点修改：把分数 score 的玩家数加上 delta（delta 可为负）—— O(log V)"""
        if not isinstance(score, int) or not 0 <= score <= self.max_score:
            raise ValueError(
                '分数 %r 必须是 [0, %d] 内的整数；'
                '若来自旧数据请清洗 users.json，若公式已改请同步 MAX_SCORE'
                % (score, self.max_score))

        i = score + self.size           # 分数 -> 叶子下标
        self.tree[i] += delta           # 先改叶子
        i //= 2
        while i:                        # 再顺祖先链向上重算（根是 1，1//2 == 0 时停）
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

        # 标准区间分解：闭区间转半开 [lo, hi+1)，左右指针一起向根爬
        l = lo + self.size
        r = hi + 1 + self.size
        total = 0
        while l < r:
            if l & 1:                   # l 是右孩子 → 它整个在区间内，计入后跳过
                total += self.tree[l]
                l += 1
            if r & 1:                   # r 是右孩子 → 它的左兄弟整个在区间内
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
        """第 k 名的分数（k = 1 即最高分）；越界返回 None —— O(log V)

        从根往下走：先看右子树（高分侧）的人够不够 k 个，
        够就往右，不够就扣掉右子树的人往左。全程不需要排序。
        """
        if k < 1 or k > self.tree[1]:
            return None
        i = 1
        while i < self.size:            # 下标 >= size 就是叶子
            right = 2 * i + 1
            if self.tree[right] >= k:
                i = right               # 第 k 名落在高分侧
            else:
                k -= self.tree[right]
                i = 2 * i               # 落在低分侧
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
        self.by_score = {}                  # 分数 -> 该分数的用户名列表（同分合并用）
        self.tree = ScoreSegmentTree(max_score)
        self.rebuild()

    def rebuild(self):
        """从 UserManager 现有账号整棵重建

        这是个安全阀：万一和 UserManager 不同步了，重跑一次即可对齐。
        """
        self.by_score = {}
        self.tree = ScoreSegmentTree(self.max_score)
        for username, acc in self.um.ht.items():
            self.tree.add(acc.high_score, 1)
            self.by_score.setdefault(acc.high_score, []).append(username)
        return self.tree.total()

    def update_player(self, username, old_high, new_high):
        """某个玩家的最高分变了 —— 两次点修改，O(log V)

        这就是「线段树存在的理由」在代码里的样子：改一个点，不用重算其他所有数据。
        """
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
        # 分数只有 0 时 top+1 == 1，正好退化成一段，不会多出一个恒为 0 的空段
        buckets = max(1, min(buckets, top + 1))

        rows = []
        for b in range(buckets):
            lo = b * (top + 1) // buckets
            hi = (b + 1) * (top + 1) // buckets - 1
            rows.append((lo, hi, self.tree.count_between(lo, hi)))
        return rows

    def top_n(self, n=10):
        """前 n 名，返回 [(分数, [同分的用户名...]), ...]，按分数降序

        分数来自 kth_largest 的树上二分，不是排序——同分的人合并成一条。
        """
        result = []
        k = 1
        total = self.tree.total()
        while k <= total and len(result) < n:
            score = self.tree.kth_largest(k)
            names = self.by_score.get(score, [])
            result.append((score, sorted(names)))
            k += max(len(names), 1)     # 跳过所有同分的人；max 是防空转兜底
        return result


BAR_CHAR = '█'     # █ 实心方块，控制台直方图的条形


def render_histogram(rows, bar_width=36):
    """把 distribution() 的结果渲染成控制台文本直方图

    规则：条形从 0 起算（不截断基线）、按分数升序排列、每条直接标出人数。
    """
    if not rows:
        return []
    peak = max([c for _, _, c in rows] + [1])

    lines = []
    for lo, hi, count in rows:
        label = '%6d' % lo if lo == hi else '%5d-%d' % (lo, hi)
        filled = int(round(count / peak * bar_width))
        if count and filled == 0:
            filled = 1                  # 有 1 个人也要看得见，不能画成 0
        bar = BAR_CHAR * filled
        lines.append('%s |%-*s %d' % (label, bar_width, bar, count))
    return lines
