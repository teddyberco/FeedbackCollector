/**
 * Modern AJAX-based Filter System
 * Eliminates page reloads and preserves state management
 */

class ModernFilterSystem {
    constructor(config = {}) {
        this.config = {
            apiEndpoint: '/api/feedback/filtered',
            containerId: 'feedback-container',
            paginationSize: 50,
            enableClientSideFiltering: false,
            preserveStateManagement: true,
            enableInfiniteScroll: true,
            debounceDelay: 300,
            ...config
        };
        
        this.activeFilters = new Map();
        this.allFeedbackData = [];
        this.filteredData = [];
        this.currentPage = 1;
        this.isLoading = false;
        this.totalCount = 0;
        this.hasMore = true;
        
        // Initialize sort and options from URL
        const urlParams = new URLSearchParams(window.location.search);
        this.currentSort = urlParams.get('sort') || 'newest';
        this.showRepeating = urlParams.get('show_repeating') === 'true';
        this.searchQuery = urlParams.get('search') || '';
        
        this.debounceTimer = null;
        
        this.init();
    }
    
    init() {
        console.log('🚀 Initializing Modern Filter System');
        
        // Initialize filter controls
        this.initializeFilterControls();
        
        // Set up URL state management
        this.initializeUrlStateManagement();
        
        // Load initial data
        this.loadInitialData();
        
        // Set up infinite scroll (optional)
        if (this.config.enableInfiniteScroll) {
            this.initializeInfiniteScroll();
        }
        
        // Initialize active filter display
        this.updateActiveFiltersDisplay();
        
        // Ensure all filter button texts are correct on initialization
        this.updateAllFilterButtonTexts();
        
        // Initialize status display
        this.updateStatusDisplay();
        
        console.log('✅ Modern Filter System initialized');
    }
    
    initializeFilterControls() {
        // Replace Apply Filters button with modern handling
        const applyBtn = document.querySelector('button[onclick="applyMultiSelectFilters()"]');
        if (applyBtn) {
            applyBtn.onclick = null;
            applyBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.applyAllFilters();
            });
        }
        
        // Handle individual filter checkboxes for real-time filtering
        document.querySelectorAll('input[data-filter]').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                if (this.config.enableRealTimeFiltering) {
                    this.handleFilterChange(e.target);
                }
            });
        });
        
        // Handle "All" checkboxes
        document.querySelectorAll('input[id$="_all"]').forEach(allCheckbox => {
            allCheckbox.addEventListener('change', (e) => {
                this.handleAllCheckboxChange(e.target);
            });
        });
        
        // Add search functionality if search input exists
        const searchInput = document.querySelector('input[type="search"], input[placeholder*="search" i]');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.handleSearchInput(e.target.value);
            });
        }
        
        // Handle sort buttons
        document.querySelectorAll('a[href*="sort="]').forEach(sortLink => {
            sortLink.addEventListener('click', (e) => {
                e.preventDefault();
                const url = new URL(sortLink.href);
                const sortValue = url.searchParams.get('sort');
                this.applySortFilter(sortValue);
            });
        });
    }
    
    initializeUrlStateManagement() {
        // Parse current URL parameters into active filters
        const urlParams = new URLSearchParams(window.location.search);
        
        const filterTypes = ['source', 'audience', 'priority', 'state', 'domain', 'sentiment', 'enhanced_category'];
        filterTypes.forEach(filterType => {
            const value = urlParams.get(filterType);
            if (value && value !== 'All') {
                if (value.includes(',')) {
                    this.activeFilters.set(filterType, value.split(','));
                } else {
                    this.activeFilters.set(filterType, [value]);
                }
            }
        });
        
        // Handle other parameters
        if (urlParams.get('search')) {
            this.activeFilters.set('search', urlParams.get('search'));
        }
        if (urlParams.get('sort')) {
            this.activeFilters.set('sort', urlParams.get('sort'));
        }
        if (urlParams.get('show_repeating') === 'true') {
            this.activeFilters.set('show_repeating', true);
        }
        if (urlParams.get('show_only_stored') === 'true') {
            this.activeFilters.set('show_only_stored', true);
        }
        
        // Update UI to reflect the filters from URL parameters
        this.syncUIWithActiveFilters();
        
        // Set up browser back/forward handling
        window.addEventListener('popstate', (event) => {
            if (event.state && event.state.filters) {
                this.activeFilters = new Map(Object.entries(event.state.filters));
                this.applyFiltersWithoutUrlUpdate();
            }
        });
    }
    
    async loadInitialData() {
        // If we have URL parameters, load filtered data
        if (this.activeFilters.size > 0) {
            await this.fetchFilteredData();
        } else {
            // Load all data initially
            await this.fetchFilteredData();
        }
    }
    
    applyAllFilters() {
        console.log('🔧 Applying all filters via AJAX');
        
        // Clear current filters
        this.activeFilters.clear();
        
        // Collect all active filters from UI
        const filterTypes = ['source', 'audience', 'priority', 'state', 'domain', 'sentiment', 'enhanced_category'];
        
        filterTypes.forEach(filterType => {
            const allCheckbox = document.getElementById(filterType + '_all');
            
            if (!allCheckbox || !allCheckbox.checked) {
                const selected = [];
                const checkboxes = document.querySelectorAll(`input[data-filter="${filterType}"]:checked`);
                checkboxes.forEach(cb => selected.push(cb.value));
                
                if (selected.length > 0) {
                    this.activeFilters.set(filterType, selected);
                }
            }
        });
        
        // Immediately update active filters display and status
        this.updateActiveFiltersDisplay();
        this.updateStatusDisplay();
        
        // Reset pagination
        this.currentPage = 1;
        
        // Apply filters
        this.fetchFilteredData();
    }
    
    handleFilterChange(checkbox) {
        const filterType = checkbox.dataset.filter;
        const value = checkbox.value;
        
        if (checkbox.checked) {
            // Add to active filters
            if (!this.activeFilters.has(filterType)) {
                this.activeFilters.set(filterType, []);
            }
            const current = this.activeFilters.get(filterType);
            if (!current.includes(value)) {
                current.push(value);
            }
        } else {
            // Remove from active filters
            if (this.activeFilters.has(filterType)) {
                const current = this.activeFilters.get(filterType);
                const index = current.indexOf(value);
                if (index > -1) {
                    current.splice(index, 1);
                }
                if (current.length === 0) {
                    this.activeFilters.delete(filterType);
                }
            }
        }
        
        // Update filter button text
        this.updateFilterButtonText(filterType);
        
        // Debounced apply
        this.debouncedApplyFilters();
    }
    
    handleAllCheckboxChange(allCheckbox) {
        const filterType = allCheckbox.id.replace('_all', '');
        const filterCheckboxes = document.querySelectorAll(`input[data-filter="${filterType}"]`);
        
        if (allCheckbox.checked) {
            // Uncheck all specific filters
            filterCheckboxes.forEach(cb => cb.checked = false);
            // Remove this filter type from active filters
            this.activeFilters.delete(filterType);
        }
        
        // Update filter button text
        this.updateFilterButtonText(filterType);
        
        this.debouncedApplyFilters();
    }
    
    handleSearchInput(searchValue) {
        if (searchValue.trim()) {
            this.activeFilters.set('search', searchValue.trim());
        } else {
            this.activeFilters.delete('search');
        }
        
        // Immediately update status display for better user feedback
        this.updateStatusDisplay();
        
        this.debouncedApplyFilters();
    }
    
    applySortFilter(sortValue) {
        this.activeFilters.set('sort', sortValue);
        this.currentPage = 1;
        this.fetchFilteredData();
    }
    
    /**
     * Public method to apply current filters
     * This is called by the legacy filter UI elements
     */
    applyFilters() {
        console.log('🔧 MODERN FILTER: Applying filters via public method');
        this.readFiltersFromUI();
        this.currentPage = 1;
        this.fetchFilteredData();
    }
    
    /**
     * Read current filter state from UI checkboxes
     */
    readFiltersFromUI() {
        console.log('🔧 MODERN FILTER: Reading filters from UI');
        console.log('🔧 MODERN FILTER: Active filters before clearing:', Array.from(this.activeFilters.entries()));
        
        // Clear current filters
        this.activeFilters.clear();
        
        // Read from checkboxes (without looking for "All" checkboxes)
        const filterTypes = ['audience', 'priority', 'state', 'source', 'domain', 'sentiment', 'enhanced_category'];
        
        filterTypes.forEach(filterType => {
            const selected = [];
            const checkboxes = document.querySelectorAll(`input[data-filter="${filterType}"]:checked`);
            console.log(`🔧 MODERN FILTER: Found ${checkboxes.length} checked checkboxes for ${filterType}`);
            
            checkboxes.forEach(cb => {
                selected.push(cb.value);
                console.log(`🔧 MODERN FILTER: - ${filterType}: ${cb.value} (checked: ${cb.checked})`);
            });
            
            if (selected.length > 0) {
                this.activeFilters.set(filterType, selected);
                console.log(`🔧 MODERN FILTER: ${filterType} = ${selected}`);
            } else {
                // Explicitly remove filter type if no checkboxes are selected
                this.activeFilters.delete(filterType);
                console.log(`🔧 MODERN FILTER: ${filterType} = (cleared)`);
            }
        });
        
        // Read search input
        const searchInput = document.getElementById('searchInput');
        if (searchInput && searchInput.value.trim()) {
            this.activeFilters.set('search', searchInput.value.trim());
            console.log(`🔧 MODERN FILTER: search = ${searchInput.value.trim()}`);
        } else {
            this.activeFilters.delete('search');
            console.log(`🔧 MODERN FILTER: search = (cleared)`);
        }
        
        console.log('🔧 MODERN FILTER: Final active filters after UI read:', Array.from(this.activeFilters.entries()));
        
        // Update active filter tags display
        this.updateActiveFilterTags();
        
        // Update all filter button texts
        this.updateAllFilterButtonTexts();
        
        // Update status display immediately after reading filters
        this.updateStatusDisplay();
    }
    
    debouncedApplyFilters() {
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => {
            this.currentPage = 1;
            this.fetchFilteredData();
        }, this.config.debounceDelay);
    }
    
    async fetchFilteredData() {
        if (this.isLoading) return;
        
        this.isLoading = true;
        this.showLoadingState();
        
        try {
            const params = new URLSearchParams();
            
            // Add active filters to params
            this.activeFilters.forEach((value, key) => {
                if (Array.isArray(value)) {
                    params.set(key, value.join(','));
                } else {
                    params.set(key, value);
                }
            });
            
            // Add pagination
            params.set('page', this.currentPage.toString());
            params.set('per_page', this.config.paginationSize.toString());
            
            // Add sort option
            if (this.currentSort) {
                params.set('sort', this.currentSort);
            }
            
            // Add other options
            if (this.showRepeating !== undefined) {
                params.set('show_repeating', this.showRepeating.toString());
            }
            
            // Add search query if exists
            if (this.searchQuery) {
                params.set('search', this.searchQuery);
            }
            
            // Preserve Fabric connection state
            if (window.fabricConnected || window.stateManagementEnabled) {
                params.set('fabric_connected', 'true');
                console.log('🔧 AJAX: Preserving Fabric connection state');
            }
            
            console.log('🔄 Fetching filtered data:', params.toString());
            
            const response = await fetch(`${this.config.apiEndpoint}?${params.toString()}`);
            const data = await response.json();
            
            if (data.success) {
                this.filteredData = data.feedback;
                this.totalCount = data.total_count;
                this.hasMore = data.has_more;
                this.lastResponse = data;  // Store the full response for state data access
                
                this.renderFeedbackCards();
                this.updateResultsCount();
                this.updateUrl();
                this.updateActiveFiltersDisplay();
                
                // CRITICAL: Preserve state management after AJAX load
                this.preserveStateManagement();
                
                console.log(`✅ Loaded ${data.feedback.length} items (${data.total_count} total)`);
                if (data.fabric_state_data && Object.keys(data.fabric_state_data).length > 0) {
                    console.log(`🎯 Included ${Object.keys(data.fabric_state_data).length} state records`);
                }
            } else {
                this.showError(data.message || 'Failed to load filtered data');
            }
        } catch (error) {
            this.showError('Failed to load filtered data');
            console.error('Filter error:', error);
        } finally {
            this.isLoading = false;
            this.hideLoadingState();
            
            // Ensure filter button texts are up to date AFTER everything else is complete
            // Use a small delay to ensure all DOM operations are finished
            setTimeout(() => {
                this.updateAllFilterButtonTexts();
                // Also ensure status display is updated in case of timing issues
                this.updateStatusDisplay();
                console.log('🔧 FILTER BUTTON: Updated all filter button texts and status display after fetch completion');
            }, 50);
        }
    }
    
    applyFiltersWithoutUrlUpdate() {
        // Used for browser back/forward navigation
        this.currentPage = 1;
        this.fetchFilteredDataWithoutUrlUpdate();
    }
    
    async fetchFilteredDataWithoutUrlUpdate() {
        // Same as fetchFilteredData but doesn't update URL
        // Implementation similar to fetchFilteredData...
        await this.fetchFilteredData();
    }
    
    renderFeedbackCards() {
        const container = document.getElementById(this.config.containerId);
        if (!container) {
            console.error('Feedback container not found:', this.config.containerId);
            return;
        }
        
        if (this.currentPage === 1) {
            // Clear container and create proper grid structure for new results
            container.innerHTML = '<div class="row row-cols-1 row-cols-md-2 row-cols-lg-3 g-4"></div>';
        }
        
        // Get the grid container
        const gridContainer = container.querySelector('.row') || container;
        
        // Get current state data if available
        const fabricStateData = this.lastResponse?.fabric_state_data || window.fabricStateData || {};
        
        // Render new cards
        this.filteredData.forEach(item => {
            const cardHtml = this.generateFeedbackCardHtml(item, fabricStateData);
            gridContainer.insertAdjacentHTML('beforeend', cardHtml);
        });
        
        // Store state data globally for other functions to access
        if (this.lastResponse?.fabric_state_data) {
            window.fabricStateData = this.lastResponse.fabric_state_data;
            console.log('🔄 Updated global fabric state data with', Object.keys(this.lastResponse.fabric_state_data).length, 'records');
        }
        
        // Reapply state management to new cards
        this.reapplyStateManagement();
    }
    
    generateFeedbackCardHtml(item, fabricStateData = {}) {
        // Generate the HTML for a feedback card that matches the template structure
        const feedbackId = item.Feedback_ID || 'unknown';
        
        // Use state from Fabric if available, otherwise use item's state, default to NEW
        let state = item.State || 'NEW';
        if (fabricStateData[feedbackId] && fabricStateData[feedbackId].state) {
            state = fabricStateData[feedbackId].state;
            console.log(`🎯 Using Fabric state for ${feedbackId}: ${state}`);
        }
        
        const stateClass = state.toLowerCase();
        const stateBadge = this.getStateBadge(state);
        const domainBadge = this.getDomainBadge(item.Primary_Domain);
        const sentimentBadge = this.getSentimentBadge(item.Sentiment);
        const audienceBadge = this.getAudienceBadge(item.Audience);
        const priorityBadge = this.getPriorityBadge(item.Priority);
        
        // Get the proper title - use Feedback_Gist, fallback to Title, then fallback to source info
        let cardTitle = 'Untitled';
        if (item.Feedback_Gist && item.Feedback_Gist.trim() && 
            item.Feedback_Gist.toLowerCase() !== 'no content' && 
            item.Feedback_Gist.toLowerCase() !== 'summary unavailable') {
            cardTitle = item.Feedback_Gist;
        } else if (item.Title && item.Title.trim()) {
            cardTitle = item.Title;
        } else if (item.Sources) {
            cardTitle = `Feedback from ${item.Sources}`;
        }
        
        return `
            <div class="col">
                <div class="card h-100 shadow-sm feedback-card" id="card-${feedbackId}">
                    <div class="card-body d-flex flex-column">
                        <h5 class="card-title">
                            ${this.escapeHtml(cardTitle)}
                        </h5>
                        <h6 class="card-subtitle mb-2 text-muted">
                            ${item.Sources || item.Source || 'Unknown Source'}
                            ${item.Created && item.Created.trim() ? ` - ${item.Created.split('T')[0]}` : ''}
                        </h6>
                        
                        <!-- Enhanced Categorization Info -->
                        ${(item.Audience || item.Enhanced_Category || item.Priority) ? `
                        <div class="category-info">
                            ${audienceBadge}
                            ${priorityBadge}
                        </div>
                        ` : ''}
                        
                        <!-- State Management Section -->
                        <div class="category-info">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <span class="state-badge state-${stateClass}"
                                          data-feedback-id="${feedbackId}"
                                          data-current-state="${state}"
                                          onclick="toggleStateDropdown(this, event)"
                                          title="Click to change state">
                                        ${stateBadge}
                                        <div class="state-dropdown" data-feedback-id="${feedbackId}">
                                            <div class="state-option" data-state="NEW">🆕 New</div>
                                            <div class="state-option" data-state="TRIAGED">🔍 Triaged</div>
                                            <div class="state-option" data-state="CLOSED">✅ Closed</div>
                                            <div class="state-option" data-state="IRRELEVANT">❌ Irrelevant</div>
                                        </div>
                                    </span>
                                    
                                    ${(fabricStateData[feedbackId]?.last_updated || item.Last_Updated) && (fabricStateData[feedbackId]?.last_updated || item.Last_Updated).trim() ? `
                                    <small class="text-muted ms-2">
                                        Updated: ${(fabricStateData[feedbackId]?.last_updated || item.Last_Updated).split('T')[0]}
                                        ${(fabricStateData[feedbackId]?.updated_by || item.Updated_By) && (fabricStateData[feedbackId]?.updated_by || item.Updated_By).trim() ? ` by ${fabricStateData[feedbackId]?.updated_by || item.Updated_By}` : ''}
                                    </small>
                                    ` : ''}
                                </div>
                                
                                <!-- Actions Menu -->
                                <div class="card-actions">
                                    <button class="btn btn-sm btn-outline-secondary"
                                            data-feedback-id="${feedbackId}"
                                            onclick="toggleActionsMenu(this)"
                                            title="More actions">
                                        [...]
                                    </button>
                                    <div class="actions-menu">
                                        <a href="#" onclick="updateDomain('${feedbackId}', '${item.Primary_Domain || ''}')">Update Domain</a>
                                        <a href="#" onclick="updateNotes('${feedbackId}', '${fabricStateData[feedbackId]?.notes || item.Feedback_Notes || ''}')">
                                            ${(fabricStateData[feedbackId]?.notes || item.Feedback_Notes) && (fabricStateData[feedbackId]?.notes || item.Feedback_Notes).trim() ? 'Edit Note' : 'Add Note'}
                                        </a>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- State Notes Display -->
                        ${(fabricStateData[feedbackId]?.notes || item.Feedback_Notes) && (fabricStateData[feedbackId]?.notes || item.Feedback_Notes).trim() ? `
                        <div class="notes-display">
                            📝 ${this.escapeHtml(fabricStateData[feedbackId]?.notes || item.Feedback_Notes)}
                        </div>
                        ` : ''}
                        
                        <div class="category-info">
                            ${item.Enhanced_Category && item.Enhanced_Category.trim() ? `
                            <strong>Category:</strong> ${item.Enhanced_Category}
                            ${item.Subcategory && item.Subcategory.trim() ? ` → ${item.Subcategory}` : ''}
                            ${item.Feature_Area && item.Feature_Area.trim() ? `<br><strong>Area:</strong> ${item.Feature_Area}` : ''}
                            ` : '<strong>Category:</strong> <em>Uncategorized</em>'}
                            ${item.Categorization_Confidence ? `
                                <span class="text-muted">(${Math.round(item.Categorization_Confidence * 100)}% confidence)</span>
                            ` : ''}
                        </div>
                        
                        <!-- Domain Information -->
                        <div class="category-info">
                            <strong>Domain:</strong>
                            ${domainBadge || '<span class="domain-badge" style="background-color: #6c757d; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.75rem;">❓ Uncategorized</span>'}
                        </div>
                        
                        <p class="card-text feedback-content mb-auto">
                            ${this.escapeHtml(item.Feedback || 'No feedback content')}
                        </p>
                        
                        <div class="mt-auto pt-2">
                            ${item.Url && item.Url.trim() ? `
                                <a href="${item.Url}" class="btn btn-outline-primary btn-sm" target="_blank" rel="noopener noreferrer">View Source</a>
                            ` : ''}
                            ${item.Tag && item.Tag.trim() ? `
                                <span class="badge bg-secondary ms-2">${item.Tag}</span>
                            ` : ''}
                            ${item.Status && item.Status.trim() ? `
                                <span class="badge bg-info ms-2">${item.Status}</span>
                            ` : ''}
                            ${sentimentBadge ? `<span class="ms-2">${sentimentBadge}</span>` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    getStateBadge(state) {
        const badges = {
            'NEW': '🆕 New',
            'TRIAGED': '🔍 Triaged',
            'CLOSED': '✅ Closed',
            'IRRELEVANT': '❌ Irrelevant'
        };
        return badges[state] || '🆕 New';
    }
    
    getDomainBadge(domain) {
        if (!domain) return '';
        const domainNames = {
            'GETTING_STARTED': 'Getting Started',
            'GOVERNANCE': 'Governance',
            'USER_EXPERIENCE': 'User Experience',
            'AUTHENTICATION': 'Authentication & Security',
            'PERFORMANCE': 'Performance & Scalability',
            'INTEGRATION': 'Integration & APIs',
            'ANALYTICS': 'Analytics & Reporting'
        };
        
        const domainColors = {
            'GETTING_STARTED': '#20c997',
            'GOVERNANCE': '#6f42c1',
            'USER_EXPERIENCE': '#28a745',
            'AUTHENTICATION': '#dc3545',
            'PERFORMANCE': '#fd7e14',
            'INTEGRATION': '#17a2b8',
            'ANALYTICS': '#ffc107'
        };
        
        const displayName = domainNames[domain] || domain;
        const color = domainColors[domain] || '#6c757d';
        return `<span class="domain-badge" style="background-color: ${color}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.75rem;">${displayName}</span>`;
    }
    
    getSentimentBadge(sentiment) {
        if (!sentiment) return '';
        const sentimentData = {
            'positive': { emoji: '😊', class: 'sentiment-positive' },
            'negative': { emoji: '😞', class: 'sentiment-negative' },
            'neutral': { emoji: '😐', class: 'sentiment-neutral' }
        };
        const data = sentimentData[sentiment?.toLowerCase()] || sentimentData.neutral;
        return `<span class="badge ${data.class}">${data.emoji} ${sentiment}</span>`;
    }
    
    getAudienceBadge(audience) {
        if (!audience) return '';
        const audienceData = {
            'Developer': '🛠️ Developer',
            'Customer': '👤 Customer',
            'ISV': '🏢 ISV'
        };
        const displayText = audienceData[audience] || audience;
        return `<span class="audience-badge audience-${audience?.toLowerCase()}" 
                        onclick="updateAudience('', '${audience}')" 
                        title="Click to update audience" 
                        style="cursor: pointer;">${displayText}</span>`;
    }
    
    getPriorityBadge(priority) {
        if (!priority) return '';
        const priorityData = {
            'critical': '🔴 Critical',
            'high': '🟠 High',
            'medium': '🟡 Medium',
            'low': '⚪ Low'
        };
        const displayText = priorityData[priority?.toLowerCase()] || priority;
        return `<span class="priority-badge priority-${priority?.toLowerCase()}" title="Priority: ${priority}">${displayText}</span>`;
    }
    
    preserveStateManagement() {
        // Ensure Fabric connection state is maintained after AJAX load
        if (window.fabricConnected || window.stateManagementEnabled) {
            document.body.classList.remove('state-management-disabled');
            
            // Update sync button if it exists
            const syncBtn = document.getElementById('fabricSyncBtn');
            if (syncBtn && !syncBtn.innerHTML.includes('Connected')) {
                syncBtn.innerHTML = '<i class="bi bi-database me-1"></i>Sync with Fabric <span class="badge bg-success ms-1">Connected</span>';
            }
            
            console.log('🔧 AJAX: State management preserved after filter');
            
            // Update status display to reflect new connection state
            this.updateStatusDisplay();
        }
        
        // Reapply cached changes if they exist
        setTimeout(() => {
            if (typeof applyCachedChangesToUI === 'function') {
                applyCachedChangesToUI();
            }
            
            // Restore state data from Fabric if available
            if (window.fabricStateData && typeof updateFeedbackWithSQLData === 'function') {
                updateFeedbackWithSQLData(window.fabricStateData);
            }
        }, 100);
    }
    
    reapplyStateManagement() {
        // Ensure state dropdowns and event handlers work on new cards
        document.querySelectorAll('.state-badge').forEach(badge => {
            if (!badge.onclick) {
                badge.onclick = function(event) {
                    if (typeof toggleStateDropdown === 'function') {
                        toggleStateDropdown(this, event);
                    }
                };
            }
        });
    }
    
    updateUrl() {
        const url = new URL(window.location);
        
        // Clear existing filter params
        const filterParams = ['source', 'audience', 'priority', 'state', 'domain', 'sentiment', 'enhanced_category', 'search', 'sort'];
        filterParams.forEach(param => url.searchParams.delete(param));
        
        // Add active filters
        this.activeFilters.forEach((value, key) => {
            if (Array.isArray(value)) {
                url.searchParams.set(key, value.join(','));
            } else {
                url.searchParams.set(key, value);
            }
        });
        
        // Preserve Fabric connection
        if (window.fabricConnected || window.stateManagementEnabled) {
            url.searchParams.set('fabric_connected', 'true');
        }
        
        // Update URL without reload
        const filterState = Object.fromEntries(this.activeFilters);
        window.history.pushState({ filters: filterState }, '', url);
    }
    
    updateResultsCount() {
        // Update main results count
        const resultElement = document.querySelector('.results-count, #resultsCount');
        if (resultElement) {
            const text = this.totalCount === 1 
                ? `${this.totalCount} feedback item found`
                : `${this.totalCount} feedback items found`;
            resultElement.textContent = text;
        }
        
        // Update status display with count and connection mode
        this.updateStatusDisplay();
    }
    
    updateStatusDisplay() {
        // Find or create the status display element
        let statusElement = document.getElementById('feedbackStatusDisplay');
        if (!statusElement) {
            statusElement = document.createElement('div');
            statusElement.id = 'feedbackStatusDisplay';
            statusElement.className = 'alert alert-light border mb-3';
            
            // Insert it above the feedback container (after filter section)
            const feedbackContainer = document.getElementById('feedback-container');
            const filterSection = document.querySelector('.filter-section');
            
            if (feedbackContainer && feedbackContainer.parentNode) {
                // Insert it right before the feedback container
                feedbackContainer.parentNode.insertBefore(statusElement, feedbackContainer);
                console.log('📊 STATUS: Created status display above feedback cards');
            } else if (filterSection && filterSection.parentNode) {
                // Fallback: insert after the filter section
                filterSection.parentNode.insertBefore(statusElement, filterSection.nextSibling);
                console.log('📊 STATUS: Created status display after filter section');
            } else {
                // Final fallback: insert after the header
                const header = document.querySelector('h1');
                if (header && header.parentNode) {
                    const headerParagraph = header.nextElementSibling;
                    if (headerParagraph && headerParagraph.tagName === 'P') {
                        headerParagraph.parentNode.insertBefore(statusElement, headerParagraph.nextSibling);
                    } else {
                        header.parentNode.insertBefore(statusElement, header.nextSibling);
                    }
                    console.log('📊 STATUS: Created status display after header (fallback)');
                } else {
                    document.body.insertBefore(statusElement, document.body.firstChild);
                    console.warn('📊 STATUS: Could not find proper location, added to body');
                }
            }
        }
        
        // Determine connection mode
        const isConnected = window.fabricConnected || window.stateManagementEnabled;
        const mode = isConnected ? 'ONLINE' : 'OFFLINE';
        const modeClass = isConnected ? 'text-success' : 'text-muted';
        const modeIcon = isConnected ? '🟢' : '🔴';
        
        // Determine if filters are active (exclude non-filtering options)
        const excludedFilterKeys = ['sort', 'show_repeating', 'show_only_stored'];
        const activeFilterKeys = Array.from(this.activeFilters.keys()).filter(key => 
            !excludedFilterKeys.includes(key) && 
            this.activeFilters.get(key) && 
            (Array.isArray(this.activeFilters.get(key)) ? this.activeFilters.get(key).length > 0 : true)
        );
        const hasActiveFilters = activeFilterKeys.length > 0;
        
        console.log(`📊 STATUS UPDATE: Active filter keys: [${activeFilterKeys.join(', ')}], Has active filters: ${hasActiveFilters}`);
        
        const displayText = hasActiveFilters ? 'Displaying filtered' : 'Displaying all';
        const itemText = this.totalCount === 1 ? 'item' : 'items';
        
        statusElement.innerHTML = `
            <div class="d-flex justify-content-between align-items-center">
                <span>
                    <i class="bi bi-list-ul me-2"></i>
                    <strong>${displayText} ${this.totalCount} collected ${itemText}.</strong>
                </span>
                <span class="${modeClass}">
                    ${modeIcon} <strong>Mode: ${mode}</strong>
                    ${isConnected ? '<small class="ms-2 text-muted">(State management enabled)</small>' : '<small class="ms-2 text-muted">(Read-only mode)</small>'}
                </span>
            </div>
        `;
        
        console.log(`📊 STATUS UPDATED: ${displayText} ${this.totalCount} ${itemText} - Mode: ${mode} - Active filters: [${activeFilterKeys.join(', ')}]`);
    }
    
    updateActiveFiltersDisplay() {
        // Create or update active filters display
        let filtersContainer = document.getElementById('activeFiltersContainer');
        if (!filtersContainer) {
            filtersContainer = document.createElement('div');
            filtersContainer.id = 'activeFiltersContainer';
            filtersContainer.className = 'active-filters-container mb-3';
            
            const mainContainer = document.getElementById(this.config.containerId);
            if (mainContainer && mainContainer.parentNode) {
                mainContainer.parentNode.insertBefore(filtersContainer, mainContainer);
            }
        }
        
        if (this.activeFilters.size === 0) {
            filtersContainer.style.display = 'none';
            return;
        }
        
        filtersContainer.style.display = 'block';
        
        let html = '<div class="d-flex flex-wrap align-items-center gap-2 mb-2">';
        html += '<span class="text-muted">Active filters:</span>';
        
        this.activeFilters.forEach((value, key) => {
            if (key === 'sort' || key === 'show_repeating' || key === 'show_only_stored') return;
            
            const displayValue = Array.isArray(value) ? value.join(', ') : value;
            html += `
                <span class="badge bg-primary filter-tag" data-filter-type="${key}">
                    ${key}: ${displayValue}
                    <i class="bi bi-x ms-1" onclick="window.modernFilterSystem.removeFilter('${key}')" style="cursor: pointer;"></i>
                </span>
            `;
        });
        
        html += `
            <button class="btn btn-sm btn-outline-secondary" onclick="window.modernFilterSystem.clearAllFilters()">
                <i class="bi bi-x-circle"></i> Clear All
            </button>
        `;
        html += '</div>';
        
        filtersContainer.innerHTML = html;
    }
    
    updateFilterButtonText(filterType) {
        // Update the button text for the specific filter type
        const filterButton = document.getElementById(filterType + 'Filter');
        if (!filterButton) {
            console.log(`🔧 FILTER BUTTON: Button not found for ${filterType}`);
            return;
        }
        
        const selectedValues = this.activeFilters.get(filterType) || [];
        // The filterButton itself is the element we need to update (it IS the .btn element)
        const buttonText = filterButton;
        
        // Double-check by also looking at actual UI state
        const checkedCheckboxes = document.querySelectorAll(`input[data-filter="${filterType}"]:checked`);
        
        console.log(`🔧 FILTER BUTTON: Updating ${filterType}`);
        console.log(`  - Active filters says: ${selectedValues.length} items`);
        console.log(`  - UI checkboxes checked: ${checkedCheckboxes.length} items`);
        
        if (buttonText) {
            let newText = '';
            
            // Use the activeFilters as the source of truth, but add validation
            const actualCount = selectedValues.length;
            
            if (actualCount > 0) {
                newText = `${actualCount} ${filterType}(s) selected`;
            } else {
                // Set default text based on filter type
                switch(filterType) {
                    case 'domain': newText = 'Select domains'; break;
                    case 'source': newText = 'Select sources'; break;
                    case 'state': newText = 'Select states'; break;
                    case 'audience': newText = 'Select audiences'; break;
                    case 'priority': newText = 'Select priorities'; break;
                    case 'sentiment': newText = 'Select sentiments'; break;
                    case 'enhanced_category': newText = 'Select categories'; break;
                    default: newText = `Select ${filterType}s`;
                }
            }
            
            const oldText = buttonText.textContent;
            buttonText.textContent = newText;
            console.log(`🔧 FILTER BUTTON: ${filterType} text changed from "${oldText}" to "${newText}"`);
            
            // Validate that the change was correct
            if (actualCount === 0 && newText.includes('selected')) {
                console.error(`🚨 FILTER BUTTON: ERROR - ${filterType} should show default text but shows "${newText}"`);
            }
        } else {
            console.log(`🔧 FILTER BUTTON: Button text element not found for ${filterType}`);
        }
    }
    
    /**
     * Update all filter button texts
     */
    updateAllFilterButtonTexts() {
        console.log('🔧 FILTER BUTTON: Updating all filter button texts');
        ['domain', 'source', 'state', 'audience', 'priority', 'sentiment', 'enhanced_category'].forEach(filterType => {
            this.updateFilterButtonText(filterType);
        });
    }
    
    /**
     * Update active filter tags display
     */
    updateActiveFilterTags() {
        // For now, just log that this was called
        // In the future, this could create/update visual filter tags
        console.log('🔧 ACTIVE FILTER TAGS: Update called for active filters:', Array.from(this.activeFilters.keys()));
        
        // Update all filter button texts to ensure consistency
        this.updateAllFilterButtonTexts();
    }
    
    /**
     * Sync UI checkboxes and button text with current active filters
     */
    syncUIWithActiveFilters() {
        console.log('🔧 SYNC UI: Syncing UI with active filters');
        
        // Update checkboxes to match active filters
        const filterTypes = ['source', 'audience', 'priority', 'state', 'domain', 'sentiment', 'enhanced_category'];
        filterTypes.forEach(filterType => {
            const activeValues = this.activeFilters.get(filterType) || [];
            
            // Check the appropriate checkboxes
            document.querySelectorAll(`input[data-filter="${filterType}"]`).forEach(checkbox => {
                checkbox.checked = activeValues.includes(checkbox.value);
            });
            
            // Update button text
            this.updateFilterButtonText(filterType);
        });
        
        // Update search input
        const searchInput = document.querySelector('input[type="search"], input[placeholder*="search" i]');
        if (searchInput && this.activeFilters.has('search')) {
            searchInput.value = this.activeFilters.get('search');
        }
    }

    removeFilter(filterType) {
        console.log(`🔧 REMOVE FILTER: Removing ${filterType} filter`);
        
        this.activeFilters.delete(filterType);
        
        // Update UI checkboxes (no longer checking "All" checkboxes since we removed them)
        document.querySelectorAll(`input[data-filter="${filterType}"]`).forEach(cb => {
            cb.checked = false;
        });
        
        // Immediately update filter button text for this specific filter
        this.updateFilterButtonText(filterType);
        
        // Immediately update active filters display and status
        this.updateActiveFiltersDisplay();
        this.updateStatusDisplay();
        
        this.currentPage = 1;
        this.fetchFilteredData();
    }
    
    clearAllFilters() {
        // Prevent multiple rapid calls
        if (this.isLoading) {
            console.log('🔧 CLEAR FILTERS: System is loading, skipping duplicate clear request');
            return;
        }
        
        console.log('🔧 CLEAR FILTERS: Clearing all filters');
        this.activeFilters.clear();
        
        // Reset all UI controls (no longer checking "All" checkboxes since we removed them)
        document.querySelectorAll('input[data-filter]').forEach(cb => cb.checked = false);
        
        // Immediately update all filter button texts to default state
        this.updateAllFilterButtonTexts();
        
        // Immediately update active filters display and status
        this.updateActiveFiltersDisplay();
        this.updateStatusDisplay();
        
        const searchInput = document.querySelector('input[type="search"], input[placeholder*="search" i]');
        if (searchInput) searchInput.value = '';
        
        this.currentPage = 1;
        this.fetchFilteredData();
    }
    
    initializeInfiniteScroll() {
        const observer = new IntersectionObserver(
            (entries) => {
                if (entries[0].isIntersecting && !this.isLoading && this.hasMore) {
                    this.loadMoreData();
                }
            },
            { threshold: 0.1 }
        );
        
        let sentinel = document.getElementById('scroll-sentinel');
        if (!sentinel) {
            sentinel = document.createElement('div');
            sentinel.id = 'scroll-sentinel';
            sentinel.className = 'text-center py-3';
            sentinel.innerHTML = `
                <div class="spinner-border spinner-border-sm" role="status"></div>
                <span class="ms-2">Loading more...</span>
            `;
            sentinel.style.display = 'none';
            
            const container = document.getElementById(this.config.containerId);
            if (container && container.parentNode) {
                container.parentNode.appendChild(sentinel);
            }
        }
        
        observer.observe(sentinel);
    }
    
    async loadMoreData() {
        if (!this.hasMore || this.isLoading) return;
        
        this.currentPage++;
        
        const sentinel = document.getElementById('scroll-sentinel');
        if (sentinel) sentinel.style.display = 'block';
        
        await this.fetchFilteredData();
        
        if (sentinel) {
            sentinel.style.display = this.hasMore ? 'none' : 'none';
        }
    }
    
    showLoadingState() {
        let loadingElement = document.getElementById('loadingState');
        if (!loadingElement) {
            loadingElement = document.createElement('div');
            loadingElement.id = 'loadingState';
            loadingElement.className = 'text-center py-4';
            loadingElement.innerHTML = `
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-2 text-muted">Applying filters...</p>
            `;
            
            const container = document.getElementById(this.config.containerId);
            if (container && container.parentNode) {
                container.parentNode.insertBefore(loadingElement, container);
            }
        }
        
        loadingElement.style.display = 'block';
        
        // Add loading class to container
        const container = document.getElementById(this.config.containerId);
        if (container) {
            container.classList.add('loading');
        }
    }
    
    hideLoadingState() {
        const loadingElement = document.getElementById('loadingState');
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
        
        // Remove loading class from container
        const container = document.getElementById(this.config.containerId);
        if (container) {
            container.classList.remove('loading');
        }
    }
    
    showError(message) {
        console.error('Filter system error:', message);
        
        // Show user-friendly error
        const container = document.getElementById(this.config.containerId);
        if (container) {
            const errorHtml = `
                <div class="alert alert-danger" role="alert">
                    <i class="bi bi-exclamation-triangle"></i>
                    <strong>Error:</strong> ${this.escapeHtml(message)}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            `;
            container.insertAdjacentHTML('afterbegin', errorHtml);
        }
    }
    
    // Utility functions
    escapeHtml(text) {
        if (!text) return '';
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, function(m) { return map[m]; });
    }
    
    formatDate(dateString) {
        if (!dateString) return 'Unknown';
        try {
            return new Date(dateString).toLocaleDateString();
        } catch {
            return dateString;
        }
    }
    
    // Sort and option update methods
    updateSort(sortBy) {
        console.log('🔄 Updating sort to:', sortBy);
        this.currentSort = sortBy;
        this.currentPage = 1; // Reset pagination
        this.fetchFilteredData();
        
        // Update button states
        document.querySelectorAll('[onclick*="updateSort"]').forEach(btn => {
            btn.classList.remove('btn-success');
            btn.classList.add('btn-outline-success');
        });
        
        const activeBtn = document.querySelector(`[onclick*="updateSort('${sortBy}')"]`);
        if (activeBtn) {
            activeBtn.classList.remove('btn-outline-success');
            activeBtn.classList.add('btn-success');
        }
    }
    
    updateRepeating(showRepeating) {
        console.log('🔄 Updating repeating requests to:', showRepeating);
        this.showRepeating = showRepeating;
        this.currentPage = 1; // Reset pagination
        this.fetchFilteredData();
        
        // Update button states
        document.querySelectorAll('[onclick*="updateRepeating"]').forEach(btn => {
            if (showRepeating) {
                btn.classList.toggle('btn-info', btn.textContent.includes('Analyze'));
                btn.classList.toggle('btn-outline-info', btn.textContent.includes('Hide'));
            } else {
                btn.classList.toggle('btn-outline-info', btn.textContent.includes('Analyze'));
                btn.classList.toggle('btn-info', btn.textContent.includes('Hide'));
            }
        });
    }
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Only initialize if we're on the feedback viewer page
    if (document.getElementById('feedback-container')) {
        console.log('🔧 Setting up Modern Filter System...');
        
        // Initialize the modern filter system
        window.modernFilterSystem = new ModernFilterSystem({
            enableRealTimeFiltering: false, // Start with manual apply
            preserveStateManagement: true,
            enableInfiniteScroll: true
        });
        
        // Override old filter functions for backward compatibility
        window.applyMultiSelectFilters = function() {
            if (window.modernFilterSystem) {
                window.modernFilterSystem.applyAllFilters();
            }
        };
        
        window.toggleFilterAll = function(filterType) {
            // This is handled by the modern system's event listeners
            console.log('🔧 toggleFilterAll called, handled by modern system');
        };
        
        console.log('✅ Modern Filter System ready');
    }
});

// Global function to update status display when connection state changes
window.updateFeedbackStatusDisplay = function() {
    if (window.modernFilterSystem) {
        window.modernFilterSystem.updateStatusDisplay();
    }
};
