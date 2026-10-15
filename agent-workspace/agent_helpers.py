"""Agent-editable browser helpers.

Add task-specific browser primitives here. Core helpers from browser_harness.helpers
load this file when BH_AGENT_WORKSPACE points at this directory, or when this
repo's default agent-workspace exists.
"""

import os
import sys

_AGENT_WORKSPACE_DIR = os.path.dirname(__file__)
if _AGENT_WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, _AGENT_WORKSPACE_DIR)

from content_extraction import (
    archive_current_page,
    extract_cards,
    extract_links,
    extract_lists,
    extract_markdown_from_current_page,
    extract_outline,
    extract_tables,
    extract_virtualized_container,
)

