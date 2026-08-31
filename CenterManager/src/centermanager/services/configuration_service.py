"""Validated system configuration lifecycle service (ADMIN 1.5)."""
import re
from copy import deepcopy
from zoneinfo import ZoneInfo
from centermanager.core.config import get_config, save_config

class ConfigurationValidationError(ValueError): pass

class ConfigurationService:
    SYSTEM_DEFAULTS = {"center_name":"", "address":"", "phone":"", "email":"", "currency":"VND", "timezone":"Asia/Ho_Chi_Minh", "academic_year":""}
    COLLAB_DEFAULTS = {"heartbeat_interval":10, "lock_timeout":60, "retry_count":3, "backup_before_publish":True, "auto_release":False}
    def load(self):
        raw=get_config().raw
        return {"system": {**self.SYSTEM_DEFAULTS, **raw.get("system",{})}, "collaboration": {**self.COLLAB_DEFAULTS, **raw.get("collaboration",{})}}
    def validate(self, data):
        errors={}; s=data["system"]; c=data["collaboration"]
        email=s.get("email", "").strip()
        if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email): errors["email"]="Email format is invalid."
        tz=s.get("timezone", "").strip()
        try: ZoneInfo(tz)
        except Exception: errors["timezone"]="Timezone must be a valid IANA timezone, e.g. Asia/Ho_Chi_Minh."
        year=s.get("academic_year", "").strip()
        if year and not re.match(r"^\d{4}-\d{4}$", year): errors["academic_year"]="Academic year must use YYYY-YYYY format."
        if year and int(year[5:]) != int(year[:4])+1: errors["academic_year"]="Academic year end must be exactly one year after start."
        cur=s.get("currency", "").strip().upper()
        if not re.match(r"^[A-Z]{3}$", cur): errors["currency"]="Currency must be a 3-letter ISO code."
        if c["lock_timeout"] <= c["heartbeat_interval"]: errors["lock_timeout"]="Lock timeout must be greater than heartbeat interval."
        if errors: raise ConfigurationValidationError(errors)
    def save(self, data):
        self.validate(data)
        old=self.load(); raw=get_config().raw
        raw["system"] = deepcopy(data["system"]); raw["collaboration"] = deepcopy(data["collaboration"])
        save_config(raw)
        # Current runtime collaboration services read these values at initialization.
        restart_required = old["collaboration"] != data["collaboration"]
        return {"restart_required": restart_required, "old": old, "new": self.load()}
