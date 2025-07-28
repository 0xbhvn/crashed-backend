"""
Logbook API routes for Crash Monitor.

This module defines API endpoints for downloading crash game analysis logs.
"""

import logging
import os
from aiohttp import web

from ... import config
from ..utils import error_response

# Configure logging
logger = logging.getLogger(__name__)

# Define routes
routes = web.RouteTableDef()


@routes.get('/api/logbook/download')
async def download_logbook(request: web.Request) -> web.Response:
    """
    Download the crash game analysis log CSV file.
    
    Returns:
        CSV file download or error response if file doesn't exist
    """
    try:
        # Get the CSV file path from config
        csv_path = config.ANALYSIS_LOG_PATH
        
        # Check if file exists
        if not os.path.exists(csv_path):
            return error_response("Logbook file not found. No games have been analyzed yet.", 404)
        
        # Check if file is readable
        if not os.access(csv_path, os.R_OK):
            return error_response("Logbook file is not readable.", 403)
        
        # Get file size for headers
        file_size = os.path.getsize(csv_path)
        
        # Create response with file
        response = web.FileResponse(
            path=csv_path,
            headers={
                'Content-Type': 'text/csv',
                'Content-Disposition': 'attachment; filename="crash_analysis_log.csv"',
                'Content-Length': str(file_size)
            }
        )
        
        logger.info(f"Logbook CSV download requested - file size: {file_size} bytes")
        
        return response
        
    except Exception as e:
        logger.error(f"Error downloading logbook: {e}")
        return error_response(f"Failed to download logbook: {str(e)}", 500)


@routes.get('/api/logbook/info')
async def get_logbook_info(request: web.Request) -> web.Response:
    """
    Get information about the logbook file without downloading it.
    
    Returns:
        JSON with file info (exists, size, last modified, line count)
    """
    try:
        csv_path = config.ANALYSIS_LOG_PATH
        
        info = {
            "exists": os.path.exists(csv_path),
            "path": csv_path,
            "google_sheets_enabled": bool(config.GOOGLE_SHEETS_CREDENTIALS and config.GOOGLE_SHEETS_ID)
        }
        
        if info["exists"]:
            stat = os.stat(csv_path)
            info.update({
                "size_bytes": stat.st_size,
                "size_human": _format_bytes(stat.st_size),
                "last_modified": stat.st_mtime,
                "last_modified_iso": _timestamp_to_iso(stat.st_mtime)
            })
            
            # Count lines (entries) in the file
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    line_count = sum(1 for _ in f)
                    # Subtract 1 for header if file has content
                    entry_count = max(0, line_count - 1) if line_count > 0 else 0
                    info["entry_count"] = entry_count
            except Exception as e:
                logger.warning(f"Could not count entries in logbook: {e}")
                info["entry_count"] = None
        
        return web.json_response(info)
        
    except Exception as e:
        logger.error(f"Error getting logbook info: {e}")
        return error_response(f"Failed to get logbook info: {str(e)}", 500)


def _format_bytes(size: int) -> str:
    """Format bytes to human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"


def _timestamp_to_iso(timestamp: float) -> str:
    """Convert timestamp to ISO format string."""
    from datetime import datetime
    return datetime.fromtimestamp(timestamp).isoformat()