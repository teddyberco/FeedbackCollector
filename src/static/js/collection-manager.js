// Enhanced Collection Manager with Source Configuration Support
class EnhancedCollectionManager {
    constructor() {
        this.isCollecting = false;
        this.collectionStatus = {
            status: 'ready',
            progress: 0,
            currentSource: null,
            totalSources: 0,
            completedSources: 0,
            results: {},
            errors: []
        };
        this.eventSource = null;
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.updateUI();
    }
    
    setupEventListeners() {
        // Main collection button
        const collectButton = document.getElementById('collectFeedbackBtn');
        if (collectButton) {
            collectButton.addEventListener('click', () => this.startCollection());
        }
        
        // Fabric write button
        const fabricButton = document.getElementById('writeToFabricBtn');
        if (fabricButton) {
            fabricButton.addEventListener('click', () => this.writeToFabric());
        }
        
        // Progress drawer close
        const closeDrawer = document.getElementById('closeCollectionDrawer');
        if (closeDrawer) {
            closeDrawer.addEventListener('click', () => this.hideProgress());
        }
    }
    
    async startCollection() {
        if (this.isCollecting) {
            this.showAlert('Collection already in progress', 'warning');
            return;
        }
        
        // Get configuration from source manager
        const config = window.sourceConfigManager?.getCollectionConfig();
        if (!config || Object.keys(config.sources).length === 0) {
            this.showAlert('Please enable at least one data source', 'error');
            return;
        }
        
        this.isCollecting = true;
        this.collectionStatus = {
            status: 'running',
            progress: 0,
            currentSource: null,
            totalSources: Object.keys(config.sources).length,
            completedSources: 0,
            results: {},
            errors: [],
            source_counts: {},  // Reset source counts
            current_source: 'Initializing...',
            message: 'Starting collection...'
        };
        
        // Reset all progress displays to 0
        this.resetProgressDisplays();
        
        // Also call the HTML template's reset function to ensure synchronization
        if (typeof resetCollectionDrawer === 'function') {
            resetCollectionDrawer();
            console.log('✅ Called HTML template resetCollectionDrawer()');
        }
        
        // Clear any saved progress state to prevent restoration of old counts
        localStorage.removeItem('progressState');
        console.log('✅ Cleared saved progress state to ensure clean start');
        
        // Additional aggressive reset after a short delay to override any state restoration
        setTimeout(() => {
            this.resetProgressDisplays();
            console.log('✅ Secondary reset completed after delay');
        }, 100);
        
        // Reset source counts in our internal state to ensure clean start
        this.collectionStatus.source_counts = {};
        
        // Trigger badge state manager update to show "Collecting..." status
        if (window.badgeStateManager) {
            window.badgeStateManager.setCollectionProgressState('running', 'Collecting...', 0);
            console.log(`[BADGE FIX] Updated badge state manager: running (Collecting...)`);
        }
        
        this.updateUI();
        this.showProgress();
        
        try {
            // Start server-sent events for real-time updates
            this.startProgressTracking();
            
            // Aggressive reset after starting SSE to override any initial stale data
            setTimeout(() => {
                this.resetProgressDisplays();
                console.log('✅ Post-SSE reset completed to override any stale server data');
            }, 200);
            
            // Send collection request
            const response = await fetch('/api/collect', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(config)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            this.handleCollectionComplete(result);
            
        } catch (error) {
            this.handleCollectionError(error);
        }
    }
    
    startProgressTracking() {
        this.eventSource = new EventSource('/api/collection-progress');
        
        this.eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.updateCollectionStatus(data);
        };
        
        this.eventSource.onerror = (error) => {
            console.error('Progress tracking error:', error);
            console.log('EventSource readyState:', this.eventSource?.readyState);
            
            // Don't close immediately - let the final updates process
            setTimeout(() => {
                if (this.eventSource) {
                    this.eventSource.close();
                    this.eventSource = null;
                }
            }, 1000);
        };
    }
    
    updateCollectionStatus(data) {
        console.log(`[SSE DEBUG] Received server-sent event data:`, data);
        
        // Clear and aggressive stale data guard:
        // If we're receiving data with source counts when we should be starting fresh,
        // and it's not completion data, ignore it
        if (data.source_counts && Object.keys(data.source_counts).length > 0) {
            const hasNonZeroCounts = Object.values(data.source_counts).some(count => count > 0);
            
            // If we have non-zero counts but we're at initialization, it's likely stale
            if (hasNonZeroCounts && 
                data.current_source === 'Initializing' && 
                data.status === 'running') {
                console.log(`[SSE GUARD] Blocking stale initialization data with counts:`, data.source_counts);
                return;
            }
            
            // Also block if our local state shows we're at 0 progress but we get old counts
            if (hasNonZeroCounts && 
                this.collectionStatus.progress === 0 && 
                data.current_source !== 'Completed' && 
                data.status !== 'completed') {
                console.log(`[SSE GUARD] Blocking stale data at local progress 0:`, data.source_counts);
                return;
            }
        }
        
        // Log specific fabricCommunity source_counts
        if (data.source_counts && data.source_counts.fabricCommunity !== undefined) {
            console.log(`[SSE FABRIC DEBUG] Received fabricCommunity count: ${data.source_counts.fabricCommunity}`);
        }
        
        this.collectionStatus = { ...this.collectionStatus, ...data };
        
        // Log the merged collection status
        console.log(`[SSE DEBUG] Updated collectionStatus.source_counts:`, this.collectionStatus.source_counts);
        
        this.updateProgressUI();
        
        // Trigger badge state manager update on status changes
        if (window.badgeStateManager) {
            window.badgeStateManager.syncCollectionProgressState();
        }
        
        // Check if collection is complete and handle accordingly
        if (data.status === 'completed') {
            console.log(`[COMPLETION] Collection completed, setting status and current_source`);
            this.collectionStatus.progress = 100;
            this.collectionStatus.message = 'Collection completed successfully';
            this.collectionStatus.current_source = 'Completed';
            console.log(`[COMPLETION] Updated collectionStatus:`, this.collectionStatus);
            this.updateProgressUI();
            
            // Close event source after a short delay to ensure final update is processed
            setTimeout(() => {
                if (this.eventSource) {
                    this.eventSource.close();
                    this.eventSource = null;
                }
            }, 500);
        } else if (data.status === 'error') {
            this.collectionStatus.progress = 0;
            this.collectionStatus.message = data.error_message || 'Collection failed';
            this.updateProgressUI();
            
            // Close event source on error
            if (this.eventSource) {
                this.eventSource.close();
                this.eventSource = null;
            }
        }
    }
    
    handleCollectionComplete(result) {
        this.isCollecting = false;
        
        // Update source counts from final results
        this.collectionStatus.source_counts = this.collectionStatus.source_counts || {};
        Object.entries(result).forEach(([source, data]) => {
            if (source !== 'total' && source !== 'csv_filename' && typeof data === 'object' && data.count !== undefined) {
                this.collectionStatus.source_counts[source] = data.count;
            }
        });
        
        // Don't close EventSource here - let updateCollectionStatus handle it
        // when it receives the completion event from the server
        
        // Set a fallback timeout to ensure UI updates if server-sent events fail
        setTimeout(() => {
            if (this.eventSource) {
                this.collectionStatus.status = 'completed';
                this.collectionStatus.progress = 100;
                this.collectionStatus.message = 'Collection completed successfully';
                this.collectionStatus.current_source = 'Completed';
                this.updateProgressUI();
                this.eventSource.close();
                this.eventSource = null;
            }
        }, 2000);
        
        // CRITICAL FIX: Ensure all source counts get updated with correct values
        // Force update source counts with final results to ensure UI shows correct numbers
        this.collectionStatus.source_counts = this.collectionStatus.source_counts || {};
        Object.entries(result).forEach(([source, data]) => {
            if (typeof data === 'object' && data.count !== undefined) {
                this.collectionStatus.source_counts[source] = data.count;
                console.log(`[FINAL UPDATE] ${source}: ${data.count} items`);
            }
        });
        
        // Force update the progress UI to reflect final counts
        this.updateProgressUI();
        
        // LEGACY FIX: Direct DOM update for fabricCount as additional safety
        const fabricCountElement = document.getElementById('fabricCount');
        if (fabricCountElement && result.fabricCommunity) {
            fabricCountElement.textContent = result.fabricCommunity.count || 0;
            console.log(`[FABRIC FIX] Updated fabricCount DOM directly to: ${result.fabricCommunity.count}`);
        }
        
        this.updateUI();
        this.showCollectionResults(result);
        
        // Update source info with collection results
        this.updateSourceInfo(result);
        
        // Trigger badge state manager update on completion
        if (window.badgeStateManager) {
            const totalItems = result.total || 0;
            window.badgeStateManager.setCollectionProgressState('completed', 'Completed', totalItems);
            console.log(`[BADGE FIX] Updated badge state manager: completed with ${totalItems} items`);
        }
    }
    
    handleCollectionError(error) {
        this.isCollecting = false;
        this.collectionStatus.status = 'error';
        this.collectionStatus.errors.push(error.message);
        
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        
        // Update badge state manager with error status
        if (window.badgeStateManager) {
            window.badgeStateManager.setCollectionProgressState('error', 'Error', 0);
            console.log(`[BADGE FIX] Updated badge state manager: error`);
        }
        
        this.updateUI();
        this.showAlert(`Collection failed: ${error.message}`, 'error');
    }
    
    updateUI() {
        const collectButton = document.getElementById('collectFeedbackBtn');
        const progressBadge = document.getElementById('progressBadge');
        
        if (collectButton) {
            collectButton.disabled = this.isCollecting;
            collectButton.innerHTML = this.isCollecting ? 
                `<span class="fluent-progress-ring"></span> Collecting...` : 
                `<i class="bi bi-search"></i> Collect Feedback Now`;
        }
        
        // Only update progress badge during active collection
        // After completion, let the badge state manager handle it
        if (progressBadge && this.isCollecting) {
            progressBadge.textContent = this.getStatusText();
            progressBadge.className = `fluent-badge ${this.getStatusClass()}`;
        }
    }
    
    updateProgressUI() {
        console.log(`[DOM UPDATE] updateProgressUI called with collectionStatus:`, this.collectionStatus);
        
        // Update progress bar
        const progressBar = document.getElementById('collectionProgressBar');
        const progressPercentage = document.getElementById('collectionProgressPercentage');
        
        if (progressBar) {
            progressBar.style.width = `${this.collectionStatus.progress}%`;
            console.log(`[DOM UPDATE] Updated progress bar width to ${this.collectionStatus.progress}%`);
        }
        
        if (progressPercentage) {
            progressPercentage.textContent = `${Math.round(this.collectionStatus.progress)}%`;
            console.log(`[DOM UPDATE] Updated progress percentage to ${Math.round(this.collectionStatus.progress)}%`);
        }
        
        // Update current source
        const currentSource = document.getElementById('collectionSourceText');
        const spinner = document.getElementById('collectionSpinner');
        
        if (currentSource) {
            const newText = this.collectionStatus.current_source || this.collectionStatus.currentSource || 'Initializing...';
            currentSource.textContent = newText;
            console.log(`[DOM UPDATE] Updated current source text to: "${newText}" (was: "${currentSource.textContent}", status: ${this.collectionStatus.status})`);
        } else {
            console.log(`[DOM UPDATE] collectionSourceText element not found!`);
        }
        
        if (spinner) {
            const shouldShow = (this.collectionStatus.status === 'running');
            const newDisplay = shouldShow ? 'block' : 'none';
            spinner.style.display = newDisplay;
            console.log(`[DOM UPDATE] Updated spinner display to: ${newDisplay} (status: ${this.collectionStatus.status}, shouldShow: ${shouldShow})`);
        } else {
            console.log(`[DOM UPDATE] collectionSpinner element not found!`);
        }
        
        // Update progress status message
        const progressStatus = document.getElementById('collectionProgressStatus');
        if (progressStatus) {
            progressStatus.textContent = this.collectionStatus.message || 'Initializing...';
            console.log(`[DOM UPDATE] Updated progress status to: "${this.collectionStatus.message || 'Initializing...'}"`);
        }
        
        // Update source-specific progress
        this.updateSourceProgress();
    }
    
    resetProgressDisplays() {
        console.log('[RESET] Starting resetProgressDisplays()');
        
        // Reset all source counts to 0 when starting a new collection
        const countElements = {
            'reddit': 'redditCount',
            'github': 'githubCount',
            'fabricCommunity': 'fabricCount',
            'fabric': 'fabricCount',
            'ado': 'adoCount'
        };
        
        const progressElements = {
            'reddit': 'redditProgress',
            'github': 'githubProgress',
            'fabricCommunity': 'fabricProgress',
            'fabric': 'fabricProgress',
            'ado': 'adoProgress'
        };
        
        // Reset counts
        Object.entries(countElements).forEach(([source, elementId]) => {
            const element = document.getElementById(elementId);
            if (element) {
                const oldValue = element.textContent;
                element.textContent = '0';
                console.log(`[RESET] ${source}Count: ${oldValue} → 0`);
            } else {
                console.log(`[RESET] ${elementId} element not found`);
            }
        });
        
        // Reset progress bars
        Object.entries(progressElements).forEach(([source, elementId]) => {
            const element = document.getElementById(elementId);
            if (element) {
                const oldWidth = element.style.width;
                element.style.width = '0%';
                console.log(`[RESET] ${source}Progress: ${oldWidth} → 0%`);
            } else {
                console.log(`[RESET] ${elementId} element not found`);
            }
        });
        
        // Reset overall progress
        const progressBar = document.getElementById('collectionProgressBar');
        const progressPercentage = document.getElementById('collectionProgressPercentage');
        const currentSource = document.getElementById('collectionSourceText');
        const progressStatus = document.getElementById('collectionProgressStatus');
        
        if (progressBar) {
            progressBar.style.width = '0%';
            console.log(`[RESET] collectionProgressBar: → 0%`);
        }
        if (progressPercentage) {
            progressPercentage.textContent = '0%';
            console.log(`[RESET] collectionProgressPercentage: → 0%`);
        }
        if (currentSource) {
            currentSource.textContent = 'Initializing...';
            console.log(`[RESET] collectionSourceText: → Initializing...`);
        }
        if (progressStatus) {
            progressStatus.textContent = 'Starting collection...';
            console.log(`[RESET] collectionProgressStatus: → Starting collection...`);
        }
        
        // Force a DOM update by triggering a reflow
        if (progressBar) {
            progressBar.offsetHeight; // Force reflow
        }
        
        console.log('✅ Reset all progress displays to 0 - DOM reflow forced');
    }
    
    updateSourceProgress() {
        console.log(`[DEBUG] updateSourceProgress called, source_counts:`, this.collectionStatus.source_counts);
        
        const sourceMap = {
            'reddit': 'redditProgress',
            'github': 'githubProgress',
            'fabricCommunity': 'fabricProgress',
            'fabric': 'fabricProgress',  // Handle both naming conventions
            'ado': 'adoProgress'
        };
        
        const countMap = {
            'reddit': 'redditCount',
            'github': 'githubCount',
            'fabricCommunity': 'fabricCount',
            'fabric': 'fabricCount',  // Handle both naming conventions
            'ado': 'adoCount'
        };
        
        // If collection is completed, set all progress bars to 100%
        if (this.collectionStatus.status === 'completed' || this.collectionStatus.current_source === 'Completed') {
            console.log(`[COMPLETION] Setting all progress bars to 100% on completion`);
            
            Object.entries(sourceMap).forEach(([source, elementId]) => {
                const element = document.getElementById(elementId);
                const countElement = document.getElementById(countMap[source]);
                
                if (element) {
                    element.style.width = '100%';
                    console.log(`[COMPLETION] Set ${source} progress to 100%`);
                }
                
                if (countElement && this.collectionStatus.source_counts && this.collectionStatus.source_counts[source] !== undefined) {
                    countElement.textContent = this.collectionStatus.source_counts[source];
                    console.log(`[COMPLETION] Set ${source} count to: ${this.collectionStatus.source_counts[source]}`);
                }
            });
            
            return; // Exit early since we've handled completion
        }
        
        // Special handling for fabricCommunity to ensure it updates
        if (this.collectionStatus.source_counts && this.collectionStatus.source_counts.fabricCommunity !== undefined) {
            const fabricElement = document.getElementById('fabricCount');
            if (fabricElement) {
                fabricElement.textContent = this.collectionStatus.source_counts.fabricCommunity;
                console.log(`[FABRIC FIX] Direct update fabricCount to: ${this.collectionStatus.source_counts.fabricCommunity}`);
            }
        }
        
        // Update all sources
        Object.entries(sourceMap).forEach(([source, elementId]) => {
            const element = document.getElementById(elementId);
            const countElement = document.getElementById(countMap[source]);
            
            if (element) {
                let progress = 0;
                let count = 0;
                
                // Check if this source has counts from server-sent events
                if (this.collectionStatus.source_counts && this.collectionStatus.source_counts[source] !== undefined) {
                    count = this.collectionStatus.source_counts[source];
                    progress = 100; // If we have a count, the source is complete
                    
                    if (source === 'fabricCommunity' || source === 'fabric') {
                        console.log(`[DEBUG] ${source} - Found in source_counts: ${count}`);
                    }
                }
                // Check if this source is in the results (fallback)
                else if (this.collectionStatus.results && this.collectionStatus.results[source]) {
                    const result = this.collectionStatus.results[source];
                    progress = result.completed ? 100 : (result.progress || 0);
                    count = result.count || 0;
                    
                    if (source === 'fabricCommunity' || source === 'fabric') {
                        console.log(`[DEBUG] ${source} - Found in results: ${count}`);
                    }
                }
                
                // Check if this source is in the completed sources
                if (this.collectionStatus.sources_completed && 
                    this.collectionStatus.sources_completed.includes(this.getSourceDisplayName(source))) {
                    progress = 100;
                }
                
                // Update progress bar
                element.style.width = `${progress}%`;
                
                // Update count element
                if (countElement) {
                    const oldValue = countElement.textContent;
                    countElement.textContent = count;
                    
                    if (source === 'fabricCommunity' || source === 'fabric') {
                        console.log(`[DEBUG] ${source} - Updated DOM: ${oldValue} → ${count} (element: ${countMap[source]})`);
                    }
                } else {
                    // Log missing count elements for debugging
                    console.warn(`Count element ${countMap[source]} not found for source: ${source}`);
                }
            } else {
                // Log missing progress elements for debugging
                console.warn(`Progress element ${elementId} not found for source: ${source}`);
            }
        });
        
        // Additional safety check: Force update fabricCount if it exists in source_counts
        if (this.collectionStatus.source_counts && this.collectionStatus.source_counts.fabricCommunity !== undefined) {
            const fabricCountElement = document.getElementById('fabricCount');
            if (fabricCountElement) {
                const expectedValue = this.collectionStatus.source_counts.fabricCommunity;
                const currentValue = fabricCountElement.textContent;
                
                if (currentValue !== expectedValue.toString()) {
                    fabricCountElement.textContent = expectedValue;
                    console.log(`[FABRIC FORCE UPDATE] fabricCount was ${currentValue}, forced to ${expectedValue}`);
                }
            }
        }
    }
    
    updateSourceInfo(results) {
        // Update the "last collected" info in source cards
        Object.entries(results).forEach(([source, data]) => {
            const sourceCard = document.querySelector(`[data-source="${source}"]`);
            if (sourceCard) {
                const infoElement = sourceCard.querySelector('.source-info');
                if (infoElement) {
                    const now = new Date().toLocaleString();
                    const count = data.count || 0;
                    infoElement.innerHTML = `
                        <span>Last collected: ${now}</span>
                        <span>Items found: ${count}</span>
                    `;
                }
            }
        });
    }
    
    showProgress() {
        const drawerElement = document.getElementById('collectionProgressDrawer');
        if (drawerElement) {
            // Use Bootstrap API if available
            if (typeof bootstrap !== 'undefined' && bootstrap.Offcanvas) {
                const bsOffcanvas = bootstrap.Offcanvas.getInstance(drawerElement) || new bootstrap.Offcanvas(drawerElement);
                bsOffcanvas.show();
            } else {
                // Fallback to manual class manipulation
                drawerElement.style.display = 'block';
                drawerElement.classList.add('show');
            }
        }
    }
    
    hideProgress() {
        const drawerElement = document.getElementById('collectionProgressDrawer');
        if (drawerElement) {
            // Use Bootstrap API if available
            if (typeof bootstrap !== 'undefined' && bootstrap.Offcanvas) {
                const bsOffcanvas = bootstrap.Offcanvas.getInstance(drawerElement);
                if (bsOffcanvas) {
                    bsOffcanvas.hide();
                }
            } else {
                // Fallback to manual class manipulation
                drawerElement.classList.remove('show');
                setTimeout(() => {
                    drawerElement.style.display = 'none';
                }, 300);
            }
        }
    }
    
    showCollectionResults(results) {
        const resultsDiv = document.getElementById('results');
        if (!resultsDiv) return;
        
        let html = '<div class="fluent-alert fluent-alert-success">';
        html += '<i class="bi bi-check-circle"></i>';
        html += '<div>';
        html += '<strong>Collection completed successfully!</strong><br>';
        
        let totalItems = 0;
        Object.entries(results).forEach(([source, data]) => {
            if (source === 'total' || source === 'csv_filename') return; // Skip total and filename
            
            const count = (typeof data === 'object' && data.count !== undefined) ? data.count : (typeof data === 'number' ? data : 0);
            totalItems += count;
            html += `${this.getSourceDisplayName(source)}: ${count} items<br>`;
        });
        
        html += `<strong>Total: ${totalItems} items</strong>`;
        html += '</div></div>';
        
        // Add download link
        if (results.csv_filename) {
            html += `<div class="mt-3">
                <a href="/data/${results.csv_filename}" class="fluent-button fluent-button-secondary" download>
                    <i class="bi bi-download"></i> Download CSV
                </a>
            </div>`;
        }
        
        resultsDiv.innerHTML = html;
    }
    
    async writeToFabric() {
        try {
            const response = await fetch('/api/write-to-fabric', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            this.showFabricResults(result);
            
        } catch (error) {
            this.showAlert(`Fabric write failed: ${error.message}`, 'error');
        }
    }
    
    showFabricResults(result) {
        const resultsDiv = document.getElementById('fabricResults');
        if (!resultsDiv) return;
        
        if (result.success) {
            resultsDiv.innerHTML = `
                <div class="fluent-alert fluent-alert-success">
                    <i class="bi bi-check-circle"></i>
                    <div>
                        <strong>Successfully written to Fabric!</strong><br>
                        Records written: ${result.records_written || 'Unknown'}<br>
                        Table: ${result.table_name || 'Unknown'}
                    </div>
                </div>
            `;
        } else {
            resultsDiv.innerHTML = `
                <div class="fluent-alert fluent-alert-error">
                    <i class="bi bi-exclamation-triangle"></i>
                    <div>
                        <strong>Failed to write to Fabric</strong><br>
                        ${result.message || 'Unknown error'}
                    </div>
                </div>
            `;
        }
    }
    
    showAlert(message, type = 'info') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `fluent-alert fluent-alert-${type}`;
        alertDiv.innerHTML = `
            <i class="bi bi-${this.getAlertIcon(type)}"></i>
            <div>${message}</div>
        `;
        
        // Insert at the top of the main container
        // Try .app-main first (new layout), then .fluent-container (legacy), then body
        const container = document.querySelector('.app-main') || document.querySelector('.fluent-container') || document.body;
        
        if (container) {
            // If it's app-main, insert before the first child (usually page-header)
            container.insertBefore(alertDiv, container.firstChild);
            
            // Auto-remove after 5 seconds
            setTimeout(() => {
                alertDiv.remove();
            }, 5000);
        }
    }
    
    getAlertIcon(type) {
        const icons = {
            'info': 'info-circle',
            'success': 'check-circle',
            'warning': 'exclamation-triangle',
            'error': 'exclamation-triangle'
        };
        return icons[type] || 'info-circle';
    }
    
    getStatusText() {
        switch (this.collectionStatus.status) {
            case 'running':
                return 'Collecting...';
            case 'completed':
                return 'Completed';
            case 'error':
                return 'Error';
            default:
                return 'Ready';
        }
    }
    
    getStatusClass() {
        switch (this.collectionStatus.status) {
            case 'running':
                return 'fluent-badge-warning';
            case 'completed':
                return 'fluent-badge-success';
            case 'error':
                return 'fluent-badge-error';
            default:
                return 'fluent-badge-secondary';
        }
    }
    
    getSourceDisplayName(source) {
        const names = {
            'reddit': 'Reddit',
            'github': 'GitHub',
            'fabricCommunity': 'Fabric Community',
            'fabric': 'Fabric Community',  // Handle both naming conventions
            'ado': 'Azure DevOps'
        };
        return names[source] || source;
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.enhancedCollectionManager = new EnhancedCollectionManager();
});

// Export for use in other scripts
window.EnhancedCollectionManager = EnhancedCollectionManager;
