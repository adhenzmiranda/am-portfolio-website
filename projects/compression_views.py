"""
Views for handling video compression progress tracking.
"""
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_http_methods
from .progress_tracker import CompressionProgressTracker
import json
import os
import tempfile
import glob

@staff_member_required
def compression_progress(request, task_id):
    """
    Return the current compression progress for a task.
    """
    tracker = CompressionProgressTracker.get_tracker_by_id(task_id)
    progress_data = tracker.get_progress()
    
    if progress_data:
        return JsonResponse(progress_data)
    else:
        return JsonResponse({
            'task_id': task_id,
            'percentage': 0,
            'stage': 'Unknown',
            'details': 'No progress data found',
            'status': 'unknown'
        })


@staff_member_required
@require_http_methods(["POST"])
def cancel_compression(request, task_id):
    """
    Cancel a compression task.
    """
    tracker = CompressionProgressTracker.get_tracker_by_id(task_id)
    tracker.cancel()
    
    return JsonResponse({
        'success': True,
        'message': 'Compression cancellation requested'
    })


@staff_member_required
def get_latest_task(request):
    """
    Get the most recent compression task ID.
    This is used by the frontend to start polling for progress.
    """
    temp_dir = tempfile.gettempdir()
    pattern = os.path.join(temp_dir, 'compression_*.json')
    progress_files = glob.glob(pattern)
    
    if not progress_files:
        return JsonResponse({
            'task_id': None,
            'message': 'No active compression tasks'
        })
    
    # Get the most recent file
    latest_file = max(progress_files, key=os.path.getctime)
    task_id = os.path.basename(latest_file).replace('compression_', '').replace('.json', '')
    
    return JsonResponse({
        'task_id': task_id,
        'found': True
    })
