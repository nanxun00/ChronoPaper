"""Backward compatibility: re-export RAG stack."""
from src.services.rag.database import DataBaseManager
from src.services.rag.history import HistoryManager
from src.services.rag.startup import startup

__all__ = ["DataBaseManager", "HistoryManager", "startup"]
