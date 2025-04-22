import base64
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime
from io import BytesIO

from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_socketio import SocketIO

# Add the parent directory to the path so we can import from batchscan
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from batchscan.core.batch_scanner import BatchScanner
from batchscan.core.repository import (FolderRepository, MetaDataRepository,
                                       PhotoPreviewRepository, PhotoRepository,
                                       TagRepository)

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'photoScannerSecretKey'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global variables
db_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'photos.db')
scanner = None
scan_thread = None
scan_running = False
scan_folder = None
scan_progress = {"total": 0, "processed": 0, "current_file": "", "percent": 0, "start_time": None, "elapsed_time": 0, "estimated_remaining": ""}

# Initialize repositories
folder_repo = FolderRepository(db_file)
photo_repo = PhotoRepository(db_file)
metadata_repo = MetaDataRepository(db_file)
tag_repo = TagRepository(db_file)
preview_repo = PhotoPreviewRepository(db_file)

def background_scan_task(folder_path):
    global scan_running, scan_progress, scanner
    
    if not scanner:
        scanner = BatchScanner(db_file)
        scanner.scanner.load_model()
        scanner.scanner.check_gpu()
    
    try:
        logger.info(f"Starting scan of directory: {folder_path}")
        scan_running = True
        # Store start_time as a timestamp instead of datetime object for JSON serialization
        start_time = datetime.now()
        scan_progress = {
            "total": 0, 
            "processed": 0, 
            "current_file": "", 
            "percent": 0, 
            "start_time": start_time.timestamp(),  # Store as timestamp for JSON serialization
            "elapsed_time": 0, 
            "estimated_remaining": ""
        }
        
        # Step 1: Collect all image files in the directory
        logger.info("Step 1: Collecting all image files...")
        scan_progress["current_file"] = "Collecting files..."
        socketio.emit('scan_update', scan_progress)
        
        image_files = []
        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    image_files.append((os.path.join(root, file), file))
        
        total_images = len(image_files)
        scan_progress["total"] = total_images
        scan_progress["current_file"] = f"Found {total_images} images"
        socketio.emit('scan_update', scan_progress)
        logger.info(f"Found {total_images} image files in directory")
        
        # Make sure the folder exists in the repository
        folder_id = folder_repo.add_folder(folder_path)
        
        # Step 2: Check which files are already processed
        logger.info("Step 2: Checking which files are already processed...")
        scan_progress["current_file"] = "Checking processed files..."
        socketio.emit('scan_update', scan_progress)
        
        # Get all existing photos in this folder
        existing_photos = photo_repo.get_photos_by_folder(folder_id)
        existing_photo_map = {photo['filename']: photo for photo in existing_photos}
        
        # Separate files into processed and unprocessed
        processed_files = []
        unprocessed_files = []
        
        for fullpath, filename in image_files:
            if not scan_running:
                logger.info("Scan stopped by user during file analysis")
                return
                
            existing_photo = existing_photo_map.get(filename)
            if existing_photo and existing_photo['is_completed'] == 1:
                processed_files.append((fullpath, filename, existing_photo))
            else:
                unprocessed_files.append((fullpath, filename, existing_photo))
        
        already_processed = len(processed_files)
        to_process = len(unprocessed_files)
        logger.info(f"Already processed: {already_processed} files")
        logger.info(f"To be processed: {to_process} files")
        
        scan_progress["current_file"] = f"{already_processed} already processed, {to_process} to process"
        socketio.emit('scan_update', scan_progress)
        
        # Step 3: Process unprocessed files
        if to_process > 0:
            logger.info("Step 3: Processing remaining files...")
        
        for i, (fullpath, filename, existing_photo) in enumerate(unprocessed_files):
            if not scan_running:
                logger.info("Scan stopped by user during processing")
                break
                
            scan_progress["current_file"] = filename
            scan_progress["processed"] = already_processed + i
            scan_progress["percent"] = int(100 * scan_progress["processed"] / total_images) if total_images > 0 else 0
            
            # Calculate elapsed time
            elapsed_time = (datetime.now() - start_time).total_seconds()
            scan_progress["elapsed_time"] = elapsed_time
            
            # Calculate average time per photo on-demand and estimate remaining time
            if scan_progress["processed"] > 0:
                avg_time_per_photo = elapsed_time / scan_progress["processed"]
                remaining_photos = total_images - scan_progress["processed"]
                estimated_seconds = int(avg_time_per_photo * remaining_photos)
                if estimated_seconds > 0:
                    minutes, seconds = divmod(estimated_seconds, 60)
                    hours, minutes = divmod(minutes, 60)
                    if hours > 0:
                        scan_progress["estimated_remaining"] = f"{hours}h {minutes}m {seconds}s"
                    elif minutes > 0:
                        scan_progress["estimated_remaining"] = f"{minutes}m {seconds}s"
                    else:
                        scan_progress["estimated_remaining"] = f"{seconds}s"
                else:
                    scan_progress["estimated_remaining"] = "0s"
            else:
                scan_progress["estimated_remaining"] = "Calculating..."
            
            socketio.emit('scan_update', scan_progress)
            
            logger.info(f"Processing image ({i+1}/{to_process}): {filename}")
            try:
                # Process the image with the PhotoScanner
                image_results = scanner.scanner.process_single_image(fullpath)
                
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
                    photo_repo.update_photo(
                        photo_id, 
                        is_completed=1,
                        **{k: v for k, v in image_metadata.items() if v is not None}
                    )
                else:
                    photo_id = photo_repo.add_photo(
                        folder_id, fullpath, filename, is_completed=1,
                        **{k: v for k, v in image_metadata.items() if v is not None}
                    )
                
                # Delete any existing metadata and tags for this photo
                metadata_repo.delete_photo_metadata(photo_id)
                tag_repo.delete_photo_tags(photo_id)
                
                # Insert metadata (answers to questions)
                for key, value in image_results.items():
                    # Skip metadata fields that are stored directly in the photos table
                    if key not in ['filesize', 'md5', 'width', 'height', 'month', 'year']:
                        metadata_repo.add_metadata(photo_id, key, value)
                
                # Parse and insert tags from q2 (keywords)
                if "q2" in image_results:
                    keywords = image_results["q2"].split(",")
                    for keyword in keywords:
                        tag = keyword.strip()
                        if tag:
                            tag_repo.add_tag(photo_id, tag)
                
                # Generate and save thumbnail
                preview_repo.delete_thumbnail(photo_id)  # Remove any existing thumbnail
                preview_repo.add_thumbnail(photo_id, fullpath)
                logger.info(f"Thumbnail created for image: {filename}")
                
            except Exception as e:
                logger.error(f"Error processing image {filename}: {str(e)}")
                # If there was an error, mark as not completed
                if existing_photo:
                    photo_repo.update_photo(existing_photo['id'], is_completed=0)
                else:
                    photo_id = photo_repo.add_photo(folder_id, fullpath, filename, is_completed=0)
        
        # Final update
        scan_progress["processed"] = total_images
        scan_progress["percent"] = 100 if total_images > 0 else 0
        scan_progress["current_file"] = "Completed"
        # Final elapsed time calculation
        scan_progress["elapsed_time"] = (datetime.now() - start_time).total_seconds()
        socketio.emit('scan_update', scan_progress)
        
    except Exception as e:
        logger.error(f"Error scanning directory: {str(e)}")
    finally:
        scan_running = False
        socketio.emit('scan_complete')
        logger.info("Scan thread completed")

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/api/folders')
def get_folders():
    """Get all folders in the database"""
    folders = folder_repo.get_all_folders()
    return jsonify([{'id': f['id'], 'path': f['path']} for f in folders])

@app.route('/api/folder/<int:folder_id>/photos')
def get_photos_by_folder(folder_id):
    """Get all photos in a folder"""
    photos = photo_repo.get_photos_by_folder(folder_id)
    result = []
    
    for photo in photos:
        photo_data = {
            'id': photo['id'],
            'filename': photo['filename'],
            'fullpath': photo['fullpath'],
            'is_completed': photo['is_completed']
        }
        
        # Add metadata
        metadata = metadata_repo.get_photo_metadata(photo['id'])
        photo_data['metadata'] = {item['key']: item['value'] for item in metadata}
        
        # Add tags
        tags = tag_repo.get_photo_tags(photo['id'])
        photo_data['tags'] = [tag['tag'] for tag in tags]
        
        # Add thumbnail if available
        thumbnail = preview_repo.get_thumbnail(photo['id'])
        if thumbnail:
            # Convert binary thumbnail to base64 for embedding in JSON
            photo_data['thumbnail'] = base64.b64encode(thumbnail).decode('utf-8')
        
        result.append(photo_data)
    
    return jsonify(result)

@app.route('/api/photo/<int:photo_id>')
def get_photo_details(photo_id):
    """Get details for a specific photo"""
    photo = photo_repo.get_photo_by_id(photo_id)
    
    if not photo:
        return jsonify({'error': 'Photo not found'}), 404
    
    # Get folder path
    folder = folder_repo.get_folder_by_id(photo['folderid'])
    folder_path = folder['path'] if folder else ''
    
    # Get metadata
    metadata = metadata_repo.get_photo_metadata(photo_id)
    metadata_dict = {item['key']: item['value'] for item in metadata}
    
    # Get tags
    tags = tag_repo.get_photo_tags(photo_id)
    tags_list = [tag['tag'] for tag in tags]
    
    # Get thumbnail if available
    thumbnail_b64 = None
    thumbnail = preview_repo.get_thumbnail(photo_id)
    if thumbnail:
        thumbnail_b64 = base64.b64encode(thumbnail).decode('utf-8')
    
    return jsonify({
        'id': photo_id,
        'filename': photo['filename'],
        'fullpath': photo['fullpath'],
        'folder': folder_path,
        'is_completed': photo['is_completed'],
        'metadata': metadata_dict,
        'tags': tags_list,
        'thumbnail': thumbnail_b64,
        'date_added': f"{photo['date']} {photo['time']}" 
    })

@app.route('/api/thumbnail/<int:photo_id>')
def get_photo_thumbnail(photo_id):
    """Get the thumbnail for a photo"""
    thumbnail = preview_repo.get_thumbnail(photo_id)
    
    if not thumbnail:
        return jsonify({'error': 'Thumbnail not found'}), 404
    
    # Return the thumbnail as a JPEG image
    return send_from_directory(
        directory=os.path.dirname(os.path.abspath(__file__)),
        path='thumbnail.jpg',
        as_attachment=False,
        mimetype='image/jpeg'
    )

@app.route('/api/scan/start', methods=['POST'])
def start_scan():
    """Start scanning a directory"""
    global scan_thread, scan_running, scan_folder
    
    if scan_running:
        return jsonify({'error': 'Scanner is already running'}), 400
    
    data = request.json
    folder_path = data.get('folder_path')
    
    if not folder_path:
        return jsonify({'error': 'No folder specified'}), 400
    
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return jsonify({'error': f'Directory does not exist: {folder_path}'}), 400
    
    scan_folder = folder_path
    scan_thread = threading.Thread(target=background_scan_task, args=(folder_path,))
    scan_thread.daemon = True
    scan_thread.start()
    
    return jsonify({'status': 'started', 'folder': folder_path})

@app.route('/api/scan/stop', methods=['POST'])
def stop_scan():
    """Stop the currently running scan"""
    global scan_running
    
    if not scan_running:
        return jsonify({'error': 'No scanner is running'}), 400
    
    scan_running = False
    return jsonify({'status': 'stopping'})

@app.route('/api/scan/status')
def scan_status():
    """Get the current scan status"""
    global scan_running, scan_progress, scan_folder
    
    return jsonify({
        'running': scan_running,
        'folder': scan_folder,
        'progress': scan_progress
    })

@app.route('/image/<path:filename>')
def serve_image(filename):
    """Serve an image file with proper handling of absolute paths"""
    # Log the requested filename for debugging
    logger.info(f"Image requested: {filename}")
    
    # Handle both cases: with or without leading slash
    # Remove any leading slashes to normalize the path
    while filename.startswith('/'):
        filename = filename[1:]
    
    # Now ensure it's an absolute path by prepending a single slash
    if not filename.startswith('/'):
        filename = '/' + filename
    
    logger.info(f"Normalized image path: {filename}")
    
    try:
        # Check if the file exists
        if os.path.isfile(filename):
            from flask import send_file
            return send_file(filename)
        else:
            logger.error(f"Image file not found: {filename}")
            return f"Image file not found: {filename}", 404
    except Exception as e:
        logger.error(f"Error serving image: {str(e)}")
        return f"Error serving image: {str(e)}", 500

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)