"""
Progress tracking system for video compression.
Tracks compression progress using file-based storage for simplicity.
"""
import os
import json
import tempfile
import uuid
from datetime import datetime
from pathlib import Path


class CompressionProgressTracker:
    """
    Tracks video compression progress and makes it available for AJAX polling.
    Uses JSON files in temp directory for simple cross-request communication.
    """
    
    def __init__(self, task_id=None):
        """
        Initialize progress tracker.
        
        Args:
            task_id: Optional task ID. If not provided, generates a new UUID.
        """
        self.task_id = task_id or str(uuid.uuid4())
        self.progress_file = Path(tempfile.gettempdir()) / f"video_compression_{self.task_id}.json"
        self.cancel_file = Path(tempfile.gettempdir()) / f"video_compression_cancel_{self.task_id}.flag"
        
    def update(self, percentage, stage, details=None):
        """
        Update compression progress.
        
        Args:
            percentage: Progress percentage (0-100)
            stage: Current stage name (e.g., "Analyzing", "Resizing", "Encoding")
            details: Optional additional details
        """
        data = {
            'task_id': self.task_id,
            'percentage': percentage,
            'stage': stage,
            'details': details or '',
            'timestamp': datetime.now().isoformat(),
            'status': 'running'
        }
        
        with open(self.progress_file, 'w') as f:
            json.dump(data, f)
    
    def complete(self, success=True, message=None, final_size_mb=None):
        """
        Mark compression as complete.
        
        Args:
            success: Whether compression succeeded
            message: Optional completion message
            final_size_mb: Final compressed file size
        """
        data = {
            'task_id': self.task_id,
            'percentage': 100,
            'stage': 'Complete' if success else 'Failed',
            'details': message or '',
            'timestamp': datetime.now().isoformat(),
            'status': 'complete' if success else 'error',
            'final_size_mb': final_size_mb
        }
        
        with open(self.progress_file, 'w') as f:
            json.dump(data, f)
    
    def get_progress(self):
        """
        Get current progress data.
        
        Returns:
            dict: Progress data or None if not found
        """
        try:
            if self.progress_file.exists():
                with open(self.progress_file, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return None
    
    def is_cancelled(self):
        """
        Check if compression has been cancelled.
        
        Returns:
            bool: True if cancellation requested
        """
        return self.cancel_file.exists()
    
    def cancel(self):
        """Request cancellation of compression."""
        self.cancel_file.touch()
        self.update(0, 'Cancelled', 'Compression cancelled by user')
    
    def cleanup(self):
        """Clean up progress and cancel files."""
        try:
            if self.progress_file.exists():
                self.progress_file.unlink()
            if self.cancel_file.exists():
                self.cancel_file.unlink()
        except Exception:
            pass
    
    @staticmethod
    def get_tracker_by_id(task_id):
        """
        Get a progress tracker by task ID.
        
        Args:
            task_id: Task ID to retrieve
            
        Returns:
            CompressionProgressTracker instance
        """
        return CompressionProgressTracker(task_id=task_id)
