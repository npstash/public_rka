from __future__ import annotations

from enum import auto
from typing import Optional, Union, Set

from rka.util.util import NameEnum


class GameClassName(NameEnum):
    Local = auto()
    Remote = auto()
    Items = auto()
    Commoner = auto()
    Ascension = auto()
    Elementalist = auto()
    Thaumaturgist = auto()
    Geomancer = auto()
    Etherealist = auto()

    Fighter = auto()
    Warrior = auto()
    Crusader = auto()
    Brawler = auto()
    Guardian = auto()
    Berserker = auto()
    Paladin = auto()
    Shadowknight = auto()
    Monk = auto()
    Bruiser = auto()

    Priest = auto()
    Cleric = auto()
    Druid = auto()
    Shaman = auto()
    Templar = auto()
    Inquisitor = auto()
    Warden = auto()
    Fury = auto()
    Mystic = auto()
    Defiler = auto()
    Channeler = auto()

    Scout = auto()
    Thug = auto()
    Bard = auto()
    Predator = auto()
    Brigand = auto()
    Swashbuckler = auto()
    Dirge = auto()
    Troubador = auto()
    Ranger = auto()
    Assassin = auto()
    Beastlord = auto()

    Mage = auto()
    Sorcerer = auto()
    Summoner = auto()
    Enchanter = auto()
    Wizard = auto()
    Warlock = auto()
    Conjuror = auto()
    Necromancer = auto()
    Illusionist = auto()
    Coercer = auto()

    Artisan = auto()
    Scholar = auto()
    Sage = auto()
    Alchemist = auto()
    Jeweler = auto()
    Craftsman = auto()
    Carpenter = auto()
    Woodworker = auto()
    Provisioner = auto()
    Outfitter = auto()
    Weaponsmith = auto()
    Armorer = auto()
    Tailor = auto()


class GameClass:
    def __init__(self, classname: GameClassName, business: int, superclasses: Optional[GameClass]):
        self.name = classname.name
        self.business = business
        self.superclass = superclasses

    def __str__(self):
        return self.name

    def get_archetype(self) -> GameClass:
        for archetype in class_archetypes:
            if self == archetype or self.is_subclass_of(archetype):
                return archetype
        return self

    def is_subclass_of(self, superclass: GameClass) -> bool:
        if self.superclass is None:
            return self == superclass
        if self.superclass == superclass:
            return True
        return self.superclass.is_subclass_of(superclass)


class GameClasses:
    Local = GameClass(GameClassName.Local, 0, None)
    Remote = GameClass(GameClassName.Remote, 0, None)
    Items = GameClass(GameClassName.Items, 0, None)
    Commoner = GameClass(GameClassName.Commoner, 0, None)

    Fighter = GameClass(GameClassName.Fighter, 0, Commoner)
    Warrior = GameClass(GameClassName.Warrior, 0, Fighter)
    Crusader = GameClass(GameClassName.Crusader, 0, Fighter)
    Brawler = GameClass(GameClassName.Brawler, 0, Fighter)
    Bruiser = GameClass(GameClassName.Bruiser, 10, Brawler)
    Monk = GameClass(GameClassName.Monk, 10, Brawler)
    Paladin = GameClass(GameClassName.Paladin, 10, Crusader)
    Shadowknight = GameClass(GameClassName.Shadowknight, 10, Crusader)
    Guardian = GameClass(GameClassName.Guardian, 10, Warrior)
    Berserker = GameClass(GameClassName.Berserker, 10, Warrior)

    Priest = GameClass(GameClassName.Priest, 0, Commoner)
    Cleric = GameClass(GameClassName.Cleric, 0, Priest)
    Shaman = GameClass(GameClassName.Shaman, 0, Priest)
    Druid = GameClass(GameClassName.Druid, 0, Priest)
    Mystic = GameClass(GameClassName.Mystic, 9, Shaman)
    Defiler = GameClass(GameClassName.Defiler, 9, Shaman)
    Templar = GameClass(GameClassName.Templar, 7, Cleric)
    Inquisitor = GameClass(GameClassName.Inquisitor, 7, Cleric)
    Warden = GameClass(GameClassName.Warden, 8, Druid)
    Fury = GameClass(GameClassName.Fury, 7, Druid)
    Channeler = GameClass(GameClassName.Channeler, 7, Priest)

    Mage = GameClass(GameClassName.Mage, 0, Commoner)
    Sorcerer = GameClass(GameClassName.Sorcerer, 0, Mage)
    Summoner = GameClass(GameClassName.Summoner, 0, Mage)
    Enchanter = GameClass(GameClassName.Enchanter, 0, Mage)
    Illusionist = GameClass(GameClassName.Illusionist, 5, Enchanter)
    Coercer = GameClass(GameClassName.Coercer, 5, Enchanter)
    Conjuror = GameClass(GameClassName.Conjuror, 3, Summoner)
    Necromancer = GameClass(GameClassName.Necromancer, 3, Summoner)
    Wizard = GameClass(GameClassName.Wizard, 0, Sorcerer)
    Warlock = GameClass(GameClassName.Warlock, 0, Sorcerer)

    Scout = GameClass(GameClassName.Scout, 0, Commoner)
    Thug = GameClass(GameClassName.Thug, 0, Scout)
    Bard = GameClass(GameClassName.Bard, 0, Scout)
    Predator = GameClass(GameClassName.Predator, 0, Scout)
    Dirge = GameClass(GameClassName.Dirge, 4, Bard)
    Troubador = GameClass(GameClassName.Troubador, 6, Bard)
    Swashbuckler = GameClass(GameClassName.Swashbuckler, 0, Thug)
    Brigand = GameClass(GameClassName.Brigand, 2, Thug)
    Ranger = GameClass(GameClassName.Ranger, 0, Predator)
    Assassin = GameClass(GameClassName.Assassin, 0, Predator)
    Beastlord = GameClass(GameClassName.Beastlord, 7, Scout)

    Ascension = GameClass(GameClassName.Ascension, 0, Commoner)
    Elementalist = GameClass(GameClassName.Elementalist, 2, Ascension)
    Etherealist = GameClass(GameClassName.Etherealist, 0, Ascension)
    Thaumaturgist = GameClass(GameClassName.Thaumaturgist, 0, Ascension)
    Geomancer = GameClass(GameClassName.Geomancer, 2, Ascension)

    Artisan = GameClass(GameClassName.Artisan, 0, None)
    Scholar = GameClass(GameClassName.Scholar, 0, Artisan)
    Sage = GameClass(GameClassName.Sage, 0, Scholar)
    Alchemist = GameClass(GameClassName.Alchemist, 0, Scholar)
    Jeweler = GameClass(GameClassName.Jeweler, 0, Scholar)
    Craftsman = GameClass(GameClassName.Craftsman, 0, Artisan)
    Carpenter = GameClass(GameClassName.Carpenter, 0, Craftsman)
    Woodworker = GameClass(GameClassName.Woodworker, 0, Craftsman)
    Provisioner = GameClass(GameClassName.Provisioner, 0, Craftsman)
    Outfitter = GameClass(GameClassName.Outfitter, 0, Artisan)
    Weaponsmith = GameClass(GameClassName.Weaponsmith, 0, Outfitter)
    Armorer = GameClass(GameClassName.Armorer, 0, Outfitter)
    Tailor = GameClass(GameClassName.Tailor, 0, Outfitter)

    @staticmethod
    def get_class_by_name(name: Union[str, GameClassName]) -> GameClass:
        if isinstance(name, GameClassName):
            name = name.name
        return GameClasses.__dict__[name]

    @staticmethod
    def get_class_by_name_lower(name: str) -> Optional[GameClass]:
        name = name.capitalize()
        if name not in GameClasses.__dict__:
            return None
        return GameClasses.__dict__[name]

    @staticmethod
    def get_subclasses(superclass: GameClass) -> Set[GameClass]:
        result = {superclass}
        for game_class in GameClasses.__dict__.values():
            if not isinstance(game_class, GameClass):
                continue
            if game_class.is_subclass_of(superclass):
                result.add(game_class)
        return result


class_archetypes = [
    GameClasses.Priest,
    GameClasses.Scout,
    GameClasses.Fighter,
    GameClasses.Mage,
    GameClasses.Scholar,
    GameClasses.Craftsman,
    GameClasses.Outfitter,
]
