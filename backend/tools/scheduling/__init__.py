from .book_slot import SCHEMA as book_slot
from .capture_preference import SCHEMA as capture_preference
from .check_appointment_requirements import SCHEMA as check_appointment_requirements
from .classify_appointment import SCHEMA as classify_appointment

__all__ = [
    "classify_appointment",
    "check_appointment_requirements",
    "capture_preference",
    "book_slot",
]