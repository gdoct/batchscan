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
    // Batch operation elements
    const batchActionsContainer = document.querySelector('.batch-actions');
    const batchDeleteDbBtn = document.getElementById('batch-delete-db');
    const batchDeleteAllBtn = document.getElementById('batch-delete-all');
    
    // Search elements
    const searchDescription = document.getElementById('search-description');
    const searchTags = document.getElementById('search-tags');
    const searchDateFrom = document.getElementById('search-date-from');
    const searchDateTo = document.getElementById('search-date-to');
    const searchApplyBtn = document.getElementById('search-apply');
    const searchResetBtn = document.getElementById('search-reset');
    const searchCollapse = document.getElementById('searchCollapse');
    const searchToggleBtn = document.querySelector('[data-bs-toggle="collapse"][data-bs-target="#searchCollapse"]');
    const searchToggleBtnIcon = searchToggleBtn.querySelector('i');
    
    // State tracking
    let currentFolderId = null;
    let currentFolderPath = null;
    let currentPhotoId = null;
    let currentPhotos = [];
    let filteredPhotos = [];
    let modalInstance = null;
    let selectedPhotos = new Set(); // Track selected photos by ID
    let availableTags = new Set(); // Track all available tags
    
    // Pagination state
    let serverPage = 1;               // Current server-side page (100 photos per page)
    let clientPage = 1;               // Current client-side page (25 photos per page)
    let totalServerPages = 1;         // Total number of server pages
    let totalClientPages = 1;         // Total number of client pages for current server page
    let clientPageSize = 25;          // Number of photos per client page
    let serverPageSize = 100;         // Number of photos per server page
    let totalPhotos = 0;              // Total number of photos in the folder

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

    // Add batch operation button event handlers
    batchDeleteDbBtn.addEventListener('click', function() {
        if (selectedPhotos.size === 0) {
            alert('No photos selected');
            return;
        }
        
        if (confirm(`Are you sure you want to delete ${selectedPhotos.size} photo(s) from the database?`)) {
            deleteSelectedPhotos(false);
        }
    });
    
    batchDeleteAllBtn.addEventListener('click', function() {
        if (selectedPhotos.size === 0) {
            alert('No photos selected');
            return;
        }
        
        if (confirm(`WARNING: This will permanently delete ${selectedPhotos.size} photo(s) from both the database AND disk. This cannot be undone. Continue?`)) {
            deleteSelectedPhotos(true);
        }
    });

    // Search event handlers
    searchApplyBtn.addEventListener('click', function() {
        applyFilters();
    });
    
    searchResetBtn.addEventListener('click', function() {
        resetFilters();
    });
    
    // Add input event for real-time filtering with description
    searchDescription.addEventListener('input', function() {
        // Only apply filter if the description is either empty or at least 3 characters
        if (this.value === '' || this.value.length >= 3) {
            applyFilters();
        }
    });

    // Update toggle button arrow when search area is expanded or collapsed
    searchCollapse.addEventListener('shown.bs.collapse', function() {
        searchToggleBtnIcon.classList.remove('bi-chevron-down');
        searchToggleBtnIcon.classList.add('bi-chevron-up');
    });

    searchCollapse.addEventListener('hidden.bs.collapse', function() {
        searchToggleBtnIcon.classList.remove('bi-chevron-up');
        searchToggleBtnIcon.classList.add('bi-chevron-down');
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
                        
                        // Reset selected photos when changing folders
                        selectedPhotos.clear();
                        updateBatchActionsVisibility();
                        
                        // Reset filters when changing folders
                        resetFilters();
                        
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

    function loadPhotosInFolder(folderId, folderPath, page = 1) {
        // Reset pagination state when loading a new folder
        if (currentFolderId !== folderId) {
            serverPage = 1;
            clientPage = 1;
        } else {
            // Otherwise use the provided page
            serverPage = page;
        }
        
        // Show loading state
        photoGrid.innerHTML = `
            <div class="col-12 text-center">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading photos...</span>
                </div>
                <p class="mt-2">Loading photos from ${folderPath}...</p>
            </div>
        `;
        
        fetch(`/api/folder/${folderId}/photos?page=${serverPage}`)
            .then(response => response.json())
            .then(data => {
                // Update state with server data
                currentPhotos = data.photos;
                filteredPhotos = data.photos; // Initially all photos are shown
                
                // Update pagination state
                totalPhotos = data.pagination.total_photos;
                totalServerPages = data.pagination.total_pages;
                totalClientPages = Math.ceil(currentPhotos.length / clientPageSize);
                
                // Reset client page when loading a new server page
                clientPage = 1;
                
                // Reset and collect available tags for this folder
                availableTags.clear();
                currentPhotos.forEach(photo => {
                    if (photo.tags && Array.isArray(photo.tags)) {
                        photo.tags.forEach(tag => availableTags.add(tag));
                    }
                });
                
                // Update tag filter options
                updateTagOptions();
                
                // Render photos with pagination
                renderPhotosPage(clientPage);
                
                // Update pagination UI
                renderPagination();
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
    
    function updateTagOptions() {
        // Clear existing options
        searchTags.innerHTML = '';
        
        // Sort tags alphabetically
        const sortedTags = Array.from(availableTags).sort();
        
        // Add options for each tag
        sortedTags.forEach(tag => {
            const option = document.createElement('option');
            option.value = tag;
            option.textContent = tag;
            searchTags.appendChild(option);
        });
    }
    
    function renderPhotos(photos) {
        // Clear previous content
        photoGrid.innerHTML = '';
                
        if (photos.length === 0) {
            photoGrid.innerHTML = `
                <div class="col-12 text-center text-muted">
                    No photos found matching your criteria
                </div>
            `;
            return;
        }
        
        // Add each photo as a card
        photos.forEach(photo => {
            const col = document.createElement('div');
            col.className = 'col-md-4 col-lg-3 mb-4';
            
            const card = document.createElement('div');
            card.className = 'card h-100 photo-card position-relative';
            card.dataset.photoId = photo.id;
            
            // Check if this photo is already selected
            if (selectedPhotos.has(photo.id)) {
                card.classList.add('selected');
            }
            
            // Add checkbox for selection
            const checkboxContainer = document.createElement('div');
            checkboxContainer.className = 'photo-checkbox-container';
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'photo-checkbox';
            checkbox.checked = selectedPhotos.has(photo.id);
            
            checkbox.addEventListener('change', function(e) {
                // Stop the event from triggering the card click
                e.stopPropagation();
                
                if (this.checked) {
                    selectedPhotos.add(photo.id);
                    card.classList.add('selected');
                } else {
                    selectedPhotos.delete(photo.id);
                    card.classList.remove('selected');
                }
                
                updateBatchActionsVisibility();
            });
            
            // Stop click on checkbox from opening the modal
            checkbox.addEventListener('click', function(e) {
                e.stopPropagation();
            });
            
            checkboxContainer.appendChild(checkbox);
            card.appendChild(checkboxContainer);
            
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
        
        // If we had selected photos before, check if they're still visible
        updateBatchActionsVisibility();
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
        const currentIndex = filteredPhotos.findIndex(photo => photo.id === currentPhotoId);
        if (currentIndex === -1) return;

        const newIndex = currentIndex + direction;
        if (newIndex >= 0 && newIndex < filteredPhotos.length) {
            showPhotoDetails(filteredPhotos[newIndex].id);
        }
    }
    
    // New functions for batch operations
    function updateBatchActionsVisibility() {
        if (selectedPhotos.size > 0) {
            batchActionsContainer.style.display = 'block';
        } else {
            batchActionsContainer.style.display = 'none';
        }
    }
    
    function deleteSelectedPhotos(deleteFromDisk) {
        // Convert Set to Array for the API call
        const photoIds = Array.from(selectedPhotos);
        
        // Call the appropriate API endpoint based on deleteFromDisk flag
        fetch('/api/photos/delete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                photo_ids: photoIds,
                delete_from_disk: deleteFromDisk
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert(`Error: ${data.error}`);
                return;
            }
            
            // Show success message
            const operation = deleteFromDisk ? 'deleted from database and disk' : 'deleted from database';
            alert(`${data.deleted} photos successfully ${operation}.`);
            
            // Reset selected photos
            selectedPhotos.clear();
            updateBatchActionsVisibility();
            
            // Reload photos to reflect the changes
            if (currentFolderId) {
                loadPhotosInFolder(currentFolderId, currentFolderPath);
            }
        })
        .catch(error => {
            console.error('Error deleting photos:', error);
            alert('Failed to delete photos. See console for details.');
        });
    }
    
    // New functions for search and filtering
    function resetFilters() {
        // Clear all search inputs
        searchDescription.value = '';
        searchDateFrom.value = '';
        searchDateTo.value = '';
        
        // Unselect all tags
        Array.from(searchTags.options).forEach(option => {
            option.selected = false;
        });
        
        // Reset to show all photos
        filteredPhotos = [...currentPhotos];
        
        // Reset to first page
        clientPage = 1;
        
        // Render photos with pagination
        renderPhotosPage(clientPage);
        renderPagination();
    }
    
    function applyFilters() {
        // Get filter criteria
        const descriptionFilter = searchDescription.value.toLowerCase().trim();
        const selectedTags = Array.from(searchTags.selectedOptions).map(option => option.value);
        const dateFrom = searchDateFrom.value ? new Date(searchDateFrom.value) : null;
        const dateTo = searchDateTo.value ? new Date(searchDateTo.value) : null;
        
        // Filter photos based on criteria
        filteredPhotos = currentPhotos.filter(photo => {
            // Description filter
            if (descriptionFilter) {
                const description = photo.metadata && photo.metadata.q1 
                    ? photo.metadata.q1.toLowerCase() 
                    : '';
                
                if (!description.includes(descriptionFilter)) {
                    return false;
                }
            }
            
            // Tag filter
            if (selectedTags.length > 0) {
                if (!photo.tags || !Array.isArray(photo.tags)) {
                    return false;
                }
                
                // Check if the photo has at least one of the selected tags
                const hasMatchingTag = selectedTags.some(tag => photo.tags.includes(tag));
                if (!hasMatchingTag) {
                    return false;
                }
            }
            
            // Date filter
            if (dateFrom || dateTo) {
                // Try to extract date from metadata or filename
                let photoDate = null;
                
                // Check if there's a date in metadata
                if (photo.metadata && (photo.metadata.year || photo.metadata.month)) {
                    const year = photo.metadata.year || '2000';
                    const month = photo.metadata.month || '01';
                    photoDate = new Date(`${year}-${month}-01`);
                }
                
                // If no date found, use the photo's added date
                if (!photoDate && photo.date_added) {
                    photoDate = new Date(photo.date_added);
                }
                
                // If we have a date to compare
                if (photoDate) {
                    // Check date range
                    if (dateFrom && photoDate < dateFrom) {
                        return false;
                    }
                    
                    if (dateTo) {
                        // Add a day to the date-to to make it inclusive
                        const adjustedDateTo = new Date(dateTo);
                        adjustedDateTo.setDate(adjustedDateTo.getDate() + 1);
                        
                        if (photoDate >= adjustedDateTo) {
                            return false;
                        }
                    }
                } else {
                    // If we can't determine a date and the user is filtering by date,
                    // exclude this photo from the results
                    return false;
                }
            }
            
            // If the photo passed all filters, include it
            return true;
        });
        
        // Reset to first page when applying filters
        clientPage = 1;
        
        // Render filtered photos with pagination
        renderPhotosPage(clientPage);
        renderPagination();
    }
    
    // Add client-side pagination functions
    function renderPhotosPage(page) {
        // Calculate the start and end indexes for the photos to display
        const start = (page - 1) * clientPageSize;
        const end = Math.min(start + clientPageSize, filteredPhotos.length);
        const photosToShow = filteredPhotos.slice(start, end);
        
        // Render the photos
        renderPhotos(photosToShow);
    }
    
    function renderPagination() {
        // Find or create pagination container
        let paginationContainer = document.getElementById('photo-pagination');
        if (!paginationContainer) {
            paginationContainer = document.createElement('div');
            paginationContainer.id = 'photo-pagination';
            paginationContainer.className = 'mt-3 d-flex justify-content-center';
            photoGrid.parentNode.appendChild(paginationContainer);
        } else {
            paginationContainer.innerHTML = '';
        }
        
        if (filteredPhotos.length === 0) {
            paginationContainer.style.display = 'none';
            return;
        }
        
        // Calculate total client pages based on filtered photos
        const filteredClientPages = Math.ceil(filteredPhotos.length / clientPageSize);
        
        // Create pagination nav
        const nav = document.createElement('nav');
        nav.setAttribute('aria-label', 'Photo navigation');
        
        const ul = document.createElement('ul');
        ul.className = 'pagination';
        
        // Server pagination controls
        if (totalServerPages > 1) {
            // Previous server page button
            const prevServerLi = document.createElement('li');
            prevServerLi.className = `page-item ${serverPage === 1 ? 'disabled' : ''}`;
            
            const prevServerButton = document.createElement('button');
            prevServerButton.className = 'page-link';
            prevServerButton.type = 'button';
            prevServerButton.innerHTML = '&laquo; Prev 100';
            prevServerButton.addEventListener('click', () => {
                if (serverPage > 1) {
                    loadPhotosInFolder(currentFolderId, currentFolderPath, serverPage - 1);
                }
            });
            
            prevServerLi.appendChild(prevServerButton);
            ul.appendChild(prevServerLi);
        }
        
        // Previous client page button
        const prevPageLi = document.createElement('li');
        prevPageLi.className = `page-item ${clientPage === 1 ? 'disabled' : ''}`;
        
        const prevPageButton = document.createElement('button');
        prevPageButton.className = 'page-link';
        prevPageButton.type = 'button';
        prevPageButton.innerHTML = '&lsaquo;';
        prevPageButton.addEventListener('click', () => {
            if (clientPage > 1) {
                clientPage--;
                renderPhotosPage(clientPage);
                renderPagination();
            }
        });
        
        prevPageLi.appendChild(prevPageButton);
        ul.appendChild(prevPageLi);
        
        // Page numbers
        // Determine range of pages to show (up to 5)
        let startPage = Math.max(1, clientPage - 2);
        let endPage = Math.min(filteredClientPages, startPage + 4);
        
        // Adjust if we're near the end
        if (endPage - startPage < 4 && startPage > 1) {
            startPage = Math.max(1, endPage - 4);
        }
        
        for (let i = startPage; i <= endPage; i++) {
            const pageLi = document.createElement('li');
            pageLi.className = `page-item ${i === clientPage ? 'active' : ''}`;
            
            const pageLink = document.createElement('button');
            pageLink.className = 'page-link';
            pageLink.type = 'button';
            pageLink.textContent = i;
            pageLink.addEventListener('click', () => {
                clientPage = i;
                renderPhotosPage(clientPage);
                renderPagination();
            });
            
            pageLi.appendChild(pageLink);
            ul.appendChild(pageLi);
        }
        
        // Next client page button
        const nextPageLi = document.createElement('li');
        nextPageLi.className = `page-item ${clientPage === filteredClientPages ? 'disabled' : ''}`;
        
        const nextPageButton = document.createElement('button');
        nextPageButton.className = 'page-link';
        nextPageButton.type = 'button';
        nextPageButton.innerHTML = '&rsaquo;';
        nextPageButton.addEventListener('click', () => {
            if (clientPage < filteredClientPages) {
                clientPage++;
                renderPhotosPage(clientPage);
                renderPagination();
            }
        });
        
        nextPageLi.appendChild(nextPageButton);
        ul.appendChild(nextPageLi);
        
        // Server pagination controls
        if (totalServerPages > 1) {
            // Next server page button
            const nextServerLi = document.createElement('li');
            nextServerLi.className = `page-item ${serverPage === totalServerPages ? 'disabled' : ''}`;
            
            const nextServerButton = document.createElement('button');
            nextServerButton.className = 'page-link';
            nextServerButton.type = 'button';
            nextServerButton.innerHTML = 'Next 100 &raquo;';
            nextServerButton.addEventListener('click', () => {
                if (serverPage < totalServerPages) {
                    loadPhotosInFolder(currentFolderId, currentFolderPath, serverPage + 1);
                }
            });
            
            nextServerLi.appendChild(nextServerButton);
            ul.appendChild(nextServerLi);
        }
        
        // Add pagination info text
        const infoDiv = document.createElement('div');
        infoDiv.className = 'ms-3 d-flex align-items-center small text-muted';
        
        const startCount = (serverPage - 1) * serverPageSize + (clientPage - 1) * clientPageSize + 1;
        const endCount = Math.min(
            (serverPage - 1) * serverPageSize + clientPage * clientPageSize,
            (serverPage - 1) * serverPageSize + filteredPhotos.length
        );
        
        infoDiv.textContent = `Showing ${startCount}-${endCount} of ${totalPhotos} photos`;
        
        nav.appendChild(ul);
        paginationContainer.appendChild(nav);
        paginationContainer.appendChild(infoDiv);
        paginationContainer.style.display = 'flex';
    }
});