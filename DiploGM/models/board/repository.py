from abc import ABC

from DiploGM.repositories.base import Repository
from .board import Board

class BoardRepository(Repository[Board], ABC):
    pass
