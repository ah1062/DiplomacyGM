from abc import ABC

from DiploGM.repositories.base import Repository
from .province import Province

class ProvinceRepository(Repository[Province], ABC):
    pass
