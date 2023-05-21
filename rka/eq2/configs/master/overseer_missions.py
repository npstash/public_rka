from enum import Enum, auto
from typing import List, Optional


class OverseerMissionTier(Enum):
    Celestial = auto()
    Fabled = auto()
    Legendary = auto()
    Treasured = auto()


class OverseerSeason:
    def __init__(self,
                 celestial_missions: List[str],
                 fabled_missions: List[str],
                 legendary_missions: List[str],
                 treasured_missions: List[str],
                 buy_charged_priority: Optional[int],
                 ):
        self.celestial_missions = celestial_missions
        self.fabled_missions = fabled_missions
        self.legendary_missions = legendary_missions
        self.treasured_missions = treasured_missions
        self.buy_charged_priority = buy_charged_priority
        self.all_missions = celestial_missions + fabled_missions + legendary_missions + treasured_missions
        self.missions_by_tier = {
            OverseerMissionTier.Celestial: celestial_missions,
            OverseerMissionTier.Fabled: fabled_missions,
            OverseerMissionTier.Legendary: legendary_missions,
            OverseerMissionTier.Treasured: treasured_missions,
        }


class OverseerSeasons(Enum):
    SEASON_1 = OverseerSeason(
        celestial_missions=[
        ],
        fabled_missions=[
            'Save the Vision of Vox',  # 20
            'Retrieval for the Crown',  # 20
            'The Word of Thule',  # 20
            'The Kra\'thuk\'s Magical Properties',  # 20
            'Eliminate Venekor',  # 20
        ],
        legendary_missions=[
            'Convince the Guardians',  # 20
            'Exact Revenge on the Drakota',  # 20
            'Reacquire the Idol of Solusek Ro',  # 20
            'Recover the Stolen Scrolls',  # 20
            'Save the Valkyrie Princess',  # 20
            'Eliminate Warlord Ix Acon',  # 15
            'Find the Golden Idol of the Drafling',  # 15
            'Save Orxilia Calogn',  # 15
            'Find the Goblin Banker\'s Loot',  # 10
            'Liberate Lady Laravale',  # 10
            'The Throne of Emperor Fyst',  # 10
        ],
        treasured_missions=[
            'Eliminate Klirkan X\'Davai',  # 15
            'Save Lira Singlebellows',  # 15
            'The Thexian Wizard\'s Wand',  # 15
            'Treasure in Shortwine Burrow',  # 15
            'Captured in Bramble Woods',  # 10
            'Rob the Fool\'s Gold Tavern',  # 10
            'Slay the Evol Ew Chieftain',  # 10
            'Thexian Treasure',  # 10
            'Valuable Runes in a Dirty Place',  # 10
            'A Dark Ceremony',  # 5
            'Eliminate the Gang Lord',  # 5
            'Keeper for the Keep',  # 5
            'Lord Sellwin\'s Locket',  # 5
            'Rescue Captain Wilcox',  # 5
        ],
        buy_charged_priority=1,
    )
    SEASON_2 = OverseerSeason(
        celestial_missions=[
            'Ewer of Sul\'Dae',  # 25
            'Eliminate the Djinn Master',  # 25
        ],
        fabled_missions=[
            'The Platinum Eye',  # 20
            'Eliminate Ahk\'Mun Rhoen',  # 20
            'The Scepter of Life',  # 20
            'Retrieve the Golden Scale',  # 20
            'Save Xideus Yoatiak',  # 20
        ],
        legendary_missions=[
            'Eliminate Meathooks',  # 20
            'Rescue Gumbolt Triggerhand',  # 20
            'The Blackened Scepter',  # 20
            'The Broken Lord\'s Crown',  # 20
            'The Golden Tablet',  # 20
            'Eliminate Blademaster Thul',  # 15
            'Save Joana Larr',  # 15
            'The Priceless Time Monocle',  # 15
            'Pirate Strongbox',  # 10
            'Save Milo Brownfoot',  # 10
            'Shield of Cazel the Mad',  # 10
        ],
        treasured_missions=[
            'Ancient Spices',
            'Eliminate Harbinger Siyuth',
            'Eliminate Herald Zydul',
            'Eliminate Lady Samiel',
            'Pilfer Tan\'ke Rei\'s Golden Cap',
            'Raja the Sunspeaker\'s Staff',
            'Rescue Dolloran Arkur from Azhahkar the Gatecaller',
            'Rescue Lady Mirolyn from Gorakhul the Annihilator',
            'Save Lord Pardun from Queen Marrowjaw',
            'Steal Yinderis the Snake Charmer\'s Jeweled Pipe',
            'The Golden Trowel',
            'The Jeweled Fez',
        ],
        buy_charged_priority=2,
    )
    SEASON_3 = OverseerSeason(
        celestial_missions=[
            'The Boots of Terror',  # 25
            'Eliminate Vilucidae the Priest of Thule',  # 25
            'The Blood Ember Breastplate',  # 30
            'Save Fitzpitzle',  # 30
            'Tarinax\'s Head',  # 30
        ],
        fabled_missions=[
            'Shield of the White Dragon',  # 20
            'Eliminate Pantrilla',  # 20
            'Save Karnos Van Kellin',  # 20
            'Retrieve the Silver Sword of Rage',  # 20
            'Gaudralek, Sword of the Sky',  # 20
        ],
        legendary_missions=[
            'The Splitscar Bow',  # 20
            'Eliminate the Enmity of Naar\'Yora',  # 20
            'Treasure in the Halls',  # 20
            'The Wand of Oblivion',  # 20
            'Rescue Raluvh',  # 20
            'Eliminate Oracle Tuunza',  # 15
            'The Vaults of El\'Arad',  # 15
            'Save Turadramin',  # 15
            'The Queen\'s Trove',  # 10
            'The Crown of X\'haviz',  # 10
            'Save Gribbly the Gallant',  # 10
        ],
        treasured_missions=[
            'The Gloompall Gewgaw',
            'The Emble of the Lost Gods',
            'The Drained Soul Husk',
            'Steal the Reformation Trinket',
            'Steal the Balefire Blade',
            'Save Jabber Longwind from The Brood Matron',
            'Rescue Gimdimble Fizzwoddle from the Ravaging Maw',
            'Rescue Constance Cloudpuff from Skymarshal Stormfeather',
            'Pilfer the Beguiler\'s Gemmed Robe',
            'Eliminate Queen Bazzt Bzzt the 200th',
            'Eliminate Konarr the Despoiler',
        ],
        buy_charged_priority=3,
    )
    SEASON_4 = OverseerSeason(
        celestial_missions=[
            'Growth Requires Seeds',
            'Rescue Simone Chelmonte',
            'Band of the Chosen',
        ],
        fabled_missions=[
            'Retrieve the Amulet of Forsaken Rites',
            'Eliminate Zylphax the Shredder',
            'Eliminate Gardener Thirgen',
            'Blood-Crusted Band',
            'Save Jamus Cornerlly',
            'The Ring of Blooding',
            'Cuirass of Perpetuity',
        ],
        legendary_missions=[
            'The Spellborn Relic',
            'Blight and Light',
            'Tools of Success',
            'Anon in Klak\'Anon',
            'The Spellborn Relic',
            'Do Not Count On the Count',
            'Some Sage Advice',
            'Throwing Down the Gauntlet',
            'The Royal Band',
            'The Davissi Code',
            'Unrest in Butcherblock',
            'Born to Somborn',
        ],
        treasured_missions=[
            'A Miner Setback',
            'Cloak of the Magi',
            'Kill Zappodill',
            'Dance Haywire, Dance',
            'Ice-forged Satchel',
            'Oversee the Overseer',
            'Runic Bow of Calling',
            'Barking and Biting Back',
            'Master the Master',
            'Eliminate Crumb Shinspitter',
            'Plunder the Pumpkin King',
            'Save Hedwocket Cobbleblork',
        ],
        buy_charged_priority=None,
    )
