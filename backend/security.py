"""安全加固：登录限流 + 密码强度校验。

登录限流：进程内内存计数（适合单实例部署）。多实例改用 Redis。
密码强度：8+ 位，含小写/大写/数字/符号中至少 3 类，禁止常见弱密码。
"""
import re
import threading
import time
from collections import defaultdict


# ==================== 登录限流 ====================

MAX_FAILS = 5            # 连续失败上限
LOCK_DURATION_SEC = 300   # 锁定时长（5 分钟）
WINDOW_SEC = 900          # 失败计数滑窗（15 分钟内累计）

# {username: {"fails": [ts, ts, ...], "locked_until": ts}}
_state: dict = defaultdict(lambda: {"fails": [], "locked_until": 0.0})
_lock = threading.Lock()


def is_locked(username: str) -> tuple[bool, int]:
    """返回 (是否被锁, 剩余秒数)。"""
    with _lock:
        st = _state[username]
        now = time.time()
        if st["locked_until"] > now:
            return True, int(st["locked_until"] - now)
        return False, 0


def record_failure(username: str) -> tuple[bool, int]:
    """记录一次失败。返回 (是否触发锁定, 剩余可尝试次数)。"""
    with _lock:
        now = time.time()
        st = _state[username]
        # 清掉窗口外的旧失败
        st["fails"] = [t for t in st["fails"] if now - t < WINDOW_SEC]
        st["fails"].append(now)
        if len(st["fails"]) >= MAX_FAILS:
            st["locked_until"] = now + LOCK_DURATION_SEC
            st["fails"] = []
            return True, 0
        return False, MAX_FAILS - len(st["fails"])


def record_success(username: str):
    """登录成功 → 清掉失败计数和锁定。"""
    with _lock:
        _state[username] = {"fails": [], "locked_until": 0.0}


# ==================== 密码强度 ====================

COMMON_WEAK = {
    "12345678", "123456789", "qwerty123", "password", "password1",
    "11111111", "00000000", "abc12345", "admin123", "letmein12",
    "iloveyou", "welcome1", "qazwsx12", "zxcvbnm1",
}


def check_password(pwd: str) -> tuple[bool, str]:
    """校验密码强度。返回 (是否合格, 错误信息)。"""
    if not isinstance(pwd, str):
        return False, "密码必须是字符串"
    if len(pwd) < 8:
        return False, "密码至少 8 位"
    if len(pwd) > 64:
        return False, "密码最多 64 位"
    if pwd.lower() in COMMON_WEAK:
        return False, "密码过于常见，请使用更复杂的"
    has_lower = bool(re.search(r"[a-z]", pwd))
    has_upper = bool(re.search(r"[A-Z]", pwd))
    has_digit = bool(re.search(r"\d", pwd))
    has_symbol = bool(re.search(r"[^a-zA-Z0-9]", pwd))
    kinds = sum([has_lower, has_upper, has_digit, has_symbol])
    if kinds < 3:
        return False, "密码须包含小写字母/大写字母/数字/符号 至少 3 类"
    return True, ""
