import logging

from bot.bot import DiploGM
from bot.core.events import Event
from bot.core.eventbus import EventBus
from bot.listeners.base import BaseListener

logger = logging.getLogger(__name__)


class SampleListener(BaseListener):
    def __init__(self, bot=None):
        self.bot: DiploGM | None = bot

    def setup(self, bus: EventBus):
        bus.subscribe(Event, self.shout)

    def teardown(self):
        pass

    def shout(self, event: Event):
        logger.info(f"{self}: AHHH")
