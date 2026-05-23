import pytest
import sqlite3
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from io import StringIO
from registration.registration import create_db, add_user, authenticate_user, display_users, user_choice, main

@pytest.fixture(scope="module")
def setup_database():
    """Фикстура для настройки базы данных перед тестами и её очистки после."""
    # Удаляем старую БД, если есть
    if os.path.exists('users.db'):
        os.remove('users.db')
    create_db()
    yield
    # Очистка после тестов
    try:
        if os.path.exists('users.db'):
            os.remove('users.db')
    except PermissionError:
        pass

@pytest.fixture
def connection():
    """Фикстура для получения соединения с базой данных и его закрытия после теста."""
    conn = sqlite3.connect('users.db')
    yield conn
    conn.close()

@pytest.fixture
def clean_db(setup_database):
    """Фикстура для очистки таблицы users перед каждым тестом."""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users")
    conn.commit()
    conn.close()
    yield

# ========== ТЕСТЫ ДЛЯ create_db ==========

def test_create_db(setup_database, connection):
    """Тест создания базы данных и таблицы пользователей."""
    cursor = connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
    table_exists = cursor.fetchone()
    assert table_exists, "Таблица 'users' должна существовать в базе данных."

def test_create_db_idempotent(setup_database, connection):
    """Тест, что create_db можно вызывать несколько раз без ошибок."""
    # Вызываем повторно
    create_db()
    cursor = connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
    table_exists = cursor.fetchone()
    assert table_exists, "Таблица должна существовать после повторного вызова"

# ========== ТЕСТЫ ДЛЯ add_user ==========

def test_add_new_user(setup_database, connection, clean_db):
    """Тест добавления нового пользователя."""
    result = add_user('testuser', 'testuser@example.com', 'password123')
    assert result is True, "Функция должна вернуть True при успешном добавлении"
    
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM users WHERE username='testuser';")
    user = cursor.fetchone()
    assert user is not None, "Пользователь должен быть добавлен в базу данных"
    assert user[0] == 'testuser'
    assert user[1] == 'testuser@example.com'
    assert user[2] == 'password123'

def test_add_existing_user(setup_database, connection, clean_db):
    """Тест добавления пользователя с существующим логином."""
    # Добавляем первого пользователя
    add_user('duplicate_user', 'first@example.com', 'pass123')
    
    # Пытаемся добавить с тем же логином
    result = add_user('duplicate_user', 'second@example.com', 'pass456')
    assert result is False, "Функция должна вернуть False при попытке добавить существующий логин"
    
    # Проверяем, что в БД осталась только первая запись
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE username='duplicate_user'")
    count = cursor.fetchone()[0]
    assert count == 1, "Должна быть только одна запись с таким логином"
    
    cursor.execute("SELECT email FROM users WHERE username='duplicate_user'")
    email = cursor.fetchone()[0]
    assert email == 'first@example.com', "Email не должен измениться"

def test_add_user_empty_fields(setup_database, connection, clean_db):
    """Тест добавления пользователя с пустыми полями."""
    result = add_user('', 'email@test.com', 'pass123')
    assert result is True, "Пустой логин может быть добавлен (зависит от требований)"
    
    result = add_user('testuser2', '', 'pass123')
    assert result is True, "Пустой email может быть добавлен"
    
    result = add_user('testuser3', 'email3@test.com', '')
    assert result is True, "Пустой пароль может быть добавлен"

# ========== ТЕСТЫ ДЛЯ authenticate_user ==========

def test_auth_success(setup_database, connection, clean_db):
    """Тест успешной аутентификации пользователя."""
    add_user('authuser', 'auth@example.com', 'correct_password')
    
    result = authenticate_user('authuser', 'correct_password')
    assert result is True, "Аутентификация с правильными данными должна быть успешной"

def test_auth_wrong_password(setup_database, connection, clean_db):
    """Тест аутентификации пользователя с неправильным паролем."""
    add_user('user123', 'user@example.com', 'realpass')
    
    result = authenticate_user('user123', 'wrongpass')
    assert result is False, "Аутентификация с неправильным паролем должна провалиться"

def test_auth_non_existent_user(setup_database, connection, clean_db):
    """Тест аутентификации несуществующего пользователя."""
    result = authenticate_user('nonexistent', 'anypassword')
    assert result is False, "Аутентификация несуществующего пользователя должна провалиться"

def test_auth_case_sensitivity(setup_database, connection, clean_db):
    """Тест чувствительности к регистру логина и пароля."""
    add_user('CaseSensitive', 'case@example.com', 'Pass123')
    
    # Проверяем разные варианты регистра
    assert authenticate_user('CaseSensitive', 'Pass123') is True, "Точное совпадение должно работать"
    assert authenticate_user('casesensitive', 'Pass123') is False, "Логин чувствителен к регистру"
    assert authenticate_user('CaseSensitive', 'pass123') is False, "Пароль чувствителен к регистру"

# ========== ТЕСТЫ ДЛЯ display_users ==========

def test_display_users_with_data(setup_database, connection, clean_db, capsys):
    """Тест отображения списка пользователей при наличии данных."""
    # Добавляем тестовых пользователей
    add_user('user1', 'user1@test.com', 'pass1')
    add_user('user2', 'user2@test.com', 'pass2')
    
    # Вызываем функцию и захватываем вывод
    display_users()
    captured = capsys.readouterr()
    
    assert "Логин: user1, Электронная почта: user1@test.com" in captured.out
    assert "Логин: user2, Электронная почта: user2@test.com" in captured.out

def test_display_users_empty_db(setup_database, connection, clean_db, capsys):
    """Тест отображения списка пользователей при пустой БД."""
    display_users()
    captured = capsys.readouterr()
    assert captured.out == "", "При пустой БД не должно быть вывода"

def test_display_users_multiple_users(setup_database, connection, clean_db, capsys):
    """Тест отображения нескольких пользователей."""
    users = [
        ('alice', 'alice@test.com', 'pass1'),
        ('bob', 'bob@test.com', 'pass2'),
        ('charlie', 'charlie@test.com', 'pass3')
    ]
    
    for username, email, password in users:
        add_user(username, email, password)
    
    display_users()
    captured = capsys.readouterr()
    
    for username, email, _ in users:
        assert f"Логин: {username}, Электронная почта: {email}" in captured.out

# ========== ТЕСТЫ ДЛЯ user_choice ==========

def test_user_choice_1(monkeypatch):
    """Тест выбора опции 1."""
    monkeypatch.setattr('builtins.input', lambda _: '1')
    result = user_choice()
    assert result == '1'
