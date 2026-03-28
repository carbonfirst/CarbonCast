#!/usr/bin/env python3
"""
Download Automation Patch for RDA Automation System

This patch ensures that completed requests are automatically downloaded
and purged to prevent the 10-request limit issue from recurring.

Apply this patch by running: python download_automation_patch.py
"""

import os
import sys
import logging
from datetime import datetime

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from logger_utils import configure_root_logging

try:
    import rdams_client
    from region_detection_utils import extract_region_and_variable_from_request, create_download_directory_path
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)


def download_and_purge_completed_requests():
    """Download and purge all completed requests automatically."""
    logger = logging.getLogger('download_automation_patch')
    
    try:
        # Get current RDA status
        status_result = rdams_client.get_status()
        if not status_result or 'data' not in status_result:
            return False
        
        completed_requests = [
            req for req in status_result['data'] 
            if req.get('status', '').lower() == 'completed'
        ]
        
        if not completed_requests:
            logger.info("No completed requests to process")
            return True
        
        logger.info(f"Processing {len(completed_requests)} completed requests...")
        
        for request in completed_requests:
            request_id = str(request.get('request_index', ''))
            
            try:
                # Extract region and variable
                region, variable = extract_region_and_variable_from_request(request)
                
                # Create download directory
                if region != "UNKNOWN" and variable != "unknown":
                    download_dir = create_download_directory_path("downloaded_files", region, variable)
                else:
                    download_dir = os.path.join("downloaded_files", "AUTO_DOWNLOAD", request_id)
                
                os.makedirs(download_dir, exist_ok=True)
                
                # Download
                logger.info(f"Downloading request {request_id} to {download_dir}")
                download_result = rdams_client.download(request_id, download_dir + "/")
                
                if download_result:
                    logger.info(f"Download successful for request {request_id}")
                    
                    # Purge after successful download
                    logger.info(f"Purging request {request_id}")
                    purge_result = rdams_client.purge_request(str(request_id))
                    
                    if purge_result:
                        logger.info(f"Successfully purged request {request_id}")
                    else:
                        logger.warning(f"Failed to purge request {request_id}")
                else:
                    logger.error(f"Download failed for request {request_id}")
                    
            except Exception as e:
                logger.error(f"Error processing request {request_id}: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error in download_and_purge_completed_requests: {e}")
        return False


if __name__ == '__main__':
    configure_root_logging(level=logging.INFO)
    success = download_and_purge_completed_requests()
    sys.exit(0 if success else 1)
