/**
 * Infinite Scroll Implementation for AI Trader Website
 * Progressive disclosure: reveals hidden posts as user scrolls down
 */

(function() {
    'use strict';
    
    // Configuration
    const SCROLL_THRESHOLD = 0.8; // Trigger when 80% scrolled
    const REVEAL_DELAY = 300; // ms delay for smooth UX
    
    // State
    let currentVisibleBatch = INITIAL_VISIBLE || 1;
    let isLoading = false;
    let allBatchesLoaded = false;
    
    // DOM elements
    const loadingIndicator = document.getElementById('loading-indicator');
    const endMessage = document.getElementById('end-message');
    const postsContainer = document.getElementById('posts-container');
    
    /**
     * Check if user has scrolled near the bottom
     */
    function isNearBottom() {
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const windowHeight = window.innerHeight;
        const documentHeight = document.documentElement.scrollHeight;
        
        const scrollPercentage = (scrollTop + windowHeight) / documentHeight;
        
        return scrollPercentage >= SCROLL_THRESHOLD;
    }
    
    /**
     * Get all posts for a specific batch
     */
    function getPostsInBatch(batchNum) {
        return document.querySelectorAll(`[data-batch="${batchNum}"]`);
    }
    
    /**
     * Reveal the next batch of posts
     */
    function revealNextBatch() {
        if (isLoading || allBatchesLoaded) {
            return;
        }
        
        const nextBatch = currentVisibleBatch + 1;
        const postsToReveal = getPostsInBatch(nextBatch);
        
        if (postsToReveal.length === 0) {
            // No more posts to load
            allBatchesLoaded = true;
            showEndMessage();
            return;
        }
        
        isLoading = true;
        showLoading();
        
        // Simulate loading delay for smooth UX
        setTimeout(() => {
            postsToReveal.forEach((post, index) => {
                // Stagger the reveal slightly for smoother animation
                setTimeout(() => {
                    post.classList.remove('hidden-post');
                    post.classList.add('fade-in');
                }, index * 50);
            });
            
            currentVisibleBatch = nextBatch;
            isLoading = false;
            hideLoading();
            
            // Check if we've loaded all batches
            if (currentVisibleBatch >= TOTAL_BATCHES) {
                allBatchesLoaded = true;
                setTimeout(showEndMessage, 500);
            }
        }, REVEAL_DELAY);
    }
    
    /**
     * Show loading indicator
     */
    function showLoading() {
        if (loadingIndicator) {
            loadingIndicator.classList.remove('hidden');
        }
    }
    
    /**
     * Hide loading indicator
     */
    function hideLoading() {
        if (loadingIndicator) {
            loadingIndicator.classList.add('hidden');
        }
    }
    
    /**
     * Show end message
     */
    function showEndMessage() {
        if (endMessage) {
            endMessage.classList.remove('hidden');
        }
    }
    
    /**
     * Handle scroll event
     */
    function handleScroll() {
        if (isNearBottom()) {
            revealNextBatch();
        }
    }
    
    /**
     * Throttle function to limit scroll event frequency
     */
    function throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
    
    /**
     * Initialize infinite scroll
     */
    function init() {
        console.log('🚀 Infinite scroll initialized');
        console.log(`   Initial visible batches: ${INITIAL_VISIBLE}`);
        console.log(`   Total batches: ${TOTAL_BATCHES}`);
        
        // Check if all batches already visible
        if (INITIAL_VISIBLE >= TOTAL_BATCHES) {
            allBatchesLoaded = true;
            showEndMessage();
            return;
        }
        
        // Add scroll listener with throttling
        window.addEventListener('scroll', throttle(handleScroll, 200));
        
        // Also check on resize (mobile rotation)
        window.addEventListener('resize', throttle(handleScroll, 500));
        
        // Initial check in case content doesn't fill screen
        setTimeout(() => {
            if (!isLoading && !allBatchesLoaded) {
                const documentHeight = document.documentElement.scrollHeight;
                const windowHeight = window.innerHeight;
                
                // If content doesn't fill screen, load more
                if (documentHeight <= windowHeight * 1.2) {
                    console.log('⚡ Content shorter than screen, auto-loading next batch');
                    revealNextBatch();
                }
            }
        }, 500);
    }
    
    /**
     * Graceful degradation: show all posts if JavaScript fails
     */
    window.addEventListener('error', function() {
        console.warn('⚠️ Error detected, revealing all posts');
        const allHiddenPosts = document.querySelectorAll('.hidden-post');
        allHiddenPosts.forEach(post => {
            post.classList.remove('hidden-post');
        });
    });
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
})();

