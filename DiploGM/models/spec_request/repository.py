from abc import ABC

from DiploGM.repositories.base import Repository
from .spec_request import SpecRequest

class SpecRequestRepository(Repository[SpecRequest], ABC):
    pass
