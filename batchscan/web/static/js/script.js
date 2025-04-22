document.addEventListener('DOMContentLoaded', function() {
    // Socket.IO connection
    const socket = io();
    
    // DOM elements
    const navPhotos = document.getElementById('nav-photos');
    const navScanner = document.getElementById('nav-scanner');
    const photosView = document.getElementById('photos-view');
    const scannerView = document.getElementById('scanner-view');
    const folderList = document.getElementById('folder-list');
    const photoGrid = document.getElementById('photo-grid');
    const photoModal = document.getElementById('photo-modal');
    const photoModalTitle = document.getElementById('photo-modal-title');
    const photoModalImage = document.getElementById('photo-modal-image');
    const photoModalMetadata = document.getElementById('photo-modal-metadata');
    const photoModalTags = document.getElementById('photo-modal-tags');
    const photoModalPrev = document.getElementById('photo-modal-prev');
    const photoModalNext = document.getElementById('photo-modal-next');
    const folderPath = document.getElementById('folder-path');
    const startScan = document.getElementById('start-scan');
    const stopScan = document.getElementById('stop-scan');
    const scanStatusElement = document.getElementById('scan-status');
    const scanFolderElement = document.getElementById('scan-folder');
    const scanProgressBar = document.getElementById('scan-progress-bar');
    const scanCurrentFileElement = document.getElementById('scan-current-file');
    const scanProcessedElement = document.getElementById('scan-processed');
    const scanTotalElement = document.getElementById('scan-total');
    const scanElapsedTimeElement = document.getElementById('scan-elapsed-time');
    const scanRemainingTimeElement = document.getElementById('scan-remaining-time');
    
    // State tracking
    let currentFolderId = null;
    let currentFolderPath = null;
    let currentPhotoId = null;
    let currentPhotos = [];
    let modalInstance = null;

    // Initialize Bootstrap modal
    if (photoModal) {
        modalInstance = new bootstrap.Modal(photoModal);
    }

    // Load folders when page loads
    loadFolders();

    // Add event listeners for navigation 
    navPhotos.addEventListener('click', function(e) {
        e.preventDefault();
        showPhotosView();
        
        // Refresh folders each time we navigate to photos view
        loadFolders();
        
        // If a folder was previously selected, refresh its photos too
        if (currentFolderId) {
            loadPhotosInFolder(currentFolderId, currentFolderPath);
        }
    });

    navScanner.addEventListener('click', function(e) {
        e.preventDefault();
        showScannerView();
    });

    // Photo modal navigation event listeners
    photoModalPrev.addEventListener('click', function() {
        navigatePhotos(-1);
    });

    photoModalNext.addEventListener('click', function() {
        navigatePhotos(1);
    });

    // Add keyboard navigation for modal
    photoModal.addEventListener('keydown', function(e) {
        if (e.key === 'ArrowLeft') {
            navigatePhotos(-1);
        } else if (e.key === 'ArrowRight') {
            navigatePhotos(1);
        }
    });

    // Socket.IO event handlers
    socket.on('scan_update', function(data) {
        // Update progress UI
        updateScanProgress(data);
    });

    socket.on('scan_complete', function() {
        scanStatusElement.textContent = 'Scan completed';
        scanProgressBar.style.width = '100%';
        scanProgressBar.textContent = '100%';
        scanProgressBar.setAttribute('aria-valuenow', 100);
        
        // Reset UI
        startScan.disabled = false;
        stopScan.disabled = true;
        
        // Reload folders and photos if we're on the photos view
        if (photosView.style.display !== 'none') {
            loadFolders();
            
            // If a folder was previously selected, refresh its photos
            if (currentFolderId) {
                loadPhotosInFolder(currentFolderId, currentFolderPath);
            }
        }
    });

    // Button click event handlers
    startScan.addEventListener('click', function() {
        const path = folderPath.value.trim();
        if (!path) {
            alert('Please enter a folder path');
            return;
        }
        
        startScanning(path);
    });

    stopScan.addEventListener('click', function() {
        stopScanning();
    });

    // Helper functions
    function showPhotosView() {
        photosView.style.display = 'block';
        scannerView.style.display = 'none';
        navPhotos.classList.add('active');
        navScanner.classList.remove('active');
    }

    function showScannerView() {
        photosView.style.display = 'none';
        scannerView.style.display = 'block';
        navPhotos.classList.remove('active');
        navScanner.classList.add('active');
    }

    function loadFolders() {
        // Show a loading spinner
        folderList.innerHTML = `
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        `;
        
        fetch('/api/folders')
            .then(response => response.json())
            .then(folders => {
                folderList.innerHTML = ''; // Clear the loading spinner
                
                if (folders.length === 0) {
                    folderList.innerHTML = '<div class="list-group-item">No folders found</div>';
                    return;
                }
                
                // Add each folder to the list
                folders.forEach(folder => {
                    const item = document.createElement('a');
                    item.href = '#';
                    item.className = 'list-group-item list-group-item-action';
                    
                    if (currentFolderId === folder.id) {
                        item.classList.add('active');
                    }
                    
                    item.textContent = folder.path;
                    item.addEventListener('click', function(e) {
                        e.preventDefault();
                        
                        // Update UI
                        document.querySelectorAll('#folder-list a').forEach(el => {
                            el.classList.remove('active');
                        });
                        this.classList.add('active');
                        
                        // Update state
                        currentFolderId = folder.id;
                        currentFolderPath = folder.path;
                        
                        // Load photos for this folder
                        loadPhotosInFolder(folder.id, folder.path);
                    });
                    
                    folderList.appendChild(item);
                });
            })
            .catch(error => {
                console.error('Error loading folders:', error);
                folderList.innerHTML = '<div class="list-group-item text-danger">Error loading folders</div>';
            });
    }

    function loadPhotosInFolder(folderId, folderPath) {
        // Show loading state
        photoGrid.innerHTML = `
            <div class="col-12 text-center">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading photos...</span>
                </div>
                <p class="mt-2">Loading photos from ${folderPath}...</p>
            </div>
        `;
        
        fetch(`/api/folder/${folderId}/photos`)
            .then(response => response.json())
            .then(photos => {
                // Update state
                currentPhotos = photos;
                
                // Clear previous content
                photoGrid.innerHTML = '';
                
                if (photos.length === 0) {
                    photoGrid.innerHTML = `
                        <div class="col-12 text-center text-muted">
                            No photos found in this folder
                        </div>
                    `;
                    return;
                }
                
                // Add each photo as a card
                photos.forEach(photo => {
                    const col = document.createElement('div');
                    col.className = 'col-md-4 col-lg-3 mb-4';
                    
                    const card = document.createElement('div');
                    card.className = 'card h-100 photo-card';
                    
                    // Add thumbnail or placeholder
                    if (photo.thumbnail) {
                        const img = document.createElement('img');
                        img.className = 'card-img-top photo-thumbnail';
                        img.src = `data:image/jpeg;base64,${photo.thumbnail}`;
                        img.alt = photo.filename;
                        card.appendChild(img);
                    } else {
                        const placeholder = document.createElement('div');
                        placeholder.className = 'card-img-top bg-light d-flex align-items-center justify-content-center';
                        placeholder.style.height = '150px';
                        placeholder.innerHTML = '<span class="text-muted">No preview</span>';
                        card.appendChild(placeholder);
                    }
                    
                    // Card body with title and description
                    const cardBody = document.createElement('div');
                    cardBody.className = 'card-body';
                    
                    const title = document.createElement('h6');
                    title.className = 'card-title';
                    title.textContent = photo.filename;
                    
                    const description = document.createElement('p');
                    description.className = 'card-text small';
                    
                    if (photo.metadata && photo.metadata.q1) {
                        description.textContent = photo.metadata.q1;
                    } else {
                        description.textContent = 'No description available';
                    }
                    
                    cardBody.appendChild(title);
                    cardBody.appendChild(description);
                    
                    // Add tags if available
                    if (photo.tags && photo.tags.length > 0) {
                        const tagsDiv = document.createElement('div');
                        tagsDiv.className = 'mt-2';
                        
                        // Show first 2 tags only
                        photo.tags.slice(0, 2).forEach(tag => {
                            const badge = document.createElement('span');
                            badge.className = 'badge bg-primary me-1 tag-badge';
                            badge.textContent = tag;
                            tagsDiv.appendChild(badge);
                        });
                        
                        if (photo.tags.length > 2) {
                            const moreBadge = document.createElement('span');
                            moreBadge.className = 'badge bg-secondary tag-badge';
                            moreBadge.textContent = `+${photo.tags.length - 2} more`;
                            tagsDiv.appendChild(moreBadge);
                        }
                        
                        cardBody.appendChild(tagsDiv);
                    }
                    
                    card.appendChild(cardBody);
                    
                    // Make the entire card clickable to open the modal
                    card.addEventListener('click', () => {
                        showPhotoDetails(photo.id);
                    });
                    
                    col.appendChild(card);
                    photoGrid.appendChild(col);
                });
            })
            .catch(error => {
                console.error('Error loading photos:', error);
                photoGrid.innerHTML = `
                    <div class="col-12 text-center text-danger">
                        Error loading photos from this folder
                    </div>
                `;
            });
    }

    function showPhotoDetails(photoId) {
        // Update current photo id
        currentPhotoId = photoId;
        
        fetch(`/api/photo/${photoId}`)
            .then(response => response.json())
            .then(photo => {
                // Update modal title
                photoModalTitle.textContent = photo.filename;
                
                // Update modal image
                photoModalImage.src = `/image${photo.fullpath}`;
                photoModalImage.alt = photo.filename;
                
                // Update metadata
                photoModalMetadata.innerHTML = '';
                const metadataFields = [
                    { label: 'Path', value: photo.fullpath },
                    { label: 'Folder', value: photo.folder },
                    { label: 'Added', value: photo.date_added },
                ];
                
                if (photo.metadata && photo.metadata.q1) {
                    metadataFields.push({ label: 'Description', value: photo.metadata.q1 });
                }
                
                metadataFields.forEach(field => {
                    const dt = document.createElement('dt');
                    dt.className = 'col-sm-3';
                    dt.textContent = field.label;
                    
                    const dd = document.createElement('dd');
                    dd.className = 'col-sm-9';
                    dd.textContent = field.value;
                    
                    photoModalMetadata.appendChild(dt);
                    photoModalMetadata.appendChild(dd);
                });
                
                // Update tags
                photoModalTags.innerHTML = '';
                
                if (photo.tags && photo.tags.length > 0) {
                    photo.tags.forEach(tag => {
                        const badge = document.createElement('span');
                        badge.className = 'badge bg-primary me-1 mb-1';
                        badge.textContent = tag;
                        photoModalTags.appendChild(badge);
                    });
                } else {
                    photoModalTags.innerHTML = '<p class="text-muted">No tags available</p>';
                }
                
                // Add navigation buttons to the modal header
                //addNavigationButtons();
                
                // Show the modal
                modalInstance.show();
            })
            .catch(error => {
                console.error('Error loading photo details:', error);
                alert('Error loading photo details');
            });
    }
    
    function addNavigationButtons() {
        // Find the current photo index
        const currentIndex = currentPhotos.findIndex(photo => photo.id === currentPhotoId);
        if (currentIndex === -1) return;
        
        // Remove existing navigation buttons if present
        const existingNav = photoModal.querySelector('.photo-navigation');
        if (existingNav) existingNav.remove();
        
        // Create navigation container
        const navContainer = document.createElement('div');
        navContainer.className = 'photo-navigation d-flex align-items-center position-absolute start-0 ms-4';
        
        // Previous button
        if (currentIndex > 0) {
            const prevBtn = document.createElement('button');
            prevBtn.type = 'button';
            prevBtn.className = 'btn btn-outline-dark btn-sm me-2';
            prevBtn.innerHTML = '<i class="bi bi-arrow-left"></i> Previous';
            prevBtn.addEventListener('click', () => {
                showPhotoDetails(currentPhotos[currentIndex - 1].id);
            });
            navContainer.appendChild(prevBtn);
        }
        
        // Next button
        if (currentIndex < currentPhotos.length - 1) {
            const nextBtn = document.createElement('button');
            nextBtn.type = 'button';
            nextBtn.className = 'btn btn-outline-dark btn-sm';
            nextBtn.innerHTML = 'Next <i class="bi bi-arrow-right"></i>';
            nextBtn.addEventListener('click', () => {
                showPhotoDetails(currentPhotos[currentIndex + 1].id);
            });
            navContainer.appendChild(nextBtn);
        }
        
        // Add counter text
        const counterText = document.createElement('small');
        counterText.className = 'ms-2 text-muted';
        counterText.textContent = `${currentIndex + 1} of ${currentPhotos.length}`;
        navContainer.appendChild(counterText);
        
        // Insert navigation to modal header
        const modalHeader = photoModal.querySelector('.modal-header');
        modalHeader.style.position = 'relative'; // Ensure positioning context
        modalHeader.appendChild(navContainer);
    }

    function startScanning(path) {
        fetch('/api/scan/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ folder_path: path })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert(`Error: ${data.error}`);
                return;
            }
            
            // Update UI
            startScan.disabled = true;
            stopScan.disabled = false;
            scanStatusElement.textContent = 'Running';
            scanFolderElement.textContent = path;
            scanProgressBar.style.width = '0%';
            scanProgressBar.textContent = '0%';
            scanProgressBar.setAttribute('aria-valuenow', 0);
            scanCurrentFileElement.textContent = 'Starting...';
            scanProcessedElement.textContent = '0';
            scanTotalElement.textContent = '0';
            scanElapsedTimeElement.textContent = '0s';
            scanRemainingTimeElement.textContent = 'Calculating...';
        })
        .catch(error => {
            console.error('Error starting scan:', error);
            alert('Failed to start scan. See console for details.');
        });
    }

    function stopScanning() {
        fetch('/api/scan/stop', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert(`Error: ${data.error}`);
                return;
            }
            
            scanStatusElement.textContent = 'Stopping...';
            stopScan.disabled = true;
        })
        .catch(error => {
            console.error('Error stopping scan:', error);
            alert('Failed to stop scan. See console for details.');
        });
    }

    function updateScanProgress(data) {
        // Update progress bar
        const percent = data.percent;
        scanProgressBar.style.width = `${percent}%`;
        scanProgressBar.textContent = `${percent}%`;
        scanProgressBar.setAttribute('aria-valuenow', percent);
        
        // Update status text
        scanCurrentFileElement.textContent = data.current_file;
        scanProcessedElement.textContent = data.processed;
        scanTotalElement.textContent = data.total;

        // Format elapsed time into minutes and seconds
        if (data.elapsed_time !== undefined) {
            const elapsedSeconds = Math.floor(data.elapsed_time);
            const minutes = Math.floor(elapsedSeconds / 60);
            const seconds = elapsedSeconds % 60;
            
            if (minutes > 0) {
                scanElapsedTimeElement.textContent = `${minutes}m ${seconds}s`;
            } else {
                scanElapsedTimeElement.textContent = `${seconds}s`;
            }
        } else {
            scanElapsedTimeElement.textContent = '0s';
        }
        
        // Display estimated remaining time
        if (data.estimated_remaining) {
            scanRemainingTimeElement.textContent = data.estimated_remaining;
        } else {
            scanRemainingTimeElement.textContent = '--';
        }
        
        // If processed photos > 0, display average time per photo
        if (data.processed > 0 && data.elapsed_time) {
            const avgTimePerPhoto = data.elapsed_time / data.processed;
            // Add as a tooltip or additional element if needed
            // Example: scanElapsedTimeElement.title = `Avg: ${avgTimePerPhoto.toFixed(2)}s per photo`;
        }
    }

    function navigatePhotos(direction) {
        const currentIndex = currentPhotos.findIndex(photo => photo.id === currentPhotoId);
        if (currentIndex === -1) return;

        const newIndex = currentIndex + direction;
        if (newIndex >= 0 && newIndex < currentPhotos.length) {
            showPhotoDetails(currentPhotos[newIndex].id);
        }
    }
});