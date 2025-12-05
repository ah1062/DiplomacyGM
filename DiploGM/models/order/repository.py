from abc import ABC

from DiploGM.repositories.base import Repository
from .order import Order

class OrderRepository(Repository[Order], ABC):
    pass
