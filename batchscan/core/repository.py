import datetime
import os
import sqlite3
from contextlib import contextmanager


class RepositoryBase:
    def __init__(self, db_file="photos.db"):
        """Initialize the repository with a database file."""
        self.db_file = db_file
        self.connection = None
        self.initialize_database()
    
    def initialize_database(self):
        """Create the database file and tables if they don't exist."""
        if not os.path.exists(self.db_file):
            self.connect()
            self.create_tables()
            self.close()
    
    def connect(self):
        """Connect to the SQLite database."""
        if self.connection is None:
            self.connection = sqlite3.connect(self.db_file)
            self.connection.row_factory = sqlite3.Row
        return self.connection
    
    def close(self):
        """Close the database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def create_tables(self):
        """Create all necessary tables in the database."""
        # This method will be overridden by subclasses
        pass
    
    @contextmanager
    def transaction(self):
        """Provide a context manager for database transactions."""
        connection = self.connect()
        try:
            cursor = connection.cursor()
            yield cursor
            connection.commit()
        except Exception as e:
            connection.rollback()
            raise e
        finally:
            cursor.close()
    
    def get_current_datetime(self):
        """Get the current date and time in a format suitable for the database."""
        now = datetime.datetime.now()
        return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")

class PhotoRepository(RepositoryBase):
    def create_tables(self):
        """Create the photos table if it doesn't exist."""
        with self.transaction() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS photos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    folderid INTEGER,
                    fullpath TEXT,
                    filename TEXT,
                    date TEXT,
                    time TEXT,
                    is_completed INTEGER DEFAULT 0,
                    FOREIGN KEY (folderid) REFERENCES folders (id)
                )
            ''')
    
    def add_photo(self, folderid, fullpath, filename, is_completed=0):
        """Add a new photo to the database."""
        date, time = self.get_current_datetime()
        with self.transaction() as cursor:
            cursor.execute('''
                INSERT INTO photos (folderid, fullpath, filename, date, time, is_completed)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (folderid, fullpath, filename, date, time, is_completed))
            return cursor.lastrowid
    
    def update_photo(self, photo_id, **kwargs):
        """Update a photo in the database."""
        allowed_fields = ['folderid', 'fullpath', 'filename', 'is_completed']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not updates:
            return
        
        # Add date and time to updates
        date, time = self.get_current_datetime()
        updates['date'] = date
        updates['time'] = time
        
        with self.transaction() as cursor:
            placeholders = ', '.join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [photo_id]
            cursor.execute(f'''
                UPDATE photos SET {placeholders} WHERE id = ?
            ''', values)
    
    def delete_photo(self, photo_id):
        """Delete a photo from the database."""
        with self.transaction() as cursor:
            cursor.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
    
    def get_photo_by_id(self, photo_id):
        """Get a photo by its ID."""
        with self.transaction() as cursor:
            cursor.execute("SELECT * FROM photos WHERE id = ?", (photo_id,))
            return cursor.fetchone()
    
    def get_photos_by_folder(self, folderid):
        """Get all photos in a specified folder."""
        with self.transaction() as cursor:
            cursor.execute("SELECT * FROM photos WHERE folderid = ?", (folderid,))
            return cursor.fetchall()
    
    def get_uncompleted_photos(self):
        """Get all photos that have not been processed."""
        with self.transaction() as cursor:
            cursor.execute("SELECT * FROM photos WHERE is_completed = 0")
            return cursor.fetchall()

class MetaDataRepository(RepositoryBase):
    def create_tables(self):
        """Create the metadata table if it doesn't exist."""
        with self.transaction() as cursor:
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
    
    def add_metadata(self, photo_id, key, value):
        """Add metadata for a photo."""
        date, time = self.get_current_datetime()
        with self.transaction() as cursor:
            cursor.execute('''
                INSERT INTO metadata (photo_id, key, value, date, time)
                VALUES (?, ?, ?, ?, ?)
            ''', (photo_id, key, value, date, time))
            return cursor.lastrowid
    
    def update_metadata(self, metadata_id, key=None, value=None):
        """Update metadata for a photo."""
        updates = {}
        if key is not None:
            updates['key'] = key
        if value is not None:
            updates['value'] = value
        
        if not updates:
            return
        
        # Add date and time to updates
        date, time = self.get_current_datetime()
        updates['date'] = date
        updates['time'] = time
        
        with self.transaction() as cursor:
            placeholders = ', '.join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [metadata_id]
            cursor.execute(f'''
                UPDATE metadata SET {placeholders} WHERE id = ?
            ''', values)
    
    def delete_metadata(self, metadata_id):
        """Delete metadata by ID."""
        with self.transaction() as cursor:
            cursor.execute("DELETE FROM metadata WHERE id = ?", (metadata_id,))
    
    def delete_photo_metadata(self, photo_id):
        """Delete all metadata for a specific photo."""
        with self.transaction() as cursor:
            cursor.execute("DELETE FROM metadata WHERE photo_id = ?", (photo_id,))
    
    def get_photo_metadata(self, photo_id):
        """Get all metadata for a specific photo."""
        with self.transaction() as cursor:
            cursor.execute("SELECT * FROM metadata WHERE photo_id = ?", (photo_id,))
            return cursor.fetchall()
    
    def get_metadata_by_key(self, photo_id, key):
        """Get specific metadata by key for a photo."""
        with self.transaction() as cursor:
            cursor.execute("SELECT * FROM metadata WHERE photo_id = ? AND key = ?", (photo_id, key))
            return cursor.fetchone()

class TagRepository(RepositoryBase):
    def create_tables(self):
        """Create the tags table if it doesn't exist."""
        with self.transaction() as cursor:
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
    
    def add_tag(self, photo_id, tag):
        """Add a tag to a photo."""
        date, time = self.get_current_datetime()
        with self.transaction() as cursor:
            cursor.execute('''
                INSERT INTO tags (photo_id, tag, date, time)
                VALUES (?, ?, ?, ?)
            ''', (photo_id, tag, date, time))
            return cursor.lastrowid
    
    def delete_tag(self, tag_id):
        """Delete a tag by ID."""
        with self.transaction() as cursor:
            cursor.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
    
    def delete_photo_tags(self, photo_id):
        """Delete all tags for a specific photo."""
        with self.transaction() as cursor:
            cursor.execute("DELETE FROM tags WHERE photo_id = ?", (photo_id,))
    
    def get_photo_tags(self, photo_id):
        """Get all tags for a specific photo."""
        with self.transaction() as cursor:
            cursor.execute("SELECT * FROM tags WHERE photo_id = ?", (photo_id,))
            return cursor.fetchall()
    
    def get_photos_by_tag(self, tag):
        """Get all photos with a specific tag."""
        with self.transaction() as cursor:
            cursor.execute('''
                SELECT p.* FROM photos p
                JOIN tags t ON p.id = t.photo_id
                WHERE t.tag = ?
            ''', (tag,))
            return cursor.fetchall()

class FolderRepository(RepositoryBase):
    def create_tables(self):
        """Create the folders table if it doesn't exist."""
        with self.transaction() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS folders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT UNIQUE,
                    date TEXT,
                    time TEXT
                )
            ''')
    
    def add_folder(self, path):
        """Add a new folder to the database."""
        date, time = self.get_current_datetime()
        with self.transaction() as cursor:
            try:
                cursor.execute('''
                    INSERT INTO folders (path, date, time)
                    VALUES (?, ?, ?)
                ''', (path, date, time))
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # Folder already exists, get its ID
                cursor.execute("SELECT id FROM folders WHERE path = ?", (path,))
                result = cursor.fetchone()
                return result['id'] if result else None
    
    def update_folder(self, folder_id, path):
        """Update a folder's path."""
        date, time = self.get_current_datetime()
        with self.transaction() as cursor:
            cursor.execute('''
                UPDATE folders SET path = ?, date = ?, time = ? WHERE id = ?
            ''', (path, date, time, folder_id))
    
    def delete_folder(self, folder_id):
        """Delete a folder from the database."""
        with self.transaction() as cursor:
            # First, delete all photos in this folder to maintain referential integrity
            cursor.execute("DELETE FROM photos WHERE folderid = ?", (folder_id,))
            # Then delete the folder
            cursor.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
    
    def get_folder_by_id(self, folder_id):
        """Get a folder by its ID."""
        with self.transaction() as cursor:
            cursor.execute("SELECT * FROM folders WHERE id = ?", (folder_id,))
            return cursor.fetchone()
    
    def get_folder_by_path(self, path):
        """Get a folder by its path."""
        with self.transaction() as cursor:
            cursor.execute("SELECT * FROM folders WHERE path = ?", (path,))
            return cursor.fetchone()
    
    def get_all_folders(self):
        """Get all folders."""
        with self.transaction() as cursor:
            cursor.execute("SELECT * FROM folders")
            return cursor.fetchall()