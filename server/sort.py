"""自实现的排序算法与 Top-K 选择

排行榜和成绩统计不再调用内置 sorted()/list.sort()，而是用这里自己写的算法，
方便比较不同算法在不同数据规模与分布下的表现（课程设计要求的一部分）。

四个对外函数都支持 key（取关键字）和 reverse（是否降序），
比较口径统一由 _less 决定：_less(x, y) 为 True 表示 x 的名次应排在 y 之前。

- insertion_sort 最好 O(n)、最坏 O(n^2)，稳定，用于规模很小的场景
- quick_sort     三数取中 + Hoare 分区 + 小区间插入排序，平均 O(n log n)
- heap_sort      原地建堆，最坏也稳定在 O(n log n)
- top_k          大小为 k 的堆选前 k 名，O(n log k)，不必对全体排序

直接运行本文件（python sort.py，可选参数指定规模）会做正确性对拍与性能实验。
"""

import random
import time


def _identity(x):
    return x


def _less(x, y, key, reverse):
    """x 的名次是否应排在 y 之前，全模块唯一的比较口径"""
    kx = key(x)
    ky = key(y)
    if reverse:
        return kx > ky
    return kx < ky


QUICK_CUTOFF = 16   # 区间长度小于它就直接插入排序，省掉递归开销


def _insertion(items, lo, hi, key, reverse):
    """对 [lo, hi] 区间做插入排序（快排对小区间的收尾也用它）"""
    for i in range(lo + 1, hi + 1):
        cur = items[i]
        j = i - 1
        while j >= lo and _less(cur, items[j], key, reverse):
            items[j + 1] = items[j]
            j -= 1
        items[j + 1] = cur


def insertion_sort(items, key=_identity, reverse=False):
    """插入排序：把每个元素插到前面已有序部分的正确位置"""
    _insertion(items, 0, len(items) - 1, key, reverse)
    return items


def _partition(a, lo, hi, key, reverse):
    """Hoare 分区，返回切分点 p，满足 [lo, p] 里没有一个元素该排在 (p, hi] 之后"""
    mid = (lo + hi) // 2
    # 三数取中：把 lo 位置换成 a[lo]、a[mid]、a[hi] 三者中的中位数当枢轴。
    # 这样已升序/已逆序的输入也会被均匀切开，不会退化成 O(n^2)。
    if _less(a[mid], a[lo], key, reverse):
        a[mid], a[lo] = a[lo], a[mid]
    if _less(a[hi], a[lo], key, reverse):
        a[hi], a[lo] = a[lo], a[hi]
    if _less(a[hi], a[mid], key, reverse):
        a[hi], a[mid] = a[mid], a[hi]
    a[mid], a[lo] = a[lo], a[mid]

    pivot = a[lo]
    i = lo - 1
    j = hi + 1
    while True:
        i += 1
        while _less(a[i], pivot, key, reverse):    # 从左找第一个不该在 pivot 之前的
            i += 1
        j -= 1
        while _less(pivot, a[j], key, reverse):    # 从右找第一个不该在 pivot 之后的
            j -= 1
        if i >= j:
            return j
        a[i], a[j] = a[j], a[i]


def _quick(a, lo, hi, key, reverse):
    while hi - lo + 1 > QUICK_CUTOFF:
        p = _partition(a, lo, hi, key, reverse)
        # 两侧都递归最坏会到 O(n) 层：先递归较短的一侧，长的一侧交给循环继续切
        if p - lo < hi - p:
            _quick(a, lo, p, key, reverse)
            lo = p + 1
        else:
            _quick(a, p + 1, hi, key, reverse)
            hi = p
    _insertion(a, lo, hi, key, reverse)


def quick_sort(items, key=_identity, reverse=False):
    """快速排序：平均 O(n log n)，原地排序，不需要额外数组"""
    _quick(items, 0, len(items) - 1, key, reverse)
    return items


def _sift_down(heap, i, end, key, reverse):
    """把 heap[i] 向下沉，保证父结点是它和孩子里名次最靠后的那个

    heap_sort 用它建堆后依次把"最靠后"的换到末尾，得到升序；
    top_k 用它维护一个大小为 k 的堆，堆顶始终是当前 k 个里最差的，
    于是新元素只要比堆顶好就能直接顶替堆顶。
    """
    while True:
        left = 2 * i + 1
        if left > end:
            return
        worst = left                                   # 先假定左孩子最靠后
        if left + 1 <= end and _less(heap[left], heap[left + 1], key, reverse):
            worst = left + 1                           # 左孩子更好，右孩子才最靠后
        if _less(heap[i], heap[worst], key, reverse):
            heap[i], heap[worst] = heap[worst], heap[i]
            i = worst
        else:
            return


def _sift_up(heap, i, key, reverse):
    """新元素从末尾上浮，同上保证父结点是最靠后的"""
    while i > 0:
        parent = (i - 1) // 2
        if _less(heap[parent], heap[i], key, reverse):
            heap[parent], heap[i] = heap[i], heap[parent]
            i = parent
        else:
            return


def heap_sort(items, key=_identity, reverse=False):
    """堆排序：先原地建堆，再反复把堆顶换到末尾，最坏 O(n log n)"""
    n = len(items)
    for start in range(n // 2 - 1, -1, -1):    # 从最后一个非叶结点往前建堆，O(n)
        _sift_down(items, start, n - 1, key, reverse)
    for end in range(n - 1, 0, -1):
        items[0], items[end] = items[end], items[0]
        _sift_down(items, 0, end - 1, key, reverse)
    return items


def top_k(items, k, key=_identity, reverse=False):
    """取名次最靠前的 k 个，返回排好序的列表

    与"整体排序再切片"的区别：堆里只留 k 个元素，
    每个元素最多 O(log k) 的调整代价，整体 O(n log k)，且额外空间只要 O(k)。
    """
    if k <= 0:
        return []

    heap = []                        # 大小为 k 的堆，heap[0] 是当前 k 个里最差的
    for x in items:
        if len(heap) < k:
            heap.append(x)
            _sift_up(heap, len(heap) - 1, key, reverse)
        elif _less(x, heap[0], key, reverse):      # 比堆顶还好，才值得顶替
            heap[0] = x
            _sift_down(heap, 0, len(heap) - 1, key, reverse)

    quick_sort(heap, key=key, reverse=reverse)
    return heap


# ---------- 自测：与内置 sorted 对拍 ----------

def _in_order(items, key=_identity, reverse=False):
    """检查 items 是否已按 _less 的口径排好"""
    for i in range(1, len(items)):
        if _less(items[i], items[i - 1], key, reverse):
            return False
    return True


PATTERNS = ("随机", "已升序", "已降序", "大量重复")
RANDOM_SEED = 20261018          # 固定种子，实验结果可复现


def make_data(n, pattern):
    """按 pattern 造 n 个整数：四种分布分别考验算法的不同弱点"""
    rnd = random.Random(RANDOM_SEED)
    if pattern == "随机":
        return rnd.sample(range(n * 3), n)
    if pattern == "已升序":
        return list(range(n))
    if pattern == "已降序":
        return list(range(n, 0, -1))
    return [rnd.choice((1, 2, 3, 4)) for _ in range(n)]   # 大量重复


ALGOS = (("insertion_sort", insertion_sort),
         ("quick_sort", quick_sort),
         ("heap_sort", heap_sort))


def check_correctness():
    """对拍：小规模的各种边界形态 + 大规模四种分布 + top_k"""
    edge_cases = {
        "空表": [],
        "单元素": [7],
        "两元素逆序": [2, 1],
        "全部相同": [5] * 50,
        "已升序": list(range(50)),
        "已降序": list(range(50, 0, -1)),
        "随机小规模": random.Random(1).sample(range(200), 80),
        "有重复": [random.Random(2).choice((1, 1, 2, 3)) for _ in range(60)],
    }

    ok = True
    for name, data in edge_cases.items():
        for algo_name, algo in ALGOS:
            if algo(list(data)) != sorted(data):
                print("  [失败] %s 在 %s 上结果不对" % (algo_name, name))
                ok = False
        if quick_sort(list(data), reverse=True) != sorted(data, reverse=True):
            print("  [失败] quick_sort 降序口径在 %s 上结果不对" % name)
            ok = False

    for pattern in PATTERNS:
        data = make_data(3000, pattern)
        for algo_name, algo in ALGOS:
            if algo(list(data)) != sorted(data):
                print("  [失败] %s 在 3000 个「%s」数据上结果不对" % (algo_name, pattern))
                ok = False

    data = make_data(2000, "随机")
    for k in (0, 1, 5, 10, 2000, 2500):
        if top_k(data, k) != sorted(data)[:k]:
            print("  [失败] top_k 在 k=%d 时结果不对" % k)
            ok = False

    # 排行榜的真实用法：按分数降序取前 n 名（分数有重复，且重复很多）
    records = [{"score": s} for s in make_data(5000, "大量重复")]
    for n in (1, 10, 500):
        got = [r["score"] for r in top_k(records, n, key=lambda r: r["score"], reverse=True)]
        if got != sorted((r["score"] for r in records), reverse=True)[:n]:
            print("  [失败] top_k 按分数降序取前 %d 名时结果不对" % n)
            ok = False

    print("对拍结果：%s" % ("全部通过" if ok else "存在失败"))
    return ok


# ---------- 自测：规模与分布的性能实验 ----------

def benchmark(sizes):
    """对比三种算法在给定规模、四种分布下的耗时

    老师强调过"只测几十个数远远不够"：这里最小规模也取一万，
    并且刻意覆盖已升序、已降序、大量重复这些会让朴素快排退化的分布。
    """
    def builtin(a):
        return sorted(a)

    print("\n%-8s %-9s %13s %13s %13s" % ("规模", "分布", "quick_sort", "heap_sort", "内置sorted"))
    for n in sizes:
        for pattern in PATTERNS:
            data = make_data(n, pattern)
            times = []
            for algo in (quick_sort, heap_sort, builtin):
                a = list(data)
                t0 = time.perf_counter()
                sorted_a = algo(a)
                times.append((time.perf_counter() - t0) * 1000)
                assert sorted_a == sorted(data), "%s 在「%s」上结果不对" % (algo, pattern)
            print("%-8d %-9s %11.1f ms %11.1f ms %11.1f ms"
                  % (n, pattern, times[0], times[1], times[2]))

    # 插入排序 O(n^2)，只在很小规模上有意义，单独挂一行作对照
    n = 2000
    data = make_data(n, "随机")
    t0 = time.perf_counter()
    assert insertion_sort(list(data)) == sorted(data)
    print("参考：插入排序 %d 个随机数 %.1f ms（规模再大就不实用了）"
          % (n, (time.perf_counter() - t0) * 1000))


if __name__ == "__main__":
    import sys

    print("===== 对拍 =====")
    check_correctness()

    print("\n===== 性能实验 =====")
    custom = [int(x) for x in sys.argv[1:] if x.isdigit()]
    benchmark(custom or [10_000, 50_000])
    print("\n提示：想看更大规模可以运行  python sort.py 1000000")
