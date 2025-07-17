// Source Configuration Manager
class SourceConfigManager {
    constructor() {
        this.sources = {
            reddit: {
                enabled: true,
                subreddit: 'MicrosoftFabric',
                sort: 'new',
                timeFilter: 'month',
                postTypes: ['all'],
                maxItems: 200
            },
            github: {
                enabled: true,
                owner: 'microsoft',
                repo: 'Microsoft-Fabric-workload-development-sample',
                state: 'all',
                labels: [],
                maxItems: 200
            },
            fabricCommunity: {
                enabled: true,
                maxItems: 200
            },
            ado: {
                enabled: true,
                parentWorkItem: '1319103',
                workItemTypes: ['Bug', 'Feature', 'User Story'],
                states: ['New', 'Active', 'Resolved'],
                maxItems: 200
            }
        };
        
        this.settings = {
            timeRangeMonths: 6,
            maxItemsPerSource: 200,
            respectRateLimits: true,
            keywords: [],
            duplicateDetection: true,
            languageFilter: 'all',
            sentimentThreshold: 0
        };
        
        this.init();
    }
    
    init() {
        this.loadConfiguration();
        this.setupEventListeners();
        this.renderSourceCards();
        this.renderSettings();
    }
    
    loadConfiguration() {
        // Load from localStorage
        const savedConfig = localStorage.getItem('feedbackCollectorConfig');
        if (savedConfig) {
            try {
                const config = JSON.parse(savedConfig);
                this.sources = { ...this.sources, ...config.sources };
                this.settings = { ...this.settings, ...config.settings };
                
                // Ensure numeric settings are properly converted to integers
                if (this.settings.maxItemsPerSource) {
                    this.settings.maxItemsPerSource = parseInt(this.settings.maxItemsPerSource);
                }
                if (this.settings.timeRangeMonths) {
                    this.settings.timeRangeMonths = parseInt(this.settings.timeRangeMonths);
                }
                
                // Ensure source maxItems are integers
                Object.keys(this.sources).forEach(sourceId => {
                    if (this.sources[sourceId].maxItems) {
                        this.sources[sourceId].maxItems = parseInt(this.sources[sourceId].maxItems);
                    }
                });
                
                // Sync individual source maxItems with global setting if they haven't been customized
                // Only do this if the global setting exists and sources are using default values
                if (this.settings.maxItemsPerSource) {
                    Object.keys(this.sources).forEach(sourceId => {
                        // If source maxItems is still at old default (100) or matches global setting, update it
                        if (!this.sources[sourceId].maxItems || this.sources[sourceId].maxItems === 100) {
                            this.sources[sourceId].maxItems = this.settings.maxItemsPerSource;
                        }
                    });
                }
            } catch (e) {
                console.error('Error loading configuration:', e);
            }
        }
        
        // Load keywords from server
        this.loadKeywords();
    }
    
    async loadKeywords() {
        try {
            const response = await fetch('/api/keywords');
            const keywords = await response.json();
            this.settings.keywords = keywords;
            this.renderKeywordsInSettings();
        } catch (e) {
            console.error('Error loading keywords:', e);
        }
    }
    
    saveConfiguration() {
        const config = {
            sources: this.sources,
            settings: this.settings
        };
        localStorage.setItem('feedbackCollectorConfig', JSON.stringify(config));
    }
    
    setupEventListeners() {
        // Source toggle listeners
        document.addEventListener('change', (e) => {
            if (e.target.matches('.source-toggle')) {
                this.handleSourceToggle(e.target);
            }
        });
        
        // Configuration button listeners
        document.addEventListener('click', (e) => {
            if (e.target.matches('.btn-configure') || e.target.closest('.btn-configure')) {
                this.toggleSourceConfig(e.target.closest('.source-card'));
            }
        });
        
        // Input change listeners
        document.addEventListener('input', (e) => {
            if (e.target.matches('.source-input')) {
                this.handleSourceInputChange(e.target);
            }
        });
        
        // Settings change listeners
        document.addEventListener('change', (e) => {
            if (e.target.matches('.setting-input')) {
                this.handleSettingChange(e.target);
            }
        });
    }
    
    handleSourceToggle(toggle) {
        const sourceCard = toggle.closest('.source-card');
        const sourceId = sourceCard.dataset.source;
        this.sources[sourceId].enabled = toggle.checked;
        
        // Update UI
        sourceCard.classList.toggle('disabled', !toggle.checked);
        this.updateSourceStatus(sourceId);
        this.saveConfiguration();
    }
    
    toggleSourceConfig(sourceCard) {
        const configDiv = sourceCard.querySelector('.source-config');
        const isExpanded = configDiv.classList.contains('expanded');
        
        // Close all other configs
        document.querySelectorAll('.source-config.expanded').forEach(config => {
            if (config !== configDiv) {
                config.classList.remove('expanded');
            }
        });
        
        // Toggle current config
        configDiv.classList.toggle('expanded', !isExpanded);
        
        // Update button icon
        const button = sourceCard.querySelector('.btn-configure i');
        button.className = isExpanded ? 'bi bi-gear' : 'bi bi-gear-fill';
    }
    
    handleSourceInputChange(input) {
        const sourceCard = input.closest('.source-card');
        const sourceId = sourceCard.dataset.source;
        const field = input.dataset.field;
        const value = input.type === 'checkbox' ? input.checked : input.value;
        
        // Update source configuration
        if (field.includes('.')) {
            const [parent, child] = field.split('.');
            if (!this.sources[sourceId][parent]) {
                this.sources[sourceId][parent] = {};
            }
            this.sources[sourceId][parent][child] = value;
        } else {
            this.sources[sourceId][field] = value;
        }
        
        this.updateSourceStatus(sourceId);
        this.saveConfiguration();
    }
    
    handleSettingChange(input) {
        const field = input.dataset.field;
        let value = input.type === 'checkbox' ? input.checked : input.value;
        
        // Convert numeric fields to integers
        if (field === 'maxItemsPerSource' || field === 'timeRangeMonths' || input.type === 'number') {
            value = parseInt(value);
        }
        
        this.settings[field] = value;
        
        // Special handling for maxItemsPerSource - apply to all sources
        if (field === 'maxItemsPerSource') {
            Object.keys(this.sources).forEach(sourceId => {
                this.sources[sourceId].maxItems = parseInt(value);
            });
            // Re-render source cards to show updated values
            this.renderSourceCards();
        }
        
        this.saveConfiguration();
    }
    
    updateSourceStatus(sourceId) {
        const sourceCard = document.querySelector(`[data-source="${sourceId}"]`);
        const statusElement = sourceCard.querySelector('.source-status');
        
        if (!this.sources[sourceId].enabled) {
            statusElement.textContent = 'Disabled';
            statusElement.className = 'source-status disabled';
            return;
        }
        
        // Check configuration validity
        let isValid = true;
        let message = 'Ready';
        
        switch (sourceId) {
            case 'reddit':
                if (!this.sources.reddit.subreddit) {
                    isValid = false;
                    message = 'Missing subreddit';
                }
                break;
            case 'github':
                if (!this.sources.github.owner || !this.sources.github.repo) {
                    isValid = false;
                    message = 'Missing repository';
                }
                break;
            case 'ado':
                if (!this.sources.ado.parentWorkItem) {
                    isValid = false;
                    message = 'Missing work item';
                }
                break;
        }
        
        statusElement.textContent = message;
        statusElement.className = `source-status ${isValid ? 'ready' : 'error'}`;
    }
    
    renderSourceCards() {
        const container = document.getElementById('dataSources');
        if (!container) return;
        
        container.innerHTML = '';
        
        const sourceConfigs = [
            {
                id: 'reddit',
                name: 'Reddit',
                icon: 'bi bi-reddit',
                description: 'Collect feedback from Reddit discussions'
            },
            {
                id: 'github',
                name: 'GitHub Discussions',
                icon: 'bi bi-github',
                description: 'Collect feedback from GitHub repository discussions'
            },
            {
                id: 'fabricCommunity',
                name: 'Fabric Community Forums',
                icon: 'bi bi-people',
                description: 'Collect feedback from Microsoft Fabric community'
            },
            {
                id: 'ado',
                name: 'Azure DevOps',
                icon: 'bi bi-kanban',
                description: 'Collect feedback from Azure DevOps work items'
            }
        ];
        
        sourceConfigs.forEach(config => {
            const card = this.createSourceCard(config);
            container.appendChild(card);
        });
    }
    
    createSourceCard(config) {
        const source = this.sources[config.id];
        const card = document.createElement('div');
        card.className = 'source-card fluent-card';
        card.dataset.source = config.id;
        
        card.innerHTML = `
            <div class="source-header">
                <label class="fluent-toggle">
                    <input type="checkbox" class="source-toggle" ${source.enabled ? 'checked' : ''}>
                    <span class="fluent-toggle-slider"></span>
                </label>
                <div class="source-title">
                    <i class="${config.icon}"></i>
                    ${config.name}
                </div>
                <span class="source-status ready">Ready</span>
                <button class="fluent-button-icon btn-configure" aria-label="Configure ${config.name}">
                    <i class="bi bi-gear"></i>
                </button>
            </div>
            <div class="source-config" id="${config.id}-config">
                ${this.renderSourceConfig(config.id)}
            </div>
        `;
        
        // Update initial status
        setTimeout(() => this.updateSourceStatus(config.id), 0);
        
        return card;
    }
    
    renderSourceConfig(sourceId) {
        const source = this.sources[sourceId];
        
        switch (sourceId) {
            case 'reddit':
                return `
                    <div class="config-field">
                        <label class="fluent-label">Subreddit:</label>
                        <input type="text" class="fluent-input source-input" 
                               data-field="subreddit" value="${source.subreddit}">
                    </div>
                    <div class="config-field-row">
                        <div class="config-field">
                            <label class="fluent-label">Sort by:</label>
                            <select class="fluent-select source-input" data-field="sort">
                                <option value="new" ${source.sort === 'new' ? 'selected' : ''}>New</option>
                                <option value="hot" ${source.sort === 'hot' ? 'selected' : ''}>Hot</option>
                                <option value="top" ${source.sort === 'top' ? 'selected' : ''}>Top</option>
                                <option value="rising" ${source.sort === 'rising' ? 'selected' : ''}>Rising</option>
                            </select>
                        </div>
                        <div class="config-field">
                            <label class="fluent-label">Time Filter:</label>
                            <select class="fluent-select source-input" data-field="timeFilter">
                                <option value="hour" ${source.timeFilter === 'hour' ? 'selected' : ''}>Past Hour</option>
                                <option value="day" ${source.timeFilter === 'day' ? 'selected' : ''}>Past Day</option>
                                <option value="week" ${source.timeFilter === 'week' ? 'selected' : ''}>Past Week</option>
                                <option value="month" ${source.timeFilter === 'month' ? 'selected' : ''}>Past Month</option>
                                <option value="year" ${source.timeFilter === 'year' ? 'selected' : ''}>Past Year</option>
                                <option value="all" ${source.timeFilter === 'all' ? 'selected' : ''}>All Time</option>
                            </select>
                        </div>
                    </div>
                    <div class="config-field">
                        <label class="fluent-label">Max Items:</label>
                        <input type="number" class="fluent-input source-input" 
                               data-field="maxItems" value="${source.maxItems}" min="1" max="1000">
                    </div>
                    <div class="source-info">
                        <span>Last collected: Never</span>
                        <span>Items found: 0</span>
                    </div>
                `;
                
            case 'github':
                return `
                    <div class="config-field-row">
                        <div class="config-field">
                            <label class="fluent-label">Owner:</label>
                            <input type="text" class="fluent-input source-input" 
                                   data-field="owner" value="${source.owner}">
                        </div>
                        <div class="config-field">
                            <label class="fluent-label">Repository:</label>
                            <input type="text" class="fluent-input source-input" 
                                   data-field="repo" value="${source.repo}">
                        </div>
                    </div>
                    <div class="config-field">
                        <label class="fluent-label">Issue State:</label>
                        <select class="fluent-select source-input" data-field="state">
                            <option value="open" ${source.state === 'open' ? 'selected' : ''}>Open</option>
                            <option value="closed" ${source.state === 'closed' ? 'selected' : ''}>Closed</option>
                            <option value="all" ${source.state === 'all' ? 'selected' : ''}>All</option>
                        </select>
                    </div>
                    <div class="config-field">
                        <label class="fluent-label">Max Items:</label>
                        <input type="number" class="fluent-input source-input" 
                               data-field="maxItems" value="${source.maxItems}" min="1" max="1000">
                    </div>
                    <div class="source-info">
                        <span>Last collected: Never</span>
                        <span>Items found: 0</span>
                    </div>
                `;
                
            case 'fabricCommunity':
                return `
                    <div class="config-field">
                        <label class="fluent-label">Max Items:</label>
                        <input type="number" class="fluent-input source-input" 
                               data-field="maxItems" value="${source.maxItems}" min="1" max="1000">
                    </div>
                    <div class="fluent-alert fluent-alert-info">
                        <i class="bi bi-info-circle"></i>
                        <div>This source uses default Microsoft Fabric Community forums configuration.</div>
                    </div>
                    <div class="source-info">
                        <span>Last collected: Never</span>
                        <span>Items found: 0</span>
                    </div>
                `;
                
            case 'ado':
                return `
                    <div class="config-field">
                        <label class="fluent-label">Parent Work Item ID:</label>
                        <input type="text" class="fluent-input source-input" 
                               data-field="parentWorkItem" value="${source.parentWorkItem}">
                    </div>
                    <div class="config-field">
                        <label class="fluent-label">Work Item Types:</label>
                        <select class="fluent-select source-input" data-field="workItemTypes" multiple>
                            <option value="Bug" ${source.workItemTypes.includes('Bug') ? 'selected' : ''}>Bug</option>
                            <option value="Feature" ${source.workItemTypes.includes('Feature') ? 'selected' : ''}>Feature</option>
                            <option value="User Story" ${source.workItemTypes.includes('User Story') ? 'selected' : ''}>User Story</option>
                            <option value="Task" ${source.workItemTypes.includes('Task') ? 'selected' : ''}>Task</option>
                        </select>
                    </div>
                    <div class="config-field">
                        <label class="fluent-label">Max Items:</label>
                        <input type="number" class="fluent-input source-input" 
                               data-field="maxItems" value="${source.maxItems}" min="1" max="1000">
                    </div>
                    <div class="source-info">
                        <span>Last collected: Never</span>
                        <span>Items found: 0</span>
                    </div>
                `;
                
            default:
                return '<div class="fluent-alert fluent-alert-warning">No configuration available for this source.</div>';
        }
    }
    
    renderSettings() {
        const container = document.getElementById('collectionSettings');
        if (!container) return;
        
        container.innerHTML = `
            <div class="config-field-row">
                <div class="config-field">
                    <label class="fluent-label">Time Range:</label>
                    <select class="fluent-select setting-input" data-field="timeRangeMonths">
                        <option value="1" ${this.settings.timeRangeMonths === 1 ? 'selected' : ''}>Last month</option>
                        <option value="3" ${this.settings.timeRangeMonths === 3 ? 'selected' : ''}>Last 3 months</option>
                        <option value="6" ${this.settings.timeRangeMonths === 6 ? 'selected' : ''}>Last 6 months</option>
                        <option value="12" ${this.settings.timeRangeMonths === 12 ? 'selected' : ''}>Last year</option>
                        <option value="0" ${this.settings.timeRangeMonths === 0 ? 'selected' : ''}>All time</option>
                    </select>
                </div>
                <div class="config-field">
                    <label class="fluent-label">Max Items per Source:</label>
                    <select class="fluent-select setting-input" data-field="maxItemsPerSource">
                        <option value="50" ${parseInt(this.settings.maxItemsPerSource) === 50 ? 'selected' : ''}>50</option>
                        <option value="100" ${parseInt(this.settings.maxItemsPerSource) === 100 ? 'selected' : ''}>100</option>
                        <option value="200" ${parseInt(this.settings.maxItemsPerSource) === 200 ? 'selected' : ''}>200</option>
                        <option value="500" ${parseInt(this.settings.maxItemsPerSource) === 500 ? 'selected' : ''}>500</option>
                    </select>
                </div>
            </div>
            <div class="config-field" style="margin-top: 12px;">
                <label class="fluent-label">
                    <input type="checkbox" class="fluent-checkbox setting-input" 
                           data-field="respectRateLimits" ${this.settings.respectRateLimits ? 'checked' : ''}>
                    Respect API rate limits
                </label>
            </div>
            <div class="config-field">
                <label class="fluent-label">
                    <input type="checkbox" class="fluent-checkbox setting-input" 
                           data-field="duplicateDetection" ${this.settings.duplicateDetection ? 'checked' : ''}>
                    Enable duplicate detection
                </label>
            </div>
        `;
    }
    
    renderKeywordsInSettings() {
        // This would update the keywords display in settings if needed
        console.log('Keywords loaded:', this.settings.keywords);
    }
    
    getCollectionConfig() {
        // Return configuration in the format expected by the backend
        return {
            sources: Object.keys(this.sources).reduce((acc, key) => {
                if (this.sources[key].enabled) {
                    acc[key] = this.sources[key];
                }
                return acc;
            }, {}),
            settings: this.settings
        };
    }
    
    resetToDefaults() {
        if (confirm('Are you sure you want to reset all source configurations to defaults?')) {
            localStorage.removeItem('feedbackCollectorConfig');
            location.reload();
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.sourceConfigManager = new SourceConfigManager();
});

// Export for use in other scripts
window.SourceConfigManager = SourceConfigManager;
