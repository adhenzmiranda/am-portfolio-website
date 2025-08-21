document.addEventListener('DOMContentLoaded', () => {
    const body = document.body;
    let lastScrollY = window.scrollY;
    
    // Initialize the CSS variable
    body.style.setProperty('--parallax-y', '0px');

    window.addEventListener('scroll', () => {
        // Get scroll direction and amount
        const currentScrollY = window.scrollY;
        const direction = currentScrollY > lastScrollY ? 1 : -1;
        
        // Adjust this value to change parallax speed (0.1 = subtle, 0.4 = medium, 0.8 = dramatic)
        // Reduced speed for a more subtle effect
        const parallaxSpeed = 0.5;
        const scrollDiff = Math.abs(currentScrollY - lastScrollY) * parallaxSpeed;

        // Get current CSS variable value
        const currentParallaxY = parseInt(getComputedStyle(body).getPropertyValue('--parallax-y')) || 0;
        const newYPos = currentParallaxY + (direction * scrollDiff);

        // Update the CSS variable
        body.style.setProperty('--parallax-y', `${newYPos}px`);

        lastScrollY = currentScrollY;
    }, { passive: true });

    // Add a debug console log to verify script is running
    console.log('Parallax script initialized');
});