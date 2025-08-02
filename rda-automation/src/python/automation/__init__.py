"""
RDA Automation System

This package provides automation functionality for the RDA (Research Data Archive) system,
including error management, request processing, and system monitoring capabilities.

Modules:
- error_manager: Automatic error detection and purging functionality
"""

from .error_manager import ErrorManager, ErrorRequest, PurgeConfig, create_error_manager

__version__ = "1.0.0"
__all__ = ["ErrorManager", "ErrorRequest", "PurgeConfig", "create_error_manager"]