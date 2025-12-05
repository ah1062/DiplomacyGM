from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Callable, Generic, Iterable, List, Optional, TypeVar

T = TypeVar('T')
Predicate = Callable[[T], bool]

class Repository(ABC, Generic[T]):
    @abstractmethod
    def save(self, entity: T) -> T: ...
    
    @abstractmethod
    def load(self, id: int) -> Optional[T]: ...
    
    @abstractmethod
    def delete(self, entity: T) -> None: ...
    
    @abstractmethod
    def all(self) -> Iterable[T]: ...

    def find_by(self, predicate: Predicate) -> List[T]:
        return [e for e in self.all() if predicate(e)]

    def find_one_by(self, predicate: Predicate) -> Optional[T]:
        for e in self.all():
            if predicate(e):
                return e

        return None
