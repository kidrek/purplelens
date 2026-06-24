import enum


class Exposure(str, enum.Enum):
    internet = "Internet"
    interne = "Interne"
    partenaire = "Partenaire"
    cloud = "Cloud"


class AuditType(str, enum.Enum):
    bas = "BAS"
    pentest = "Pentest"
    red_team = "Red Team"
    purple_team = "Purple Team"


class AuditStatus(str, enum.Enum):
    draft = "Draft"
    scoping = "Scoping"
    in_progress = "In Progress"
    review = "Review"
    completed = "Completed"
    closed = "Closed"


class FindingStatus(str, enum.Enum):
    open = "Open"
    validated = "Validated"
    assigned = "Assigned"
    in_progress = "In Progress"
    fixed = "Fixed"
    retested = "Retested"
    closed = "Closed"


class Severity(str, enum.Enum):
    critical = "Critical"
    high = "High"
    medium = "Medium"
    low = "Low"
    info = "Info"
