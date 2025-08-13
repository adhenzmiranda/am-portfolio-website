// Entry point for frontend JavaScript.

// iOS Blend Mode Fallback
(function() {
    var ua = window.navigator.userAgent;
    var iOS = /iPad|iPhone|iPod/.test(ua) && !window.MSStream;
    if (iOS) {
        document.body.classList.add('ios-blend-fallback');
    }
})();

// Embed Responsiveness Handler
window.EmbedHandler = {
    // Initialize all embed handlers
    init: function() {
        this.handleIframeEmbeds();
        this.handleInstagramEmbeds();
        this.handleTwitterEmbeds();
        this.handleGenericEmbeds();
        
        // Reinitialize after potential dynamic loads
        setTimeout(() => this.reinitialize(), 1000);
        setTimeout(() => this.reinitialize(), 3000);
    },
    
    // Handle iframe embeds with proper aspect ratios
    handleIframeEmbeds: function() {
        const iframes = document.querySelectorAll('.project-embeds .embed-gallery-grid .embed-item iframe');
        iframes.forEach(iframe => {
            const src = iframe.src || '';
            
            // Check if it's a social media iframe that needs natural dimensions
            const isSocialMedia = src.includes('facebook.com') || 
                                 src.includes('instagram.com') || 
                                 src.includes('twitter.com') || 
                                 src.includes('x.com') || 
                                 src.includes('tiktok.com') || 
                                 src.includes('linkedin.com');
            
            if (isSocialMedia) {
                // Get original dimensions from attributes
                const originalWidth = iframe.getAttribute('width');
                const originalHeight = iframe.getAttribute('height');
                
                console.log('Processing social iframe:', {
                    src: src,
                    originalWidth: originalWidth,
                    originalHeight: originalHeight
                });
                
                if (originalWidth && originalHeight) {
                    // Calculate and apply aspect ratio
                    const aspectRatio = originalWidth / originalHeight;
                    
                    // Set CSS custom property for aspect ratio
                    iframe.style.setProperty('--original-aspect-ratio', aspectRatio);
                    iframe.style.aspectRatio = aspectRatio;
                    
                    // Store original dimensions as data attributes
                    iframe.dataset.originalWidth = originalWidth;
                    iframe.dataset.originalHeight = originalHeight;
                    iframe.dataset.aspectRatio = aspectRatio;
                    
                    console.log('Applied aspect ratio:', aspectRatio);
                } else {
                    console.log('No width/height attributes found, using CSS defaults');
                }
                
                // Add responsive class
                iframe.classList.add('social-iframe');
                
                // Remove any hardcoded width/height styles that might interfere
                iframe.style.width = '100%';
                iframe.style.height = 'auto';
            }
            
            // Add container class
            const container = iframe.closest('.embed-item');
            if (container && isSocialMedia) {
                container.classList.add('social-embed-container');
            }
        });
    },
    
    // Handle Instagram embeds specifically
    handleInstagramEmbeds: function() {
        const instagramEmbeds = document.querySelectorAll('.instagram-media');
        instagramEmbeds.forEach(embed => {
            // Remove hardcoded styles that might interfere
            embed.style.width = '';
            embed.style.maxWidth = '';
            embed.style.minWidth = '';
            
            // Add responsive class
            embed.classList.add('responsive-embed');
            
            // Ensure proper container styling
            const container = embed.closest('.embed-item');
            if (container) {
                container.classList.add('social-embed-container');
            }
        });
    },
    
    // Handle Twitter embeds
    handleTwitterEmbeds: function() {
        const twitterEmbeds = document.querySelectorAll('.twitter-tweet');
        twitterEmbeds.forEach(embed => {
            embed.classList.add('responsive-embed');
            
            const container = embed.closest('.embed-item');
            if (container) {
                container.classList.add('social-embed-container');
            }
        });
    },
    
    // Handle other generic embeds
    handleGenericEmbeds: function() {
        const blockquoteEmbeds = document.querySelectorAll('blockquote[class*="tiktok-"], blockquote[class*="facebook-"], blockquote[class*="linkedin-"]');
        blockquoteEmbeds.forEach(embed => {
            embed.classList.add('responsive-embed');
            
            const container = embed.closest('.embed-item');
            if (container) {
                container.classList.add('social-embed-container');
            }
        });
    },
    
    // Reinitialize for dynamically loaded content
    reinitialize: function() {
        this.handleIframeEmbeds();
        this.handleInstagramEmbeds();
        this.handleTwitterEmbeds();
        this.handleGenericEmbeds();
        
        // Process Instagram embeds if the API is available
        if (window.instgrm && window.instgrm.Embeds) {
            window.instgrm.Embeds.process();
        }
        
        // Process Twitter embeds if the API is available
        if (window.twttr && window.twttr.widgets) {
            window.twttr.widgets.load();
        }
    }
};

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    window.EmbedHandler.init();
});