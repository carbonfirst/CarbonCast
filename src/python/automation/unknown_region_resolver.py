#!/usr/bin/env python3
"""
Enhanced Unknown Region Resolver for RDA Automation System

This module provides comprehensive unknown region detection and resolution capabilities
including multiple resolution strategies, fallback naming, and database integration.

Key Features:
- Multi-strategy region resolution (robust mapping, control file parsing, geographic fallback)
- Fallback naming system (REQ_001, REQ_002, etc.)
- Database integration for tracking resolution attempts
- Manual override capabilities
- Comprehensive logging and metrics
"""

import os
import sys
import json
import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import threading

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger_utils import get_logger

from coordinate_utils import get_region_and_variable_from_request_enhanced


@dataclass
class ResolutionAttempt:
    """Data class for tracking resolution attempts."""
    request_id: str
    request_index: int
    strategy: str
    result_region: str
    result_variable: str
    confidence: float
    timestamp: str
    success: bool
    error_message: Optional[str] = None
    details: Dict[str, Any] = None


@dataclass
class UnknownRegionRequest:
    """Data class for unknown region request information."""
    request_id: str
    request_index: int
    rinfo: str
    subset_note: str
    raw_response: Dict[str, Any]
    assigned_name: Optional[str] = None
    resolution_attempts: List[ResolutionAttempt] = None
    resolved_region: Optional[str] = None
    resolved_variable: Optional[str] = None
    manual_override: bool = False
    created_at: str = None
    updated_at: str = None

    def __post_init__(self):
        if self.resolution_attempts is None:
            self.resolution_attempts = []
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.updated_at is None:
            self.updated_at = datetime.now().isoformat()


class EnhancedUnknownRegionResolver:
    """
    Enhanced unknown region resolver with multiple resolution strategies.
    
    Provides comprehensive unknown region detection and resolution using:
    1. Robust region mapping with multiple tolerance levels
    2. Control file coordinate parsing
    3. Database lookup of historical mappings
    4. Geographic fallback matching
    5. Fallback naming system (REQ_001, etc.)
    """
    
    def __init__(self, db_path: str = "src/python/data/automation_state.db"):
        """
        Initialize the Enhanced Unknown Region Resolver.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.logger = self._setup_logging()
        self.resolver_lock = threading.Lock()
        
        # Initialize database schema
        self._initialize_database()
        
        # Resolution statistics
        self.resolution_stats = {
            'total_attempts': 0,
            'successful_resolutions': 0,
            'fallback_assignments': 0,
            'manual_overrides': 0,
            'last_resolution_time': None
        }
        
        self.logger.info("Enhanced Unknown Region Resolver initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('rda_automation.unknown_region_resolver', level=logging.INFO)
    
    def _initialize_database(self):
        """Initialize database tables for unknown region tracking."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Unknown regions tracking table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS unknown_regions_tracking (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        request_id TEXT NOT NULL,
                        request_index INTEGER NOT NULL,
                        rinfo TEXT,
                        subset_note TEXT,
                        raw_response TEXT,
                        assigned_name TEXT,
                        resolved_region TEXT,
                        resolved_variable TEXT,
                        manual_override BOOLEAN DEFAULT FALSE,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(request_id)
                    )
                """)
                
                # Resolution attempts tracking table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS resolution_attempts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        request_id TEXT NOT NULL,
                        request_index INTEGER NOT NULL,
                        strategy TEXT NOT NULL,
                        result_region TEXT,
                        result_variable TEXT,
                        confidence REAL DEFAULT 0.0,
                        success BOOLEAN DEFAULT FALSE,
                        error_message TEXT,
                        details TEXT,
                        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (request_id) REFERENCES unknown_regions_tracking(request_id)
                    )
                """)
                
                # Resolution history table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS resolution_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        request_id TEXT NOT NULL,
                        old_region TEXT,
                        new_region TEXT,
                        old_variable TEXT,
                        new_variable TEXT,
                        resolution_method TEXT,
                        confidence REAL,
                        resolved_by TEXT DEFAULT 'system',
                        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_unknown_regions_request_id ON unknown_regions_tracking(request_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_resolution_attempts_request_id ON resolution_attempts(request_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_resolution_attempts_strategy ON resolution_attempts(strategy)")
                
                conn.commit()
                self.logger.info("Unknown region tracking database initialized")
                
        except Exception as e:
            self.logger.error(f"Error initializing database: {e}")
            raise
    
    def detect_unknown_regions(self) -> List[UnknownRegionRequest]:
        """
        Detect all requests with unknown or NULL regions in the database.
        
        Returns:
            List of UnknownRegionRequest objects
        """
        try:
            self.logger.info("🔍 Detecting unknown region requests...")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT request_id, request_index, rinfo, subset_note, raw_response
                    FROM rda_requests 
                    WHERE region IS NULL OR region = 'UNKNOWN'
                    ORDER BY request_index DESC
                """)
                
                unknown_requests = []
                for row in cursor.fetchall():
                    request_id, request_index, rinfo, subset_note, raw_response_str = row
                    
                    try:
                        raw_response = json.loads(raw_response_str) if raw_response_str else {}
                    except:
                        raw_response = {}
                    
                    unknown_request = UnknownRegionRequest(
                        request_id=request_id,
                        request_index=request_index,
                        rinfo=rinfo or "",
                        subset_note=subset_note or "",
                        raw_response=raw_response
                    )
                    
                    unknown_requests.append(unknown_request)
                
                self.logger.info(f"📊 Found {len(unknown_requests)} unknown region requests")
                return unknown_requests
                
        except Exception as e:
            self.logger.error(f"Error detecting unknown regions: {e}")
            return []
    
    def resolve_unknown_region(self, unknown_request: UnknownRegionRequest) -> UnknownRegionRequest:
        """
        Resolve a single unknown region request using multiple strategies.
        
        Args:
            unknown_request: UnknownRegionRequest to resolve
            
        Returns:
            Updated UnknownRegionRequest with resolution results
        """
        self.logger.info(f"🔄 Resolving unknown region for request {unknown_request.request_id}")
        
        with self.resolver_lock:
            self.resolution_stats['total_attempts'] += 1
        
        # Strategy 1: Enhanced robust region mapping
        attempt = self._try_robust_region_mapping(unknown_request)
        unknown_request.resolution_attempts.append(attempt)
        
        if attempt.success and attempt.result_region != 'UNKNOWN':
            unknown_request.resolved_region = attempt.result_region
            unknown_request.resolved_variable = attempt.result_variable
            self.logger.info(f"✅ Resolved using robust mapping: {unknown_request.request_id} -> {attempt.result_region}/{attempt.result_variable}")
            self._update_resolution_stats(True)
            return self._finalize_resolution(unknown_request)
        
        # Strategy 2: Control file coordinate parsing
        attempt = self._try_control_file_parsing(unknown_request)
        unknown_request.resolution_attempts.append(attempt)
        
        if attempt.success and attempt.result_region != 'UNKNOWN':
            unknown_request.resolved_region = attempt.result_region
            unknown_request.resolved_variable = attempt.result_variable
            self.logger.info(f"✅ Resolved using control file parsing: {unknown_request.request_id} -> {attempt.result_region}/{attempt.result_variable}")
            self._update_resolution_stats(True)
            return self._finalize_resolution(unknown_request)
        
        # Strategy 3: Database lookup of historical mappings
        attempt = self._try_database_lookup(unknown_request)
        unknown_request.resolution_attempts.append(attempt)
        
        if attempt.success and attempt.result_region != 'UNKNOWN':
            unknown_request.resolved_region = attempt.result_region
            unknown_request.resolved_variable = attempt.result_variable
            self.logger.info(f"✅ Resolved using database lookup: {unknown_request.request_id} -> {attempt.result_region}/{attempt.result_variable}")
            self._update_resolution_stats(True)
            return self._finalize_resolution(unknown_request)
        
        # Strategy 4: Geographic fallback matching
        attempt = self._try_geographic_fallback(unknown_request)
        unknown_request.resolution_attempts.append(attempt)
        
        if attempt.success and attempt.result_region != 'UNKNOWN':
            unknown_request.resolved_region = attempt.result_region
            unknown_request.resolved_variable = attempt.result_variable
            self.logger.info(f"✅ Resolved using geographic fallback: {unknown_request.request_id} -> {attempt.result_region}/{attempt.result_variable}")
            self._update_resolution_stats(True)
            return self._finalize_resolution(unknown_request)
        
        # Final fallback: Assign REQ_XXX name
        fallback_name = self._assign_fallback_name(unknown_request)
        unknown_request.assigned_name = fallback_name
        unknown_request.resolved_region = fallback_name
        unknown_request.resolved_variable = "unknown"
        
        self.logger.warning(f"⚠️ Could not resolve region, assigned fallback name: {unknown_request.request_id} -> {fallback_name}")
        
        with self.resolver_lock:
            self.resolution_stats['fallback_assignments'] += 1
        
        return self._finalize_resolution(unknown_request)
    
    def _try_robust_region_mapping(self, unknown_request: UnknownRegionRequest) -> ResolutionAttempt:
        """Try to resolve using robust region mapping."""
        try:
            # Create mock request for enhanced detection
            mock_request = {
                'request_index': unknown_request.request_index,
                'request_id': unknown_request.request_id,
                'rinfo': unknown_request.rinfo,
                'subset_info': {'note': unknown_request.subset_note},
                'raw_data': unknown_request.raw_response
            }
            
            region, variable = get_region_and_variable_from_request_enhanced(mock_request)
            
            return ResolutionAttempt(
                request_id=unknown_request.request_id,
                request_index=unknown_request.request_index,
                strategy="robust_region_mapping",
                result_region=region,
                result_variable=variable,
                confidence=1.0 if region != 'UNKNOWN' else 0.0,
                timestamp=datetime.now().isoformat(),
                success=region != 'UNKNOWN',
                details={'method': 'enhanced_coordinate_detection'}
            )
            
        except Exception as e:
            return ResolutionAttempt(
                request_id=unknown_request.request_id,
                request_index=unknown_request.request_index,
                strategy="robust_region_mapping",
                result_region="UNKNOWN",
                result_variable="unknown",
                confidence=0.0,
                timestamp=datetime.now().isoformat(),
                success=False,
                error_message=str(e)
            )
    
    def _try_control_file_parsing(self, unknown_request: UnknownRegionRequest) -> ResolutionAttempt:
        """Try to resolve by parsing control file coordinates."""
        try:
            # Extract coordinates from rinfo
            coordinates = {}
            if unknown_request.rinfo:
                for param in unknown_request.rinfo.split(';'):
                    if '=' in param:
                        key, value = param.split('=', 1)
                        key = key.strip()
                        if key in ['nlat', 'slat', 'wlon', 'elon']:
                            try:
                                coordinates[key] = float(value.strip())
                            except:
                                pass
            
            if len(coordinates) == 4:
                # Use coordinate-based region detection
                from coordinate_utils import detect_region_from_coordinates
                region = detect_region_from_coordinates(
                    coordinates['nlat'], coordinates['slat'], 
                    coordinates['wlon'], coordinates['elon']
                )
                
                # Extract variable from subset_note
                variable = self._extract_variable_from_subset_note(unknown_request.subset_note)
                
                return ResolutionAttempt(
                    request_id=unknown_request.request_id,
                    request_index=unknown_request.request_index,
                    strategy="control_file_parsing",
                    result_region=region,
                    result_variable=variable,
                    confidence=0.8 if region != 'UNKNOWN' else 0.0,
                    timestamp=datetime.now().isoformat(),
                    success=region != 'UNKNOWN',
                    details={'coordinates': coordinates}
                )
            else:
                return ResolutionAttempt(
                    request_id=unknown_request.request_id,
                    request_index=unknown_request.request_index,
                    strategy="control_file_parsing",
                    result_region="UNKNOWN",
                    result_variable="unknown",
                    confidence=0.0,
                    timestamp=datetime.now().isoformat(),
                    success=False,
                    error_message="Insufficient coordinate data"
                )
                
        except Exception as e:
            return ResolutionAttempt(
                request_id=unknown_request.request_id,
                request_index=unknown_request.request_index,
                strategy="control_file_parsing",
                result_region="UNKNOWN",
                result_variable="unknown",
                confidence=0.0,
                timestamp=datetime.now().isoformat(),
                success=False,
                error_message=str(e)
            )
    
    def _try_database_lookup(self, unknown_request: UnknownRegionRequest) -> ResolutionAttempt:
        """Try to resolve using historical database mappings."""
        try:
            # Look for similar requests in the database
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT region, variable_type, COUNT(*) as count
                    FROM rda_requests 
                    WHERE rinfo = ? AND region IS NOT NULL AND region != 'UNKNOWN'
                    GROUP BY region, variable_type
                    ORDER BY count DESC
                    LIMIT 1
                """, (unknown_request.rinfo,))
                
                result = cursor.fetchone()
                if result:
                    region, variable, count = result
                    return ResolutionAttempt(
                        request_id=unknown_request.request_id,
                        request_index=unknown_request.request_index,
                        strategy="database_lookup",
                        result_region=region,
                        result_variable=variable,
                        confidence=0.7,
                        timestamp=datetime.now().isoformat(),
                        success=True,
                        details={'historical_matches': count}
                    )
                else:
                    return ResolutionAttempt(
                        request_id=unknown_request.request_id,
                        request_index=unknown_request.request_index,
                        strategy="database_lookup",
                        result_region="UNKNOWN",
                        result_variable="unknown",
                        confidence=0.0,
                        timestamp=datetime.now().isoformat(),
                        success=False,
                        error_message="No historical matches found"
                    )
                    
        except Exception as e:
            return ResolutionAttempt(
                request_id=unknown_request.request_id,
                request_index=unknown_request.request_index,
                strategy="database_lookup",
                result_region="UNKNOWN",
                result_variable="unknown",
                confidence=0.0,
                timestamp=datetime.now().isoformat(),
                success=False,
                error_message=str(e)
            )
    
    def _try_geographic_fallback(self, unknown_request: UnknownRegionRequest) -> ResolutionAttempt:
        """Try to resolve using approximate geographic matching."""
        try:
            # Extract coordinates and try approximate matching
            coordinates = {}
            if unknown_request.rinfo:
                for param in unknown_request.rinfo.split(';'):
                    if '=' in param:
                        key, value = param.split('=', 1)
                        key = key.strip()
                        if key in ['nlat', 'slat', 'wlon', 'elon']:
                            try:
                                coordinates[key] = float(value.strip())
                            except:
                                pass
            
            if len(coordinates) == 4:
                # Simple geographic classification
                lat_center = (coordinates['nlat'] + coordinates['slat']) / 2
                lon_center = (coordinates['wlon'] + coordinates['elon']) / 2
                
                # Basic geographic regions
                if lon_center < 0:  # Western hemisphere
                    if lat_center > 45:
                        region = "NORTHERN_US"
                    elif lat_center > 35:
                        region = "CENTRAL_US"
                    else:
                        region = "SOUTHERN_US"
                else:  # Eastern hemisphere
                    if lat_center > 50:
                        region = "NORTHERN_EUROPE"
                    elif lat_center > 40:
                        region = "CENTRAL_EUROPE"
                    else:
                        region = "SOUTHERN_EUROPE"
                
                variable = self._extract_variable_from_subset_note(unknown_request.subset_note)
                
                return ResolutionAttempt(
                    request_id=unknown_request.request_id,
                    request_index=unknown_request.request_index,
                    strategy="geographic_fallback",
                    result_region=region,
                    result_variable=variable,
                    confidence=0.5,
                    timestamp=datetime.now().isoformat(),
                    success=True,
                    details={'lat_center': lat_center, 'lon_center': lon_center}
                )
            else:
                return ResolutionAttempt(
                    request_id=unknown_request.request_id,
                    request_index=unknown_request.request_index,
                    strategy="geographic_fallback",
                    result_region="UNKNOWN",
                    result_variable="unknown",
                    confidence=0.0,
                    timestamp=datetime.now().isoformat(),
                    success=False,
                    error_message="Insufficient coordinate data for geographic fallback"
                )
                
        except Exception as e:
            return ResolutionAttempt(
                request_id=unknown_request.request_id,
                request_index=unknown_request.request_index,
                strategy="geographic_fallback",
                result_region="UNKNOWN",
                result_variable="unknown",
                confidence=0.0,
                timestamp=datetime.now().isoformat(),
                success=False,
                error_message=str(e)
            )
    
    def _extract_variable_from_subset_note(self, subset_note: str) -> str:
        """Extract weather variable from subset note."""
        if not subset_note:
            return "unknown"
        
        note_lower = subset_note.lower()
        
        # Map common variable patterns
        if any(term in note_lower for term in ['solar', 'radiation', 'dswrf', 'shortwave']):
            return "dswrf"
        elif any(term in note_lower for term in ['wind', 'ugrd', 'vgrd', 'u-component', 'v-component']):
            return "ugrd_vgrd"
        elif any(term in note_lower for term in ['rain', 'precip', 'apcp', 'precipitation']):
            return "apcp"
        elif any(term in note_lower for term in ['temp', 'temperature', 'tmp', 'dewpoint']):
            return "tmp_dpt"
        else:
            return "unknown"
    
    def _assign_fallback_name(self, unknown_request: UnknownRegionRequest) -> str:
        """Assign a fallback name in REQ_XXX format."""
        try:
            # Get the next available REQ number
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM unknown_regions_tracking 
                    WHERE assigned_name LIKE 'REQ_%'
                """)
                count = cursor.fetchone()[0]
                
                return f"REQ_{count + 1:03d}"
                
        except Exception as e:
            # Fallback to timestamp-based name
            return f"REQ_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    def _finalize_resolution(self, unknown_request: UnknownRegionRequest) -> UnknownRegionRequest:
        """Finalize the resolution by updating database and tracking."""
        try:
            unknown_request.updated_at = datetime.now().isoformat()
            
            # Save to unknown regions tracking table
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO unknown_regions_tracking
                    (request_id, request_index, rinfo, subset_note, raw_response,
                     assigned_name, resolved_region, resolved_variable, manual_override,
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    unknown_request.request_id,
                    unknown_request.request_index,
                    unknown_request.rinfo,
                    unknown_request.subset_note,
                    json.dumps(unknown_request.raw_response),
                    unknown_request.assigned_name,
                    unknown_request.resolved_region,
                    unknown_request.resolved_variable,
                    unknown_request.manual_override,
                    unknown_request.created_at,
                    unknown_request.updated_at
                ))
                
                # Save resolution attempts
                for attempt in unknown_request.resolution_attempts:
                    cursor.execute("""
                        INSERT INTO resolution_attempts
                        (request_id, request_index, strategy, result_region, result_variable,
                         confidence, success, error_message, details, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        attempt.request_id,
                        attempt.request_index,
                        attempt.strategy,
                        attempt.result_region,
                        attempt.result_variable,
                        attempt.confidence,
                        attempt.success,
                        attempt.error_message,
                        json.dumps(attempt.details) if attempt.details else None,
                        attempt.timestamp
                    ))
                
                # Update the main rda_requests table if resolution was successful
                if unknown_request.resolved_region and unknown_request.resolved_region != 'UNKNOWN':
                    cursor.execute("""
                        UPDATE rda_requests 
                        SET region = ?, variable_type = ?, updated_at = ?
                        WHERE request_id = ?
                    """, (
                        unknown_request.resolved_region,
                        unknown_request.resolved_variable,
                        unknown_request.updated_at,
                        unknown_request.request_id
                    ))
                
                conn.commit()
                
            return unknown_request
            
        except Exception as e:
            self.logger.error(f"Error finalizing resolution for {unknown_request.request_id}: {e}")
            return unknown_request
    
    def _update_resolution_stats(self, success: bool):
        """Update resolution statistics."""
        with self.resolver_lock:
            if success:
                self.resolution_stats['successful_resolutions'] += 1
            self.resolution_stats['last_resolution_time'] = datetime.now().isoformat()
    
    def resolve_all_unknown_regions(self) -> Dict[str, Any]:
        """
        Resolve all unknown regions in the system.
        
        Returns:
            Dictionary with resolution results and statistics
        """
        start_time = datetime.now()
        self.logger.info("🚀 Starting comprehensive unknown region resolution...")
        
        # Detect all unknown regions
        unknown_requests = self.detect_unknown_regions()
        
        if not unknown_requests:
            return {
                'success': True,
                'message': 'No unknown regions found',
                'total_requests': 0,
                'resolved_count': 0,
                'fallback_count': 0,
                'duration_seconds': 0,
                'timestamp': start_time.isoformat()
            }
        
        resolved_count = 0
        fallback_count = 0
        results = []
        
        for unknown_request in unknown_requests:
            try:
                resolved_request = self.resolve_unknown_region(unknown_request)
                
                if resolved_request.resolved_region and resolved_request.resolved_region != 'UNKNOWN':
                    if resolved_request.assigned_name and resolved_request.assigned_name.startswith('REQ_'):
                        fallback_count += 1
                    else:
                        resolved_count += 1
                
                results.append({
                    'request_id': resolved_request.request_id,
                    'request_index': resolved_request.request_index,
                    'resolved_region': resolved_request.resolved_region,
                    'resolved_variable': resolved_request.resolved_variable,
                    'assigned_name': resolved_request.assigned_name,
                    'attempts': len(resolved_request.resolution_attempts),
                    'successful_strategy': next(
                        (attempt.strategy for attempt in resolved_request.resolution_attempts if attempt.success),
                        None
                    )
                })
                
            except Exception as e:
                self.logger.error(f"Error resolving request {unknown_request.request_id}: {e}")
                results.append({
                    'request_id': unknown_request.request_id,
                    'request_index': unknown_request.request_index,
                    'error': str(e)
                })
        
        duration = (datetime.now() - start_time).total_seconds()
        
        result_summary = {
            'success': True,
            'total_requests': len(unknown_requests),
            'resolved_count': resolved_count,
            'fallback_count': fallback_count,
            'failed_count': len(unknown_requests) - resolved_count - fallback_count,
            'duration_seconds': duration,
            'results': results,
            'statistics': self.resolution_stats.copy(),
            'timestamp': start_time.isoformat()
        }
        
        self.logger.info(f"✅ Resolution completed: {resolved_count} resolved, {fallback_count} fallback assignments in {duration:.2f}s")
        return result_summary
    
    def get_unknown_regions_status(self) -> Dict[str, Any]:
        """
        Get current status of unknown regions tracking.
        
        Returns:
            Dictionary with unknown regions status and statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get unknown regions summary
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_unknown,
                        COUNT(CASE WHEN resolved_region IS NOT NULL AND resolved_region != 'UNKNOWN' THEN 1 END) as resolved,
                        COUNT(CASE WHEN assigned_name LIKE 'REQ_%' THEN 1 END) as fallback_assigned,
                        COUNT(CASE WHEN manual_override = 1 THEN 1 END) as manual_overrides
                    FROM unknown_regions_tracking
                """)
                summary = cursor.fetchone()
                
                # Get resolution strategy statistics
                cursor = conn.execute("""
                    SELECT strategy, COUNT(*) as count, AVG(confidence) as avg_confidence
                    FROM resolution_attempts
                    WHERE success = 1
                    GROUP BY strategy
                    ORDER BY count DESC
                """)
                strategy_stats = {row[0]: {'count': row[1], 'avg_confidence': row[2]} 
                                for row in cursor.fetchall()}
                
                # Get recent unknown regions
                cursor = conn.execute("""
                    SELECT request_id, request_index, resolved_region, resolved_variable, 
                           assigned_name, updated_at
                    FROM unknown_regions_tracking
                    ORDER BY updated_at DESC
                    LIMIT 10
                """)
                recent_unknown = [
                    {
                        'request_id': row[0],
                        'request_index': row[1],
                        'resolved_region': row[2],
                        'resolved_variable': row[3],
                        'assigned_name': row[4],
                        'updated_at': row[5]
                    }
                    for row in cursor.fetchall()
                ]
                
                return {
                    'summary': {
                        'total_unknown': summary[0] if summary else 0,
                        'resolved': summary[1] if summary else 0,
                        'fallback_assigned': summary[2] if summary else 0,
                        'manual_overrides': summary[3] if summary else 0
                    },
                    'strategy_statistics': strategy_stats,
                    'recent_unknown_regions': recent_unknown,
                    'resolution_statistics': self.resolution_stats.copy(),
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error getting unknown regions status: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def manual_override_region(self, request_id: str, region: str, variable: str,
                             override_by: str = "user") -> Dict[str, Any]:
        """
        Manually override the region assignment for a request.
        
        Args:
            request_id: The request ID to override
            region: The new region assignment
            variable: The new variable assignment
            override_by: Who performed the override (default: "user")
            
        Returns:
            Dictionary with override result
        """
        try:
            self.logger.info(f"🔧 Manual override for {request_id}: {region}/{variable}")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Update unknown regions tracking
                cursor.execute("""
                    UPDATE unknown_regions_tracking
                    SET resolved_region = ?, resolved_variable = ?,
                        manual_override = 1, updated_at = ?
                    WHERE request_id = ?
                """, (region, variable, datetime.now().isoformat(), request_id))
                
                # Update main rda_requests table
                cursor.execute("""
                    UPDATE rda_requests
                    SET region = ?, variable_type = ?, updated_at = ?
                    WHERE request_id = ?
                """, (region, variable, datetime.now().isoformat(), request_id))
                
                # Record in resolution history
                cursor.execute("""
                    INSERT INTO resolution_history
                    (request_id, new_region, new_variable, resolution_method,
                     confidence, resolved_by, timestamp)
                    VALUES (?, ?, ?, 'manual_override', 1.0, ?, ?)
                """, (request_id, region, variable, override_by, datetime.now().isoformat()))
                
                conn.commit()
                
                with self.resolver_lock:
                    self.resolution_stats['manual_overrides'] += 1
                
                return {
                    'success': True,
                    'request_id': request_id,
                    'new_region': region,
                    'new_variable': variable,
                    'override_by': override_by,
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error in manual override for {request_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'request_id': request_id,
                'timestamp': datetime.now().isoformat()
            }
    
    def get_resolution_details(self, request_id: str) -> Dict[str, Any]:
        """
        Get detailed resolution information for a specific request.
        
        Args:
            request_id: The request ID to get details for
            
        Returns:
            Dictionary with detailed resolution information
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get unknown region tracking info
                cursor = conn.execute("""
                    SELECT * FROM unknown_regions_tracking
                    WHERE request_id = ?
                """, (request_id,))
                
                tracking_info = cursor.fetchone()
                if not tracking_info:
                    return {'error': f'Request {request_id} not found in unknown regions tracking'}
                
                # Get resolution attempts
                cursor = conn.execute("""
                    SELECT * FROM resolution_attempts
                    WHERE request_id = ?
                    ORDER BY timestamp ASC
                """, (request_id,))
                
                attempts = [
                    {
                        'strategy': row[3],
                        'result_region': row[4],
                        'result_variable': row[5],
                        'confidence': row[6],
                        'success': bool(row[7]),
                        'error_message': row[8],
                        'details': json.loads(row[9]) if row[9] else {},
                        'timestamp': row[10]
                    }
                    for row in cursor.fetchall()
                ]
                
                # Get resolution history
                cursor = conn.execute("""
                    SELECT * FROM resolution_history
                    WHERE request_id = ?
                    ORDER BY timestamp DESC
                """, (request_id,))
                
                history = [
                    {
                        'old_region': row[2],
                        'new_region': row[3],
                        'old_variable': row[4],
                        'new_variable': row[5],
                        'resolution_method': row[6],
                        'confidence': row[7],
                        'resolved_by': row[8],
                        'timestamp': row[9]
                    }
                    for row in cursor.fetchall()
                ]
                
                return {
                    'request_id': request_id,
                    'tracking_info': {
                        'request_index': tracking_info[2],
                        'rinfo': tracking_info[3],
                        'subset_note': tracking_info[4],
                        'assigned_name': tracking_info[6],
                        'resolved_region': tracking_info[7],
                        'resolved_variable': tracking_info[8],
                        'manual_override': bool(tracking_info[9]),
                        'created_at': tracking_info[10],
                        'updated_at': tracking_info[11]
                    },
                    'resolution_attempts': attempts,
                    'resolution_history': history,
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error getting resolution details for {request_id}: {e}")
            return {
                'error': str(e),
                'request_id': request_id,
                'timestamp': datetime.now().isoformat()
            }


if __name__ == "__main__":
    """
    Command-line interface for the Enhanced Unknown Region Resolver.
    
    Usage:
        python unknown_region_resolver.py detect
        python unknown_region_resolver.py resolve-all
        python unknown_region_resolver.py status
        python unknown_region_resolver.py resolve <request_id>
        python unknown_region_resolver.py override <request_id> <region> <variable>
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced Unknown Region Resolver")
    parser.add_argument("command", choices=["detect", "resolve-all", "status", "resolve", "override"],
                       help="Command to execute")
    parser.add_argument("request_id", nargs="?", help="Request ID for resolve/override commands")
    parser.add_argument("region", nargs="?", help="Region for override command")
    parser.add_argument("variable", nargs="?", help="Variable for override command")
    parser.add_argument("--db-path", default="src/python/data/automation_state.db",
                       help="Path to database file")
    
    args = parser.parse_args()
    
    resolver = EnhancedUnknownRegionResolver(db_path=args.db_path)
    
    if args.command == "detect":
        unknown_requests = resolver.detect_unknown_regions()
        print(f"Found {len(unknown_requests)} unknown region requests:")
        for req in unknown_requests:
            print(f"  - {req.request_id} (index: {req.request_index})")
    
    elif args.command == "resolve-all":
        result = resolver.resolve_all_unknown_regions()
        print(json.dumps(result, indent=2))
    
    elif args.command == "status":
        status = resolver.get_unknown_regions_status()
        print(json.dumps(status, indent=2))
    
    elif args.command == "resolve":
        if not args.request_id:
            print("Error: request_id required for resolve command")
            sys.exit(1)
        
        # Find the request
        unknown_requests = resolver.detect_unknown_regions()
        target_request = next((req for req in unknown_requests if req.request_id == args.request_id), None)
        
        if not target_request:
            print(f"Error: Request {args.request_id} not found in unknown regions")
            sys.exit(1)
        
        result = resolver.resolve_unknown_region(target_request)
        print(f"Resolution result for {args.request_id}:")
        print(f"  Resolved Region: {result.resolved_region}")
        print(f"  Resolved Variable: {result.resolved_variable}")
        print(f"  Assigned Name: {result.assigned_name}")
        print(f"  Attempts: {len(result.resolution_attempts)}")
    
    elif args.command == "override":
        if not all([args.request_id, args.region, args.variable]):
            print("Error: request_id, region, and variable required for override command")
            sys.exit(1)
        
        result = resolver.manual_override_region(args.request_id, args.region, args.variable)
        print(json.dumps(result, indent=2))