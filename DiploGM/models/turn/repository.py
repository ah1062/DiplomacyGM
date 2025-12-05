from abc import ABC

from DiploGM.repositories.base import Repository
from .turn import Turn

class TurnRepoistory(Repository[Turn], ABC):
    pass
