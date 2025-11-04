import logging
from typing import Callable, Dict, List, Type

from .events import Event

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._subs: Dict[Type[Event], List[Callable]] = {}

    def subscribe(self, event_type: Type[Event], handler: Callable):
        self._subs.setdefault(event_type, []).append(handler)

    def publish(self, event: Event):
        handlers = self._subs.get(type(event), [])
        if not handlers:
            logger.warning(f"No handlers registered for event: {type(event)}")

        for handler in handlers:
            handler(event)
