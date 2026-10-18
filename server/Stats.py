"""值域线段树 + 基于 users.json 的分数统计脚本

支持任意分数段的人数查询，以及每 BUCKET 分一段的分布。
值域有界（无限模式得分收敛），所以可以用静态数组存线段树。
脚本只读 users.json，不依赖 auth 的哈希表。
用法：python Stats.py
"""

import json
import os

USER_DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'users.json')

MAX_SCORE = 16383
BUCKET = 1000     # 分段统计的粒度


class ScoreSegmentTree:
    """值域线段树：叶子是单个分数，节点存区间内的人数，tree[1] 是总人数

    分数 s 的叶子下标是 s + size，所以递归查询只需在 [0, size-1] 上讨论。
    """

    def __init__(self, max_score=MAX_SCORE):
        self.max_score = max_score

        # 叶子要放 0 ~ max_score，所以区间长度取大于 max_score 的 2 的幂
        size = 1
        while size <= max_score:
            size *= 2
        self.size = size
        self.tree = [0] * (2 * size)

    def add(self, score):
        """score 这个分数的玩家数加 1"""
        score = int(score)
        if not 0 <= score <= self.max_score:
            raise ValueError("分数超出范围: %r" % score)

        # 从叶子往根走，路径上每个节点都 +1
        i = score + self.size
        while i:
            self.tree[i] += 1
            i //= 2

    def count_between(self, lo, hi):
        """分数在闭区间 [lo, hi] 内的玩家数"""
        # 用户可能输入 -100 或超过 max_score 的分数，先裁到值域内
        lo = max(lo, 0)
        hi = min(hi, self.max_score)
        if lo > hi:
            return 0
        return self._count(1, 0, self.size - 1, lo, hi)

    def _count(self, node, left, right, lo, hi):
        """node 管着 [left, right]，返回它和 [lo, hi] 重叠部分的玩家数"""
        if hi < left or right < lo:          # 完全没重叠
            return 0
        if lo <= left and right <= hi:       # 完全在查询范围内，直接用整段
            return self.tree[node]

        # 只有部分重叠：从中间切开，左右孩子分别继续找
        mid = (left + right) // 2
        return (self._count(2 * node, left, mid, lo, hi)
                + self._count(2 * node + 1, mid + 1, right, lo, hi))

    def total(self):
        """玩家总数"""
        return self.tree[1]


# ---------- 查询菜单 ----------
def build():
    """直接读 users.json，返回按最高分建好的线段树"""
    with open(USER_DATA_FILE, encoding='utf-8') as f:
        data = json.load(f)

    # 每个玩家只贡献一个最高分，和排行榜的统计口径一致
    scores = [info.get('high_score', 0) for info in data.values()]

    # 得分算法保证最高分不超过 MAX_SCORE，值域可以直接固定
    tree = ScoreSegmentTree()
    for score in scores:
        tree.add(score)
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

    # 先把每个分段都算出来，再去掉末尾没人、只会刷屏的空段
    rows = []
    lo = 0
    while lo <= tree.max_score:
        hi = min(lo + BUCKET - 1, tree.max_score)
        rows.append((lo, hi, tree.count_between(lo, hi)))
        lo += BUCKET
    while rows and rows[-1][2] == 0:
        rows.pop()

    print("\n--- 每 %d 分一段的人数 ---" % BUCKET)
    for lo, hi, cnt in rows:
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
        # 文件被手改坏（JSON 不合法、字段类型不对等）时，提示后退出，不带半棵树继续跑
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
