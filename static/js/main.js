// Entry point for frontend JavaScript.

// iOS Blend Mode Fallback
(function() {
    var ua = window.navigator.userAgent;
    var iOS = /iPad|iPhone|iPod/.test(ua) && !window.MSStream;
    
    // Check if background-blend-mode is actually supported
    var supportsBlendMode = false;
    var testDiv = document.createElement('div');
    testDiv.style.backgroundBlendMode = 'overlay';
    supportsBlendMode = testDiv.style.backgroundBlendMode === 'overlay';
    
    // Apply fallback if iOS or blend mode not supported
    if (iOS || !supportsBlendMode) {
        document.body.classList.add('ios-blend-fallback');
    }
})();
