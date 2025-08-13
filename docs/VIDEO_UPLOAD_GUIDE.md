# Video Upload Guidelines

## File Size Limits

**Maximum file size: ~100MB (104,857,600 bytes)**

If you encounter the "File size too large" error, you need to compress your video before uploading.

## Recommended Video Specifications

### For Best Results:

- **Resolution**: Up to 1280x720 (720p)
- **Bitrate**: 1-2 Mbps
- **Format**: MP4 (H.264 codec)
- **Frame Rate**: 30fps or less
- **Duration**: Keep under 5 minutes for web optimization

### Supported Formats:

- MP4 (recommended)
- MOV
- AVI
- WMV
- MKV
- WebM

## How to Compress Large Videos

### Option 1: Online Tools (Free)

1. **CloudConvert** (https://cloudconvert.com)
   - Upload your video
   - Choose MP4 output
   - Set quality to "Medium" or "720p"
2. **Clideo** (https://clideo.com/compress-video)
   - Simple drag-and-drop interface
   - Automatic compression

### Option 2: Desktop Software

1. **HandBrake** (Free, Open Source)

   - Download from handbrake.fr
   - Use "Web Optimized" preset
   - Adjust quality slider to 22-24

2. **VLC Media Player** (Free)
   - Media > Convert/Save
   - Choose profile: Video - H.264 + MP3 (MP4)
   - Adjust bitrate in settings

### Option 3: Mobile Apps

- **Video Compressor** (Android/iOS)
- **Video Compress** (iOS)
- **Video Dieter 2** (Android)

## Quick Compression Tips

### If your video is over 100MB:

1. **Reduce resolution**: 1080p → 720p can cut file size by 50%
2. **Lower bitrate**: Try 1Mbps for social media videos
3. **Trim duration**: Remove unnecessary parts
4. **Reduce frame rate**: 60fps → 30fps saves space

### For Social Media Videos:

- Instagram/Facebook videos: Usually already optimized
- Use "Share" → "Save Video" to get compressed version
- Download in lower quality when possible

## What Happens After Upload

Once uploaded successfully, Cloudinary will:

- ✅ Further optimize your video for web playback
- ✅ Generate multiple formats for browser compatibility
- ✅ Create responsive versions for different devices
- ✅ Ensure fast loading with CDN delivery

## Troubleshooting

### "File size too large" Error:

- Compress your video using methods above
- Check file size before upload (should be under 100MB)
- Consider splitting long videos into shorter segments

### Upload Timeout:

- Check your internet connection
- Try uploading during off-peak hours
- Compress the video further

### Video Not Playing:

- Ensure format is supported (MP4 recommended)
- Clear browser cache and try again
- Check that video isn't corrupted

## Need Help?

If you continue having issues:

1. Check the video file properties (right-click > Properties)
2. Ensure file size is under 100MB
3. Try converting to MP4 format
4. Test with a shorter video clip first

Remember: The system will automatically optimize your videos for web playback, so you don't need perfect settings - just get under the 100MB limit!
