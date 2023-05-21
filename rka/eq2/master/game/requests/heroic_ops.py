from rka.eq2.master.game.ability import HOIcon
from rka.eq2.master.game.engine.heroic import HOs

HEROIC_OPPORTUNITIES = {
    # Priest
    'Divine Judgement': HOs.all(HOIcon.DivineProvidence, HOIcon.Hammer).plus(HOIcon.Hammer),
    'Inspiring Piety': HOs.all(HOIcon.DivineProvidence, HOIcon.Hammer).plus(HOIcon.Hammer),
    'Blessing of Faith': HOs.all(HOIcon.DivineProvidence, HOIcon.Hammer).plus(HOIcon.Chalice),
    # Priest->Scout
    'Piercing Faith': HOs.all(HOIcon.DivineProvidence, HOIcon.Coin).plus(HOIcon.Cloak).plus(HOIcon.Moon),
    'Divine Trickery': HOs.seq(HOIcon.DivineProvidence, HOIcon.Coin).then(HOIcon.Chalice).then(HOIcon.Cloak),
    'Fervent Quickening': HOs.seq(HOIcon.DivineProvidence, HOIcon.Coin).then(HOIcon.Dagger).then(HOIcon.Chalice),
    'Faith\'s Bulwark': HOs.seq(HOIcon.DivineProvidence, HOIcon.Coin).then(HOIcon.Chalice).then(HOIcon.Cloak),

    # Mage
    'Arcane Fury': HOs.all(HOIcon.ArcaneAugur, HOIcon.Lightning).plus(HOIcon.Lightning),
    'Arcane Storm': HOs.all(HOIcon.ArcaneAugur, HOIcon.Lightning).plus(HOIcon.Star),
    'Arcane Enlightenment': HOs.all(HOIcon.ArcaneAugur, HOIcon.Lightning).plus(HOIcon.Flame),
    # Mage->Priest
    'Ancient Crucible': HOs.all(HOIcon.ArcaneAugur, HOIcon.Hammer).plus(HOIcon.Moon),
    'Suffocating Wrath': HOs.all(HOIcon.ArcaneAugur, HOIcon.Hammer).plus(HOIcon.Hammer).plus(HOIcon.Lightning),
    'Celestial Bloom': HOs.all(HOIcon.ArcaneAugur, HOIcon.Hammer).plus(HOIcon.Lightning).plus(HOIcon.Chalice),
    'Arcane Chalice': HOs.seq(HOIcon.ArcaneAugur, HOIcon.Hammer).then(HOIcon.Flame).then(HOIcon.Chalice),
    # Mage->Scout
    'Arcane Trickery': HOs.all(HOIcon.ArcaneAugur, HOIcon.Coin).plus(HOIcon.Lightning).plus(HOIcon.Dagger),
    'Resonating Cascade': HOs.all(HOIcon.ArcaneAugur, HOIcon.Coin).plus(HOIcon.Mask).plus(HOIcon.Dagger).plus(HOIcon.Lightning),
    'Trickster\'s Grasp': HOs.seq(HOIcon.ArcaneAugur, HOIcon.Coin).then(HOIcon.Flame).then(HOIcon.Mask),
    'Shower of Daggers': HOs.seq(HOIcon.ArcaneAugur, HOIcon.Coin).then(HOIcon.Dagger).then(HOIcon.Lightning),

    # Fighter
    'Crushing Anvil': HOs.all(HOIcon.FightingChance, HOIcon.Sword).plus(HOIcon.Fist),
    'Sky Cleave': HOs.all(HOIcon.FightingChance, HOIcon.Sword).plus(HOIcon.Fist),
    'Hero\'s Armor': HOs.all(HOIcon.FightingChance, HOIcon.Sword).plus(HOIcon.Fist),
    # Fighter->Scout
    'Luck\'s Bite': HOs.all(HOIcon.FightingChance, HOIcon.Coin).plus(HOIcon.Boot).plus(HOIcon.Cloak),
    'Ardent Challenge': HOs.all(HOIcon.FightingChance, HOIcon.Coin).plus(HOIcon.Arm).plus(HOIcon.Mask),
    'Swindler\'s Gift': HOs.seq(HOIcon.FightingChance, HOIcon.Coin).then(HOIcon.Cloak).then(HOIcon.Arm),
    'Raging Sword': HOs.seq(HOIcon.FightingChance, HOIcon.Coin).then(HOIcon.Cloak).then(HOIcon.Horn),
    # Fighter->Mage
    'Scholar\'s Insight': HOs.seq(HOIcon.FightingChance, HOIcon.Lightning).then(HOIcon.Horn).then(HOIcon.Lightning),
    'Arcane Aegis': HOs.all(HOIcon.FightingChance, HOIcon.Lightning).plus(HOIcon.Fist).plus(HOIcon.Star),
    'Storm of Ancients': HOs.all(HOIcon.FightingChance, HOIcon.Lightning).plus(HOIcon.Lightning).plus(HOIcon.Horn),
    'Soldier\'s Instinct': HOs.seq(HOIcon.FightingChance, HOIcon.Lightning).then(HOIcon.Flame).then(HOIcon.Arm),
    # Fighter->Priest
    'Divine Blade': HOs.all(HOIcon.FightingChance, HOIcon.Chalice).plus(HOIcon.Hammer).plus(HOIcon.Sword),
    'Divine Nobility': HOs.all(HOIcon.FightingChance, HOIcon.Chalice).plus(HOIcon.Sword).plus(HOIcon.Chalice),
    'Crippling Shroud': HOs.all(HOIcon.FightingChance, HOIcon.Chalice).plus(HOIcon.Horn).plus(HOIcon.Moon),
    'Chalice of Life': HOs.all(HOIcon.FightingChance, HOIcon.Chalice).plus(HOIcon.Chalice),
    # Fighter->Priest+Mage
    'Arcane Salvation': HOs.all(HOIcon.FightingChance, [HOIcon.Hammer, HOIcon.Lightning]).plus(HOIcon.Star).plus(HOIcon.Arm).plus(HOIcon.Chalice),
    'Archaic Ruin': HOs.seq(HOIcon.FightingChance, [HOIcon.Hammer, HOIcon.Lightning]).then(HOIcon.Eye).then(HOIcon.Arm).then(HOIcon.Flame),
    'Thunder Slash': HOs.all(HOIcon.FightingChance, [HOIcon.Hammer, HOIcon.Lightning]).plus(HOIcon.Sword).plus(HOIcon.Flame).plus(HOIcon.Hammer),
    'Ancient Wrath': HOs.seq(HOIcon.FightingChance, [HOIcon.Hammer, HOIcon.Lightning]).then(HOIcon.Flame).then(HOIcon.Fist).then(HOIcon.Hammer),

    # Scout
    'Ringing Blow': HOs.all(HOIcon.LuckyBreak, HOIcon.Coin).plus(HOIcon.Dagger),
    'Swindler\'s Luck': HOs.all(HOIcon.LuckyBreak, HOIcon.Coin).plus(HOIcon.Dagger),
    'Bravo\'s Dance': HOs.all(HOIcon.LuckyBreak, HOIcon.Coin).plus(HOIcon.Dagger),
    # Scout->Priest+Fighter
    'Verdant Trinity': HOs.all(HOIcon.LuckyBreak, [HOIcon.Boot, HOIcon.Chalice]).plus(HOIcon.Chalice),
    'Capricious Strike': HOs.all(HOIcon.LuckyBreak, [HOIcon.Boot, HOIcon.Chalice]).plus(HOIcon.Hammer).plus(HOIcon.Dagger).plus(HOIcon.Sword),
    'Nature\'s Growth': HOs.all(HOIcon.LuckyBreak, [HOIcon.Boot, HOIcon.Chalice]).plus(HOIcon.Mask).plus(HOIcon.Sword).plus(HOIcon.Hammer),
    'Shield of Ancients': HOs.all(HOIcon.LuckyBreak, [HOIcon.Boot, HOIcon.Chalice]).plus(HOIcon.Lightning).plus(HOIcon.Horn).plus(HOIcon.Moon),
    # Scout->Mage+Fighter
    'Trinity Divide': HOs.all(HOIcon.LuckyBreak, [HOIcon.Horn, HOIcon.Lightning]).plus(HOIcon.Star).plus(HOIcon.Mask).plus(HOIcon.Horn),
    'Soldier\'s Gambit': HOs.all(HOIcon.LuckyBreak, [HOIcon.Horn, HOIcon.Lightning]).plus(HOIcon.Sword).plus(HOIcon.Dagger).plus(HOIcon.Lightning),
    'Grand Proclamation': HOs.seq(HOIcon.LuckyBreak, [HOIcon.Horn, HOIcon.Lightning]).then(HOIcon.Lightning).then(HOIcon.Mask).then(HOIcon.Arm),
    'Ancient\'s Embrace': HOs.seq(HOIcon.LuckyBreak, [HOIcon.Horn, HOIcon.Lightning]).then(HOIcon.Flame).then(HOIcon.Cloak).then(HOIcon.Arm),
    # Scout->Priest+Mage
    'Breaking Faith': HOs.seq(HOIcon.LuckyBreak, [HOIcon.Chalice, HOIcon.Lightning]).then(HOIcon.Lightning).then(HOIcon.Eye),
    'Archaic Shackles': HOs.seq(HOIcon.LuckyBreak, [HOIcon.Chalice, HOIcon.Lightning]).then(HOIcon.Lightning).then(HOIcon.Hammer).then(HOIcon.Dagger),
    'Crucible of Life': HOs.seq(HOIcon.LuckyBreak, [HOIcon.Chalice, HOIcon.Lightning]).then(HOIcon.Lightning).then(HOIcon.Cloak).then(HOIcon.Chalice),
    'Luminary Fate': HOs.seq(HOIcon.LuckyBreak, [HOIcon.Chalice, HOIcon.Lightning]).then(HOIcon.Sword).then(HOIcon.Eye).then(HOIcon.Flame),
    # Scout->Priest+Mage+Fighter
    'Tears of Luclin': HOs.seq(HOIcon.LuckyBreak, [HOIcon.Horn, HOIcon.Moon, HOIcon.Flame]).then(HOIcon.Boot).then(HOIcon.Dagger).then(HOIcon.Lightning),
    'Strength in Unity': HOs.all(HOIcon.LuckyBreak, [HOIcon.Horn, HOIcon.Moon, HOIcon.Flame]).plus(HOIcon.Chalice).plus(HOIcon.Arm),
    'Past\'s Awakening': HOs.seq(HOIcon.LuckyBreak, [HOIcon.Horn, HOIcon.Moon, HOIcon.Flame]).then(HOIcon.Star).then(HOIcon.Arm).then(HOIcon.Cloak),
    'Ancient Demise': HOs.all(HOIcon.LuckyBreak, [HOIcon.Horn, HOIcon.Moon, HOIcon.Flame]).plus(HOIcon.Boot).plus(HOIcon.Cloak).plus(HOIcon.Lightning).plus(
        HOIcon.Hammer),
}
