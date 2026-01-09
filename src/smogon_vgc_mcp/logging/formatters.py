"""JSON log formatter for structured logging."""

import json
import logging
from datetime import UTC, datetime

from smogon_vgc_mcp.logging.context import get_correlation_id


class JSONFormatter(logging.Formatter):
    """Formats log records as JSON for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        cid = get_correlation_id()
        if cid:
            log_entry["correlation_id"] = cid

        if hasattr(record, "extra_data") and record.extra_data:
            log_entry.update(record.extra_data)

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)
