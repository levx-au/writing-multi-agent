"""数据库连接管理模块（SQLite + WAL 模式 + 文件锁）"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

# 线程本地存储：每个线程独立的连接
_local = threading.local()

# 默认超时和重试配置
DEFAULT_TIMEOUT = 30.0  # 秒
MAX_RETRIES = 5
RETRY_DELAY = 0.2  # 秒

# Schema 版本号（每次 schema.sql 重大变更需要递增）
CURRENT_SCHEMA_VERSION = 1


class DatabaseError(Exception):
    """数据库操作异常"""
    pass


class ConflictError(DatabaseError):
    """并发冲突异常（乐观锁失败）"""
    pass


def get_schema_path() -> Path:
    """获取 schema.sql 文件路径"""
    return Path(__file__).parent / "schema.sql"


def get_db_path(novel_id: int, db_dir: Optional[str] = None) -> Path:
    """获取小说对应的数据库文件路径"""
    if db_dir:
        root = Path(db_dir).expanduser().resolve()
    else:
        root = Path.cwd() / "novel_dbs"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"novel_{novel_id}.db"


def _create_connection(db_path: Path) -> sqlite3.Connection:
    """创建一个配置好的数据库连接（带完整 PRAGMA）"""
    conn = sqlite3.connect(str(db_path), timeout=DEFAULT_TIMEOUT, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-64000")
    conn.row_factory = sqlite3.Row
    return conn


def _is_connection_alive(conn: sqlite3.Connection) -> bool:
    """
    检查连接是否有效。

    使用真正的查询测试，而不仅仅是 execute("SELECT 1")，
    因为某些情况下连接虽然不报错但实际已失效。
    """
    try:
        cursor = conn.execute("SELECT 1 AS alive")
        cursor.fetchone()
        cursor.close()
        return True
    except sqlite3.Error:
        return False


def _acquire_file_lock(lock_path: Path, timeout: float = 30.0) -> bool:
    """
    获取文件锁（跨进程）。

    使用带 PID 标记的锁文件，并检测孤儿锁：
    1. 如果锁文件存在但 PID 已消亡，视为孤儿锁，直接占有
    2. 否则等待，直到获得锁或超时

    这样即使进程崩溃，锁也会在下一个尝试获取锁的进程中被自动回收。
    """
    import os

    start = time.time()
    my_pid = os.getpid()
    pid_file = lock_path / "pid.txt"

    while time.time() - start < timeout:
        try:
            # 尝试创建锁目录
            lock_path.mkdir(exist_ok=False)
            # 写入当前 PID 到文件
            pid_file.write_text(str(my_pid), encoding="utf-8")
            return True
        except FileExistsError:
            # 锁目录已存在，检查是否是孤儿锁
            orphan = False
            try:
                if pid_file.exists():
                    lock_content = pid_file.read_text(encoding="utf-8")
                    lock_pid = int(lock_content.strip())
                    try:
                        os.kill(lock_pid, 0)
                    except (OSError, ProcessLookupError):
                        # PID 不存在，是孤儿锁
                        orphan = True
            except (ValueError, OSError):
                # 读取失败，当作孤儿处理
                orphan = True

            if orphan:
                # 确认为孤儿锁，释放后等待一小段时间再重试，避免立即被抢走
                _release_file_lock(lock_path)
                time.sleep(0.05)
                continue

            # 非孤儿锁，等待后重试
            time.sleep(0.05)
    return False


def _try_clean_stale_lock(lock_path: Path) -> None:
    """
    尝试清理孤儿锁目录（如果锁文件对应的进程已消亡）。

    这是一个尽力而为的操作，不会抛出异常。
    """
    import os

    try:
        if not lock_path.exists():
            return
        pid_file = lock_path / "pid.txt"
        try:
            if pid_file.exists():
                lock_content = pid_file.read_text(encoding="utf-8")
                lock_pid = int(lock_content.strip())
                try:
                    os.kill(lock_pid, 0)
                    return  # 进程还活着，锁有效，不清理
                except (OSError, ProcessLookupError):
                    pass  # 进程已死，清理锁
        except (ValueError, OSError, PermissionError):
            pass  # 内容无效或读取失败，清理
        _release_file_lock(lock_path)
    except (OSError, RuntimeError):
        # 锁已被其他进程获取，或目录不存在，无需清理
        pass


def _release_file_lock(lock_path: Path) -> None:
    """释放文件锁"""
    try:
        lock_path.rmdir()
    except OSError:
        try:
            lock_path.unlink()
        except OSError:
            pass


def _get_schema_version(conn: sqlite3.Connection) -> int:
    """获取数据库当前 schema 版本"""
    try:
        row = conn.execute(
            "SELECT version FROM _schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()
        return row["version"] if row else 0
    except sqlite3.OperationalError:
        return 0


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    """设置数据库 schema 版本"""
    conn.execute(
        "INSERT OR REPLACE INTO _schema_version (version, applied_at) VALUES (?, CURRENT_TIMESTAMP)",
        (version,),
    )


def init_db(novel_id: int, title: str = "", genre: str = "玄幻", db_dir: Optional[str] = None) -> sqlite3.Connection:
    """
    初始化小说数据库（创建表结构 + 写入元数据记录）。

    带文件锁：多进程同时初始化同一数据库时，排队等待。
    锁文件包含 PID，会自动清理孤儿锁。
    """
    db_path = get_db_path(novel_id, db_dir)
    lock_path = db_path.with_suffix(".init.lock")

    # 先尝试清理任何残留的孤儿锁（主动回收）
    _try_clean_stale_lock(lock_path)

    if not _acquire_file_lock(lock_path, timeout=30.0):
        raise DatabaseError(f"数据库初始化被锁定，请稍后重试（{db_path.name}）")

    try:
        db_existed = db_path.exists()
        conn = _create_connection(db_path)

        # 读取并执行 schema（CREATE TABLE IF NOT EXISTS 保证幂等性）
        schema_path = get_schema_path()
        schema_sql = schema_path.read_text(encoding="utf-8")
        conn.executescript(schema_sql)

        # 确保 _schema_version 表存在（早期版本可能没有）
        conn.execute("""
            CREATE TABLE IF NOT EXISTS _schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        current_version = _get_schema_version(conn)

        # Schema 版本不匹配时执行升级逻辑（当前仅 v1，无需迁移）
        if current_version < CURRENT_SCHEMA_VERSION:
            # 这里可以添加未来版本迁移逻辑
            # if current_version < 2: migrate_v1_to_v2(conn)
            _set_schema_version(conn, CURRENT_SCHEMA_VERSION)

        # 检查元数据记录是否存在
        row = conn.execute(
            "SELECT id FROM novel_metadata WHERE id = ?",
            (novel_id,),
        ).fetchone()
        if not row:
            conn.execute(
                """
                INSERT OR IGNORE INTO novel_metadata
                (id, title, genre, world_rules, power_system_name, main_plot_outline)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (novel_id, title or f"我的小说{novel_id}", genre, "{}", "", ""),
            )
            conn.commit()

        return conn
    except sqlite3.Error as e:
        raise DatabaseError(f"初始化数据库失败: {e}") from e
    finally:
        _release_file_lock(lock_path)


def _remove_stale_connection(novel_id: int) -> None:
    """安全移除失效的线程本地连接"""
    if hasattr(_local, "connections") and novel_id in _local.connections:
        old_conn = _local.connections.pop(novel_id, None)
        if old_conn is not None:
            try:
                old_conn.close()
            except sqlite3.Error:
                pass


def get_db_connection(
    novel_id: int,
    db_dir: Optional[str] = None,
    auto_init: bool = True,
) -> sqlite3.Connection:
    """
    获取小说数据库连接（线程本地存储，重复调用返回同一连接）。

    自动处理失效连接：如果检测到连接已失效，自动重建连接。
    """
    thread_conn = getattr(_local, "connections", {}).get(novel_id)

    if thread_conn is not None:
        if _is_connection_alive(thread_conn):
            return thread_conn
        _remove_stale_connection(novel_id)

    db_path = get_db_path(novel_id, db_dir)

    if not db_path.exists() and auto_init:
        conn = init_db(novel_id, db_dir=db_dir)
    elif not db_path.exists():
        raise DatabaseError(f"数据库不存在: {db_path}")
    else:
        conn = _create_connection(db_path)
        if not _is_connection_alive(conn):
            conn.close()
            raise DatabaseError(f"无法建立有效的数据库连接: {db_path}")

    if not hasattr(_local, "connections"):
        _local.connections = {}
    _local.connections[novel_id] = conn

    return conn


@contextmanager
def get_db(novel_id: int, db_dir: Optional[str] = None):
    """
    上下文管理器：获取数据库连接，自动处理归还和错误。

    与 transaction() 的区别：此方法不自动提交，
    调用者需要自行 commit/rollback。
    """
    conn = get_db_connection(novel_id, db_dir)
    try:
        yield conn
    except sqlite3.Error:
        if hasattr(_local, "connections") and _local.connections.get(novel_id) is conn:
            _remove_stale_connection(novel_id)
        raise


@contextmanager
def transaction(novel_id: int, db_dir: Optional[str] = None, max_retries: int = MAX_RETRIES):
    """
    上下文管理器：自动管理事务（commit on success, rollback on error）。

    带有重试机制：遇到数据库锁定时自动重试。
    """
    last_error = None
    for attempt in range(max_retries):
        conn = get_db_connection(novel_id, db_dir)
        try:
            yield conn
            conn.commit()
            return
        except sqlite3.OperationalError as e:
            last_error = e
            if "database is locked" in str(e).lower() or "busy" in str(e).lower():
                if attempt < max_retries - 1:
                    if hasattr(_local, "connections") and _local.connections.get(novel_id) is conn:
                        _remove_stale_connection(novel_id)
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
            conn.rollback()
            raise
        except sqlite3.Error:
            conn.rollback()
            if hasattr(_local, "connections") and _local.connections.get(novel_id) is conn:
                _remove_stale_connection(novel_id)
            raise

    raise ConflictError(f"事务失败，已重试 {max_retries} 次: {last_error}")


def close_db(novel_id: int) -> None:
    """关闭指定小说的数据库连接（仅当前线程）"""
    _remove_stale_connection(novel_id)


def close_all_db() -> None:
    """关闭当前线程的所有数据库连接"""
    if hasattr(_local, "connections"):
        for novel_id in list(_local.connections.keys()):
            _remove_stale_connection(novel_id)
        _local.connections.clear()


def execute_with_retry(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple = (),
    max_retries: int = MAX_RETRIES,
) -> sqlite3.Cursor:
    """
    带重试的执行（处理并发冲突和锁定）。

    在 `transaction()` 上下文中会自动重试，一般不需要直接调用。
    """
    last_error = None
    for attempt in range(max_retries):
        try:
            cursor = conn.execute(sql, params)
            return cursor
        except sqlite3.OperationalError as e:
            last_error = e
            if "database is locked" in str(e).lower() or "busy" in str(e).lower():
                if attempt < max_retries - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
            raise
        except sqlite3.Error as e:
            raise

    raise ConflictError(f"执行失败，已重试 {max_retries} 次: {last_error}")


def vacuum_db(novel_id: int, db_dir: Optional[str] = None) -> None:
    """整理数据库（清理 WAL 文件，执行 VACUUM）"""
    conn = get_db_connection(novel_id, db_dir)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("VACUUM")
        conn.commit()
    finally:
        pass


def checkpoint_db(novel_id: int, db_dir: Optional[str] = None) -> None:
    """对数据库执行检查点操作，回收 WAL 文件空间"""
    conn = get_db_connection(novel_id, db_dir)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except sqlite3.Error:
        pass


def repair_if_needed(novel_id: int, db_dir: Optional[str] = None) -> bool:
    """
    检查并修复可能的数据库问题。

    Returns:
        True 表示数据库正常或已修复，False 表示无法修复
    """
    db_path = get_db_path(novel_id, db_dir)
    wal_path = db_path.with_suffix(".db-wal")
    shm_path = db_path.with_suffix(".db-shm")

    try:
        conn = _create_connection(db_path)

        if not _is_connection_alive(conn):
            conn.close()
            return False

        conn.execute("PRAGMA integrity_check")
        result = conn.execute("PRAGMA quick_check").fetchone()
        conn.close()

        if result and result[0] != "ok":
            return False

        return True
    except sqlite3.Error:
        return False
