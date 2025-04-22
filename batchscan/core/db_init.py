"""
Database initialization functionality for the BatchScan package.

This module contains functions for creating and initializing the database
tables required by the application.
"""

from sqlite3 import connect


def initialize_database_tables(db_file):
    """Initialize database tables in the correct order to respect foreign key relationships

    Args:
        db_file (str): Path to the SQLite database file
    """
    # Use one connection to create all tables in the correct order
    conn = connect(db_file)
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON")
    
    # Create folders table first (no dependencies)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE,
            date TEXT,
            time TEXT
        )
    ''')
    
    # Create photos table (depends on folders)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folderid INTEGER,
            fullpath TEXT,
            filename TEXT,
            date TEXT,
            time TEXT,
            is_completed INTEGER DEFAULT 0,
            filesize INTEGER,
            md5 TEXT,
            width INTEGER,
            height INTEGER,
            month INTEGER,
            year INTEGER,
            FOREIGN KEY (folderid) REFERENCES folders (id)
        )
    ''')
    
    # Create metadata table (depends on photos)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id INTEGER,
            key TEXT,
            value TEXT,
            date TEXT,
            time TEXT,
            FOREIGN KEY (photo_id) REFERENCES photos (id)
        )
    ''')
    
    # Create tags table (depends on photos)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id INTEGER,
            tag TEXT,
            date TEXT,
            time TEXT,
            FOREIGN KEY (photo_id) REFERENCES photos (id)
        )
    ''')
    
    # Create photo_preview table (depends on photos)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS photo_preview (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id INTEGER UNIQUE,
            thumbnail BLOB,
            width INTEGER,
            height INTEGER,
            date TEXT,
            time TEXT,
            FOREIGN KEY (photo_id) REFERENCES photos (id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()