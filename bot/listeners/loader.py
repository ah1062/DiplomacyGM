import importlib
import logging
import pkgutil
from typing import List

import bot.listeners as ln_pkg
from bot.listeners.base import BaseListener

logger = logging.getLogger(__name__)


def load_listeners(package: str, bot=None) -> List[BaseListener]:
    listeners = []
    for _, name, _ in pkgutil.iter_modules(ln_pkg.__path__):
        module = importlib.import_module(f"{package}.{name}")
        for obj in module.__dict__.values():
            if obj is BaseListener:
                continue

            if isinstance(obj, type) and issubclass(obj, BaseListener):
                instance = obj(bot)
                listeners.append(instance)

    return listeners
