#!/usr/bin/env python3
"""
Directory Utilities for RDA Automation System

This module provides utilities for ensuring all required directories exist
before the automation system starts, preventing '[Errno 2] No such file or directory' errors.
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Tuple
from logger_utils import configure_root_logging

def ensure_required_directories(base_dir: str = None, logger: logging.Logger = None) -> Dict[str, any]:
    """
    Ensure all required directories exist for the RDA automation system.
    
    Args:
        base_dir: Base directory path (defaults to current working directory)
        logger: Logger instance for output (optional)
    
    Returns:
        Dict with creation results: {'created': [...], 'existed': [...], 'errors': [...]}
    """
    if base_dir is None:
        base_dir = os.getcwd()
    
    if logger is None:
        logger = logging.getLogger(__name__)
    
    base_path = Path(base_dir)
    
    # Define all required directories
    required_directories = [
        # Core directories
        "src/python/downloaded_files",
        "src/python/logs", 
        "src/python/data",
        "src/python/data/backups",
        "src/python/templates",
        "src/python/incoming",
        "src/python/control_files",
        
        # Root level directories
        "downloaded_files",
        "logs",
        "data",
        "data/reports",
        "results",
        "results/summaries",
        "templates",
        "control_files",
        
        # Crisis resolution directories
        "downloaded_files/CRISIS_RESOLUTION",
        "src/python/downloaded_files/CRISIS_RESOLUTION",
    ]
    
    results = {
        'created': [],
        'existed': [],
        'errors': []
    }
    
    for dir_path in required_directories:
        full_path = base_path / dir_path
        
        try:
            if full_path.exists():
                results['existed'].append(str(dir_path))
                logger.debug(f"Directory exists: {dir_path}")
            else:
                full_path.mkdir(parents=True, exist_ok=True)
                results['created'].append(str(dir_path))
                logger.info(f"Created directory: {dir_path}")
                
        except Exception as e:
            error_msg = f"{dir_path}: {str(e)}"
            results['errors'].append(error_msg)
            logger.error(f"Error creating directory {dir_path}: {e}")
    
    return results

def ensure_download_directory_structure(base_download_dir: str = "downloaded_files",
                                      regions: List[str] = None,
                                      variables: List[str] = None,
                                      logger: logging.Logger = None,
                                      create_subdirectories: bool = False) -> Dict[str, any]:
    """
    Ensure download directory structure exists for specified regions and variables.
    
    Args:
        base_download_dir: Base download directory path
        regions: List of region codes (e.g., ['CISO', 'ERCOT', 'PJM'])
        variables: List of weather variables (e.g., ['dswrf', 'wind', 'temp', 'rain'])
        logger: Logger instance for output (optional)
        create_subdirectories: Whether to create region/variable subdirectories (default: False)
                              Only set to True when actually processing completed requests
    
    Returns:
        Dict with creation results
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    base_path = Path(base_download_dir)
    
    results = {
        'created': [],
        'existed': [],
        'errors': []
    }
    
    # Create base download directory
    try:
        if not base_path.exists():
            base_path.mkdir(parents=True, exist_ok=True)
            results['created'].append(str(base_download_dir))
            logger.info(f"Created base download directory: {base_download_dir}")
        else:
            results['existed'].append(str(base_download_dir))
    except Exception as e:
        results['errors'].append(f"{base_download_dir}: {str(e)}")
        logger.error(f"Error creating base download directory: {e}")
        return results
    
    # Only create region/variable subdirectories if explicitly requested
    # This prevents premature directory creation during startup
    if create_subdirectories and regions is not None and variables is not None:
        logger.info(f"Creating region/variable subdirectories for {len(regions)} regions and {len(variables)} variables")
        
        # Create region/variable subdirectories
        for region in regions:
            region_path = base_path / region
            
            try:
                if not region_path.exists():
                    region_path.mkdir(parents=True, exist_ok=True)
                    results['created'].append(f"{base_download_dir}/{region}")
                    logger.debug(f"Created region directory: {region}")
                else:
                    results['existed'].append(f"{base_download_dir}/{region}")
                
                # Create variable subdirectories
                for variable in variables:
                    var_path = region_path / variable
                    
                    try:
                        if not var_path.exists():
                            var_path.mkdir(parents=True, exist_ok=True)
                            results['created'].append(f"{base_download_dir}/{region}/{variable}")
                            logger.debug(f"Created variable directory: {region}/{variable}")
                        else:
                            results['existed'].append(f"{base_download_dir}/{region}/{variable}")
                            
                    except Exception as e:
                        error_msg = f"{base_download_dir}/{region}/{variable}: {str(e)}"
                        results['errors'].append(error_msg)
                        logger.error(f"Error creating variable directory {region}/{variable}: {e}")
                        
            except Exception as e:
                error_msg = f"{base_download_dir}/{region}: {str(e)}"
                results['errors'].append(error_msg)
                logger.error(f"Error creating region directory {region}: {e}")
    else:
        logger.debug(f"Skipping region/variable subdirectory creation during startup (create_subdirectories={create_subdirectories})")
    
    return results

def create_download_directory_path(base_dir: str, region: str, variable: str, 
                                 ensure_exists: bool = True, 
                                 logger: logging.Logger = None) -> str:
    """
    Create and return the standardized download directory path for a region/variable combination.
    
    Args:
        base_dir: Base download directory
        region: Region code (e.g., 'CISO')
        variable: Weather variable (e.g., 'dswrf')
        ensure_exists: Whether to create the directory if it doesn't exist
        logger: Logger instance for output (optional)
    
    Returns:
        String path to the download directory
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    # Standardize inputs
    region = region.upper() if region else "UNKNOWN"
    variable = variable.lower() if variable else "unknown"
    
    # Create path
    download_path = os.path.join(base_dir, region, variable)
    
    if ensure_exists:
        try:
            os.makedirs(download_path, exist_ok=True)
            logger.debug(f"Ensured directory exists: {download_path}")
        except Exception as e:
            logger.error(f"Error creating download directory {download_path}: {e}")
            # Return path anyway, let calling code handle the error
    
    return download_path

def initialize_automation_directories(config: Dict = None, logger: logging.Logger = None) -> bool:
    """
    Initialize all directories required by the automation system based on configuration.
    
    Args:
        config: Configuration dictionary with directory settings
        logger: Logger instance for output (optional)
    
    Returns:
        True if all directories were created successfully, False otherwise
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    if config is None:
        config = {}
    
    logger.info("Initializing automation system directories...")
    
    # Get directory configuration
    directories_config = config.get('directories', {})
    base_download_dir = directories_config.get('base_download_dir', 'downloaded_files')
    logs_dir = directories_config.get('logs_dir', 'logs')
    data_dir = directories_config.get('data_dir', 'data')
    
    success = True
    
    # 1. Ensure core required directories
    core_results = ensure_required_directories(logger=logger)
    if core_results['errors']:
        logger.error(f"Errors creating core directories: {len(core_results['errors'])}")
        success = False
    else:
        logger.info(f"Core directories: {len(core_results['created'])} created, {len(core_results['existed'])} existed")
    
    # 2. Ensure download directory structure (base directory only, no subdirectories during startup)
    download_results = ensure_download_directory_structure(
        base_download_dir=base_download_dir,
        logger=logger,
        create_subdirectories=False  # Prevent premature directory creation during startup
    )
    if download_results['errors']:
        logger.error(f"Errors creating download directories: {len(download_results['errors'])}")
        success = False
    else:
        logger.info(f"Download directories: {len(download_results['created'])} created, {len(download_results['existed'])} existed")
    
    # 3. Create .gitkeep files for empty directories
    try:
        _create_gitkeep_files([
            base_download_dir,
            logs_dir,
            data_dir,
            "templates",
            "results/summaries"
        ], logger)
    except Exception as e:
        logger.warning(f"Error creating .gitkeep files: {e}")
        # Don't fail initialization for .gitkeep errors
    
    if success:
        logger.info("✅ All automation directories initialized successfully")
    else:
        logger.error("❌ Some errors occurred during directory initialization")
    
    return success

def _create_gitkeep_files(directories: List[str], logger: logging.Logger):
    """Create .gitkeep files in specified directories to preserve structure in git."""
    for dir_path in directories:
        gitkeep_path = Path(dir_path) / ".gitkeep"
        try:
            if not gitkeep_path.exists() and Path(dir_path).exists():
                gitkeep_path.touch()
                logger.debug(f"Created .gitkeep in {dir_path}")
        except Exception as e:
            logger.warning(f"Could not create .gitkeep in {dir_path}: {e}")

# Convenience function for easy import and use
def setup_directories(config: Dict = None, logger: logging.Logger = None) -> bool:
    """
    Convenience function to set up all required directories.
    This is the main function that should be called by automation components.
    
    Args:
        config: Configuration dictionary
        logger: Logger instance
    
    Returns:
        True if setup was successful
    """
    return initialize_automation_directories(config, logger)

if __name__ == "__main__":
    # Allow running as standalone script
    import logging

    configure_root_logging(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    print("🔧 Setting up RDA Automation System directories...")
    success = setup_directories(logger=logger)
    
    if success:
        print("✅ Directory setup completed successfully!")
    else:
        print("❌ Directory setup completed with errors. Check logs for details.")