from dataclasses import dataclass


@dataclass
class Progress:
    completed: bool = False
    actual_amount: int = 0

