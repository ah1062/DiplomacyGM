from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Type, TypeVar

from DiploGM.repositories.base.base import Repository

T = TypeVar("T")

class RepositoryFactory(ABC):
    @abstractmethod
    def create(self, model_type: Type[T]) -> Repository[T]:
        pass
