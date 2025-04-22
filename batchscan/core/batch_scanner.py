import os

from .photo_scanner import PhotoScanner
from .repository import (FolderRepository, MetaDataRepository, PhotoRepository,
                         TagRepository)


class BatchScanner:
    def __init__(self, db_file="photos.db"):
        """Initialize the BatchScanner with repositories and PhotoScanner"""
        # Initialize database tables in the correct order
        self._initialize_database_tables(db_file)
        
        # After tables are created, set up repository objects
        self.folder_repo = FolderRepository(db_file)
        self.photo_repo = PhotoRepository(db_file)
        self.metadata_repo = MetaDataRepository(db_file)
        self.tag_repo = TagRepository(db_file)
        
        self.scanner = PhotoScanner()
        self.model_loaded = False
    
    def _initialize_database_tables(self, db_file):
        """Initialize database tables in the correct order to respect foreign key relationships"""
        # Use one connection to create all tables in the correct order
        from sqlite3 import connect
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
        
        conn.commit()
        conn.close()
    
    def _ensure_model_loaded(self):
        """Ensure the model is loaded before processing images"""
        if not self.model_loaded:
            self.scanner.load_model()
            self.scanner.check_gpu()
            self.model_loaded = True
    
    def _dump_photo_info(self, photo_id, filename, is_skipped=False):
        """
        Dump all information about a photo to the console.
        
        Args:
            photo_id (int): The ID of the photo in the repository
            filename (str): The filename of the photo
            is_skipped (bool): Whether the photo was skipped (already processed)
        """
        photo = self.photo_repo.get_photo_by_id(photo_id)
        if not photo:
            print(f"No information found for photo ID {photo_id}")
            return
            
        print("\n" + "="*80)
        if is_skipped:
            print(f"SKIPPED - EXISTING PHOTO: {filename} (ID: {photo_id})")
        else:
            print(f"PROCESSED PHOTO: {filename} (ID: {photo_id})")
        print("="*80)
        
        print(f"Path: {photo['fullpath']}")
        print(f"Status: {'Processed' if photo['is_completed'] == 1 else 'Not processed'}")
        print(f"Date added: {photo['date']} {photo['time']}")
        
        # Get metadata
        metadata = self.metadata_repo.get_photo_metadata(photo_id)
        if metadata:
            print("\nMETADATA:")
            print("-"*80)
            for item in metadata:
                print(f"{item['key']}: {item['value']}")
        
        # Get tags
        tags = self.tag_repo.get_photo_tags(photo_id)
        if tags:
            tag_list = [tag['tag'] for tag in tags]
            print("\nTAGS:")
            print("-"*80)
            print(", ".join(tag_list))
            
        print("\n")
    
    def scan_directory(self, directory_path):
        """
        Scan all images in the specified directory and process them.
        
        Args:
            directory_path (str): Path to the directory containing images
        
        Returns:
            dict: Summary of the scan results
        """
        
        if not os.path.exists(directory_path) or not os.path.isdir(directory_path):
            print(f"Error: Directory '{directory_path}' does not exist or is not a directory")
            return {"error": "Invalid directory", "path": directory_path}
        
        self._ensure_model_loaded()
        print(f"Scanning directory: {directory_path}")
        
        # Add folder to repository if it doesn't exist
        folder_id = self.folder_repo.add_folder(directory_path)
        
        # Track statistics
        total_images = 0
        processed_images = 0
        skipped_images = 0
        
        # Scan each image file in the directory
        for filename in os.listdir(directory_path):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                total_images += 1
                fullpath = os.path.join(directory_path, filename)
                
                # Check if the image exists in the repository
                existing_photos = self.photo_repo.get_photos_by_folder(folder_id)
                existing_photo = None
                for photo in existing_photos:
                    if photo['filename'] == filename:
                        existing_photo = photo
                        break
                
                if existing_photo and existing_photo['is_completed'] == 1:
                    print(f"Skipping already processed image: {filename}")
                    skipped_images += 1
                    # Dump information for skipped photo
                    self._dump_photo_info(existing_photo['id'], filename, is_skipped=True)
                    continue
                
                # Process the image
                print(f"Processing image: {filename}")
                try:
                    # Process the image with the PhotoScanner
                    image_results = self.scanner.process_single_image(fullpath)
                    
                    # Get or create photo record
                    photo_id = None
                    if existing_photo:
                        photo_id = existing_photo['id']
                        self.photo_repo.update_photo(photo_id, is_completed=1)
                    else:
                        photo_id = self.photo_repo.add_photo(
                            folder_id, fullpath, filename, is_completed=1
                        )
                    
                    # Delete any existing metadata and tags for this photo
                    # to avoid duplicates if we're reprocessing
                    self.metadata_repo.delete_photo_metadata(photo_id)
                    self.tag_repo.delete_photo_tags(photo_id)
                    
                    # Insert metadata (answers to questions)
                    for key, value in image_results.items():
                        self.metadata_repo.add_metadata(photo_id, key, value)
                    
                    # Parse and insert tags from q2 (keywords)
                    if "q2" in image_results:
                        keywords = image_results["q2"].split(",")
                        for keyword in keywords:
                            tag = keyword.strip()
                            if tag:
                                self.tag_repo.add_tag(photo_id, tag)
                    
                    processed_images += 1
                    
                    # Dump information for processed photo
                    self._dump_photo_info(photo_id, filename)
                    
                except Exception as e:
                    print(f"Error processing image {filename}: {str(e)}")
                    # If there was an error, mark as not completed
                    if existing_photo:
                        self.photo_repo.update_photo(existing_photo['id'], is_completed=0)
                    else:
                        photo_id = self.photo_repo.add_photo(folder_id, fullpath, filename, is_completed=0)
        
        return {
            "directory": directory_path,
            "total_images": total_images,
            "processed": processed_images,
            "skipped": skipped_images
        }

    def scan_recursive(self, root_directory):
        """
        Recursively scan all subdirectories starting from the root directory.
        
        Args:
            root_directory (str): Path to the root directory
            
        Returns:
            dict: Summary of scan results for all directories
        """
        self._ensure_model_loaded()
        
        if not os.path.exists(root_directory) or not os.path.isdir(root_directory):
            print(f"Error: Directory '{root_directory}' does not exist or is not a directory")
            return {"error": "Invalid directory", "path": root_directory}
        
        results = {"directories_scanned": 0, "total_images": 0, "processed": 0, "skipped": 0}
        
        for dirpath, dirnames, filenames in os.walk(root_directory):
            dir_result = self.scan_directory(dirpath)
            
            # Update overall statistics
            results["directories_scanned"] += 1
            if "total_images" in dir_result:
                results["total_images"] += dir_result["total_images"]
            if "processed" in dir_result:
                results["processed"] += dir_result["processed"]
            if "skipped" in dir_result:
                results["skipped"] += dir_result["skipped"]
        
        return results