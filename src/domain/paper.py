"""Domain enums and value objects."""
from enum import Enum


class ParseStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    PARSING = "parsing"
    DONE = "done"
    FAILED = "failed"
    DOWNLOAD_FAILED = "download_failed"


class TaskRunStatus(str, Enum):
    WAITING = "waiting"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Visibility(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
