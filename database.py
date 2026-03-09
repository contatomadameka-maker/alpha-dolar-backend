import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'alpha_dolar.db')

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deriv_id TEXT UNIQUE NOT NULL,
            nome TEXT,
            email TEXT,
            token_demo TEXT,
            token_real TEXT,
            account_type TEXT DEFAULT 'demo',
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ultimo_acesso TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS operacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id TEXT,
            bot_name TEXT,
            tipo TEXT,
            stake REAL,
            resultado TEXT,
            lucro REAL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print("Banco criado com sucesso!")

if __name__ == '__main__':
    init_db()
