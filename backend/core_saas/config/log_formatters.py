import json
import logging
from datetime import UTC, datetime

# Attributes every LogRecord has. Anything else on a record came from extra={...}.
_STANDARD_ATTRS = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """
    One JSON object per line, so log tools can filter by field:

        logger.info("Job finished", extra={"job_id": job.id, "status": "SUCCESS"})
        {"timestamp": "...", "level": "INFO", "logger": "predictions.tasks",
         "message": "Job finished", "job_id": "...", "status": "SUCCESS"}
    """

    def format(self, record):
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in vars(record).items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                entry[key] = value
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)