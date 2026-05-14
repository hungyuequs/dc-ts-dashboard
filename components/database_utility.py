# database utility.py
"""Utility functions for interacting with the SQLite database."""
import sqlite3
import os
import pandas as pd

######################　Basic functions for database interaction #########################

def get_database_path():
    """Get the path to the SQLite database file"""
    current_dir = os.getcwd()
    parent_dir = os.path.dirname(current_dir)
    return os.path.join(parent_dir, "Database", "DC_TS_database.db")

def ensure_database_exists():
    """Ensure the database directory and file exist"""
    db_path = get_database_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if not os.path.exists(db_path):
        # Create an empty database
        conn = sqlite3.connect(db_path)
        conn.close()
    return db_path

def get_table_names():
    """Get all table names from SQLite DB"""
    db_path = ensure_database_exists()
    
    try:
        conn = sqlite3.connect(db_path)
        # Get all table names
        table_names = pd.read_sql(
            "SELECT name FROM sqlite_master WHERE type='table'",
            conn
        )['name'].tolist()
        conn.close()
        return table_names
        
    except Exception as e:
        print(f"Error connecting to database: {str(e)}")
        return []

def load_table_data(table_name):
    """Load data from a specific table in the SQLite DB"""
    db_path = ensure_database_exists()
    
    try:
        conn = sqlite3.connect(db_path)
        # Load data from the specific table
        df = pd.read_sql(f"SELECT * FROM '{table_name}'", conn)
        
        # Standardize wafer column name
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
    """Check if a specific table exists in the database"""
    all_tables = get_table_names()
    return table_name in all_tables

def get_table_info(table_name):
    """Get detailed information about a specific table"""
    db_path = ensure_database_exists()
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Get table schema information
        schema_info = pd.read_sql(f"PRAGMA table_info('{table_name}')", conn)
        
        # Get row count
        row_count = pd.read_sql(f"SELECT COUNT(*) as count FROM '{table_name}'", conn)['count'][0]
        
        conn.close()
        
        return {
            'schema': schema_info,
            'row_count': row_count,
            'column_count': len(schema_info)
        }
        
    except Exception as e:
        print(f"Error getting table info for '{table_name}': {str(e)}")
        return None

def save_dataframe_to_table(df, table_name, if_exists='replace'):
    """Save a pandas DataFrame to a table in the database
    
    Args:
        df (pandas.DataFrame): The DataFrame to save
        table_name (str): Name of the table
        if_exists (str): How to behave if table exists ('fail', 'replace', 'append')
    """
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
    """Execute a custom SQL query
    
    Args:
        query (str): SQL query to execute
        params (tuple, optional): Parameters for the query
    """
    db_path = ensure_database_exists()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
            
        conn.commit()
        result = cursor.fetchall()
        conn.close()
        return result
    
    except Exception as e:
        print(f"Error executing query: {str(e)}")
        return None

def delete_table(table_name):
    """Delete a table from the database
    
    Args:
        table_name (str): Name of the table to delete
    """
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
    """Get all column names from a specific table
    
    Args:
        table_name (str): Name of the table
    
    Returns:
        list: List of column names, empty list if table doesn't exist or error occurs
    """
    if not check_table_exists(table_name):
        print(f"Table '{table_name}' does not exist")
        return []
    
    try:
        conn = sqlite3.connect(get_database_path())
        cursor = conn.cursor()
        
        # Get column information from the table
        cursor.execute(f"PRAGMA table_info('{table_name}')")
        columns = [col[1] for col in cursor.fetchall()]  # col[1] contains the column name
        
        conn.close()
        return columns
        
    except Exception as e:
        print(f"Error getting column names for table '{table_name}': {str(e)}")
        return []

def append_data_to_table(df, table_name, identifier_columns=None):
    """Append data to a table, checking for duplicates using identifier columns if provided.
    If the table doesn't exist, it will be created with appropriate column types.
    If new columns are found, they will be added to the existing table.
    Missing columns in the input data will be filled with NULL.
    
    Args:
        df (pandas.DataFrame): DataFrame containing the data to append
        table_name (str): Name of the target table
        identifier_columns (list, optional): List of column names that uniquely identify a row.
                                          If None, all records will be appended.
    
    Returns:
        bool: True if successful, False otherwise
    """
    db_path = get_database_path()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Make sure all column names are strings
        df = df.copy()
        df.columns = df.columns.map(str)
        
        # Check if table exists and handle columns
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        table_exists = cursor.fetchone() is not None

        if table_exists:
            # Get existing columns and their types
            table_info = pd.read_sql(f'PRAGMA table_info(`{table_name}`)', conn)
            existing_columns = set(table_info['name'].tolist())
            column_types = dict(zip(table_info['name'], table_info['type']))

            # Add columns from existing table that are missing in the DataFrame
            for col in existing_columns - set(df.columns):
                print(f"Adding missing column '{col}' to DataFrame with NULL values")
                sql_type = column_types[col]
                if sql_type in ('INTEGER', 'REAL'):
                    df[col] = pd.NA
                else:
                    df[col] = None

            # Add missing columns with auto type detection
            for col in df.columns:
                if col not in existing_columns:
                    # Guess SQLite type
                    series = df[col]
                    if pd.api.types.is_integer_dtype(series.dropna()):
                        sql_type = "INTEGER"
                    elif pd.api.types.is_float_dtype(series.dropna()):
                        sql_type = "REAL"
                    elif pd.api.types.is_bool_dtype(series.dropna()):
                        sql_type = "INTEGER"  # SQLite has no native boolean, store as 0/1
                    else:
                        sql_type = "TEXT"

                    cursor.execute(f'ALTER TABLE `{table_name}` ADD COLUMN `{col}` {sql_type}')
                    print(f"Added new column `{col}` ({sql_type}) to table `{table_name}`")
            
            # If identifier columns are provided, filter out duplicates
            if identifier_columns:
                # Verify identifier columns exist
                for col in identifier_columns:
                    if col not in df.columns:
                        print(f"Identifier column '{col}' missing from input data")
                        conn.close()
                        return False
                
                # Load existing data (only identifier columns)
                id_cols_str = ", ".join([f"'{col}'" for col in identifier_columns])
                existing_data = pd.read_sql(f"SELECT {id_cols_str} FROM '{table_name}'", conn)
                
                # Identify new records
                merged = pd.merge(existing_data, df[identifier_columns], how='inner', on=identifier_columns)
                duplicate_mask = df[identifier_columns].apply(tuple, axis=1).isin(
                    merged[identifier_columns].apply(tuple, axis=1)
                )
                df = df[~duplicate_mask]
                
                if len(df) == 0:
                    print("No new records to append - all identifiers already exist in table")
                    conn.close()
                    return True

        else:
            print(f"Creating new table: {table_name}")
        
        # Insert data
        df.to_sql(table_name, conn, if_exists='append' if table_exists else 'replace', index=False)
        
        # Verify and report results
        cursor.execute(f"SELECT COUNT(*) FROM '{table_name}'")
        total_records = cursor.fetchone()[0]
        
        print(f"✅ Successfully added {len(df)} records to table '{table_name}'")
        print(f"Total records in table '{table_name}': {total_records}")
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error appending data to table '{table_name}': {str(e)}")
        return False

def filter_table_data(table_name, filter_dict):
    """Filter rows from a table based on column values
    
    Args:
        table_name (str): Name of the table to filter
        filter_dict (dict): Dictionary of {column_name: filter_value} pairs
    
    Returns:
        pandas.DataFrame: Filtered DataFrame, empty DataFrame if error occurs
    """
    if not check_table_exists(table_name):
        print(f"Table '{table_name}' does not exist")
        return pd.DataFrame()
    
    # Verify all filter columns exist in the table
    table_columns = get_column_names(table_name)
    for col in filter_dict.keys():
        if col not in table_columns:
            print(f"Filter column '{col}' does not exist in table")
            return pd.DataFrame()
    
    try:
        conn = sqlite3.connect(get_database_path())
        
        # Construct WHERE clause
        where_conditions = []
        params = []
        for col, value in filter_dict.items():
            where_conditions.append(f"'{col}' = ?")
            params.append(value)
        
        where_clause = " AND ".join(where_conditions)
        query = f"SELECT * FROM '{table_name}' WHERE {where_clause}"
        
        # Execute query with parameters
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        
        return df
        
    except Exception as e:
        print(f"Error filtering data from table '{table_name}': {str(e)}")
        return pd.DataFrame()

