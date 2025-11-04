from abc import ABC, abstractmethod


from bot.core.eventbus import EventBus


class BaseListener(ABC):
    def __init__(self, bot=None):
        self.bot = bot

    @abstractmethod
    def setup(self, bus: EventBus):
        pass

    def teardown(self):
        pass
