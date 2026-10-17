"""值域线段树 + 基于 users.json 的分数统计脚本

支持任意分数段的人数查询，以及按固定粒度（默认每 1000 分）的分段分布。

选线段树而不是排序数组 / 前缀和，是因为分数会变（破纪录时 high_score 更新）：
点修改 O(log V)，前缀和要 O(V) 重算。值域有界（无限模式得分收敛）才用得起静态数组。

脚本只读 users.json，不依赖 auth 的哈希表。
用法：python Stats.py
"""

import json
import os

USER_DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'users.json')

MAX_SCORE = 16383
BUCKET = 1000     # 分段统计的粒度


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

    def total(self):
        """树里的玩家总数 —— O(1)"""
        return self.tree[1]


# ---------- 查询菜单 ----------
def build():
    """直接读 users.json，返回按最高分建好的线段树"""
    with open(USER_DATA_FILE, encoding='utf-8') as f:
        data = json.load(f)

    top_score = max((info.get('high_score', 0) for info in data.values()),
                    default=0)
    # 值域至少覆盖现存最高分，旧数据超出 MAX_SCORE 也不会让建树失败
    tree = ScoreSegmentTree(max(MAX_SCORE, top_score))
    for info in data.values():
        tree.add(info.get('high_score', 0))
    return tree


def ask_int(prompt, default=None):
    raw = input(prompt).strip()
    if not raw and default is not None:
        return default
    try:
        return int(raw)
    except ValueError:
        print("请输入整数")
        return None


def show_buckets(tree):
    total = tree.total()
    if total == 0:
        print("暂无玩家记录")
        return

    rows = []
    lo = 0
    while lo <= tree.max_score:
        hi = min(lo + BUCKET - 1, tree.max_score)
        rows.append((lo, hi, tree.count_between(lo, hi)))
        lo += BUCKET

    # 只列到最后一个有人的分段，否则默认值域会多刷十几行空分段
    last = max(i for i, (_, _, cnt) in enumerate(rows) if cnt > 0)

    print("\n--- 每 %d 分一段的人数 ---" % BUCKET)
    for lo, hi, cnt in rows[:last + 1]:
        print(f"[{lo:>6}, {hi:>6}]  {cnt:>4} 人  {cnt / total:>6.1%}")


def show_range(tree):
    lo = ask_int("下界分数: ")
    hi = ask_int("上界分数: ")
    if lo is None or hi is None:
        return
    print(f"[{lo}, {hi}] 内有 {tree.count_between(lo, hi)} 名玩家")


def main():
    try:
        tree = build()
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"读取 users.json 失败（{type(e).__name__}: {e}），请检查文件后重试")
        return

    while True:
        print("\n===== 分数统计（只读 users.json）=====")
        print("1. 每 %d 分一段的人数" % BUCKET)
        print("2. 自定义分数段人数")
        print("r. 重新读取 users.json")
        print("0. 退出")

        choice = input("请选择: ").strip().lower()

        if choice == "0":
            return
        elif choice == "1":
            show_buckets(tree)
        elif choice == "2":
            show_range(tree)
        elif choice == "r":
            try:
                tree = build()
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"重新读取失败（{type(e).__name__}: {e}）")
                continue
            print("已重新读取，共 %d 名玩家" % tree.total())
        else:
            print("无效选择")


if __name__ == '__main__':
    main()
