import sqlite3
from config import Config


def get_db():
    db = sqlite3.connect(Config.DATABASE)
    db.row_factory = sqlite3.Row
    return db


def _table_exists(db, table_name):
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (str(table_name),),
    ).fetchone()
    return bool(row)


def _table_columns(db, table_name):
    cols = {}
    try:
        for r in db.execute(f"PRAGMA table_info({table_name})").fetchall():
            cols[str(r[1])] = {
                "type": str(r[2] or ""),
                "notnull": int(r[3] or 0),
                "dflt": r[4],
                "pk": int(r[5] or 0),
            }
    except Exception:
        return {}
    return cols


def _has_unique_index_on_columns(db, table_name, wanted_cols):
    wanted = [str(x) for x in (wanted_cols or [])]
    try:
        idx_rows = db.execute(f"PRAGMA index_list({table_name})").fetchall()
    except Exception:
        return False
    for idx in idx_rows or []:
        unique = int(idx[2] or 0)
        idx_name = str(idx[1] or "")
        if unique != 1 or not idx_name:
            continue
        try:
            info_rows = db.execute(f"PRAGMA index_info('{idx_name}')").fetchall()
        except Exception:
            continue
        cols = [str(r[2]) for r in info_rows if r[2] is not None]
        if cols == wanted:
            return True
    return False


def _rebuild_agents_config_per_client(db):
    if not _table_exists(db, "agents_config"):
        return
    cols = _table_columns(db, "agents_config")
    if (
        cols.get("client_id", {}).get("notnull") == 1
        and _has_unique_index_on_columns(db, "agents_config", ["user_id", "agent_slug", "client_id"])
    ):
        return

    old_name = "agents_config_old_pcuniq"
    db.execute(f"DROP TABLE IF EXISTS {old_name}")
    db.execute("ALTER TABLE agents_config RENAME TO agents_config_old_pcuniq")
    db.execute('''
        CREATE TABLE agents_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            client_id INTEGER NOT NULL DEFAULT 0,
            agent_slug TEXT NOT NULL,
            custom_name TEXT,
            avatar_base64 TEXT,
            avatar_colors TEXT,
            llm_provider TEXT,
            llm_model TEXT,
            api_key TEXT,
            temperature REAL DEFAULT 0.7,
            max_tokens INTEGER DEFAULT 2048,
            rag_enabled INTEGER DEFAULT 1,
            status TEXT DEFAULT 'Active',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, agent_slug, client_id)
        )
    ''')
    old_cols = _table_columns(db, old_name)
    expr = {
        "id": "id" if "id" in old_cols else "NULL",
        "user_id": "user_id" if "user_id" in old_cols else "1",
        "client_id": "COALESCE(client_id, 0)" if "client_id" in old_cols else "0",
        "agent_slug": "agent_slug" if "agent_slug" in old_cols else "''",
        "custom_name": "custom_name" if "custom_name" in old_cols else "NULL",
        "avatar_base64": "avatar_base64" if "avatar_base64" in old_cols else "NULL",
        "avatar_colors": "avatar_colors" if "avatar_colors" in old_cols else "NULL",
        "llm_provider": "llm_provider" if "llm_provider" in old_cols else "NULL",
        "llm_model": "llm_model" if "llm_model" in old_cols else "NULL",
        "api_key": "api_key" if "api_key" in old_cols else "NULL",
        "temperature": "temperature" if "temperature" in old_cols else "0.7",
        "max_tokens": "max_tokens" if "max_tokens" in old_cols else "2048",
        "rag_enabled": "rag_enabled" if "rag_enabled" in old_cols else "1",
        "status": "status" if "status" in old_cols else "'Active'",
        "created_at": "created_at" if "created_at" in old_cols else "datetime('now')",
        "updated_at": "updated_at" if "updated_at" in old_cols else "datetime('now')",
    }
    db.execute(f"""
        INSERT INTO agents_config (
            id, user_id, client_id, agent_slug, custom_name, avatar_base64, avatar_colors,
            llm_provider, llm_model, api_key, temperature, max_tokens, rag_enabled, status, created_at, updated_at
        )
        SELECT
            {expr["id"]}, {expr["user_id"]}, {expr["client_id"]}, {expr["agent_slug"]},
            {expr["custom_name"]}, {expr["avatar_base64"]}, {expr["avatar_colors"]},
            {expr["llm_provider"]}, {expr["llm_model"]}, {expr["api_key"]}, {expr["temperature"]},
            {expr["max_tokens"]}, {expr["rag_enabled"]}, {expr["status"]}, {expr["created_at"]}, {expr["updated_at"]}
        FROM {old_name}
    """)
    db.execute(f"DROP TABLE {old_name}")


def _rebuild_connectors_config_per_client(db):
    if not _table_exists(db, "connectors_config"):
        return
    cols = _table_columns(db, "connectors_config")
    if (
        cols.get("client_id", {}).get("notnull") == 1
        and _has_unique_index_on_columns(db, "connectors_config", ["user_id", "connector_slug", "client_id"])
    ):
        return

    old_name = "connectors_config_old_pcuniq"
    db.execute(f"DROP TABLE IF EXISTS {old_name}")
    db.execute("ALTER TABLE connectors_config RENAME TO connectors_config_old_pcuniq")
    db.execute('''
        CREATE TABLE connectors_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            client_id INTEGER NOT NULL DEFAULT 0,
            connector_slug TEXT NOT NULL,
            status TEXT DEFAULT 'Disconnected',
            config_json TEXT,
            last_connected TEXT,
            UNIQUE(user_id, connector_slug, client_id)
        )
    ''')
    old_cols = _table_columns(db, old_name)
    expr = {
        "id": "id" if "id" in old_cols else "NULL",
        "user_id": "user_id" if "user_id" in old_cols else "1",
        "client_id": "COALESCE(client_id, 0)" if "client_id" in old_cols else "0",
        "connector_slug": "connector_slug" if "connector_slug" in old_cols else "''",
        "status": "status" if "status" in old_cols else "'Disconnected'",
        "config_json": "config_json" if "config_json" in old_cols else "NULL",
        "last_connected": "last_connected" if "last_connected" in old_cols else "NULL",
    }
    db.execute(f"""
        INSERT INTO connectors_config (
            id, user_id, client_id, connector_slug, status, config_json, last_connected
        )
        SELECT
            {expr["id"]}, {expr["user_id"]}, {expr["client_id"]}, {expr["connector_slug"]},
            {expr["status"]}, {expr["config_json"]}, {expr["last_connected"]}
        FROM {old_name}
    """)
    db.execute(f"DROP TABLE {old_name}")


def init_db():
    db = get_db()
    db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            is_premium BOOLEAN DEFAULT FALSE
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            client_id INTEGER,
            workspace_slug TEXT NOT NULL,
            agent_slug TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            title TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY,
            conv_id INTEGER NOT NULL,
            role TEXT NOT NULL,  -- 'user' or 'agent'
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conv_id) REFERENCES conversations (id)
        )
    ''')

    # Clients
    db.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL DEFAULT 'person',
            name TEXT,
            company_name TEXT,
            email TEXT,
            website TEXT,
            phone TEXT,
            address TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    ''')

    db.execute('''
        CREATE TABLE IF NOT EXISTS client_connectors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            connector_slug TEXT NOT NULL,
            account_id TEXT,
            account_name TEXT,
            status TEXT DEFAULT 'pending',
            config_json TEXT,
            last_synced TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
    ''')

    db.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            settings_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    db.execute('''
        CREATE TABLE IF NOT EXISTS usage_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            client_id INTEGER,
            event_type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            description TEXT,
            request_id TEXT,
            workspace_id TEXT,
            run_id TEXT,
            step_id TEXT,
            agent_id TEXT,
            trace_id TEXT,
            provider TEXT DEFAULT 'mock',
            model TEXT DEFAULT 'mock',
            region TEXT DEFAULT 'unknown',
            model_class TEXT DEFAULT 'auto',
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            tool_calls INTEGER DEFAULT 0,
            connector_calls INTEGER DEFAULT 0,
            latency_ms INTEGER DEFAULT 0,
            status TEXT DEFAULT 'ok',
            error_code TEXT,
            cost_estimate_usd REAL DEFAULT 0,
            cost_final_usd REAL DEFAULT 0,
            meta_json TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    for stmt in (
        "ALTER TABLE usage_ledger ADD COLUMN request_id TEXT",
        "ALTER TABLE usage_ledger ADD COLUMN workspace_id TEXT",
        "ALTER TABLE usage_ledger ADD COLUMN run_id TEXT",
        "ALTER TABLE usage_ledger ADD COLUMN step_id TEXT",
        "ALTER TABLE usage_ledger ADD COLUMN agent_id TEXT",
        "ALTER TABLE usage_ledger ADD COLUMN trace_id TEXT",
        "ALTER TABLE usage_ledger ADD COLUMN provider TEXT DEFAULT 'mock'",
        "ALTER TABLE usage_ledger ADD COLUMN model TEXT DEFAULT 'mock'",
        "ALTER TABLE usage_ledger ADD COLUMN region TEXT DEFAULT 'unknown'",
        "ALTER TABLE usage_ledger ADD COLUMN model_class TEXT DEFAULT 'auto'",
        "ALTER TABLE usage_ledger ADD COLUMN input_tokens INTEGER DEFAULT 0",
        "ALTER TABLE usage_ledger ADD COLUMN output_tokens INTEGER DEFAULT 0",
        "ALTER TABLE usage_ledger ADD COLUMN tool_calls INTEGER DEFAULT 0",
        "ALTER TABLE usage_ledger ADD COLUMN connector_calls INTEGER DEFAULT 0",
        "ALTER TABLE usage_ledger ADD COLUMN latency_ms INTEGER DEFAULT 0",
        "ALTER TABLE usage_ledger ADD COLUMN status TEXT DEFAULT 'ok'",
        "ALTER TABLE usage_ledger ADD COLUMN error_code TEXT",
        "ALTER TABLE usage_ledger ADD COLUMN cost_estimate_usd REAL DEFAULT 0",
        "ALTER TABLE usage_ledger ADD COLUMN cost_final_usd REAL DEFAULT 0",
        "ALTER TABLE usage_ledger ADD COLUMN meta_json TEXT",
    ):
        try:
            db.execute(stmt)
            db.commit()
        except Exception:
            pass

    # Insert mock users
    db.execute('INSERT OR IGNORE INTO users (id, username, is_premium) VALUES (1, "dev", FALSE)')
    db.execute('INSERT OR IGNORE INTO users (id, username, is_premium) VALUES (2, "Alice", FALSE)')
    db.execute('INSERT OR IGNORE INTO users (id, username, is_premium) VALUES (3, "Bob", TRUE)')

    # Flows table for orchestrator
    db.execute('''
        CREATE TABLE IF NOT EXISTS flows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT 'Untitled Flow',
            user_id INTEGER DEFAULT 1,
            client_id INTEGER,
            flow_json TEXT NOT NULL,
            thumbnail TEXT,
            category TEXT DEFAULT 'Uncategorized',
            description TEXT DEFAULT '',
            is_template INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            is_active INTEGER DEFAULT 1
        )
    ''')

    # Migrations: add flows columns if missing (existing DBs)
    for stmt in (
        "ALTER TABLE flows ADD COLUMN thumbnail TEXT",
        "ALTER TABLE flows ADD COLUMN category TEXT DEFAULT 'Uncategorized'",
        "ALTER TABLE flows ADD COLUMN description TEXT DEFAULT ''",
        "ALTER TABLE flows ADD COLUMN is_template INTEGER DEFAULT 0",
        "ALTER TABLE flows ADD COLUMN client_id INTEGER",
        "ALTER TABLE conversations ADD COLUMN client_id INTEGER",
        "ALTER TABLE agents_config ADD COLUMN client_id INTEGER",
        "ALTER TABLE connectors_config ADD COLUMN client_id INTEGER",
    ):
        try:
            db.execute(stmt)
            db.commit()
        except Exception:
            pass  # column already exists or table not yet present

    # Chunks table for RAG
    db.execute('''
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chunk_id TEXT UNIQUE,
            title TEXT,
            summary TEXT,
            content TEXT,
            source TEXT,
            timestamp TEXT DEFAULT (datetime('now'))
        )
    ''')

    # Agents config table
    db.execute('''
        CREATE TABLE IF NOT EXISTS agents_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            client_id INTEGER NOT NULL DEFAULT 0,
            agent_slug TEXT NOT NULL,
            custom_name TEXT,
            avatar_base64 TEXT,
            avatar_colors TEXT,
            llm_provider TEXT,
            llm_model TEXT,
            api_key TEXT,
            temperature REAL DEFAULT 0.7,
            max_tokens INTEGER DEFAULT 2048,
            rag_enabled INTEGER DEFAULT 1,
            status TEXT DEFAULT 'Active',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, agent_slug, client_id)
        )
    ''')

    # Migration: add avatar_colors/client_id column if missing (existing DBs)
    try:
        db.execute('ALTER TABLE agents_config ADD COLUMN avatar_colors TEXT')
        db.commit()
    except Exception:
        pass
    try:
        db.execute('ALTER TABLE agents_config ADD COLUMN client_id INTEGER')
        db.commit()
    except Exception:
        pass

    # Connectors config table
    db.execute('''
        CREATE TABLE IF NOT EXISTS connectors_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            client_id INTEGER NOT NULL DEFAULT 0,
            connector_slug TEXT NOT NULL,
            status TEXT DEFAULT 'Disconnected',
            config_json TEXT,
            last_connected TEXT,
            UNIQUE(user_id, connector_slug, client_id)
        )
    ''')

    try:
        db.execute('ALTER TABLE connectors_config ADD COLUMN client_id INTEGER')
        db.commit()
    except Exception:
        pass
    try:
        _rebuild_agents_config_per_client(db)
    except Exception:
        pass
    try:
        _rebuild_connectors_config_per_client(db)
    except Exception:
        pass

    # Helpful indexes
    try:
        db.execute('CREATE INDEX IF NOT EXISTS idx_clients_user ON clients(user_id)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_client_connectors_client ON client_connectors(client_id)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_flows_user_client ON flows(user_id, client_id)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_conversations_user_client ON conversations(user_id, client_id)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_agents_user_client ON agents_config(user_id, client_id)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_connectors_user_client ON connectors_config(user_id, client_id)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_user_settings_user ON user_settings(user_id)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_usage_ledger_user_created ON usage_ledger(user_id, created_at)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_usage_ledger_user_event ON usage_ledger(user_id, event_type)')
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_usage_ledger_request_id_unique "
            "ON usage_ledger(request_id) WHERE request_id IS NOT NULL AND request_id <> ''"
        )
    except Exception:
        pass

    db.commit()
    db.close()


def get_recent_conversations(user_id, workspace_slug, limit=5, client_id=None):
    db = get_db()
    sql = '''
        SELECT c.agent_slug, MAX(m.timestamp) as last_msg, c.title
        FROM conversations c
        JOIN messages m ON c.id = m.conv_id
        WHERE c.user_id = ? AND c.workspace_slug = ?
    '''
    params = [user_id, workspace_slug]
    if client_id is not None:
        sql += ' AND COALESCE(c.client_id, 0) = ?'
        params.append(int(client_id))
    sql += ' GROUP BY c.id ORDER BY last_msg DESC LIMIT ?'
    params.append(limit)
    rows = db.execute(sql, tuple(params)).fetchall()
    db.close()
    return [{'agent_slug': row[0], 'last_msg': row[1], 'title': row[2] or row[0]} for row in rows]


def get_conversation_context(conv_id, max_messages=4):
    db = get_db()
    rows = db.execute('SELECT role, content FROM messages WHERE conv_id = ? ORDER BY timestamp DESC LIMIT ?', (conv_id, max_messages)).fetchall()
    db.close()
    context = []
    for row in reversed(rows):
        context.append(f"{row[0].capitalize()}: {row[1]}")
    return "\n".join(context)


def create_new_conversation(user_id, workspace_slug, agent_slug, title="", client_id=None):
    db = get_db()
    try:
        cursor = db.execute(
            'INSERT INTO conversations (user_id, client_id, workspace_slug, agent_slug, title) VALUES (?, ?, ?, ?, ?)',
            (user_id, client_id, workspace_slug, agent_slug, title)
        )
    except Exception:
        cursor = db.execute(
            'INSERT INTO conversations (user_id, workspace_slug, agent_slug, title) VALUES (?, ?, ?, ?)',
            (user_id, workspace_slug, agent_slug, title)
        )
    conv_id = cursor.lastrowid
    db.commit()
    db.close()
    return conv_id


def get_or_create_conversation(user_id, workspace_slug, agent_slug, client_id=None):
    db = get_db()
    if client_id is None:
        row = db.execute(
            'SELECT id FROM conversations WHERE user_id = ? AND workspace_slug = ? AND agent_slug = ? ORDER BY created_at DESC LIMIT 1',
            (user_id, workspace_slug, agent_slug)
        ).fetchone()
    else:
        try:
            row = db.execute(
                'SELECT id FROM conversations WHERE user_id = ? AND workspace_slug = ? AND agent_slug = ? AND COALESCE(client_id, 0) = ? ORDER BY created_at DESC LIMIT 1',
                (user_id, workspace_slug, agent_slug, int(client_id))
            ).fetchone()
        except Exception:
            row = db.execute(
                'SELECT id FROM conversations WHERE user_id = ? AND workspace_slug = ? AND agent_slug = ? ORDER BY created_at DESC LIMIT 1',
                (user_id, workspace_slug, agent_slug)
            ).fetchone()

    if row:
        conv_id = row[0]
    else:
        conv_id = create_new_conversation(user_id, workspace_slug, agent_slug, client_id=client_id)
    db.close()
    return conv_id


def save_message(conv_id, role, content):
    db = get_db()
    db.execute('INSERT INTO messages (conv_id, role, content) VALUES (?, ?, ?)', (conv_id, role, content))
    db.commit()
    db.close()


def get_messages(conv_id):
    db = get_db()
    rows = db.execute('SELECT role, content FROM messages WHERE conv_id = ? ORDER BY timestamp', (conv_id,)).fetchall()
    db.close()
    return [{'role': row[0], 'content': row[1]} for row in rows]


def get_daily_message_count(user_id, client_id=None):
    db = get_db()
    if client_id is None:
        row = db.execute(
            'SELECT COUNT(*) FROM messages WHERE conv_id IN (SELECT id FROM conversations WHERE user_id = ?) AND DATE(timestamp) = DATE("now")',
            (user_id,)
        ).fetchone()
    else:
        try:
            row = db.execute(
                'SELECT COUNT(*) FROM messages WHERE conv_id IN (SELECT id FROM conversations WHERE user_id = ? AND COALESCE(client_id, 0) = ?) AND DATE(timestamp) = DATE("now")',
                (user_id, int(client_id))
            ).fetchone()
        except Exception:
            row = db.execute(
                'SELECT COUNT(*) FROM messages WHERE conv_id IN (SELECT id FROM conversations WHERE user_id = ?) AND DATE(timestamp) = DATE("now")',
                (user_id,)
            ).fetchone()
    db.close()
    return row[0]


def update_conversation_title(conv_id, title):
    db = get_db()
    db.execute('UPDATE conversations SET title = ? WHERE id = ?', (title, conv_id))
    db.commit()
    db.close()


def search_conversations(user_id, workspace_slug, query, limit=10, client_id=None):
    db = get_db()
    sql = '''
        SELECT c.agent_slug, MAX(m.timestamp) as last_msg, c.title
        FROM conversations c
        JOIN messages m ON c.id = m.conv_id
        WHERE c.user_id = ? AND c.workspace_slug = ? AND (c.title LIKE ? OR m.content LIKE ?)
    '''
    params = [user_id, workspace_slug, f'%{query}%', f'%{query}%']
    if client_id is not None:
        sql += ' AND COALESCE(c.client_id, 0) = ?'
        params.append(int(client_id))
    sql += ' GROUP BY c.id ORDER BY last_msg DESC LIMIT ?'
    params.append(limit)
    rows = db.execute(sql, tuple(params)).fetchall()
    db.close()
    return [{'agent_slug': row[0], 'last_msg': row[1], 'title': row[2] or row[0]} for row in rows]


def is_user_premium(user_id):
    db = get_db()
    row = db.execute('SELECT is_premium FROM users WHERE id = ?', (user_id,)).fetchone()
    db.close()
    return row[0] if row else False

