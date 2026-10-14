class Stack:
    """栈：后进先出（LIFO）数据结构

    底层用列表模拟，栈顶在列表末尾（append / pop 都是 O(1)）。
    可选最大容量，超出时自动丢弃栈底最旧元素（滑动窗口语义）。
    """

    def __init__(self, max_size=None):
        self._items = []
        self._max_size = max_size

    def push(self, item):
        if self._max_size is not None and len(self._items) >= self._max_size:
            self._items.pop(0)
        self._items.append(item)

    def pop(self):
        if self.is_empty():
            raise IndexError("pop from empty stack")
        return self._items.pop()

    def peek(self):
        if self.is_empty():
            raise IndexError("peek from empty stack")
        return self._items[-1]

    def is_empty(self):
        return len(self._items) == 0

    def size(self):
        return len(self._items)

    def clear(self):
        self._items.clear()

    def __repr__(self):
        return "Stack(%r)" % self._items

    def __len__(self):
        return len(self._items)