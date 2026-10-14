import json
import os
import hashlib
import getpass
from datetime import datetime

# users.json 放在项目根目录（src 的上一级）
USER_DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'users.json')


# 哈希表（链地址法）
class HashTable:
    """链地址法解决冲突的哈希表，key 为字符串

    装填因子超过 LOAD_FACTOR_LIMIT 时会自动扩容并重新散列，
    避免链表越挂越长、查找退化成顺序查找。
    """

    LOAD_FACTOR_LIMIT = 0.75   # 超过这个装填因子就扩容

    def __init__(self, capacity=101):
        self.capacity = capacity
        self.size = 0
        self.table = [[] for _ in range(capacity)]

    def _hash(self, key):
        """字符串哈希：31 进制 + 除留余数法"""
        h = 0
        for ch in key:
            h = (h * 31 + ord(ch)) % self.capacity
        return h

    def _resize(self, new_capacity):
        """扩容并重新散列

        注意不能直接把旧 table 拼过去：取模的除数变了，
        同一个 key 算出来的下标和原来不一样，必须逐个重新插入。
        """
        old_table = self.table
        self.capacity = new_capacity
        self.table = [[] for _ in range(new_capacity)]
        self.size = 0                     # 重新插入时会重新累加

        for bucket in old_table:
            for k, v in bucket:
                self.insert(k, v)

    def insert(self, key, value):
        idx = self._hash(key)
        bucket = self.table[idx]

        # 先找有没有这个 key：更新已有 key 不会让 size 变大，不该触发扩容
        for i, (k, v) in enumerate(bucket):
            if k == key:
                bucket[i] = (key, value)  # 更新
                return

        # 新 key 才会让 size 变大，这时才判断要不要扩容
        if (self.size + 1) > self.capacity * self.LOAD_FACTOR_LIMIT:
            self._resize(self._next_capacity())
            idx = self._hash(key)         # 扩容后除数变了，下标要重算
            bucket = self.table[idx]

        bucket.append((key, value))
        self.size += 1

    def _next_capacity(self):
        """找一个大约两倍大的质数作为新容量

        容量取质数能让 key 分布更均匀，减少冲突。
        """
        candidate = self.capacity * 2 + 1
        while not self._is_prime(candidate):
            candidate += 2
        return candidate

    @staticmethod
    def _is_prime(n):
        if n < 2:
            return False
        if n % 2 == 0:
            return n == 2
        i = 3
        while i * i <= n:
            if n % i == 0:
                return False
            i += 2
        return True

    def get(self, key):
        idx = self._hash(key)
        for k, v in self.table[idx]:
            if k == key:
                return v
        return None

    def delete(self, key):
        idx = self._hash(key)
        bucket = self.table[idx]
        for i, (k, v) in enumerate(bucket):
            if k == key:
                del bucket[i]
                self.size -= 1
                return True
        return False

    def items(self):
        for bucket in self.table:
            for k, v in bucket:
                yield k, v

    def load_factor(self):
        return self.size / self.capacity


# 账号类
class Account:
    def __init__(self, username, password_hash, salt,
                 high_score=0, created_at=None, history=None):
        self.username = username
        self.password_hash = password_hash
        self.salt = salt
        self.high_score = high_score
        self.created_at = created_at or datetime.now().isoformat(timespec='seconds')
        self.history = history or []   # 每次游戏记录：{"score": int, "time": str}

    def to_dict(self):
        return {
            'password_hash': self.password_hash,
            'salt': self.salt,
            'high_score': self.high_score,
            'created_at': self.created_at,
            'history': self.history,
        }

    @staticmethod
    def from_dict(username, info):
        return Account(
            username=username,
            password_hash=info['password_hash'],
            salt=info['salt'],
            high_score=info.get('high_score', 0),
            created_at=info.get('created_at'),
            history=info.get('history', []),
        )


# 用户管理器（用哈希表存账号）
class UserManager:
    def __init__(self, data_file=USER_DATA_FILE, capacity=101):
        self.data_file = data_file
        self.ht = HashTable(capacity=capacity)
        self.load()

    # ---- 密码哈希 ----
    def _hash_password(self, password, salt=None):
        if salt is None:
            salt = os.urandom(16).hex()
        pwd_hash = hashlib.pbkdf2_hmac(
            'sha256', password.encode(), salt.encode(), 100000
        ).hex()
        return f"{salt}${pwd_hash}"

    # 返回用户全服排名
    def total_ranking(self, score):
        counter = 0
        for item in self.ht.items():
            if (item[1].high_score > score):
                counter += 1

        return counter + 1

    def _verify(self, password, stored):
        salt, _ = stored.split('$')
        return self._hash_password(password, salt) == stored

    # 注册
    def register(self, username, password):
        if not username:
            return False, "用户名不能为空"
        if len(password) < 3:
            return False, "密码长度至少 3 位"
        if self.ht.get(username) is not None:
            return False, "用户名已存在"

        stored = self._hash_password(password)
        salt, _ = stored.split('$')
        acc = Account(username, stored, salt)
        self.ht.insert(username, acc)
        self.save()
        return True, "注册成功"

    # 登录
    def login(self, username, password):
        acc = self.ht.get(username)
        if acc is None:
            return False, None, "用户不存在"
        if self._verify(password, acc.password_hash):
            return True, acc, "登录成功"
        return False, None, "密码错误"

    # 更新分数
    def update_score(self, username, score):
        acc = self.ht.get(username)
        if acc is None:
            return
        acc.history.append({
            'score': score,
            'time': datetime.now().isoformat(timespec='seconds'),
        })
        if score > acc.high_score:
            acc.high_score = score
        self.save()

    # 排行榜（按高分排序，前n名）
    def top_players(self, n=10):
        players = [acc for _, acc in self.ht.items()]
        players.sort(key=lambda a: a.high_score, reverse=True)
        return players[:n]

    # 持久化
    def save(self):
        data = {}
        for username, acc in self.ht.items():
            data[username] = acc.to_dict()
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self):
        if not os.path.exists(self.data_file):
            return
        with open(self.data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for username, info in data.items():
            acc = Account.from_dict(username, info)
            self.ht.insert(username, acc)

    #统计
    def analyse(self, username):
        acc = self.ht.get(username)
        if acc is None:
            return None

        scores = [h['score'] for h in acc.history]
        n = len(scores)
        ordered = sorted(scores)

        # 排除边界条件，若为新用户则无记录的情况
        if n == 0:
            return None

        # 二分查找排位
        left, right = 0, len(ordered)
        while (left<right):
            mid = (left+right) // 2
            if ordered[mid] < acc.high_score:
                left = mid+1
            else:
                right = mid

        #返回总局数、最高分、最低分、平均分、全服排名
        return {'total': n,
                'max_score': max(scores),
                'min_score': min(scores),
                'avg_score': sum(scores)/n,
                'rank': self.total_ranking(acc.high_score)
                }


# 控制台交互：登录 / 注册菜单
def login_or_register(um: UserManager):
    """
    返回登录成功后的 Account 对象；用户选择退出返回 None。
    """
    while True:
        print("\n===== QuickHit 账号系统 =====")
        print("1. 登录")
        print("2. 注册")
        print("3. 查看排行榜")
        print("4. 退出")
        choice = input("请选择 (1/2/3/4): ").strip()

        if choice == '1':
            username = input("用户名: ").strip()
            password = getpass.getpass("密码: ")
            ok, acc, msg = um.login(username, password)
            if ok:
                print(f"登录成功，欢迎回来，{username}！")
                return acc
            else:
                print(msg)

        elif choice == '2':
            username = input("用户名: ").strip()
            password = getpass.getpass("密码: ")
            confirm = getpass.getpass("确认密码: ")
            if password != confirm:
                print("两次密码不一致")
                continue
            ok, msg = um.register(username, password)
            print(msg)
            if ok:
                # 注册成功直接登录
                ok2, acc, _ = um.login(username, password)
                if ok2:
                    return acc

        elif choice == '3':
            top = um.top_players(10)
            if not top:
                print("暂无玩家记录")
            else:
                print("\n--- 排行榜 TOP 10 ---")
                for i, acc in enumerate(top, 1):
                    print(f"{i:>2}. {acc.username:<12} 最高分: {acc.high_score}")

        elif choice == '4':
            return None
        else:
            print("无效选择，请重新输入。")