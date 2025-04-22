import os

from .db_init import initialize_database_tables
from .photo_scanner import PhotoScanner
from .repository import (FolderRepository, MetaDataRepository,
                         PhotoPreviewRepository, PhotoRepository,
                         TagRepository)


class BatchScanner:
    def __init__(self, db_file="photos.db"):
        """Initialize the BatchScanner with repositories and PhotoScanner"""
        # Initialize database tables in the correct order
        initialize_database_tables(db_file)
        
        # After tables are created, set up repository objects
        self.folder_repo = FolderRepository(db_file)
        self.photo_repo = PhotoRepository(db_file)
        self.metadata_repo = MetaDataRepository(db_file)
        self.tag_repo = TagRepository(db_file)
        self.preview_repo = PhotoPreviewRepository(db_file)
        
        self.scanner = PhotoScanner()
        self.model_loaded = False
    
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
        First reads all files from the folder and checks which are already processed,
        then processes all remaining images in a separate step.
        
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
        duplicates_found = 0
        
        # Step 1: Collect all image files in the directory
        print("Step 1: Collecting image files...")
        image_files = []
        for filename in os.listdir(directory_path):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                fullpath = os.path.join(directory_path, filename)
                image_files.append((filename, fullpath))
                total_images += 1
        
        print(f"Found {total_images} image files in directory")
        
        # Step 2: Check which files are already processed
        print("Step 2: Checking which files are already processed...")
        existing_photos = self.photo_repo.get_photos_by_folder(folder_id)
        existing_photo_map = {photo['filename']: photo for photo in existing_photos}
        
        # Separate files into processed and unprocessed
        processed_files = []
        unprocessed_files = []
        
        for filename, fullpath in image_files:
            existing_photo = existing_photo_map.get(filename)
            if existing_photo and existing_photo['is_completed'] == 1:
                processed_files.append((filename, fullpath, existing_photo))
            else:
                unprocessed_files.append((filename, fullpath, existing_photo))
        
        print(f"Already processed: {len(processed_files)} files")
        print(f"To be processed: {len(unprocessed_files)} files")
        
        # Step 3: Process skipped files and show info
        for filename, _, existing_photo in processed_files:
            print(f"Skipping already processed image: {filename}")
            skipped_images += 1
            # Dump information for skipped photo
            self._dump_photo_info(existing_photo['id'], filename, is_skipped=True)
        
        # Step 4: Process unprocessed files
        print("Step 3: Processing remaining files...")
        for idx, (filename, fullpath, existing_photo) in enumerate(unprocessed_files):
            print(f"Processing file {idx+1} of {len(unprocessed_files)}: {filename}")
            
            # Calculate file size and MD5 before full processing
            file_size = os.path.getsize(fullpath)
            
            # Calculate MD5
            import hashlib
            md5_hash = hashlib.md5()
            with open(fullpath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    md5_hash.update(chunk)
            md5_value = md5_hash.hexdigest()
            
            # Check if a photo with the same filesize and MD5 exists
            duplicate_photo = self.photo_repo.get_photo_by_filesize_and_md5(file_size, md5_value)
            
            if duplicate_photo and duplicate_photo['id'] != (existing_photo['id'] if existing_photo else None):
                print(f"Found duplicate photo for {filename} - using existing metadata")
                
                # Create new photo entry or update existing one
                photo_id = None
                if existing_photo:
                    photo_id = existing_photo['id']
                    # Update with is_completed and metadata from duplicate photo
                    self.photo_repo.update_photo(
                        photo_id, 
                        is_completed=1,
                        filesize=file_size,
                        md5=md5_value,
                        width=duplicate_photo['width'],
                        height=duplicate_photo['height'],
                        month=duplicate_photo['month'],
                        year=duplicate_photo['year']
                    )
                else:
                    photo_id = self.photo_repo.add_photo(
                        folder_id, fullpath, filename, is_completed=1,
                        filesize=file_size,
                        md5=md5_value,
                        width=duplicate_photo['width'],
                        height=duplicate_photo['height'],
                        month=duplicate_photo['month'],
                        year=duplicate_photo['year']
                    )
                
                # Copy metadata and tags from the duplicate photo
                self._copy_photo_metadata_and_tags(duplicate_photo['id'], photo_id)
                
                duplicates_found += 1
                print(f"Copied metadata from photo ID {duplicate_photo['id']} to {photo_id}")
                self._dump_photo_info(photo_id, filename)
                continue
            
            # Process the image
            print(f"Processing image: {filename}")
            try:
                # Process the image with the PhotoScanner
                image_results = self.scanner.process_single_image(fullpath)
                
                # Extract metadata fields to pass to photo repository
                image_metadata = {
                    'filesize': image_results.get('filesize'),
                    'md5': image_results.get('md5'),
                    'width': image_results.get('width'),
                    'height': image_results.get('height'),
                    'month': image_results.get('month'),
                    'year': image_results.get('year')
                }
                
                # Get or create photo record
                photo_id = None
                if existing_photo:
                    photo_id = existing_photo['id']
                    # Update with is_completed and metadata
                    self.photo_repo.update_photo(
                        photo_id, 
                        is_completed=1,
                        **image_metadata
                    )
                else:
                    photo_id = self.photo_repo.add_photo(
                        folder_id, fullpath, filename, is_completed=1,
                        **image_metadata
                    )
                
                # Delete any existing metadata and tags for this photo
                # to avoid duplicates if we're reprocessing
                self.metadata_repo.delete_photo_metadata(photo_id)
                self.tag_repo.delete_photo_tags(photo_id)
                
                # Insert metadata (answers to questions)
                for key, value in image_results.items():
                    # Skip metadata fields that are stored directly in the photos table
                    if key not in ['filesize', 'md5', 'width', 'height', 'month', 'year']:
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
            "skipped": skipped_images,
            "duplicates": duplicates_found
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

    def _copy_photo_metadata_and_tags(self, source_photo_id, target_photo_id):
        """
        Copy all metadata and tags from one photo to another.
        
        Args:
            source_photo_id (int): ID of the source photo
            target_photo_id (int): ID of the target photo
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get metadata from source photo
            source_metadata = self.metadata_repo.get_photo_metadata(source_photo_id)
            
            # Delete any existing metadata for target photo
            self.metadata_repo.delete_photo_metadata(target_photo_id)
            
            # Copy metadata to target photo
            for item in source_metadata:
                self.metadata_repo.add_metadata(target_photo_id, item['key'], item['value'])
            
            # Get tags from source photo
            source_tags = self.tag_repo.get_photo_tags(source_photo_id)
            
            # Delete any existing tags for target photo
            self.tag_repo.delete_photo_tags(target_photo_id)
            
            # Copy tags to target photo
            for item in source_tags:
                self.tag_repo.add_tag(target_photo_id, item['tag'])
                
            return True
        except Exception as e:
            print(f"Error copying metadata and tags: {str(e)}")
            return False