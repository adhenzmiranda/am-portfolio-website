"""
Custom field implementations for the projects app.
"""
from cloudinary.models import CloudinaryField
from cloudinary import uploader
import logging

logger = logging.getLogger(__name__)


class CompressedVideoField(CloudinaryField):
    """
    A CloudinaryField that automatically compresses videos before upload.
    
    This field intercepts the upload process and compresses videos larger
    than 100MB before sending them to Cloudinary.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize field without eager transformations."""
        # Remove transformation and eager settings to avoid Cloudinary processing
        kwargs.pop('transformation', None)
        kwargs.pop('eager', None)
        kwargs.pop('eager_async', None)
        
        super().__init__(*args, **kwargs)
    
    def upload_options(self, model_instance):
        """
        Override upload options to disable eager transformations.
        We're doing our own compression, so we don't need Cloudinary to process the video.
        """
        options = super().upload_options(model_instance)
        
        # Remove any eager transformation settings
        options.pop('eager', None)
        options.pop('eager_async', None)
        options.pop('transformation', None)
        
        # Set resource type to video
        options['resource_type'] = 'video'
        
        logger.info(f"[CUSTOM FIELD] Upload options: {options}")
        
        return options
    
    def pre_save(self, model_instance, add):
        """
        Override pre_save to compress video before Cloudinary upload.
        
        This is called right before the model is saved to the database,
        and is where CloudinaryField normally uploads the file.
        """
        file = getattr(model_instance, self.attname)
        
        logger.info(f"[CUSTOM FIELD] pre_save called, file type: {type(file)}")
        
        # Check if there's a file to upload
        if file:
            from .video_utils import process_video_upload, needs_compression
            from .progress_tracker import CompressionProgressTracker
            
            # Try to get size from different possible locations
            file_size = None
            if hasattr(file, 'size'):
                file_size = file.size
            elif hasattr(file, 'file') and hasattr(file.file, 'size'):
                file_size = file.file.size
            
            if file_size:
                logger.info(f"[CUSTOM FIELD] Video upload: size={file_size / (1024*1024):.2f}MB")
                
                # Compress if needed
                if needs_compression(file_size):
                    try:
                        # Create progress tracker
                        progress_tracker = CompressionProgressTracker()
                        task_id = progress_tracker.task_id
                        
                        logger.info(f"[CUSTOM FIELD] Starting compression [Task: {task_id}]...")
                        
                        # Store task ID in model instance for frontend to poll
                        model_instance._compression_task_id = task_id
                        
                        # Get quality preference from model instance (defaults to 'high')
                        quality = getattr(model_instance, 'compression_quality', 'high')
                        
                        compressed_file, was_compressed, orig_mb, final_mb, _ = process_video_upload(
                            file, 
                            progress_tracker=progress_tracker,
                            quality=quality
                        )
                        
                        if was_compressed:
                            logger.info(f"[CUSTOM FIELD] Compression successful: {orig_mb:.2f}MB → {final_mb:.2f}MB")
                            
                            # Replace the file with compressed version
                            setattr(model_instance, self.attname, compressed_file)
                            
                            # Store compression metadata on the model instance
                            model_instance.was_compressed = True
                            model_instance.original_size_mb = orig_mb
                            model_instance.compressed_size_mb = final_mb
                            
                            # Update file reference for parent's pre_save
                            file = compressed_file
                            
                    except Exception as e:
                        logger.error(f"[CUSTOM FIELD] Compression failed: {e}", exc_info=True)
                        from django.core.exceptions import ValidationError
                        raise ValidationError(f"Video compression failed: {str(e)}")
            else:
                logger.warning("[CUSTOM FIELD] Could not determine file size!")
        
        # Call parent's pre_save with potentially compressed file
        return super().pre_save(model_instance, add)
