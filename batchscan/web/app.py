import json
import logging
import os
import sys
import threading
import time

from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_socketio import SocketIO

# Add the parent directory to the path so we can import from batchscan
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from batchscan.core.batch_scanner import BatchScanner
from batchscan.core.repository import (FolderRepository, MetaDataRepository,
                                       PhotoRepository, TagRepository)

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
scan_progress = {"total": 0, "processed": 0, "current_file": "", "percent": 0}

# Initialize repositories
folder_repo = FolderRepository(db_file)
photo_repo = PhotoRepository(db_file)
metadata_repo = MetaDataRepository(db_file)
tag_repo = TagRepository(db_file)

def background_scan_task(folder_path):
    global scan_running, scan_progress, scanner
    
    if not scanner:
        scanner = BatchScanner(db_file)
        scanner.scanner.load_model()
        scanner.scanner.check_gpu()
    
    try:
        logger.info(f"Starting scan of directory: {folder_path}")
        scan_running = True
        scan_progress = {"total": 0, "processed": 0, "current_file": "", "percent": 0}
        
        # Get all image files in the directory
        image_files = []
        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    image_files.append(os.path.join(root, file))
        
        scan_progress["total"] = len(image_files)
        socketio.emit('scan_update', scan_progress)
        
        # Add folder to repository
        folder_id = folder_repo.add_folder(folder_path)
        
        for i, fullpath in enumerate(image_files):
            if not scan_running:
                logger.info("Scan stopped by user")
                break
                
            filename = os.path.basename(fullpath)
            scan_progress["current_file"] = filename
            scan_progress["processed"] = i
            scan_progress["percent"] = int(100 * i / scan_progress["total"]) if scan_progress["total"] > 0 else 0
            socketio.emit('scan_update', scan_progress)
            
            # Check if the image exists in the repository
            existing_photos = photo_repo.get_photos_by_folder(folder_id)
            existing_photo = None
            for photo in existing_photos:
                if photo['filename'] == filename:
                    existing_photo = photo
                    break
            
            if existing_photo and existing_photo['is_completed'] == 1:
                logger.info(f"Skipping already processed image: {filename}")
                continue
            
            # Process the image
            logger.info(f"Processing image: {filename}")
            try:
                # Process the image with the PhotoScanner
                image_results = scanner.scanner.process_single_image(fullpath)
                
                # Get or create photo record
                photo_id = None
                if existing_photo:
                    photo_id = existing_photo['id']
                    photo_repo.update_photo(photo_id, is_completed=1)
                else:
                    photo_id = photo_repo.add_photo(folder_id, fullpath, filename, is_completed=1)
                
                # Delete any existing metadata and tags for this photo
                metadata_repo.delete_photo_metadata(photo_id)
                tag_repo.delete_photo_tags(photo_id)
                
                # Insert metadata (answers to questions)
                for key, value in image_results.items():
                    metadata_repo.add_metadata(photo_id, key, value)
                
                # Parse and insert tags from q2 (keywords)
                if "q2" in image_results:
                    keywords = image_results["q2"].split(",")
                    for keyword in keywords:
                        tag = keyword.strip()
                        if tag:
                            tag_repo.add_tag(photo_id, tag)
                
            except Exception as e:
                logger.error(f"Error processing image {filename}: {str(e)}")
                # If there was an error, mark as not completed
                if existing_photo:
                    photo_repo.update_photo(existing_photo['id'], is_completed=0)
                else:
                    photo_id = photo_repo.add_photo(folder_id, fullpath, filename, is_completed=0)
        
        # Final update
        scan_progress["processed"] = scan_progress["total"]
        scan_progress["percent"] = 100 if scan_progress["total"] > 0 else 0
        scan_progress["current_file"] = "Completed"
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
    
    return jsonify({
        'id': photo_id,
        'filename': photo['filename'],
        'fullpath': photo['fullpath'],
        'folder': folder_path,
        'is_completed': photo['is_completed'],
        'metadata': metadata_dict,
        'tags': tags_list,
        'date_added': f"{photo['date']} {photo['time']}" 
    })

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