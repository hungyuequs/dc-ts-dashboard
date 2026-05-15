# database utility.py
"""Utility functions for interacting with the SQLite database."""
import sqlite3
import os
import tempfile
import shutil
import pandas as pd
from pathlib import Path
from urllib.request import Request, urlopen

######################　Basic functions for database interaction #########################

def _get_secret_or_env(key, default=None):
    """Read from environment variable first, then Streamlit secrets."""
    val = os.getenv(key)
    if val:
        return val
    try:
        import streamlit as st
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return default

def _normalize_dropbox_url(url: str) -> str:
    """Convert a Dropbox share URL to a direct-download URL.
    Handles both old-style (?dl=0) and new-style (/scl/fi/... with &dl=0) URLs.
    """
    if not url:
        return url
    if "dropbox.com" in url:
        # Replace dl=0 with dl=1 wherever it appears in the query string
        url = url.replace("&dl=0", "&dl=1")
        url = url.replace("?dl=0", "?dl=1")
        # For old-style URLs with no dl param, append it
        if "dl=" not in url:
            url += ("&" if "?" in url else "?") + "dl=1"
    return url

def _download_file(url: str, dst: Path):
    """Download a file from url to dst, with a basic size sanity check."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    req = Request(_normalize_dropbox_url(url), headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=300) as resp, open(dst, "wb") as f:
        shutil.copyfileobj(resp, f)
    if dst.stat().st_size < 1024 * 1024:  # <1 MB is likely an HTML error page
        raise RuntimeError(f"Downloaded file is suspiciously small: {dst} ({dst.stat().st_size} bytes)")

def get_database_path():
    """
    Resolve the database path in this order:
      1) DASHBOARD_DB_PATH env/secret  — explicit override
      2) ./data/DC_TS_database.db      — repo-local copy
      3) ../Database/DC_TS_database.db — old local layout
      4) DB_URL env/secret             — download from Dropbox (cloud deployment)
    """
    # 1) Explicit path override
    explicit = _get_secret_or_env("DASHBOARD_DB_PATH")
    if explicit:
        p = Path(explicit)
        if p.exists():
            return str(p)
        raise FileNotFoundError(f"DASHBOARD_DB_PATH is set but file not found: {explicit}")

    # 2/3) Local file candidates (used by the batch-file / local dev workflow)
    repo_root = Path(__file__).resolve().parents[1]  # components/ -> repo root
    candidates = [
        repo_root / "data" / "DC_TS_database.db",
        repo_root.parent / "Database" / "DC_TS_database.db",
    ]
    for p in candidates:
        if p.exists():
            return str(p)

    # 4) Cloud download via Dropbox (Streamlit Community Cloud deployment)
    db_url = _get_secret_or_env("DB_URL")
    if db_url:
        db_name = _get_secret_or_env("DB_FILENAME", "DC_TS_database.db")
        cache_dir = Path(tempfile.gettempdir()) / "dc_ts_dashboard"
        db_path = cache_dir / db_name
        force_refresh = str(_get_secret_or_env("DB_FORCE_REFRESH", "0")) == "1"
        if force_refresh or not db_path.exists():
            _download_file(db_url, db_path)
        return str(db_path)

    raise FileNotFoundError(
        "Database not found. Options:\n"
        "  • Local: place DB in ./data/DC_TS_database.db\n"
        "  • Cloud: set DB_URL in Streamlit secrets or environment variable"
    )


def ensure_database_exists():
    """Ensure the database directory and file exist."""
    db_path = get_database_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if not os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        conn.close()
    return db_path

def get_table_names():
    """Get all table names from the SQLite database."""
    db_path = ensure_database_exists()
    try:
        conn = sqlite3.connect(db_path)
        table_names = pd.read_sql(
            "SELECT name FROM sqlite_master WHERE type='table'", conn
        )['name'].tolist()
        conn.close()
        return table_names
    except Exception as e:
        print(f"Error connecting to database: {str(e)}")
        return []

def load_table_data(table_name):
    """Load data from a specific table in the SQLite database."""
    db_path = ensure_database_exists()
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql(f"SELECT * FROM '{table_name}'", conn)
        if 'wafer_name' in df.columns:
            df.rename(columns={'wafer_name': 'Wafer'}, inplace=True)
        elif 'Wafer' not in df.columns:
            df['Wafer'] = 'Unknown'
        conn.close()
        return df
    except Exception as e:
        print(f"Error loading table '{table_name}': {str(e)}")
        return pd.DataFrame()

def check_table_exists(table_name):
    """Check if a specific table exists in the database."""
    return table_name in get_table_names()

def get_table_info(table_name):
    """Get schema and row count for a specific table."""
    db_path = ensure_database_exists()
    try:
        conn = sqlite3.connect(db_path)
        schema_info = pd.read_sql(f"PRAGMA table_info('{table_name}')", conn)
        row_count = pd.read_sql(f"SELECT COUNT(*) as count FROM '{table_name}'", conn)['count'][0]
        conn.close()
        return {'schema': schema_info, 'row_count': row_count, 'column_count': len(schema_info)}
    except Exception as e:
        print(f"Error getting table info for '{table_name}': {str(e)}")
        return None

def save_dataframe_to_table(df, table_name, if_exists='replace'):
    """Save a DataFrame to a table in the database."""
    db_path = ensure_database_exists()
    try:
        conn = sqlite3.connect(db_path)
        df.to_sql(table_name, conn, if_exists=if_exists, index=False)
        conn.close()
        print(f"✅ Successfully saved data to table '{table_name}'")
        return True
    except Exception as e:
        print(f"Error saving data to table '{table_name}': {str(e)}")
        return False

def execute_query(query, params=None):
    """Execute a custom SQL query."""
    db_path = ensure_database_exists()
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(query, params) if params else cursor.execute(query)
        conn.commit()
        result = cursor.fetchall()
        conn.close()
        return result
    except Exception as e:
        print(f"Error executing query: {str(e)}")
        return None

def delete_table(table_name):
    """Delete a table from the database."""
    if not check_table_exists(table_name):
        print(f"Table '{table_name}' does not exist")
        return False
    try:
        execute_query(f"DROP TABLE IF EXISTS '{table_name}'")
        print(f"✅ Successfully deleted table '{table_name}'")
        return True
    except Exception as e:
        print(f"Error deleting table '{table_name}': {str(e)}")
        return False

def get_column_names(table_name):
    """Get all column names from a specific table."""
    if not check_table_exists(table_name):
        print(f"Table '{table_name}' does not exist")
        return []
    try:
        conn = sqlite3.connect(get_database_path())
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info('{table_name}')")
        columns = [col[1] for col in cursor.fetchall()]
        conn.close()
        return columns
    except Exception as e:
        print(f"Error getting column names for table '{table_name}': {str(e)}")
        return []

def append_data_to_table(df, table_name, identifier_columns=None):
    """Append data to a table, skipping duplicate rows identified by identifier_columns.
    Creates the table if it does not exist; adds missing columns automatically.
    """
    db_path = get_database_path()
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        df = df.copy()
        df.columns = df.columns.map(str)

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        table_exists = cursor.fetchone() is not None

        if table_exists:
            table_info = pd.read_sql(f'PRAGMA table_info(`{table_name}`)', conn)
            existing_columns = set(table_info['name'].tolist())
            column_types = dict(zip(table_info['name'], table_info['type']))

            for col in existing_columns - set(df.columns):
                sql_type = column_types[col]
                df[col] = pd.NA if sql_type in ('INTEGER', 'REAL') else None

            for col in df.columns:
                if col not in existing_columns:
                    series = df[col]
                    if pd.api.types.is_integer_dtype(series.dropna()):
                        sql_type = "INTEGER"
                    elif pd.api.types.is_float_dtype(series.dropna()):
                        sql_type = "REAL"
                    elif pd.api.types.is_bool_dtype(series.dropna()):
                        sql_type = "INTEGER"
                    else:
                        sql_type = "TEXT"
                    cursor.execute(f'ALTER TABLE `{table_name}` ADD COLUMN `{col}` {sql_type}')

            if identifier_columns:
                for col in identifier_columns:
                    if col not in df.columns:
                        print(f"Identifier column '{col}' missing from input data")
                        conn.close()
                        return False
                id_cols_str = ", ".join([f"'{col}'" for col in identifier_columns])
                existing_data = pd.read_sql(f"SELECT {id_cols_str} FROM '{table_name}'", conn)
                merged = pd.merge(existing_data, df[identifier_columns], how='inner', on=identifier_columns)
                duplicate_mask = df[identifier_columns].apply(tuple, axis=1).isin(
                    merged[identifier_columns].apply(tuple, axis=1)
                )
                df = df[~duplicate_mask]
                if len(df) == 0:
                    print("No new records to append — all identifiers already exist")
                    conn.close()
                    return True
        else:
            print(f"Creating new table: {table_name}")

        df.to_sql(table_name, conn, if_exists='append' if table_exists else 'replace', index=False)
        cursor.execute(f"SELECT COUNT(*) FROM '{table_name}'")
        total_records = cursor.fetchone()[0]
        print(f"✅ Added {len(df)} records to '{table_name}' (total: {total_records})")
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error appending data to table '{table_name}': {str(e)}")
        return False

def filter_table_data(table_name, filter_dict):
    """Filter rows from a table based on column value equality."""
    if not check_table_exists(table_name):
        return pd.DataFrame()
    table_columns = get_column_names(table_name)
    for col in filter_dict.keys():
        if col not in table_columns:
            print(f"Filter column '{col}' does not exist in table")
            return pd.DataFrame()
    try:
        conn = sqlite3.connect(get_database_path())
        where_conditions = [f"'{col}' = ?" for col in filter_dict]
        params = list(filter_dict.values())
        query = f"SELECT * FROM '{table_name}' WHERE {' AND '.join(where_conditions)}"
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        print(f"Error filtering data from table '{table_name}': {str(e)}")
        return pd.DataFrame()