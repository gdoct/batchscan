document.addEventListener('DOMContentLoaded', function() {
    // Socket.io setup
    const socket = io();
    let activeFolderId = null;
    let photoModal = null;
    
    // Initialize Bootstrap modal
    photoModal = new bootstrap.Modal(document.getElementById('photo-modal'));
    
    // Add this utility function at the top of your script (inside the DOMContentLoaded event listener)
    function formatImageUrl(path) {
        // Remove any leading slashes from the path
        let normalizedPath = path;
        while (normalizedPath.startsWith('/')) {
            normalizedPath = normalizedPath.substring(1);
        }
        
        // Create the URL with exactly one slash between 'image' and the path
        return `/image/${normalizedPath}`;
    }

    // Navigation
    document.getElementById('nav-photos').addEventListener('click', function(e) {
        e.preventDefault();
        document.getElementById('photos-view').style.display = 'block';
        document.getElementById('scanner-view').style.display = 'none';
        document.getElementById('nav-photos').classList.add('active');
        document.getElementById('nav-scanner').classList.remove('active');
    });
    
    document.getElementById('nav-scanner').addEventListener('click', function(e) {
        e.preventDefault();
        document.getElementById('photos-view').style.display = 'none';
        document.getElementById('scanner-view').style.display = 'block';
        document.getElementById('nav-scanner').classList.add('active');
        document.getElementById('nav-photos').classList.remove('active');
        
        // Update scanner status when switching to this view
        updateScannerStatus();
    });
    
    // Load folders
    function loadFolders() {
        fetch('/api/folders')
            .then(response => response.json())
            .then(folders => {
                const folderList = document.getElementById('folder-list');
                folderList.innerHTML = '';
                
                if (folders.length === 0) {
                    folderList.innerHTML = '<div class="list-group-item">No folders found</div>';
                    return;
                }
                
                folders.forEach(folder => {
                    const folderItem = document.createElement('a');
                    folderItem.className = 'list-group-item list-group-item-action folder-item';
                    folderItem.dataset.folderId = folder.id;
                    folderItem.innerHTML = `
                        <span class="folder-path">${folder.path}</span>
                    `;
                    
                    folderItem.addEventListener('click', function() {
                        // Mark as active
                        document.querySelectorAll('.folder-item').forEach(item => {
                            item.classList.remove('active');
                        });
                        this.classList.add('active');
                        
                        // Load photos for this folder
                        activeFolderId = folder.id;
                        loadPhotos(folder.id);
                    });
                    
                    folderList.appendChild(folderItem);
                });
            })
            .catch(error => {
                console.error('Error loading folders:', error);
                document.getElementById('folder-list').innerHTML = '<div class="list-group-item text-danger">Error loading folders</div>';
            });
    }
    
    // Load photos for a folder
    function loadPhotos(folderId) {
        const photoGrid = document.getElementById('photo-grid');
        photoGrid.innerHTML = `
            <div class="col-12 text-center">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading photos...</span>
                </div>
            </div>
        `;
        
        fetch(`/api/folder/${folderId}/photos`)
            .then(response => response.json())
            .then(photos => {
                photoGrid.innerHTML = '';
                
                if (photos.length === 0) {
                    photoGrid.innerHTML = '<div class="col-12 text-center text-muted">No photos found in this folder</div>';
                    return;
                }
                
                photos.forEach(photo => {
                    // Only show completed photos
                    if (photo.is_completed !== 1) return;
                    
                    const photoCard = document.createElement('div');
                    photoCard.className = 'col-md-4 col-sm-6 photo-card';
                    
                    // Use the formatting function to ensure proper URL structure
                    const imagePath = formatImageUrl(photo.fullpath);
                    
                    // Get description from metadata
                    let description = '';
                    if (photo.metadata && photo.metadata.q1) {
                        description = photo.metadata.q1;
                    }
                    
                    photoCard.innerHTML = `
                        <div class="card">
                            <img src="${imagePath}" class="card-img-top photo-thumbnail" alt="${photo.filename}">
                            <div class="card-body">
                                <h5 class="card-title">${photo.filename}</h5>
                                <p class="card-text small text-truncate">${description}</p>
                            </div>
                        </div>
                    `;
                    
                    photoCard.addEventListener('click', function() {
                        showPhotoDetails(photo.id);
                    });
                    
                    photoGrid.appendChild(photoCard);
                });
            })
            .catch(error => {
                console.error('Error loading photos:', error);
                photoGrid.innerHTML = '<div class="col-12 text-center text-danger">Error loading photos</div>';
            });
    }
    
    // Show photo details
    function showPhotoDetails(photoId) {
        fetch(`/api/photo/${photoId}`)
            .then(response => response.json())
            .then(photo => {
                // Set modal title
                document.getElementById('photo-modal-title').textContent = photo.filename;
                
                // Use the formatting function to ensure proper URL structure
                const imagePath = formatImageUrl(photo.fullpath);
                document.getElementById('photo-modal-image').src = imagePath;
                
                // Set metadata
                const metadataContainer = document.getElementById('photo-modal-metadata');
                metadataContainer.innerHTML = '';
                
                if (photo.metadata) {
                    for (const [key, value] of Object.entries(photo.metadata)) {
                        let label = key;
                        if (key === 'q1') label = 'Description';
                        if (key === 'q2') label = 'Keywords';
                        
                        metadataContainer.innerHTML += `
                            <dt class="col-sm-3">${label}</dt>
                            <dd class="col-sm-9">${value}</dd>
                        `;
                    }
                }
                
                // Set tags
                const tagsContainer = document.getElementById('photo-modal-tags');
                tagsContainer.innerHTML = '';
                
                if (photo.tags && photo.tags.length > 0) {
                    photo.tags.forEach(tag => {
                        tagsContainer.innerHTML += `
                            <span class="badge bg-secondary tag-badge">${tag}</span>
                        `;
                    });
                } else {
                    tagsContainer.innerHTML = '<em>No tags found</em>';
                }
                
                // Show modal
                photoModal.show();
            })
            .catch(error => {
                console.error('Error loading photo details:', error);
                alert('Error loading photo details');
            });
    }
    
    // Scanner control
    document.getElementById('start-scan').addEventListener('click', function() {
        const folderPath = document.getElementById('folder-path').value.trim();
        
        if (!folderPath) {
            alert('Please enter a folder path');
            return;
        }
        
        fetch('/api/scan/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ folder_path: folderPath })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert('Error: ' + data.error);
            } else {
                updateScannerUI(true, folderPath);
            }
        })
        .catch(error => {
            console.error('Error starting scan:', error);
            alert('Error starting scan');
        });
    });
    
    document.getElementById('stop-scan').addEventListener('click', function() {
        fetch('/api/scan/stop', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert('Error: ' + data.error);
            } else {
                alert('Scan is stopping...');
                // Will be updated via socket.io event
            }
        })
        .catch(error => {
            console.error('Error stopping scan:', error);
            alert('Error stopping scan');
        });
    });
    
    // Socket.io event handlers
    socket.on('connect', function() {
        console.log('Connected to server');
        updateScannerStatus();
    });
    
    socket.on('scan_update', function(data) {
        document.getElementById('scan-current-file').textContent = data.current_file || 'None';
        document.getElementById('scan-processed').textContent = data.processed;
        document.getElementById('scan-total').textContent = data.total;
        
        const progressBar = document.getElementById('scan-progress-bar');
        const percent = data.percent || 0;
        progressBar.style.width = percent + '%';
        progressBar.textContent = percent + '%';
        progressBar.setAttribute('aria-valuenow', percent);
    });
    
    socket.on('scan_complete', function() {
        updateScannerUI(false);
        // Refresh folder list and photos if we're viewing the relevant folder
        loadFolders();
        if (activeFolderId) {
            loadPhotos(activeFolderId);
        }
    });
    
    // Update scanner status from server
    function updateScannerStatus() {
        fetch('/api/scan/status')
            .then(response => response.json())
            .then(data => {
                updateScannerUI(data.running, data.folder);
                
                // Update progress if scan is running
                if (data.running && data.progress) {
                    socket.emit('scan_update', data.progress);
                }
            })
            .catch(error => {
                console.error('Error fetching scanner status:', error);
            });
    }
    
    // Update scanner UI elements
    function updateScannerUI(isRunning, folderPath) {
        const startScanButton = document.getElementById('start-scan');
        const stopScanButton = document.getElementById('stop-scan');
        const scanStatusElement = document.getElementById('scan-status');
        const scanFolderElement = document.getElementById('scan-folder');
        
        if (isRunning) {
            startScanButton.disabled = true;
            stopScanButton.disabled = false;
            scanStatusElement.textContent = 'Running';
            scanStatusElement.className = 'text-success';
            scanFolderElement.textContent = folderPath || 'Unknown';
            
            // Also update the folder path input
            if (folderPath) {
                document.getElementById('folder-path').value = folderPath;
            }
        } else {
            startScanButton.disabled = false;
            stopScanButton.disabled = true;
            scanStatusElement.textContent = 'Not running';
            scanStatusElement.className = '';
            
            // Only reset folder if not provided
            if (!folderPath) {
                scanFolderElement.textContent = 'None';
            }
        }
    }
    
    // Initialize
    loadFolders();
});