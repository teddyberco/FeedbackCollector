// Source Configuration Manager
class SourceConfigManager {
    constructor() {
        this.activeProjectId = null;
        
        this.defaultSources = {
            reddit: {
                enabled: true,
                subreddit: 'MicrosoftFabric',
                sort: 'new',
                timeFilter: 'month',
                postTypes: ['all'],
                maxItems: 5
            },
            github: {
                enabled: true,
                repositories: [
                    {
                        owner: 'microsoft',
                        repo: 'Microsoft-Fabric-workload-development-sample',
                        enabled: true
                    },
                    {
                        owner: 'microsoft',
                        repo: 'fabric-extensibility-toolkit',
                        enabled: true
                    },
                    {
                        owner: 'microsoft',
                        repo: 'Microsoft-fabric-tools-workload',
                        enabled: true
                    }
                ],
                state: 'all',
                labels: [],
                maxItems: 5
            },
            githubIssues: {
                enabled: true,
                repositories: [
                    {
                        owner: 'microsoft',
                        repo: 'Microsoft-Fabric-workload-development-sample',
                        enabled: true
                    },
                    {
                        owner: 'microsoft',
                        repo: 'fabric-extensibility-toolkit',
                        enabled: true
                    },
                    {
                        owner: 'microsoft',
                        repo: 'Microsoft-fabric-tools-workload',
                        enabled: true
                    }
                ],
                state: 'all',
                labels: [],
                maxItems: 5
            },
            fabricCommunity: {
                enabled: true,
                forums: [],
                maxItems: 5
            },
            ado: {
                enabled: true,
                parentWorkItem: '1319103',
                workItemTypes: ['Bug', 'Feature', 'User Story'],
                states: ['New', 'Active', 'Resolved'],
                maxItems: 5
            }
        };

        this.sources = JSON.parse(JSON.stringify(this.defaultSources));
        
        this.settings = {
            timeRangeMonths: 6,
            maxItemsPerSource: 5,
            respectRateLimits: true,
            keywords: [],
            duplicateDetection: true,
            languageFilter: 'all',
            sentimentThreshold: 0
        };
        
        this.init();
    }
    
    init() {
        this.loadActiveProject();
        this.loadConfiguration();
        this.setupEventListeners();
        this.renderSourceCards();
        this.renderSettings();
        this.updateActiveSourcesCount();
    }
    
    async loadActiveProject() {
        try {
            const response = await fetch('/api/active-config');
            const data = await response.json();
            if (data.status === 'success' && data.active_project_id) {
                this.activeProjectId = data.active_project_id;
                // Load project-specific sources
                await this.loadProjectSources(data.active_project_id);
            }
        } catch (e) {
            console.error('Error loading active project:', e);
        }
    }
    
    async loadProjectSources(projectId) {
        try {
            const response = await fetch(`/api/projects/${projectId}/sources`);
            const data = await response.json();
            if (data.status === 'success' && data.sources) {
                // Merge project sources with defaults (to ensure all fields exist)
                Object.keys(data.sources).forEach(sourceId => {
                    if (this.sources[sourceId]) {
                        this.sources[sourceId] = { ...this.sources[sourceId], ...data.sources[sourceId] };
                    } else {
                        this.sources[sourceId] = data.sources[sourceId];
                    }
                });
                this.renderSourceCards();
                this.updateActiveSourcesCount();
            }
        } catch (e) {
            console.error('Error loading project sources:', e);
        }
    }
    
    async applyProjectConfig(projectId) {
        // Apply a project's source configuration to the UI
        this.activeProjectId = projectId;
        if (projectId) {
            await this.loadProjectSources(projectId);
        } else {
            // Reset to defaults for legacy mode
            this.sources = JSON.parse(JSON.stringify(this.defaultSources));
            this.loadConfiguration();  // Load from localStorage
        }
        this.renderSourceCards();
        this.renderSettings();
        this.updateActiveSourcesCount();
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
        
        // Also save to the active project on the server
        if (this.activeProjectId) {
            fetch(`/api/projects/${this.activeProjectId}/sources`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.sources)
            }).catch(e => console.error('Error saving project sources:', e));
        }
    }
    
    updateActiveSourcesCount() {
        // Count how many sources are enabled
        const enabledCount = Object.values(this.sources).filter(source => source.enabled).length;
        
        // Update the dashboard stat
        const statElement = document.getElementById('statActiveSources');
        if (statElement) {
            statElement.textContent = enabledCount;
        }
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
            
            // Add repository button
            if (e.target.matches('.btn-add-repo') || e.target.closest('.btn-add-repo')) {
                this.handleAddRepository(e.target.closest('.source-card'));
            }
            
            // Remove repository button
            if (e.target.matches('.btn-remove-repo') || e.target.closest('.btn-remove-repo')) {
                const button = e.target.closest('.btn-remove-repo');
                const repoIndex = parseInt(button.dataset.repoIndex);
                this.handleRemoveRepository(repoIndex);
            }
            
            // GitHub Discussions - Add repository button
            if (e.target.matches('.btn-add-github-repo') || e.target.closest('.btn-add-github-repo')) {
                this.handleAddGithubRepository(e.target.closest('.source-card'));
            }
            
            // GitHub Discussions - Remove repository button
            if (e.target.matches('.btn-remove-github-repo') || e.target.closest('.btn-remove-github-repo')) {
                const button = e.target.closest('.btn-remove-github-repo');
                const repoIndex = parseInt(button.dataset.repoIndex);
                this.handleRemoveGithubRepository(repoIndex);
            }
            
            // Community Forum - Add forum button
            if (e.target.matches('.btn-add-forum') || e.target.closest('.btn-add-forum')) {
                this.handleAddForum();
            }
            
            // Community Forum - Remove forum button
            if (e.target.matches('.btn-remove-forum') || e.target.closest('.btn-remove-forum')) {
                const button = e.target.closest('.btn-remove-forum');
                const forumIndex = parseInt(button.dataset.forumIndex);
                this.handleRemoveForum(forumIndex);
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
            
            // Repository toggle listeners
            if (e.target.matches('.repo-toggle')) {
                this.handleRepoToggle(e.target);
            }
            
            // GitHub repo toggle listeners
            if (e.target.matches('.github-repo-toggle')) {
                this.handleGithubRepoToggle(e.target);
            }
            
            // Forum toggle listeners
            if (e.target.matches('.forum-toggle')) {
                const forumIndex = parseInt(e.target.dataset.forumIndex);
                if (this.sources.fabricCommunity.forums && this.sources.fabricCommunity.forums[forumIndex]) {
                    this.sources.fabricCommunity.forums[forumIndex].enabled = e.target.checked;
                    this.saveConfiguration();
                }
            }
        });
    }
    
    handleAddRepository(sourceCard) {
        const ownerInput = sourceCard.querySelector('#newRepoOwner');
        const repoInput = sourceCard.querySelector('#newRepoName');
        
        const owner = ownerInput.value.trim();
        const repo = repoInput.value.trim();
        
        if (!owner || !repo) {
            alert('Please enter both owner and repository name');
            return;
        }
        
        // Check for duplicates
        const existingRepos = this.sources.githubIssues.repositories || [];
        const isDuplicate = existingRepos.some(r => 
            r.owner.toLowerCase() === owner.toLowerCase() && 
            r.repo.toLowerCase() === repo.toLowerCase()
        );
        
        if (isDuplicate) {
            alert('This repository is already in the list');
            return;
        }
        
        // Add the new repository
        if (!this.sources.githubIssues.repositories) {
            this.sources.githubIssues.repositories = [];
        }
        
        this.sources.githubIssues.repositories.push({
            owner: owner,
            repo: repo,
            enabled: true
        });
        
        // Clear inputs
        ownerInput.value = '';
        repoInput.value = '';
        
        // Re-render the source card
        this.renderSourceCards();
        this.saveConfiguration();
        
        // Re-open the configuration panel
        setTimeout(() => {
            const newCard = document.querySelector('[data-source="githubIssues"]');
            const configDiv = newCard.querySelector('.source-config');
            configDiv.classList.add('expanded');
        }, 100);
    }
    
    handleRemoveRepository(repoIndex) {
        if (!confirm('Are you sure you want to remove this repository?')) {
            return;
        }
        
        this.sources.githubIssues.repositories.splice(repoIndex, 1);
        this.renderSourceCards();
        this.saveConfiguration();
        
        // Re-open the configuration panel
        setTimeout(() => {
            const card = document.querySelector('[data-source="githubIssues"]');
            const configDiv = card.querySelector('.source-config');
            configDiv.classList.add('expanded');
        }, 100);
    }
    
    handleRepoToggle(toggle) {
        const repoIndex = parseInt(toggle.dataset.repoIndex);
        this.sources.githubIssues.repositories[repoIndex].enabled = toggle.checked;
        this.updateSourceStatus('githubIssues');
        this.saveConfiguration();
    }
    
    handleAddGithubRepository(sourceCard) {
        const ownerInput = sourceCard.querySelector('#newGithubRepoOwner');
        const repoInput = sourceCard.querySelector('#newGithubRepoName');
        
        const owner = ownerInput.value.trim();
        const repo = repoInput.value.trim();
        
        if (!owner || !repo) {
            alert('Please enter both owner and repository name');
            return;
        }
        
        // Check for duplicates
        const existingRepos = this.sources.github.repositories || [];
        const isDuplicate = existingRepos.some(r => 
            r.owner.toLowerCase() === owner.toLowerCase() && 
            r.repo.toLowerCase() === repo.toLowerCase()
        );
        
        if (isDuplicate) {
            alert('This repository is already in the list');
            return;
        }
        
        // Add the new repository
        if (!this.sources.github.repositories) {
            this.sources.github.repositories = [];
        }
        
        this.sources.github.repositories.push({
            owner: owner,
            repo: repo,
            enabled: true
        });
        
        // Clear inputs
        ownerInput.value = '';
        repoInput.value = '';
        
        // Re-render the source card
        this.renderSourceCards();
        this.saveConfiguration();
        
        // Re-open the configuration panel
        setTimeout(() => {
            const newCard = document.querySelector('[data-source="github"]');
            const configDiv = newCard.querySelector('.source-config');
            configDiv.classList.add('expanded');
        }, 100);
    }
    
    handleRemoveGithubRepository(repoIndex) {
        if (!confirm('Are you sure you want to remove this repository?')) {
            return;
        }
        
        this.sources.github.repositories.splice(repoIndex, 1);
        this.renderSourceCards();
        this.saveConfiguration();
        
        // Re-open the configuration panel
        setTimeout(() => {
            const card = document.querySelector('[data-source="github"]');
            const configDiv = card.querySelector('.source-config');
            configDiv.classList.add('expanded');
        }, 100);
    }
    
    handleGithubRepoToggle(toggle) {
        const repoIndex = parseInt(toggle.dataset.repoIndex);
        this.sources.github.repositories[repoIndex].enabled = toggle.checked;
        this.updateSourceStatus('github');
        this.saveConfiguration();
    }
    
    handleAddForum() {
        const nameInput = document.getElementById('newForumName');
        const urlInput = document.getElementById('newForumUrl');
        
        const name = nameInput ? nameInput.value.trim() : '';
        const url = urlInput ? urlInput.value.trim() : '';
        
        if (!name || !url) {
            alert('Please enter both forum name and URL');
            return;
        }
        
        if (!this.sources.fabricCommunity.forums) {
            this.sources.fabricCommunity.forums = [];
        }
        
        // Check for duplicates
        const isDuplicate = this.sources.fabricCommunity.forums.some(f => f.url === url);
        if (isDuplicate) {
            alert('This forum URL is already in the list');
            return;
        }
        
        this.sources.fabricCommunity.forums.push({
            name: name,
            url: url,
            enabled: true
        });
        
        this.renderSourceCards();
        this.saveConfiguration();
        
        // Re-open the config panel
        setTimeout(() => {
            const card = document.querySelector('[data-source="fabricCommunity"]');
            if (card) {
                const configDiv = card.querySelector('.source-config');
                configDiv.classList.add('expanded');
            }
        }, 100);
    }
    
    handleRemoveForum(forumIndex) {
        if (!confirm('Are you sure you want to remove this forum?')) return;
        
        this.sources.fabricCommunity.forums.splice(forumIndex, 1);
        this.renderSourceCards();
        this.saveConfiguration();
        
        setTimeout(() => {
            const card = document.querySelector('[data-source="fabricCommunity"]');
            if (card) {
                const configDiv = card.querySelector('.source-config');
                configDiv.classList.add('expanded');
            }
        }, 100);
    }
    
    handleSourceToggle(toggle) {
        const sourceCard = toggle.closest('.source-card');
        const sourceId = sourceCard.dataset.source;
        this.sources[sourceId].enabled = toggle.checked;
        
        // Update UI
        sourceCard.classList.toggle('disabled', !toggle.checked);
        this.updateSourceStatus(sourceId);
        this.saveConfiguration();
        this.updateActiveSourcesCount();
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
                const githubRepos = this.sources.github.repositories || [];
                const enabledGithubRepos = githubRepos.filter(r => r.enabled);
                if (enabledGithubRepos.length === 0) {
                    isValid = false;
                    message = 'No repositories enabled';
                }
                break;
            case 'githubIssues':
                const repos = this.sources.githubIssues.repositories || [];
                const enabledRepos = repos.filter(r => r.enabled);
                if (enabledRepos.length === 0) {
                    isValid = false;
                    message = 'No repositories enabled';
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
                id: 'githubIssues',
                name: 'GitHub Issues',
                icon: 'bi bi-exclamation-circle',
                description: 'Collect feedback from GitHub repository issues'
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
                const githubRepos = source.repositories || [];
                const githubRepoList = githubRepos.map((repo, index) => `
                    <div class="repo-item" data-repo-index="${index}">
                        <div class="config-field-row" style="align-items: center;">
                            <label class="fluent-toggle" style="margin: 0;">
                                <input type="checkbox" class="github-repo-toggle" 
                                       data-repo-index="${index}" ${repo.enabled ? 'checked' : ''}>
                                <span class="fluent-toggle-slider"></span>
                            </label>
                            <div style="flex: 1;">
                                <strong>${repo.owner}/${repo.repo}</strong>
                            </div>
                            <button class="fluent-button-icon btn-remove-github-repo" 
                                    data-repo-index="${index}" 
                                    aria-label="Remove repository"
                                    style="color: var(--error-color);">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </div>
                `).join('');
                
                return `
                    <div class="config-field">
                        <label class="fluent-label">Repositories:</label>
                        <div class="repo-list" style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px;">
                            ${githubRepoList || '<div class="fluent-alert fluent-alert-warning"><i class="bi bi-exclamation-triangle"></i><div>No repositories configured</div></div>'}
                        </div>
                    </div>
                    
                    <div class="config-field" style="border-top: 1px solid var(--border-color); padding-top: 12px;">
                        <label class="fluent-label">Add New Repository:</label>
                        <div class="config-field-row">
                            <input type="text" class="fluent-input" 
                                   id="newGithubRepoOwner" placeholder="Owner (e.g., microsoft)">
                            <input type="text" class="fluent-input" 
                                   id="newGithubRepoName" placeholder="Repository (e.g., fabric-samples)">
                            <button class="fluent-button fluent-button-primary btn-add-github-repo">
                                <i class="bi bi-plus"></i> Add
                            </button>
                        </div>
                    </div>
                    
                    <div class="config-field">
                        <label class="fluent-label">Discussion State:</label>
                        <select class="fluent-select source-input" data-field="state">
                            <option value="open" ${source.state === 'open' ? 'selected' : ''}>Open</option>
                            <option value="closed" ${source.state === 'closed' ? 'selected' : ''}>Closed</option>
                            <option value="all" ${source.state === 'all' ? 'selected' : ''}>All</option>
                        </select>
                    </div>
                    <div class="config-field">
                        <label class="fluent-label">Max Items per Repository:</label>
                        <input type="number" class="fluent-input source-input" 
                               data-field="maxItems" value="${source.maxItems}" min="1" max="1000">
                    </div>
                    <div class="fluent-alert fluent-alert-info">
                        <i class="bi bi-info-circle"></i>
                        <div>Note: Repository must have Discussions enabled. All enabled repositories will be collected.</div>
                    </div>
                    <div class="source-info">
                        <span>Repositories: ${githubRepos.filter(r => r.enabled).length} enabled / ${githubRepos.length} total</span>
                    </div>
                `;
                
            case 'githubIssues':
                const repos = source.repositories || [];
                const repoList = repos.map((repo, index) => `
                    <div class="repo-item" data-repo-index="${index}">
                        <div class="config-field-row" style="align-items: center;">
                            <label class="fluent-toggle" style="margin: 0;">
                                <input type="checkbox" class="repo-toggle" 
                                       data-repo-index="${index}" ${repo.enabled ? 'checked' : ''}>
                                <span class="fluent-toggle-slider"></span>
                            </label>
                            <div style="flex: 1;">
                                <strong>${repo.owner}/${repo.repo}</strong>
                            </div>
                            <button class="fluent-button-icon btn-remove-repo" 
                                    data-repo-index="${index}" 
                                    aria-label="Remove repository"
                                    style="color: var(--error-color);">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </div>
                `).join('');
                
                return `
                    <div class="config-field">
                        <label class="fluent-label">Repositories:</label>
                        <div class="repo-list" style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px;">
                            ${repoList || '<div class="fluent-alert fluent-alert-warning"><i class="bi bi-exclamation-triangle"></i><div>No repositories configured</div></div>'}
                        </div>
                    </div>
                    
                    <div class="config-field" style="border-top: 1px solid var(--border-color); padding-top: 12px;">
                        <label class="fluent-label">Add New Repository:</label>
                        <div class="config-field-row">
                            <input type="text" class="fluent-input" 
                                   id="newRepoOwner" placeholder="Owner (e.g., microsoft)">
                            <input type="text" class="fluent-input" 
                                   id="newRepoName" placeholder="Repository (e.g., fabric-samples)">
                            <button class="fluent-button fluent-button-primary btn-add-repo">
                                <i class="bi bi-plus"></i> Add
                            </button>
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
                        <label class="fluent-label">Max Items per Repository:</label>
                        <input type="number" class="fluent-input source-input" 
                               data-field="maxItems" value="${source.maxItems}" min="1" max="1000">
                    </div>
                    <div class="fluent-alert fluent-alert-info">
                        <i class="bi bi-info-circle"></i>
                        <div>Collects issues only (excludes pull requests). All enabled repositories will be collected.</div>
                    </div>
                    <div class="source-info">
                        <span>Repositories: ${repos.filter(r => r.enabled).length} enabled / ${repos.length} total</span>
                    </div>
                `;
                
            case 'fabricCommunity':
                const forums = source.forums || [];
                const forumList = forums.map((forum, index) => `
                    <div class="repo-item" data-forum-index="${index}">
                        <div class="config-field-row" style="align-items: center;">
                            <label class="fluent-toggle" style="margin: 0;">
                                <input type="checkbox" class="forum-toggle" 
                                       data-forum-index="${index}" ${forum.enabled !== false ? 'checked' : ''}>
                                <span class="fluent-toggle-slider"></span>
                            </label>
                            <div style="flex: 1;">
                                <strong>${forum.name || 'Community Forum'}</strong>
                                <div style="font-size: 0.8em; color: var(--text-secondary); word-break: break-all;">${forum.url || ''}</div>
                            </div>
                            <button class="fluent-button-icon btn-remove-forum" 
                                    data-forum-index="${index}" 
                                    aria-label="Remove forum"
                                    style="color: var(--error-color);">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </div>
                `).join('');
                
                return `
                    <div class="config-field">
                        <label class="fluent-label">Community Forums:</label>
                        <div class="repo-list" style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px;">
                            ${forumList || '<div class="fluent-alert fluent-alert-info"><i class="bi bi-info-circle"></i><div>Using default Fabric Platform Forum. Add more forums below.</div></div>'}
                        </div>
                    </div>
                    
                    <div class="config-field" style="border-top: 1px solid var(--border-color); padding-top: 12px;">
                        <label class="fluent-label">Add Community Forum:</label>
                        <div class="config-field-row">
                            <input type="text" class="fluent-input" 
                                   id="newForumName" placeholder="Forum Name (e.g., Data Science)">
                            <input type="text" class="fluent-input" 
                                   id="newForumUrl" placeholder="Forum URL">
                            <button class="fluent-button fluent-button-primary btn-add-forum">
                                <i class="bi bi-plus"></i> Add
                            </button>
                        </div>
                    </div>
                    
                    <div class="config-field">
                        <label class="fluent-label">Max Items:</label>
                        <input type="number" class="fluent-input source-input" 
                               data-field="maxItems" value="${source.maxItems}" min="1" max="1000">
                    </div>
                    <div class="source-info">
                        <span>Forums: ${forums.filter(f => f.enabled !== false).length} enabled / ${forums.length} total</span>
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
                        <option value="5" ${parseInt(this.settings.maxItemsPerSource) === 5 ? 'selected' : ''}>5</option>
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
