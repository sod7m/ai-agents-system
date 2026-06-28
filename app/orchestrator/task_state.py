from __future__ import annotations

from enum import Enum


class TaskStatus(str, Enum):
    IDLE = "idle"
    TASK_CREATED = "task_created"
    PM_PLANNING = "pm_planning"
    CODING = "coding"
    QA_CHECKING = "qa_checking"
    QA_FAILED = "qa_failed"
    QA_PASSED = "qa_passed"
    FINAL_SUMMARY = "final_summary"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
