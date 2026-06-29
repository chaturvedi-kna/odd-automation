import enum


class RequestStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLEDBACK = "ROLLEDBACK"


class DecisionType(str, enum.Enum):
    ADD = "ADD"
    DELETE = "DELETE"
    DEPENDENCY_ADD = "DEPENDENCY_ADD"
    DEPENDENCY_DELETE = "DEPENDENCY_DELETE"
    SUPERSEDE = "SUPERSEDE"
    SUPERSEDE_PENDING = "SUPERSEDE_PENDING"
    SKIPPED = "SKIPPED"


class ImplStatus(str, enum.Enum):
    PENDING = "PENDING FOR RECONCILIATION"
    IMPLEMENTED = "IMPLEMENTED"
    AWAITING_IMPLEMENTATION = "AWAITING_IMPLEMENTATION"
    CANCELLED = "CANCELLED"


class UserRole(str, enum.Enum):
    admin = "admin"
    operator = "operator"
    viewer = "viewer"


class ActionType(str, enum.Enum):
    ADD = "ADD"
    DELETE = "DELETE"


class EntryType(str, enum.Enum):
    PRR = "PRR"
    RBAR = "RBAR"
