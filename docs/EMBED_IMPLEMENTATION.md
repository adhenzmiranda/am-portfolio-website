# Embed Implementation for Different Frame Types

## Overview

This implementation enhances the portfolio website's project detail page to handle different types of social media embeds with varying frame dimensions and requirements.

## Key Changes Made

### 1. Template Updates (`templates/project_detail.html`)

- Added Instagram embed script (`//www.instagram.com/embed.js`)
- Added wrapper div structure for better embed handling
- Integrated with enhanced JavaScript handling
- Added main.js import for embed utilities

### 2. SCSS Styling Updates (`static/scss/scss-styles-pages/_project_details.scss`)

- **Flexible iframe handling**: Maintains 16:9 aspect ratio for video embeds (YouTube, Vimeo)
- **Instagram-specific styling**:
  - Max width: 540px (Instagram's standard)
  - Min width: 320px (responsive minimum)
  - Mobile-responsive adjustments
- **Twitter/X embed support**: Max width 550px with responsive behavior
- **TikTok embed support**: Max width 605px
- **Generic social media support**: Flexible width handling for Facebook, LinkedIn, etc.
- **Responsive classes**: Added `.responsive-embed` and `.social-embed-container` classes

### 3. JavaScript Enhancements (`static/js/main.js`)

- **EmbedHandler utility**: Centralized embed management
- **Dynamic initialization**: Handles embeds loaded after page load
- **Platform-specific handlers**: Instagram, Twitter, and generic social media
- **Responsive class management**: Automatically applies responsive styling
- **API integration**: Reinitializes platform-specific embed APIs

## Supported Embed Types

### Video Embeds (iframe-based)

- YouTube
- Vimeo
- Other iframe video players
- **Behavior**: Fixed 16:9 aspect ratio, full responsive width

### Social Media Embeds (blockquote-based)

- **Instagram**:
  - Max width: 540px
  - Min width: 320px (280px on mobile)
  - Maintains original aspect ratio
- **Twitter/X**:
  - Max width: 550px
  - Full responsive width on mobile
- **TikTok**:
  - Max width: 605px
  - Full responsive width on mobile
- **Facebook, LinkedIn**:
  - Max width: 550px
  - Responsive behavior

## Usage Instructions

### Adding Instagram Embeds

1. Get the embed code from Instagram (includes `<blockquote class="instagram-media">` and `<script>` tag)
2. Paste the complete embed code into the ProjectEmbed model's `embed_code` field
3. The system will automatically:
   - Load the Instagram script
   - Apply responsive styling
   - Handle different screen sizes appropriately

### Adding Other Social Media Embeds

- Twitter: Paste the complete embed code with `<blockquote class="twitter-tweet">`
- TikTok: Paste the complete embed code with TikTok's blockquote structure
- Facebook: Use Facebook's embed code
- The JavaScript handler will automatically detect and style these appropriately

### Adding Video Embeds

- YouTube/Vimeo: Paste iframe embed codes
- System maintains 16:9 aspect ratio automatically
- Full responsive width behavior

## Technical Details

### CSS Approach

- Uses `!important` declarations to override platform-specific inline styles
- Implements mobile-first responsive design
- Maintains platform-specific maximum widths while ensuring mobile compatibility

### JavaScript Approach

- Non-blocking initialization (works even if embeds load slowly)
- Multiple initialization attempts to catch dynamically loaded content
- Platform API integration for proper embed rendering

### Performance Considerations

- Scripts loaded asynchronously where possible
- Minimal DOM manipulation
- Efficient CSS targeting with specific selectors

## Browser Compatibility

- Modern browsers (ES6+ support)
- Mobile responsive design
- Instagram embed script handles cross-browser compatibility
- Fallback styling for unsupported features
