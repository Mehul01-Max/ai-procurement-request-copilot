from __future__ import annotations

from src.tools.budget import TOOL_SCHEMA as BUDGET_SCHEMA, check_budget
from src.tools.catalog import TOOL_SCHEMA as CATALOG_SCHEMA, search_software_catalog
from src.tools.injection import TOOL_SCHEMA as INJECTION_SCHEMA, scan_prompt_injection
from src.tools.policy import TOOL_SCHEMA as POLICY_SCHEMA, get_policy_requirements
from src.tools.vendor import TOOL_SCHEMA as VENDOR_SCHEMA, get_vendor_security_status

TOOL_SCHEMAS = [CATALOG_SCHEMA, BUDGET_SCHEMA, VENDOR_SCHEMA, POLICY_SCHEMA, INJECTION_SCHEMA]

__all__ = ["TOOL_SCHEMAS", "search_software_catalog", "check_budget",
           "get_vendor_security_status", "get_policy_requirements", "scan_prompt_injection"]
