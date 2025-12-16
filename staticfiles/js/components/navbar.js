function initializeNavbar() {
    const toggleNavButton = document.querySelector('.toggle-nav-btn img');
    const navbarLinks = document.querySelector('.navbar-links');

    if (!toggleNavButton || !navbarLinks) {
        console.error('Required elements not found');
        return;
    }

    let isMenuOpen = false;

    toggleNavButton.parentElement.addEventListener('click', () => {
        if (!isMenuOpen) {
            // toggleNavButton.src = '/static/assets/images/navbar/close.png';
            toggleNavButton.parentElement.classList.add('rotated');
            navbarLinks.classList.add('active');
            isMenuOpen = true;
        } else {
            // toggleNavButton.src = '/static/assets/images/navbar/hamburger.png';
            toggleNavButton.parentElement.classList.remove('rotated');
            navbarLinks.classList.remove('active');
            isMenuOpen = false;
        }
    });
}

// Initialize when script loads
initializeNavbar();