from dataclasses import dataclass, field


@dataclass
class Activity:
    title: str
    activity_type: str
    deadline: str = ""
    estimated_hours: float = 0
    metadata: dict = field(default_factory=dict)

