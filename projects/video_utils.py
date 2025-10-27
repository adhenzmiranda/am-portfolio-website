"""
Video compression utilities for project videos.
Automatically compresses videos before uploading to Cloudinary.
"""
import os
import tempfile
from pathlib import Path
from moviepy import VideoFileClip
from django.core.files import File
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
import logging

logger = logging.getLogger(__name__)

# Maximum file size in bytes (100MB)
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# Target settings for compression
TARGET_RESOLUTION = (1280, 720)  # 720p
TARGET_BITRATE = "1000k"  # 1Mbps
TARGET_FPS = 30


def get_video_info(video_path):
    """Get basic information about a video file."""
    try:
        clip = VideoFileClip(str(video_path))
        info = {
            'duration': clip.duration,
            'fps': clip.fps,
            'size': clip.size,  # (width, height)
            'file_size': os.path.getsize(video_path)
        }
        clip.close()
        return info
    except Exception as e:
        logger.error(f"Error getting video info: {e}")
        return None


def needs_compression(file_size, video_info=None):
    """Determine if video needs compression."""
    # Always compress if over 100MB
    if file_size > MAX_FILE_SIZE:
        return True
    
    # Also compress if resolution is very high (4K, etc.)
    if video_info and video_info.get('size'):
        width, height = video_info['size']
        if width > 1920 or height > 1080:
            return True
    
    return False


def compress_video(input_file, output_path=None, target_size_mb=95):
    """
    Compress video to meet size requirements.
    
    Args:
        input_file: Django uploaded file object or file path
        output_path: Optional output path (creates temp file if not provided)
        target_size_mb: Target file size in MB (default 95MB to leave buffer)
    
    Returns:
        Path to compressed video file
    """
    # Create temporary file for input if needed
    if hasattr(input_file, 'temporary_file_path'):
        input_path = input_file.temporary_file_path()
    elif hasattr(input_file, 'read'):
        # It's an in-memory file, save to temp
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
            for chunk in input_file.chunks():
                tmp.write(chunk)
            input_path = tmp.name
    else:
        input_path = str(input_file)
    
    # Create output path if not provided
    if output_path is None:
        output_path = tempfile.mktemp(suffix='_compressed.mp4')
    
    try:
        logger.info(f"Starting video compression: {input_path}")
        
        # Load video
        clip = VideoFileClip(input_path)
        
        # Get original dimensions
        original_width, original_height = clip.size
        original_size_mb = os.path.getsize(input_path) / (1024 * 1024)
        
        logger.info(f"Original: {original_width}x{original_height}, {original_size_mb:.2f}MB")
        
        # Calculate new dimensions maintaining aspect ratio
        target_width, target_height = TARGET_RESOLUTION
        aspect_ratio = original_width / original_height
        
        if aspect_ratio > (target_width / target_height):
            # Width is limiting factor
            new_width = min(target_width, original_width)
            new_height = int(new_width / aspect_ratio)
        else:
            # Height is limiting factor
            new_height = min(target_height, original_height)
            new_width = int(new_height * aspect_ratio)
        
        # Ensure even dimensions (required by some codecs)
        new_width = new_width - (new_width % 2)
        new_height = new_height - (new_height % 2)
        
        logger.info(f"Compressing to: {new_width}x{new_height}")
        
        # Resize video (moviepy 2.x uses .resized() not .resize())
        resized_clip = clip.resized((new_width, new_height))
        
        # Reduce FPS if needed
        target_fps = min(TARGET_FPS, clip.fps)
        
        # Write compressed video
        resized_clip.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            fps=target_fps,
            bitrate=TARGET_BITRATE,
            preset='medium',  # Balance between speed and compression
            threads=4,
            logger=None  # Suppress moviepy's verbose output
        )
        
        # Clean up
        resized_clip.close()
        clip.close()
        
        # Check final size
        final_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        logger.info(f"Compression complete: {final_size_mb:.2f}MB")
        
        # If still too large, try more aggressive compression
        if final_size_mb > target_size_mb:
            logger.warning(f"File still too large ({final_size_mb:.2f}MB), applying aggressive compression")
            return compress_video_aggressive(input_path, output_path, target_size_mb)
        
        return output_path
        
    except Exception as e:
        logger.error(f"Error compressing video: {e}")
        # Clean up on error
        if output_path and os.path.exists(output_path):
            os.remove(output_path)
        raise


def compress_video_aggressive(input_path, output_path, target_size_mb=95):
    """
    More aggressive compression for very large files.
    """
    try:
        clip = VideoFileClip(input_path)
        
        # More aggressive settings
        new_width = 1024
        new_height = int(1024 / (clip.size[0] / clip.size[1]))
        new_height = new_height - (new_height % 2)
        
        resized_clip = clip.resized((new_width, new_height))
        
        resized_clip.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            fps=24,  # Lower FPS
            bitrate='800k',  # Lower bitrate
            preset='fast',
            threads=4,
            logger=None
        )
        
        resized_clip.close()
        clip.close()
        
        final_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        logger.info(f"Aggressive compression complete: {final_size_mb:.2f}MB")
        
        return output_path
        
    except Exception as e:
        logger.error(f"Error in aggressive compression: {e}")
        raise


def process_video_upload(uploaded_file):
    """
    Main function to process uploaded video.
    Compresses if needed, returns file ready for Cloudinary upload.
    
    Args:
        uploaded_file: Django UploadedFile object
    
    Returns:
        Tuple of (file_object, was_compressed, original_size_mb, final_size_mb)
    """
    original_size = uploaded_file.size
    original_size_mb = original_size / (1024 * 1024)
    
    logger.info(f"Processing video upload: {uploaded_file.name} ({original_size_mb:.2f}MB)")
    
    # Check if compression is needed
    if original_size <= MAX_FILE_SIZE:
        logger.info("Video is under size limit, no compression needed")
        return (uploaded_file, False, original_size_mb, original_size_mb)
    
    # Compress the video
    compressed_path = None
    try:
        logger.info(f"Starting compression for {original_size_mb:.2f}MB file...")
        compressed_path = compress_video(uploaded_file)
        
        final_size_mb = os.path.getsize(compressed_path) / (1024 * 1024)
        logger.info(f"Compression successful: {original_size_mb:.2f}MB → {final_size_mb:.2f}MB")
        
        # Open compressed file and create Django File object
        with open(compressed_path, 'rb') as f:
            from django.core.files.uploadedfile import InMemoryUploadedFile
            import io
            
            # Read compressed file into memory
            file_content = f.read()
            file_io = io.BytesIO(file_content)
            
            # Create new uploaded file object
            compressed_uploaded_file = InMemoryUploadedFile(
                file_io,
                field_name='video',
                name=uploaded_file.name,
                content_type='video/mp4',
                size=len(file_content),
                charset=None
            )
            
            return (compressed_uploaded_file, True, original_size_mb, final_size_mb)
            
    except Exception as e:
        logger.error(f"Video compression failed: {e}", exc_info=True)
        raise Exception(f"Failed to compress video: {str(e)}")
    finally:
        # Clean up temp file
        if compressed_path and os.path.exists(compressed_path):
            try:
                os.remove(compressed_path)
                logger.info("Cleaned up temporary compressed file")
            except:
                pass
