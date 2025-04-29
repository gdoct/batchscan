import datetime
import io
import os
import sqlite3
import threading
from contextlib import contextmanager

from PIL import Image


class RepositoryBase:
    def __init__(self, db_file="photos.db"):
        """Initialize the repository with a database file."""
        self.db_file = db_file
        self._local = threading.local()
    
    def connect(self):
        """Connect to the SQLite database in a thread-safe way."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(self.db_file)
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    def close(self):
        """Close the database connection for the current thread."""
        if hasattr(self._local, 'connection') and self._local.connection is not None:
            self._local.connection.close()
            self._local.connection = None
    
    @contextmanager
    def transaction(self):
        """Provide a context manager for database transactions."""
        connection = self.connect()
        cursor = None
        try:
            cursor = connection.cursor()
            yield cursor
            connection.commit()
        except Exception as e:
            if connection:
                try:
                    connection.rollback()
                except Exception as rollback_error:
                    # Rollback failed, log error but continue with original error
                    print(f"Rollback failed: {rollback_error}")
            raise e
        finally:
            if cursor is not None:
                cursor.close()
    
    def get_current_datetime(self):
        """Get the current date and time in a format suitable for the database."""
        now = datetime.datetime.now()
        return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")

class PhotoRepository(RepositoryBase):
    def add_photo(self, folderid, fullpath, filename, is_completed=0, filesize=None, md5=None, width=None, height=None, month=None, year=None):
        """Add a new photo to the database."""
        date, time = self.get_current_datetime()
        with self.transaction() as cursor:
            cursor.execute('''
                INSERT INTO photos (folderid, fullpath, filename, date, time, is_completed, 
                                   filesize, md5, width, height, month, year)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (folderid, fullpath, filename, date, time, is_completed, 
                 filesize, md5, width, height, month, year))
            return cursor.lastrowid
    
    def update_photo(self, photo_id, **kwargs):
        """Update a photo in the database."""
        allowed_fields = ['folderid', 'fullpath', 'filename', 'is_completed', 
                          'filesize', 'md5', 'width', 'height', 'month', 'year']
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
    
    def get_photos_count_by_folder(self, folderid):
        """Get the count of photos in a specified folder.
        
        Args:
            folderid (int): ID of the folder
            
        Returns:
            int: Count of photos in the folder
        """
        with self.transaction() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM photos WHERE folderid = ?", (folderid,))
            result = cursor.fetchone()
            return result['count'] if result else 0
    
    def get_photos_by_folder_paginated(self, folderid, offset, limit):
        """Get paginated photos in a specified folder.
        
        Args:
            folderid (int): ID of the folder
            offset (int): Number of records to skip
            limit (int): Maximum number of records to return
            
        Returns:
            list: List of photo records
        """
        with self.transaction() as cursor:
            cursor.execute("""
                SELECT * FROM photos 
                WHERE folderid = ? 
                ORDER BY filename
                LIMIT ? OFFSET ?
            """, (folderid, limit, offset))
            return cursor.fetchall()
    
    def get_uncompleted_photos(self):
        """Get all photos that have not been processed."""
        with self.transaction() as cursor:
            cursor.execute("SELECT * FROM photos WHERE is_completed = 0")
            return cursor.fetchall()
    
    def get_photo_by_filesize_and_md5(self, filesize, md5):
        """Find a photo with matching filesize and MD5 hash.
        
        Args:
            filesize (int): Size of the file in bytes
            md5 (str): MD5 hash of the file
            
        Returns:
            dict: Photo record if found, None otherwise
        """
        with self.transaction() as cursor:
            cursor.execute("""
                SELECT * FROM photos 
                WHERE filesize = ? AND md5 = ? AND is_completed = 1
                LIMIT 1
            """, (filesize, md5))
            return cursor.fetchone()

class MetaDataRepository(RepositoryBase):
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

class PhotoPreviewRepository(RepositoryBase):
    def add_thumbnail(self, photo_id, image_path):
        """Add a thumbnail for a photo."""
        date, time = self.get_current_datetime()
        thumbnail = self.create_thumbnail(image_path)
        with self.transaction() as cursor:
            cursor.execute('''
                INSERT INTO photo_preview (photo_id, thumbnail, date, time)
                VALUES (?, ?, ?, ?)
            ''', (photo_id, thumbnail, date, time))
            return cursor.lastrowid
    
    def create_thumbnail(self, image_path, size=(128, 128)):
        """Create a thumbnail for an image, preserving orientation."""
        try:
            with Image.open(image_path) as img:
                # Apply orientation based on EXIF data
                if hasattr(img, '_getexif') and img._getexif() is not None:
                    exif = dict(img._getexif().items())
                    # EXIF orientation tag is 0x0112 (274)
                    if 274 in exif:
                        orientation = exif[274]
                        # Handle orientation values
                        if orientation == 2:
                            img = img.transpose(Image.FLIP_LEFT_RIGHT)
                        elif orientation == 3:
                            img = img.transpose(Image.ROTATE_180)
                        elif orientation == 4:
                            img = img.transpose(Image.FLIP_TOP_BOTTOM)
                        elif orientation == 5:
                            img = img.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.ROTATE_90)
                        elif orientation == 6:
                            img = img.transpose(Image.ROTATE_270)
                        elif orientation == 7:
                            img = img.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.ROTATE_270)
                        elif orientation == 8:
                            img = img.transpose(Image.ROTATE_90)
                
                # Create thumbnail while maintaining aspect ratio
                img.thumbnail(size, Image.LANCZOS)
                
                with io.BytesIO() as output:
                    # Save with highest quality to maintain clarity
                    img.save(output, format="JPEG", quality=95)
                    return output.getvalue()
        except Exception as e:
            print(f"Error creating thumbnail: {str(e)}")
            # Return a placeholder thumbnail or None
            return None
    
    def get_thumbnail(self, photo_id):
        """Get the thumbnail for a photo."""
        with self.transaction() as cursor:
            cursor.execute("SELECT thumbnail FROM photo_preview WHERE photo_id = ?", (photo_id,))
            result = cursor.fetchone()
            return result['thumbnail'] if result else None
    
    def delete_thumbnail(self, photo_id):
        """Delete the thumbnail for a photo."""
        with self.transaction() as cursor:
            cursor.execute("DELETE FROM photo_preview WHERE photo_id = ?", (photo_id,))