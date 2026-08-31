# -*- coding: utf-8 -*-
"""ADMIN 1.6 system operations health aggregation."""
from __future__ import annotations
import os, sqlite3, sys, platform, subprocess, shutil
from datetime import datetime
from pathlib import Path
from centermanager.core.paths import get_paths

class SystemOperationsService:
    def __init__(self, collaboration_manager=None, git_config_service=None):
        self._collaboration_manager = collaboration_manager
        self._git_config_service = git_config_service

    def snapshot(self):
        paths = get_paths()
        runtime = Path(paths.runtime_root)
        db_path = Path(paths.database_dir / 'center.db')
        items = []
        items.append(self._database(db_path))
        items.append(self._runtime(runtime))
        items.append(self._collaboration())
        items.append(self._git())
        items.append(self._storage(runtime))
        return {"generated_at": datetime.now(), "components": items, "version": self._version()}

    def _database(self, path):
        try:
            with sqlite3.connect(str(path)) as conn:
                conn.execute("SELECT 1").fetchone()
            return {"name":"Database","status":"HEALTHY","summary":f"SQLite available ({path.stat().st_size:,} bytes)","details":str(path)}
        except Exception as e:
            return {"name":"Database","status":"ERROR","summary":str(e),"details":str(path)}

    def _runtime(self, path):
        required=["Database","metadata","repository","collaboration"]
        missing=[x for x in required if not (path/x).exists()]
        if missing: return {"name":"Runtime","status":"WARNING","summary":"Missing: "+", ".join(missing),"details":str(path)}
        return {"name":"Runtime","status":"HEALTHY","summary":"Runtime structure is available","details":str(path)}

    def _collaboration(self):
        if not self._collaboration_manager:
            return {"name":"Collaboration","status":"UNKNOWN","summary":"Manager not available","details":""}
        try:
            diag=self._collaboration_manager.get_diagnostics()
            health=self._collaboration_manager.get_health()
            status=health.get("status","UNKNOWN") if isinstance(health,dict) else str(getattr(health,"status","UNKNOWN"))
            return {"name":"Collaboration","status":status,"summary":f"Mode: {diag.get('mode','UNKNOWN')}","details":str(diag)}
        except Exception as e:
            return {"name":"Collaboration","status":"WARNING","summary":"Diagnostics unavailable","details":str(e)}

    def _git(self):
        if not self._collaboration_manager:
            return {"name":"Git Sync","status":"UNKNOWN","summary":"Not available","details":""}
        try:
            diag=self._collaboration_manager.get_diagnostics(); git=diag.get("git",{})
            state=str(git.get("state","UNKNOWN")).upper()
            status="HEALTHY" if state in ("READY","SYNCED","CLEAN","DISABLED") else ("WARNING" if state!="ERROR" else "ERROR")
            return {"name":"Git Sync","status":status,"summary":git.get("status", git.get("state","Unknown")),"details":str(git)}
        except Exception as e:
            return {"name":"Git Sync","status":"WARNING","summary":"Status unavailable","details":str(e)}

    def _storage(self, path):
        try:
            usage=shutil.disk_usage(path)
            return {"name":"Storage","status":"HEALTHY","summary":f"Free space: {usage.free:,} bytes","details":str(path)}
        except Exception as e:
            return {"name":"Storage","status":"WARNING","summary":"Unable to inspect storage","details":str(e)}

    def _version(self):
        return {"application":"CenterManager","python":sys.version.split()[0],"platform":platform.platform()}
