/**
 * Bulletproof Badge State Manager
 * Ensures 100% reliable badge persistence across all pages
 */

class BadgeStateManager {
    constructor() {
        this.states = {
            fabricAuth: {
                status: 'disconnected', // disconnected, connected, validating, error
                badge: 'Not Connected',
                lastValidated: null,
                sessionId: null
            },
            collectionProgress: {
                status: 'ready', // ready, running, completed, error  
                badge: 'Ready',
                totalItems: 0,
                lastRun: null
            }
        };
        
        this.retryCount = 0;
        this.maxRetries = 3;
        this.retryDelay = 1000; // 1 second
        this.syncInProgress = false;
        
        console.log('🔧 BadgeStateManager: Initialized');
    }
    
    /**
     * Initialize badge states on page load
     */
    async initialize() {
        if (this.syncInProgress) {
            console.log('🔧 BadgeStateManager: Sync already in progress, skipping');
            return;
        }
        
        console.log('🔧 BadgeStateManager: Starting initialization...');
        this.syncInProgress = true;
        
        try {
            // Wait for DOM to be ready
            await this.waitForDOM();
            
            // Sync both states in parallel
            const [fabricResult, collectionResult] = await Promise.allSettled([
                this.syncFabricAuthState(),
                this.syncCollectionProgressState()
            ]);
            
            // Log results
            if (fabricResult.status === 'fulfilled') {
                console.log('✅ BadgeStateManager: Fabric Auth sync successful');
            } else {
                console.error('❌ BadgeStateManager: Fabric Auth sync failed:', fabricResult.reason);
            }
            
            if (collectionResult.status === 'fulfilled') {
                console.log('✅ BadgeStateManager: Collection Progress sync successful');
            } else {
                console.error('❌ BadgeStateManager: Collection Progress sync failed:', collectionResult.reason);
            }
            
            // Force update badges regardless of API results
            this.updateAllBadges();
            
        } catch (error) {
            console.error('❌ BadgeStateManager: Initialization failed:', error);
        } finally {
            this.syncInProgress = false;
        }
    }
    
    /**
     * Wait for DOM elements to be available
     */
    waitForDOM() {
        return new Promise((resolve) => {
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', resolve);
            } else {
                resolve();
            }
        });
    }
    
    /**
     * Sync Fabric Auth state from server
     */
    async syncFabricAuthState() {
        try {
            console.log('🔧 BadgeStateManager: Syncing Fabric Auth state...');
            
            const response = await fetch('/api/fabric/token/status', {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log('🔧 BadgeStateManager: Fabric Auth API response:', data);
            
            // Update internal state
            if (data.has_token) {
                this.states.fabricAuth = {
                    status: 'connected',
                    badge: 'Connected',
                    lastValidated: data.last_validated || new Date().toISOString(),
                    sessionId: data.session_id || null
                };
            } else {
                this.states.fabricAuth = {
                    status: 'disconnected',
                    badge: 'Not Connected',
                    lastValidated: null,
                    sessionId: null
                };
            }
            
            console.log('✅ BadgeStateManager: Fabric Auth state updated:', this.states.fabricAuth);
            return this.states.fabricAuth;
            
        } catch (error) {
            console.error('❌ BadgeStateManager: Fabric Auth sync error:', error);
            
            // Fallback to disconnected state
            this.states.fabricAuth = {
                status: 'error',
                badge: 'Error',
                lastValidated: null,
                sessionId: null
            };
            
            throw error;
        }
    }
    
    /**
     * Sync Collection Progress state from server
     */
    async syncCollectionProgressState() {
        try {
            console.log('🔧 BadgeStateManager: Syncing Collection Progress state...');
            
            const response = await fetch('/api/collection_status', {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log('🔧 BadgeStateManager: Collection Progress API response:', data);
            
            // Update internal state based on response
            let status = 'ready';
            let badge = 'Ready';
            
            if (data.status === 'running') {
                status = 'running';
                badge = 'Running';
            } else if (data.status === 'completed') {
                status = 'completed';
                badge = 'Completed';
            } else if (data.status === 'error') {
                status = 'error';
                badge = 'Error';
            }
            
            this.states.collectionProgress = {
                status: status,
                badge: badge,
                totalItems: data.total_items || 0,
                lastRun: data.last_run || null
            };
            
            console.log('✅ BadgeStateManager: Collection Progress state updated:', this.states.collectionProgress);
            return this.states.collectionProgress;
            
        } catch (error) {
            console.error('❌ BadgeStateManager: Collection Progress sync error:', error);
            
            // Fallback to ready state
            this.states.collectionProgress = {
                status: 'ready',
                badge: 'Ready',
                totalItems: 0,
                lastRun: null
            };
            
            throw error;
        }
    }
    
    /**
     * Update all badge elements on the page
     */
    updateAllBadges() {
        console.log('🔧 BadgeStateManager: Updating all badge elements...');
        
        // Update Fabric Auth badge
        this.updateFabricAuthBadge();
        
        // Update Collection Progress badge
        this.updateCollectionProgressBadge();
        
        console.log('✅ BadgeStateManager: All badges updated');
    }
    
    /**
     * Update Fabric Auth badge element
     */
    updateFabricAuthBadge() {
        const badge = document.getElementById('fabricAuthBadge');
        if (badge) {
            const state = this.states.fabricAuth;
            badge.textContent = state.badge;
            
            // Remove all status classes
            badge.classList.remove('bg-secondary', 'bg-success', 'bg-warning', 'bg-danger');
            
            // Add appropriate class based on status
            switch (state.status) {
                case 'connected':
                    badge.classList.add('bg-success');
                    break;
                case 'validating':
                    badge.classList.add('bg-warning');
                    break;
                case 'error':
                    badge.classList.add('bg-danger');
                    break;
                default: // disconnected
                    badge.classList.add('bg-secondary');
                    break;
            }
            
            console.log(`✅ BadgeStateManager: Fabric Auth badge updated to "${state.badge}" (${state.status})`);
        } else {
            console.log('⚠️ BadgeStateManager: Fabric Auth badge element not found');
        }
    }
    
    /**
     * Update Collection Progress badge element
     */
    updateCollectionProgressBadge() {
        const badge = document.getElementById('progressBadge');
        if (badge) {
            const state = this.states.collectionProgress;
            badge.textContent = state.badge;
            
            // Remove all status classes
            badge.classList.remove('bg-secondary', 'bg-success', 'bg-warning', 'bg-danger', 'bg-primary');
            
            // Add appropriate class based on status
            switch (state.status) {
                case 'running':
                    badge.classList.add('bg-warning');
                    break;
                case 'completed':
                    badge.classList.add('bg-success');
                    break;
                case 'error':
                    badge.classList.add('bg-danger');
                    break;
                default: // ready
                    badge.classList.add('bg-secondary');
                    break;
            }
            
            console.log(`✅ BadgeStateManager: Collection Progress badge updated to "${state.badge}" (${state.status})`);
        } else {
            console.log('⚠️ BadgeStateManager: Collection Progress badge element not found');
        }
    }
    
    /**
     * Force refresh all states (for use after navigation/filtering)
     */
    async forceRefresh() {
        console.log('🔧 BadgeStateManager: Force refresh requested');
        await this.initialize();
    }
    
    /**
     * Get current state (for debugging)
     */
    getCurrentState() {
        return { ...this.states };
    }
    
    /**
     * Update Fabric Auth state manually (after token validation)
     */
    setFabricAuthState(status, badge, sessionId = null) {
        this.states.fabricAuth = {
            status: status,
            badge: badge,
            lastValidated: new Date().toISOString(),
            sessionId: sessionId
        };
        this.updateFabricAuthBadge();
        console.log('✅ BadgeStateManager: Fabric Auth state manually updated:', this.states.fabricAuth);
    }
    
    /**
     * Update Collection Progress state manually (after collection operation)
     */
    setCollectionProgressState(status, badge, totalItems = 0) {
        this.states.collectionProgress = {
            status: status,
            badge: badge,
            totalItems: totalItems,
            lastRun: new Date().toISOString()
        };
        this.updateCollectionProgressBadge();
        console.log('✅ BadgeStateManager: Collection Progress state manually updated:', this.states.collectionProgress);
    }
}

// Create global instance
window.badgeStateManager = new BadgeStateManager();

// Auto-initialize when DOM is ready
if (document && document.addEventListener) {
    document.addEventListener('DOMContentLoaded', () => {
        console.log('🔧 BadgeStateManager: DOM ready, initializing...');
        window.badgeStateManager.initialize();
    });
}

// Re-sync after page visibility changes
if (document && document.addEventListener) {
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            console.log('🔧 BadgeStateManager: Page became visible, refreshing...');
            setTimeout(() => {
                window.badgeStateManager.forceRefresh();
            }, 100);
        }
    });
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = BadgeStateManager;
}