from dataclasses import dataclass


class Event:
    pass


@dataclass
class OrderSubmitted(Event):
    pass
