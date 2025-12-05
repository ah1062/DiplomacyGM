from abc import ABC

from DiploGM.repositories.base import Repository
from .player import Player

class PlayerRepoistory(Repository[Player], ABC):
    pass
