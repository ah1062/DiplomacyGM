import logging

from events import Event, OrderSubmitted
from eventbus import EventBus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def orders(e: OrderSubmitted):
    logger.info(f"Order {e}")


bus = EventBus()
bus.subscribe(OrderSubmitted, orders)

o = OrderSubmitted()
bus.publish(o)

o = Event()
bus.publish(o)
