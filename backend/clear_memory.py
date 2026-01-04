#!/usr/bin/env python
"""清理记忆数据库

用法：
    python clear_memory.py --view    # 查看当前数据
    python clear_memory.py --clear   # 清空所有数据
    python clear_memory.py --delete  # 删除数据库文件
"""
import sqlite3
import argparse
from pathlib import Path


DB_PATH = "data/memory.db"


def view_data():
    """查看数据库中的所有数据"""
    if not Path(DB_PATH).exists():
        print("❌ 数据库文件不存在")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 查看所有表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    if not tables:
        print("📭 数据库为空（没有表）")
        conn.close()
        return

    print("📊 数据库表列表：")
    for table in tables:
        table_name = table[0]
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"  - {table_name}: {count} 条记录")

    # 查看各表详细内容
    for table in tables:
        table_name = table[0]
        print(f"\n{'='*60}")
        print(f"表: {table_name}")
        print(f"{'='*60}")

        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()

        if not rows:
            print("  (空表)")
            continue

        # 获取列名
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"列: {', '.join(columns)}\n")

        for i, row in enumerate(rows, 1):
            print(f"记录 {i}:")
            for col, val in zip(columns, row):
                print(f"  {col}: {val}")
            print()

    conn.close()


def clear_data():
    """清空所有表的数据（保留表结构）"""
    if not Path(DB_PATH).exists():
        print("❌ 数据库文件不存在")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 获取所有表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    if not tables:
        print("📭 数据库为空（没有表）")
        conn.close()
        return

    # 清空每个表
    for table in tables:
        table_name = table[0]
        cursor.execute(f"DELETE FROM {table_name}")
        print(f"✅ 已清空表: {table_name}")

    conn.commit()
    conn.close()
    print("\n🎉 所有记忆数据已清空！")


def delete_db():
    """删除整个数据库文件"""
    if not Path(DB_PATH).exists():
        print("❌ 数据库文件不存在")
        return

    confirm = input(f"⚠️  确认要删除数据库文件 '{DB_PATH}' 吗？(yes/no): ")
    if confirm.lower() in ['yes', 'y']:
        Path(DB_PATH).unlink()
        print("✅ 数据库文件已删除")
    else:
        print("❌ 取消删除")


def main():
    parser = argparse.ArgumentParser(
        description="记忆数据库管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python clear_memory.py --view     # 查看所有数据
  python clear_memory.py --clear    # 清空所有数据
  python clear_memory.py --delete   # 删除数据库文件
        """
    )

    parser.add_argument('--view', action='store_true', help='查看数据库内容')
    parser.add_argument('--clear', action='store_true', help='清空所有数据（保留表结构）')
    parser.add_argument('--delete', action='store_true', help='删除数据库文件')

    args = parser.parse_args()

    if args.view:
        view_data()
    elif args.clear:
        clear_data()
    elif args.delete:
        delete_db()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
