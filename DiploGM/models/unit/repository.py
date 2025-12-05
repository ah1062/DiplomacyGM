from abc import ABC

from DiploGM.repositories.base import Repository
from .unit import Unit

class UnitRepository(Repository[Unit], ABC):
    pass
