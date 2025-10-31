/**
 * Options Timeline Indicator
 * Dynamically positions the current date indicator on the timeline from post date to expiry
 */

(function() {
    'use strict';
    
    /**
     * Parse various date formats from AI output
     */
    function parseExpiryDate(expiryStr) {
        if (!expiryStr) return null;
        
        // Remove any extra whitespace
        expiryStr = expiryStr.trim();
        
        // Try to extract year (4 digits)
        const yearMatch = expiryStr.match(/20\d{2}/);
        if (!yearMatch) return null;
        const year = parseInt(yearMatch[0]);
        
        // Try to extract month
        const monthPatterns = {
            'jan': 0, 'january': 0, '1月': 0,
            'feb': 1, 'february': 1, '2月': 1,
            'mar': 2, 'march': 2, '3月': 2,
            'apr': 3, 'april': 3, '4月': 3,
            'may': 4, '5月': 4,
            'jun': 5, 'june': 5, '6月': 5,
            'jul': 6, 'july': 6, '7月': 6,
            'aug': 7, 'august': 7, '8月': 7,
            'sep': 8, 'september': 8, '9月': 8,
            'oct': 9, 'october': 9, '10月': 9,
            'nov': 10, 'november': 10, '11月': 10,
            'dec': 11, 'december': 11, '12月': 11
        };
        
        let month = 11; // Default to December
        const lowerExpiry = expiryStr.toLowerCase();
        
        for (const [key, value] of Object.entries(monthPatterns)) {
            if (lowerExpiry.includes(key)) {
                month = value;
                break;
            }
        }
        
        // If date range like "Feb-Mar", use the later month
        if (lowerExpiry.includes('-')) {
            const parts = lowerExpiry.split('-');
            if (parts.length > 1) {
                for (const [key, value] of Object.entries(monthPatterns)) {
                    if (parts[1].includes(key)) {
                        month = value;
                        break;
                    }
                }
            }
        }
        
        // Create date (use last day of month)
        return new Date(year, month + 1, 0); // Last day of the month
    }
    
    /**
     * Parse ISO date string
     */
    function parsePostDate(dateStr) {
        try {
            return new Date(dateStr.replace('Z', '+00:00'));
        } catch (e) {
            console.error('Error parsing post date:', e);
            return new Date();
        }
    }
    
    /**
     * Calculate position percentage
     */
    function calculatePosition(postDate, currentDate, expiryDate) {
        const totalTime = expiryDate.getTime() - postDate.getTime();
        const elapsedTime = currentDate.getTime() - postDate.getTime();
        
        if (totalTime <= 0) return 0;
        if (elapsedTime <= 0) return 0;
        if (elapsedTime >= totalTime) return 100;
        
        return (elapsedTime / totalTime) * 100;
    }
    
    /**
     * Update all timeline indicators
     */
    function updateTimelineIndicators() {
        const timelines = document.querySelectorAll('.option-timeline');
        const currentDate = new Date();
        
        timelines.forEach(timeline => {
            const postDateStr = timeline.getAttribute('data-post-date');
            const expiryStr = timeline.getAttribute('data-expiry');
            
            if (!postDateStr || !expiryStr) return;
            
            const postDate = parsePostDate(postDateStr);
            const expiryDate = parseExpiryDate(expiryStr);
            
            if (!expiryDate) {
                console.warn('Could not parse expiry date:', expiryStr);
                return;
            }
            
            // Calculate position percentage
            const position = calculatePosition(postDate, currentDate, expiryDate);
            
            // Update indicator position
            const indicator = timeline.querySelector('.timeline-indicator');
            if (indicator) {
                indicator.style.left = `${position}%`;
            }
            
            // Update bar gradient based on position
            // 0-50% green, 50-75% yellow, 75-90% orange, 90-100% red
            const bar = timeline.querySelector('.timeline-bar');
            if (bar) {
                bar.style.background = `linear-gradient(to right, 
                    #4CAF50 0%, 
                    #4CAF50 50%, 
                    #FFC107 50%, 
                    #FFC107 75%, 
                    #FF9800 75%,
                    #FF9800 90%,
                    #F44336 90%,
                    #F44336 100%)`;
            }
            
            // Add tooltip with dates
            timeline.title = `Post: ${postDate.toLocaleDateString()} | Current: ${currentDate.toLocaleDateString()} | Expiry: ${expiryDate.toLocaleDateString()}`;
            
            // Add warning class if too close to expiry (> 80%)
            if (position > 80) {
                timeline.classList.add('timeline-warning');
            }
        });
    }
    
    /**
     * Initialize
     */
    function init() {
        // Update on page load
        updateTimelineIndicators();
        
        // Update every hour (in case page stays open)
        setInterval(updateTimelineIndicators, 3600000); // 1 hour
        
        console.log('✅ Timeline indicators initialized');
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
})();

