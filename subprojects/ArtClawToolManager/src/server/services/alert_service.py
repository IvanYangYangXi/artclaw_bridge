# Ref: docs/features/official-system-tools.md#AlertsAPI
"""Alert service for managing system alerts."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from ..core.config import settings
from ..schemas.alert import Alert, AlertCreateRequest, AlertUpdateRequest

logger = logging.getLogger(__name__)


class AlertService:
    """Service for managing system alerts."""
    
    def __init__(self):
        """Initialize alert service."""
        self._alerts_dir = Path.home() / ".artclaw" / "alerts" 
        self._alerts_file = self._alerts_dir / "alerts.json"
        self._ensure_dir_exists()
    
    def _ensure_dir_exists(self) -> None:
        """Ensure alerts directory exists."""
        try:
            self._alerts_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error("Failed to create alerts directory: %s", e)
    
    def _load_alerts(self) -> Dict[str, Any]:
        """Load alerts from JSON file."""
        if not self._alerts_file.exists():
            return {"version": "1.0", "alerts": [], "lastCleanup": ""}
        
        try:
            with open(self._alerts_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to load alerts: %s", e)
            return {"version": "1.0", "alerts": [], "lastCleanup": ""}
    
    def _save_alerts(self, data: Dict[str, Any]) -> bool:
        """Save alerts to JSON file."""
        try:
            # Backup current file if exists
            if self._alerts_file.exists():
                backup_file = self._alerts_dir / f"alerts-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
                self._alerts_file.rename(backup_file)
            
            with open(self._alerts_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except OSError as e:
            logger.error("Failed to save alerts: %s", e)
            return False
    
    def get_alerts(self, resolved: Optional[bool] = None) -> List[Alert]:
        """Get alerts, optionally filtered by resolved status."""
        data = self._load_alerts()
        alerts = []
        
        for alert_dict in data.get("alerts", []):
            try:
                alert = Alert(**alert_dict)
                
                # Filter by resolved status if specified
                if resolved is not None:
                    is_resolved = alert.resolvedAt is not None
                    if resolved != is_resolved:
                        continue
                
                alerts.append(alert)
            except Exception as e:
                logger.warning("Invalid alert data: %s", e)
        
        return alerts
    
    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Get alert by ID."""
        alerts = self.get_alerts()
        for alert in alerts:
            if alert.id == alert_id:
                return alert
        return None
    
    def create_alert(self, request: AlertCreateRequest) -> Optional[Alert]:
        """Create a new alert (or update existing duplicate).

        Deduplication: if an unresolved alert with the same ``source`` and
        ``title`` already exists, update its detail/metadata/level in-place
        instead of creating a duplicate.
        """
        data = self._load_alerts()
        now = datetime.now(timezone.utc).isoformat()

        # --- Dedup: find existing unresolved alert with same source+level ---
        # Title may change between runs (e.g. count differs), so we match on
        # source + level only.  This keeps at most one active alert per
        # source+level combination.
        for alert_dict in data.get("alerts", []):
            if (
                alert_dict.get("source") == request.source
                and alert_dict.get("level") == request.level
                and alert_dict.get("resolvedAt") is None
            ):
                # Update in-place
                alert_dict["title"] = request.title
                alert_dict["detail"] = request.detail
                alert_dict["metadata"] = request.metadata
                alert_dict["updatedAt"] = now
                if self._save_alerts(data):
                    logger.info("Dedup-updated alert: %s", alert_dict["id"])
                    return Alert(**alert_dict)
                return None

        # --- No duplicate — create new ---
        alert_id = f"alert-{uuid.uuid4().hex[:8]}"
        
        # Create alert object
        alert = Alert(
            id=alert_id,
            level=request.level,
            source=request.source,
            title=request.title,
            detail=request.detail,
            createdAt=now,
            resolvedAt=None,
            metadata=request.metadata
        )
        
        # Add to data
        data["alerts"].append(alert.dict())
        
        # Save to file
        if self._save_alerts(data):
            logger.info("Created alert: %s", alert_id)
            return alert
        else:
            logger.error("Failed to save alert: %s", alert_id)
            return None
    
    def update_alert(self, alert_id: str, request: AlertUpdateRequest) -> Optional[Alert]:
        """Update an existing alert."""
        data = self._load_alerts()
        alerts = data.get("alerts", [])
        
        # Find and update alert
        for i, alert_dict in enumerate(alerts):
            if alert_dict.get("id") == alert_id:
                if request.resolved:
                    alert_dict["resolvedAt"] = request.resolvedAt or datetime.now(timezone.utc).isoformat()
                else:
                    alert_dict["resolvedAt"] = None
                
                # Save and return updated alert
                if self._save_alerts(data):
                    logger.info("Updated alert: %s", alert_id)
                    return Alert(**alert_dict)
                else:
                    logger.error("Failed to save alert update: %s", alert_id)
                    return None
        
        logger.warning("Alert not found: %s", alert_id)
        return None
    
    def delete_alert(self, alert_id: str) -> bool:
        """Delete an alert."""
        data = self._load_alerts()
        alerts = data.get("alerts", [])
        
        # Find and remove alert
        original_count = len(alerts)
        data["alerts"] = [a for a in alerts if a.get("id") != alert_id]
        
        if len(data["alerts"]) < original_count:
            if self._save_alerts(data):
                logger.info("Deleted alert: %s", alert_id)
                return True
            else:
                logger.error("Failed to save after deleting alert: %s", alert_id)
                return False
        else:
            logger.warning("Alert not found for deletion: %s", alert_id)
            return False
    
    def cleanup_old_alerts(self, days: int = 7) -> int:
        """Clean up resolved alerts older than specified days."""
        data = self._load_alerts()
        alerts = data.get("alerts", [])
        
        # Calculate cutoff time
        cutoff = datetime.now(timezone.utc).timestamp() - (days * 24 * 3600)
        
        # Filter out old resolved alerts
        original_count = len(alerts)
        filtered_alerts = []
        
        for alert_dict in alerts:
            resolved_at = alert_dict.get("resolvedAt")
            if resolved_at:
                try:
                    resolved_time = datetime.fromisoformat(resolved_at.replace('Z', '+00:00'))
                    if resolved_time.timestamp() < cutoff:
                        continue  # Skip old resolved alert
                except ValueError:
                    pass  # Keep alert if timestamp parsing fails
            
            filtered_alerts.append(alert_dict)
        
        # Save if changed
        cleaned_count = original_count - len(filtered_alerts)
        if cleaned_count > 0:
            data["alerts"] = filtered_alerts
            data["lastCleanup"] = datetime.now(timezone.utc).isoformat()
            
            if self._save_alerts(data):
                logger.info("Cleaned up %d old alerts", cleaned_count)
                return cleaned_count
            else:
                logger.error("Failed to save after cleanup")
                return 0
        
        return 0
    
    def get_stats(self) -> Dict[str, int]:
        """Get alert statistics."""
        alerts = self.get_alerts()
        
        total = len(alerts)
        resolved = sum(1 for a in alerts if a.resolvedAt is not None)
        unresolved = total - resolved
        
        warnings = sum(1 for a in alerts if a.level == "warning" and a.resolvedAt is None)
        errors = sum(1 for a in alerts if a.level == "error" and a.resolvedAt is None)
        
        return {
            "total": total,
            "resolved": resolved,
            "unresolved": unresolved,
            "warnings": warnings,
            "errors": errors
        }