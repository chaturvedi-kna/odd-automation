import enum


class RequestStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    DONE_PARTIAL = "DONE_PARTIAL"
    FAILED = "FAILED"


class DecisionType(str, Enum):
    ADD = "ADD"
    DELETE = "DELETE"

    DEPENDENCY_ADD = "DEPENDENCY_ADD"
    DEPENDENCY_DELETE = "DEPENDENCY_DELETE"

    SUPERSEDE = "SUPERSEDE"

    SKIPPED = "SKIPPED"


class ImplStatus(str, enum.Enum):
    PENDING = "PENDING FOR RECONCILATION"
    IMPLEMENTED = "IMPLEMENTED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


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