from dataclasses import dataclass


@dataclass
class Course:
    name: str
    color: str = "#2563eb"

