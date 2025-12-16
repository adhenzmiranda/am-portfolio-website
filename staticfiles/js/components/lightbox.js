class Lightbox {
    constructor() {
        this.currentIndex = 0;
        this.images = [];
        this.lightboxEl = null;
        this.imageEl = null;
        this.captionEl = null;
        this.counterEl = null;
        this.init();
    }

    init() {
        // Create lightbox HTML
        this.createLightbox();
        
        // Get all gallery images
        this.setupGalleryImages();
        
        // Setup event listeners
        this.setupEventListeners();
    }

    createLightbox() {
        const lightboxHTML = `
            <div class="lightbox" id="lightbox">
                <button class="lightbox-close" aria-label="Close lightbox">&times;</button>
                <div class="lightbox-counter"></div>
                <div class="lightbox-content">
                    <div class="lightbox-media-container"></div>
                    <div class="lightbox-caption"></div>
                </div>
                <button class="lightbox-nav lightbox-prev" aria-label="Previous item">&#8249;</button>
                <button class="lightbox-nav lightbox-next" aria-label="Next item">&#8250;</button>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', lightboxHTML);
        
        this.lightboxEl = document.getElementById('lightbox');
        this.mediaContainer = this.lightboxEl.querySelector('.lightbox-media-container');
        this.captionEl = this.lightboxEl.querySelector('.lightbox-caption');
        this.counterEl = this.lightboxEl.querySelector('.lightbox-counter');
    }

    setupGalleryImages() {
        // Get all media items from different sections
        const videoItems = document.querySelectorAll('.video-item');
        const embedItems = document.querySelectorAll('.embed-item');
        const galleryItems = document.querySelectorAll('.gallery-item');
        
        let allItems = [];
        
        // Process project videos FIRST
        videoItems.forEach((item) => {
            const video = item.querySelector('video');
            const caption = item.querySelector('.video-caption')?.textContent || '';
            
            if (video) {
                allItems.push({
                    element: item,
                    data: {
                        type: 'video',
                        src: video.querySelector('source')?.src || video.src,
                        poster: video.poster,
                        caption: caption
                    }
                });
            }
        });
        
        // Process project embeds SECOND
        embedItems.forEach((item) => {
            const iframe = item.querySelector('iframe');
            const caption = item.querySelector('.embed-caption')?.textContent || '';
            
            if (iframe) {
                allItems.push({
                    element: item,
                    data: {
                        type: 'embed',
                        src: iframe.src,
                        caption: caption
                    }
                });
            }
        });
        
        // Process gallery images LAST
        galleryItems.forEach((item) => {
            const img = item.querySelector('img');
            const caption = item.querySelector('.gallery-caption')?.textContent || '';
            
            if (img) {
                allItems.push({
                    element: item,
                    data: {
                        type: 'image',
                        src: img.src,
                        alt: img.alt,
                        caption: caption
                    }
                });
            }
        });
        
        // Setup click handlers and store data
        allItems.forEach((item, index) => {
            this.images.push(item.data);
            
            // Make item clickable
            item.element.style.cursor = 'pointer';
            item.element.addEventListener('click', () => this.open(index));
        });
    }

    setupEventListeners() {
        // Close button
        this.lightboxEl.querySelector('.lightbox-close').addEventListener('click', () => this.close());
        
        // Navigation buttons
        this.lightboxEl.querySelector('.lightbox-prev').addEventListener('click', () => this.prev());
        this.lightboxEl.querySelector('.lightbox-next').addEventListener('click', () => this.next());
        
        // Click outside image to close
        this.lightboxEl.addEventListener('click', (e) => {
            if (e.target === this.lightboxEl) {
                this.close();
            }
        });
        
        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            if (!this.lightboxEl.classList.contains('active')) return;
            
            switch(e.key) {
                case 'Escape':
                    this.close();
                    break;
                case 'ArrowLeft':
                    this.prev();
                    break;
                case 'ArrowRight':
                    this.next();
                    break;
            }
        });
    }

    open(index) {
        this.currentIndex = index;
        this.updateImage();
        this.lightboxEl.classList.add('active');
        document.body.style.overflow = 'hidden'; // Prevent background scrolling
    }

    close() {
        this.lightboxEl.classList.remove('active');
        document.body.style.overflow = ''; // Restore scrolling
    }

    next() {
        this.currentIndex = (this.currentIndex + 1) % this.images.length;
        this.updateImage();
    }

    prev() {
        this.currentIndex = (this.currentIndex - 1 + this.images.length) % this.images.length;
        this.updateImage();
    }

    updateImage() {
        const media = this.images[this.currentIndex];
        
        // Clear previous content
        this.mediaContainer.innerHTML = '';
        
        // Create appropriate media element based on type
        if (media.type === 'image') {
            const img = document.createElement('img');
            img.className = 'lightbox-image';
            img.src = media.src;
            img.alt = media.alt || '';
            this.mediaContainer.appendChild(img);
        } 
        else if (media.type === 'video') {
            const video = document.createElement('video');
            video.className = 'lightbox-video';
            video.controls = true;
            video.autoplay = true;
            if (media.poster) video.poster = media.poster;
            
            const source = document.createElement('source');
            source.src = media.src;
            source.type = 'video/mp4';
            video.appendChild(source);
            
            this.mediaContainer.appendChild(video);
        }
        else if (media.type === 'embed') {
            const iframe = document.createElement('iframe');
            iframe.className = 'lightbox-embed';
            iframe.src = media.src;
            iframe.setAttribute('frameborder', '0');
            iframe.setAttribute('allowfullscreen', '');
            iframe.setAttribute('allow', 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture');
            this.mediaContainer.appendChild(iframe);
        }
        
        this.captionEl.textContent = media.caption;
        this.counterEl.textContent = `${this.currentIndex + 1} / ${this.images.length}`;
        
        // Update navigation button states
        const prevBtn = this.lightboxEl.querySelector('.lightbox-prev');
        const nextBtn = this.lightboxEl.querySelector('.lightbox-next');
        
        // Optionally disable buttons at ends (remove these lines for infinite loop)
        // prevBtn.disabled = this.currentIndex === 0;
        // nextBtn.disabled = this.currentIndex === this.images.length - 1;
    }
}

// Initialize lightbox when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const hasMedia = document.querySelector('.gallery-item, .video-item, .embed-item');
    if (hasMedia) {
        new Lightbox();
    }
});
