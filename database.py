import sqlite3
from datetime import datetime

DB_NAME = "tasks.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Таблица для задач
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            day_of_week TEXT,
            task_text TEXT
        )
    """)
    
    # Таблица для оценок дня
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT,
            rating INTEGER,
            UNIQUE(user_id, date)
        )
    """)
    
    conn.commit()
    conn.close()

# Функция для добавления задачи
def add_task_to_db(user_id, day_of_week, task_text):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tasks (user_id, day_of_week, task_text) VALUES (?, ?, ?)",
        (user_id, day_of_week, task_text)
    )
    conn.commit()
    conn.close()

# Функция получения задач на конкретный день недели
def get_tasks_for_day(user_id, day_of_week):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, task_text FROM tasks WHERE user_id = ? AND day_of_week = ?",
        (user_id, day_of_week)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

# Функция сохранения оценки дня
def save_daily_rating(user_id, rating):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    today_date = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
        INSERT INTO daily_ratings (user_id, date, rating) VALUES (?, ?, ?)
        ON CONFLICT(user_id, date) DO UPDATE SET rating = ?
    """, (user_id, today_date, rating, rating))
    conn.commit()
    conn.close()