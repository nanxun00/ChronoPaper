from enum import Enum


class TaskType(str, Enum):
    CRAWL = "crawl"
    PUSH = "push"
    COMPILE = "compile"
    TIMERAG = "timerag"
