from rka.eq2.master.game.gameclass import GameClasses
from rka.eq2.master.game.ability.ability_locator import AbilityLocatorFactory


class AlchemistAbilities:
    analyze = AbilityLocatorFactory.create(GameClasses.Alchemist, 'analyze', 'analyze', 'experiment')
    endothermic = AbilityLocatorFactory.create(GameClasses.Alchemist, 'endothermic', 'endothermic', 'endothermic')
    exothermic = AbilityLocatorFactory.create(GameClasses.Alchemist, 'exothermic', 'exothermic', 'endothermic')
    experiment = AbilityLocatorFactory.create(GameClasses.Alchemist, 'experiment', 'experiment', 'experiment')
    reactions = AbilityLocatorFactory.create(GameClasses.Alchemist, 'reactions', 'reactions', 'reactions')
    synthesis = AbilityLocatorFactory.create(GameClasses.Alchemist, 'synthesis', 'synthesis', 'reactions')


class ArmorerAbilities:
    angle_joint = AbilityLocatorFactory.create(GameClasses.Armorer, 'angle_joint', 'angle joint', 'angle joint')
    bridle_joint = AbilityLocatorFactory.create(GameClasses.Armorer, 'bridle_joint', 'bridle joint', 'angle joint')
    hammering = AbilityLocatorFactory.create(GameClasses.Armorer, 'hammering', 'hammering', 'hammering')
    steady_heat = AbilityLocatorFactory.create(GameClasses.Armorer, 'steady_heat', 'steady heat', 'steady heat')
    stoke_coals = AbilityLocatorFactory.create(GameClasses.Armorer, 'stoke_coals', 'stoke coals', 'steady heat')
    strikes = AbilityLocatorFactory.create(GameClasses.Armorer, 'strikes', 'strikes', 'hammering')


class ArtisanAbilities:
    salvage = AbilityLocatorFactory.create(GameClasses.Artisan, 'salvage', 'salvage', 'salvage')


class BardAbilities:
    bladedance = AbilityLocatorFactory.create(GameClasses.Bard, 'bladedance', 'bladedance', 'bladedance')
    deadly_dance = AbilityLocatorFactory.create(GameClasses.Bard, 'deadly_dance', 'deadly dance', 'deadly dance')
    disheartening_descant = AbilityLocatorFactory.create(GameClasses.Bard, 'disheartening_descant', 'disheartening descant', 'disheartening descant')
    dodge_and_cover = AbilityLocatorFactory.create(GameClasses.Bard, 'dodge_and_cover', 'dodge and cover', 'dodge and cover')
    hungering_lyric = AbilityLocatorFactory.create(GameClasses.Bard, 'hungering_lyric', 'hungering lyric', 'hungering lyric')
    melody_of_affliction = AbilityLocatorFactory.create(GameClasses.Bard, 'melody_of_affliction', 'melody of affliction', 'melody of affliction')
    quick_tempo = AbilityLocatorFactory.create(GameClasses.Bard, 'quick_tempo', 'quick tempo', 'quick tempo')
    requiem = AbilityLocatorFactory.create(GameClasses.Bard, 'requiem', 'requiem', 'requiem')
    shroud = AbilityLocatorFactory.create(GameClasses.Bard, 'shroud', 'shroud', 'shroud')
    song_of_shielding = AbilityLocatorFactory.create(GameClasses.Bard, 'song_of_shielding', 'song of shielding', 'song of shielding')
    songspinners_note = AbilityLocatorFactory.create(GameClasses.Bard, 'songspinners_note', 'songspinner\'s note', 'songspinner\'s note')
    veil_of_notes = AbilityLocatorFactory.create(GameClasses.Bard, 'veil_of_notes', 'veil of notes', 'veil of notes')
    zanders_choral_rebuff = AbilityLocatorFactory.create(GameClasses.Bard, 'zanders_choral_rebuff', 'zander\'s choral rebuff', 'zander\'s choral rebuff')
    brias_inspiring_ballad = AbilityLocatorFactory.create(GameClasses.Bard, 'brias_inspiring_ballad', 'bria\'s inspiring ballad', 'bria\'s inspiring ballad')


class BrawlerAbilities:
    baton_flurry = AbilityLocatorFactory.create(GameClasses.Brawler, 'baton_flurry', 'baton flurry', 'baton flurry')
    boneshattering_combination = AbilityLocatorFactory.create(GameClasses.Brawler, 'boneshattering_combination', 'boneshattering combination', 'boneshattering combination')
    brawlers_tenacity = AbilityLocatorFactory.create(GameClasses.Brawler, 'brawlers_tenacity', 'brawler\'s tenacity', 'brawler\'s tenacity')
    chi = AbilityLocatorFactory.create(GameClasses.Brawler, 'chi', 'chi', 'chi')
    combat_mastery = AbilityLocatorFactory.create(GameClasses.Brawler, 'combat_mastery', 'combat mastery', 'combat mastery')
    crane_flock = AbilityLocatorFactory.create(GameClasses.Brawler, 'crane_flock', 'crane flock', 'crane flock')
    crane_sweep = AbilityLocatorFactory.create(GameClasses.Brawler, 'crane_sweep', 'crane sweep', 'crane sweep')
    devastation_fist = AbilityLocatorFactory.create(GameClasses.Brawler, 'devastation_fist', 'devastation fist', 'devastation fist')
    eagle_spin = AbilityLocatorFactory.create(GameClasses.Brawler, 'eagle_spin', 'eagle spin', 'eagle spin')
    eagles_patience = AbilityLocatorFactory.create(GameClasses.Brawler, 'eagles_patience', 'eagle\'s patience', 'eagle\'s patience')
    inner_focus = AbilityLocatorFactory.create(GameClasses.Brawler, 'inner_focus', 'inner focus', 'inner focus')
    mantis_leap = AbilityLocatorFactory.create(GameClasses.Brawler, 'mantis_leap', 'mantis leap', 'mantis leap')
    mantis_star = AbilityLocatorFactory.create(GameClasses.Brawler, 'mantis_star', 'mantis star', 'mantis star')
    pressure_point = AbilityLocatorFactory.create(GameClasses.Brawler, 'pressure_point', 'pressure point', 'pressure point')
    sneering_assault = AbilityLocatorFactory.create(GameClasses.Brawler, 'sneering_assault', 'sneering assault', 'sneering assault')
    stone_cold = AbilityLocatorFactory.create(GameClasses.Brawler, 'stone_cold', 'stone cold', 'stone cold')
    tag_team = AbilityLocatorFactory.create(GameClasses.Brawler, 'tag_team', 'tag team', 'tag team')


class BrigandAbilities:
    barroom_negotiation = AbilityLocatorFactory.create(GameClasses.Brigand, 'barroom_negotiation', 'barroom negotiation', 'barroom negotiation')
    battery_and_assault = AbilityLocatorFactory.create(GameClasses.Brigand, 'battery_and_assault', 'battery and assault', 'battery and assault')
    beg_for_mercy = AbilityLocatorFactory.create(GameClasses.Brigand, 'beg_for_mercy', 'beg for mercy', 'beg for mercy')
    black_jack = AbilityLocatorFactory.create(GameClasses.Brigand, 'black_jack', 'black jack', 'black jack')
    blinding_dust = AbilityLocatorFactory.create(GameClasses.Brigand, 'blinding_dust', 'blinding dust', 'blinding dust')
    bum_rush = AbilityLocatorFactory.create(GameClasses.Brigand, 'bum_rush', 'bum rush', 'bum rush')
    cornered = AbilityLocatorFactory.create(GameClasses.Brigand, 'cornered', 'cornered', 'cornered')
    crimson_swath = AbilityLocatorFactory.create(GameClasses.Brigand, 'crimson_swath', 'crimson swath', 'crimson swath')
    cuss = AbilityLocatorFactory.create(GameClasses.Brigand, 'cuss', 'cuss', 'cuss')
    debilitate = AbilityLocatorFactory.create(GameClasses.Brigand, 'debilitate', 'debilitate', 'debilitate')
    deceit = AbilityLocatorFactory.create(GameClasses.Brigand, 'deceit', 'deceit', 'deceit')
    deft_disarm = AbilityLocatorFactory.create(GameClasses.Brigand, 'deft_disarm', 'deft disarm', 'deft disarm')
    desperate_thrust = AbilityLocatorFactory.create(GameClasses.Brigand, 'desperate_thrust', 'desperate thrust', 'desperate thrust')
    dispatch = AbilityLocatorFactory.create(GameClasses.Brigand, 'dispatch', 'dispatch', 'dispatch')
    double_up = AbilityLocatorFactory.create(GameClasses.Brigand, 'double_up', 'double up', 'double up')
    entangle = AbilityLocatorFactory.create(GameClasses.Brigand, 'entangle', 'entangle', 'entangle')
    forced_arbitration = AbilityLocatorFactory.create(GameClasses.Brigand, 'forced_arbitration', 'forced arbitration', 'barroom negotiation')
    gut_rip = AbilityLocatorFactory.create(GameClasses.Brigand, 'gut_rip', 'gut rip', 'gut rip')
    holdup = AbilityLocatorFactory.create(GameClasses.Brigand, 'holdup', 'holdup', 'trick of the hunter')
    mug = AbilityLocatorFactory.create(GameClasses.Brigand, 'mug', 'mug', 'mug')
    murderous_rake = AbilityLocatorFactory.create(GameClasses.Brigand, 'murderous_rake', 'murderous rake', 'murderous rake')
    perforate = AbilityLocatorFactory.create(GameClasses.Brigand, 'perforate', 'perforate', 'puncture')
    puncture = AbilityLocatorFactory.create(GameClasses.Brigand, 'puncture', 'puncture', 'puncture')
    riot = AbilityLocatorFactory.create(GameClasses.Brigand, 'riot', 'riot', 'riot')
    safehouse = AbilityLocatorFactory.create(GameClasses.Brigand, 'safehouse', 'safehouse', 'safehouse')
    stunning_blow = AbilityLocatorFactory.create(GameClasses.Brigand, 'stunning_blow', 'stunning blow', 'stunning blow')
    thieves_guild = AbilityLocatorFactory.create(GameClasses.Brigand, 'thieves_guild', 'thieves guild', 'thieves guild')
    vital_strike = AbilityLocatorFactory.create(GameClasses.Brigand, 'vital_strike', 'vital strike', 'vital strike')
    will_to_survive = AbilityLocatorFactory.create(GameClasses.Brigand, 'will_to_survive', 'will to survive', 'will to survive')


class CarpenterAbilities:
    concentrate = AbilityLocatorFactory.create(GameClasses.Carpenter, 'concentrate', 'concentrate', 'concentrate')
    metallurgy = AbilityLocatorFactory.create(GameClasses.Carpenter, 'metallurgy', 'metallurgy', 'metallurgy')
    ponder = AbilityLocatorFactory.create(GameClasses.Carpenter, 'ponder', 'ponder', 'concentrate')
    smelting = AbilityLocatorFactory.create(GameClasses.Carpenter, 'smelting', 'smelting', 'metallurgy')
    tee_joint = AbilityLocatorFactory.create(GameClasses.Carpenter, 'tee_joint', 'tee joint', 'tee joint')
    wedge_joint = AbilityLocatorFactory.create(GameClasses.Carpenter, 'wedge_joint', 'wedge joint', 'tee joint')


class ClericAbilities:
    bulwark_of_faith = AbilityLocatorFactory.create(GameClasses.Cleric, 'bulwark_of_faith', 'bulwark of faith', 'bulwark of faith')
    divine_guidance = AbilityLocatorFactory.create(GameClasses.Cleric, 'divine_guidance', 'divine guidance', 'divine guidance')
    divine_waters = AbilityLocatorFactory.create(GameClasses.Cleric, 'divine_waters', 'divine waters', 'divine waters')
    equilibrium = AbilityLocatorFactory.create(GameClasses.Cleric, 'equilibrium', 'equilibrium', 'equilibrium')
    immaculate_revival = AbilityLocatorFactory.create(GameClasses.Cleric, 'immaculate_revival', 'immaculate revival', 'immaculate revival')
    light_of_devotion = AbilityLocatorFactory.create(GameClasses.Cleric, 'light_of_devotion', 'light of devotion', 'light of devotion')
    perseverance_of_the_divine = AbilityLocatorFactory.create(GameClasses.Cleric, 'perseverance_of_the_divine', 'perseverance of the divine', 'perseverance of the divine')


class CoercerAbilities:
    asylum = AbilityLocatorFactory.create(GameClasses.Coercer, 'asylum', 'asylum', 'asylum')
    brainshock = AbilityLocatorFactory.create(GameClasses.Coercer, 'brainshock', 'brainshock', 'brainshock')
    cannibalize_thoughts = AbilityLocatorFactory.create(GameClasses.Coercer, 'cannibalize_thoughts', 'cannibalize thoughts', 'cannibalize thoughts')
    channel = AbilityLocatorFactory.create(GameClasses.Coercer, 'channel', 'channel', 'channel')
    coercive_healing = AbilityLocatorFactory.create(GameClasses.Coercer, 'coercive_healing', 'coercive healing', 'coercive healing')
    enraging_demeanor = AbilityLocatorFactory.create(GameClasses.Coercer, 'enraging_demeanor', 'enraging demeanor', 'enraging demeanor')
    ether_balance = AbilityLocatorFactory.create(GameClasses.Coercer, 'ether_balance', 'ether balance', 'ether balance')
    hemorrhage = AbilityLocatorFactory.create(GameClasses.Coercer, 'hemorrhage', 'hemorrhage', 'hemorrhage')
    intellectual_remedy = AbilityLocatorFactory.create(GameClasses.Coercer, 'intellectual_remedy', 'intellectual remedy', 'intellectual remedy')
    lethal_focus = AbilityLocatorFactory.create(GameClasses.Coercer, 'lethal_focus', 'lethal focus', 'lethal focus')
    manaward = AbilityLocatorFactory.create(GameClasses.Coercer, 'manaward', 'manaward', 'manaward')
    medusa_gaze = AbilityLocatorFactory.create(GameClasses.Coercer, 'medusa_gaze', 'medusa gaze', 'medusa gaze')
    mesmerize = AbilityLocatorFactory.create(GameClasses.Coercer, 'mesmerize', 'mesmerize', 'mesmerize')
    mind_control = AbilityLocatorFactory.create(GameClasses.Coercer, 'mind_control', 'mind control', 'mind control')
    mindbend = AbilityLocatorFactory.create(GameClasses.Coercer, 'mindbend', 'mindbend', 'mindbend')
    obliterated_psyche = AbilityLocatorFactory.create(GameClasses.Coercer, 'obliterated_psyche', 'obliterated psyche', 'obliterated psyche')
    peaceful_link = AbilityLocatorFactory.create(GameClasses.Coercer, 'peaceful_link', 'peaceful link', 'peaceful link')
    possess_essence = AbilityLocatorFactory.create(GameClasses.Coercer, 'possess_essence', 'possess essence', 'possess essence')
    shift_mana = AbilityLocatorFactory.create(GameClasses.Coercer, 'shift_mana', 'shift mana', 'shift mana')
    shock_wave = AbilityLocatorFactory.create(GameClasses.Coercer, 'shock_wave', 'shock wave', 'shock wave')
    silence = AbilityLocatorFactory.create(GameClasses.Coercer, 'silence', 'silence', 'silence')
    simple_minds = AbilityLocatorFactory.create(GameClasses.Coercer, 'simple_minds', 'simple minds', 'simple minds')
    sirens_stare = AbilityLocatorFactory.create(GameClasses.Coercer, 'sirens_stare', 'siren\'s stare', 'siren\'s stare')
    stupefy = AbilityLocatorFactory.create(GameClasses.Coercer, 'stupefy', 'stupefy', 'stupefy')
    support = AbilityLocatorFactory.create(GameClasses.Coercer, 'support', 'support', 'support')
    tashiana = AbilityLocatorFactory.create(GameClasses.Coercer, 'tashiana', 'tashiana', 'tashiana')
    velocity = AbilityLocatorFactory.create(GameClasses.Coercer, 'velocity', 'velocity', 'velocity')


class CommonerAbilities:
    abstract_ability = AbilityLocatorFactory.create(GameClasses.Commoner, 'abstract_ability', 'abstract ability', 'abstract ability')
    call_to_guild_hall = AbilityLocatorFactory.create(GameClasses.Commoner, 'call_to_guild_hall', 'call to guild hall', 'call to guild hall')
    call_to_home = AbilityLocatorFactory.create(GameClasses.Commoner, 'call_to_home', 'call to home', 'call to home')
    cancel_spellcast = AbilityLocatorFactory.create(GameClasses.Commoner, 'cancel_spellcast', 'cancel spellcast', 'cancel spellcast')
    extract_planar_essence = AbilityLocatorFactory.create(GameClasses.Commoner, 'extract_planar_essence', 'extract planar essence', 'extract planar essence')
    loc = AbilityLocatorFactory.create(GameClasses.Commoner, 'loc', 'loc', 'loc')
    salve = AbilityLocatorFactory.create(GameClasses.Commoner, 'salve', 'salve', 'salve')
    set_target = AbilityLocatorFactory.create(GameClasses.Commoner, 'set_target', 'set target', 'set target')
    transmute = AbilityLocatorFactory.create(GameClasses.Commoner, 'transmute', 'transmute', 'transmute')
    who = AbilityLocatorFactory.create(GameClasses.Commoner, 'who', 'who', 'who')
    visions_of_vetrovia_flawless_execution = AbilityLocatorFactory.create(GameClasses.Commoner, 'visions_of_vetrovia_flawless_execution', 'visions of vetrovia: flawless execution', 'visions of vetrovia: flawless execution')


class ConjurorAbilities:
    aqueous_swarm = AbilityLocatorFactory.create(GameClasses.Conjuror, 'aqueous_swarm', 'aqueous swarm', 'aqueous swarm')
    call_of_the_hero = AbilityLocatorFactory.create(GameClasses.Conjuror, 'call_of_the_hero', 'call of the hero', 'call of the hero')
    crystal_blast = AbilityLocatorFactory.create(GameClasses.Conjuror, 'crystal_blast', 'crystal blast', 'crystal blast')
    earthen_avatar = AbilityLocatorFactory.create(GameClasses.Conjuror, 'earthen_avatar', 'earthen avatar', 'earthen avatar')
    earthquake = AbilityLocatorFactory.create(GameClasses.Conjuror, 'earthquake', 'earthquake', 'earthquake')
    elemental_barrier = AbilityLocatorFactory.create(GameClasses.Conjuror, 'elemental_barrier', 'elemental barrier', 'elemental barrier')
    elemental_blast = AbilityLocatorFactory.create(GameClasses.Conjuror, 'elemental_blast', 'elemental blast', 'elemental blast')
    essence_shift = AbilityLocatorFactory.create(GameClasses.Conjuror, 'essence_shift', 'essence shift', 'essence shift')
    fire_seed = AbilityLocatorFactory.create(GameClasses.Conjuror, 'fire_seed', 'fire seed', 'fire seed')
    flameshield = AbilityLocatorFactory.create(GameClasses.Conjuror, 'flameshield', 'flameshield', 'flameshield')
    petrify = AbilityLocatorFactory.create(GameClasses.Conjuror, 'petrify', 'petrify', 'petrify')
    plane_shift = AbilityLocatorFactory.create(GameClasses.Conjuror, 'plane_shift', 'plane shift', 'plane shift')
    sacrifice = AbilityLocatorFactory.create(GameClasses.Conjuror, 'sacrifice', 'sacrifice', 'sacrifice')
    servants_intervention = AbilityLocatorFactory.create(GameClasses.Conjuror, 'servants_intervention', 'servant\'s intervention', 'servant\'s intervention')
    stoneskin = AbilityLocatorFactory.create(GameClasses.Conjuror, 'stoneskin', 'stoneskin', 'stoneskin')
    stoneskins = AbilityLocatorFactory.create(GameClasses.Conjuror, 'stoneskins', 'stoneskins', 'stoneskins')
    summoners_siphon = AbilityLocatorFactory.create(GameClasses.Conjuror, 'summoners_siphon', 'summoners siphon', 'summoners siphon')
    unflinching_servant = AbilityLocatorFactory.create(GameClasses.Conjuror, 'unflinching_servant', 'unflinching servant', 'unflinching servant')
    winds_of_velious = AbilityLocatorFactory.create(GameClasses.Conjuror, 'winds_of_velious', 'winds of velious', 'winds of velious')
    world_ablaze = AbilityLocatorFactory.create(GameClasses.Conjuror, 'world_ablaze', 'world ablaze', 'world ablaze')


class CrusaderAbilities:
    vital_trigger = AbilityLocatorFactory.create(GameClasses.Crusader, 'vital_trigger', 'vital trigger', 'vital trigger')
    zealots_challenge = AbilityLocatorFactory.create(GameClasses.Crusader, 'zealots_challenge', 'zealot\'s challenge', 'zealot\'s challenge')
    hammer_ground = AbilityLocatorFactory.create(GameClasses.Crusader, 'hammer_ground', 'hammer ground', 'hammer ground')
    legionnaires_smite = AbilityLocatorFactory.create(GameClasses.Crusader, 'legionnaires_smite', 'legionnaire\'s smite', 'legionnaire\'s smite')


class DefilerAbilities:
    abhorrent_seal = AbilityLocatorFactory.create(GameClasses.Defiler, 'abhorrent_seal', 'abhorrent seal', 'abhorrent seal')
    abomination = AbilityLocatorFactory.create(GameClasses.Defiler, 'abomination', 'abomination', 'abomination')
    ancestral_avenger = AbilityLocatorFactory.create(GameClasses.Defiler, 'ancestral_avenger', 'ancestral avenger', 'ancestral avenger')
    ancient_shroud = AbilityLocatorFactory.create(GameClasses.Defiler, 'ancient_shroud', 'ancient shroud', 'ancient shroud')
    bane_of_warding = AbilityLocatorFactory.create(GameClasses.Defiler, 'bane_of_warding', 'bane of warding', 'bane of warding')
    cannibalize = AbilityLocatorFactory.create(GameClasses.Defiler, 'cannibalize', 'cannibalize', 'cannibalize')
    carrion_warding = AbilityLocatorFactory.create(GameClasses.Defiler, 'carrion_warding', 'carrion warding', 'carrion warding')
    death_cries = AbilityLocatorFactory.create(GameClasses.Defiler, 'death_cries', 'death cries', 'death cries')
    harbinger = AbilityLocatorFactory.create(GameClasses.Defiler, 'harbinger', 'harbinger', 'harbinger')
    hexation = AbilityLocatorFactory.create(GameClasses.Defiler, 'hexation', 'hexation', 'hexation')
    invective = AbilityLocatorFactory.create(GameClasses.Defiler, 'invective', 'invective', 'invective')
    maelstrom = AbilityLocatorFactory.create(GameClasses.Defiler, 'maelstrom', 'maelstrom', 'maelstrom')
    mail_of_souls = AbilityLocatorFactory.create(GameClasses.Defiler, 'mail_of_souls', 'mail of souls', 'mail of souls')
    malicious_spirits = AbilityLocatorFactory.create(GameClasses.Defiler, 'malicious_spirits', 'malicious spirits', 'malicious spirits')
    nightmares = AbilityLocatorFactory.create(GameClasses.Defiler, 'nightmares', 'nightmares', 'nightmares')
    phantasmal_barrier = AbilityLocatorFactory.create(GameClasses.Defiler, 'phantasmal_barrier', 'phantasmal barrier', 'phantasmal barrier')
    purulence = AbilityLocatorFactory.create(GameClasses.Defiler, 'purulence', 'purulence', 'purulence')
    soul_cannibalize = AbilityLocatorFactory.create(GameClasses.Defiler, 'soul_cannibalize', 'soul cannibalize', 'soul cannibalize')
    spiritual_circle = AbilityLocatorFactory.create(GameClasses.Defiler, 'spiritual_circle', 'spiritual circle', 'spiritual circle')
    tendrils_of_horror = AbilityLocatorFactory.create(GameClasses.Defiler, 'tendrils_of_horror', 'tendrils of horror', 'tendrils of horror')
    voice_of_the_ancestors = AbilityLocatorFactory.create(GameClasses.Defiler, 'voice_of_the_ancestors', 'voice of the ancestors', 'voice of the ancestors')
    wild_accretion = AbilityLocatorFactory.create(GameClasses.Defiler, 'wild_accretion', 'wild accretion', 'wild accretion')
    wraithwall = AbilityLocatorFactory.create(GameClasses.Defiler, 'wraithwall', 'wraithwall', 'wraithwall')


class DirgeAbilities:
    anthem_of_war = AbilityLocatorFactory.create(GameClasses.Dirge, 'anthem_of_war', 'anthem of war', 'anthem of war')
    battle_cry = AbilityLocatorFactory.create(GameClasses.Dirge, 'battle_cry', 'battle cry', 'battle cry')
    cacophony_of_blades = AbilityLocatorFactory.create(GameClasses.Dirge, 'cacophony_of_blades', 'cacophony of blades', 'cacophony of blades')
    claras_chaotic_cacophony = AbilityLocatorFactory.create(GameClasses.Dirge, 'claras_chaotic_cacophony', 'clara\'s chaotic cacophony', 'clara\'s chaotic cacophony')
    confront_fear = AbilityLocatorFactory.create(GameClasses.Dirge, 'confront_fear', 'confront fear', 'confront fear')
    darksong_spin = AbilityLocatorFactory.create(GameClasses.Dirge, 'darksong_spin', 'darksong spin', 'darksong spin')
    daros_sorrowful_dirge = AbilityLocatorFactory.create(GameClasses.Dirge, 'daros_sorrowful_dirge', 'daro\'s sorrowful dirge', 'daro\'s sorrowful dirge')
    dirges_refrain = AbilityLocatorFactory.create(GameClasses.Dirge, 'dirges_refrain', 'dirges refrain', 'gravitas')
    echoing_howl = AbilityLocatorFactory.create(GameClasses.Dirge, 'echoing_howl', 'echoing howl', 'echoing howl')
    exuberant_encore = AbilityLocatorFactory.create(GameClasses.Dirge, 'exuberant_encore', 'exuberant encore', 'exuberant encore')
    gravitas = AbilityLocatorFactory.create(GameClasses.Dirge, 'gravitas', 'gravitas', 'gravitas')
    howl_of_death = AbilityLocatorFactory.create(GameClasses.Dirge, 'howl_of_death', 'howl of death', 'howl of death')
    hymn_of_horror = AbilityLocatorFactory.create(GameClasses.Dirge, 'hymn_of_horror', 'hymn of horror', 'hymn of horror')
    hyrans_seething_sonata = AbilityLocatorFactory.create(GameClasses.Dirge, 'hyrans_seething_sonata', 'hyran\'s seething sonata', 'hyran\'s seething sonata')
    jarols_sorrowful_requiem = AbilityLocatorFactory.create(GameClasses.Dirge, 'jarols_sorrowful_requiem', 'jarol\'s sorrowful requiem', 'jarol\'s sorrowful requiem')
    lanets_excruciating_scream = AbilityLocatorFactory.create(GameClasses.Dirge, 'lanets_excruciating_scream', 'lanet\'s excruciating scream', 'lanet\'s excruciating scream')
    ludas_nefarious_wail = AbilityLocatorFactory.create(GameClasses.Dirge, 'ludas_nefarious_wail', 'luda\'s nefarious wail', 'luda\'s nefarious wail')
    magnetic_note = AbilityLocatorFactory.create(GameClasses.Dirge, 'magnetic_note', 'magnetic note', 'magnetic note')
    oration_of_sacrifice = AbilityLocatorFactory.create(GameClasses.Dirge, 'oration_of_sacrifice', 'oration of sacrifice', 'oration of sacrifice')
    peal_of_battle = AbilityLocatorFactory.create(GameClasses.Dirge, 'peal_of_battle', 'peal of battle', 'peal of battle')
    sonic_barrier = AbilityLocatorFactory.create(GameClasses.Dirge, 'sonic_barrier', 'sonic barrier', 'sonic barrier')
    support = AbilityLocatorFactory.create(GameClasses.Dirge, 'support', 'support', 'support')
    tarvens_crippling_crescendo = AbilityLocatorFactory.create(GameClasses.Dirge, 'tarvens_crippling_crescendo', 'tarven\'s crippling crescendo', 'tarven\'s crippling crescendo')
    thuris_doleful_thrust = AbilityLocatorFactory.create(GameClasses.Dirge, 'thuris_doleful_thrust', 'thuri\'s doleful thrust', 'thuri\'s doleful thrust')
    verliens_keen_of_despair = AbilityLocatorFactory.create(GameClasses.Dirge, 'verliens_keen_of_despair', 'verlien\'s keen of despair', 'trick of the hunter')
    percussion_of_stone = AbilityLocatorFactory.create(GameClasses.Dirge, 'percussion_of_stone', 'percussion of stone', 'percussion of stone')
    rianas_relentless_tune = AbilityLocatorFactory.create(GameClasses.Dirge, 'rianas_relentless_tune', 'riana\'s relentless tune', 'riana\'s relentless tune')
    luck_of_the_dirge = AbilityLocatorFactory.create(GameClasses.Dirge, 'luck_of_the_dirge', 'luck of the dirge', 'luck of the dirge')
    harls_rousing_tune = AbilityLocatorFactory.create(GameClasses.Dirge, 'harls_rousing_tune', 'harl\'s rousing tune', 'harl\'s rousing tune')
    anthem_of_battle = AbilityLocatorFactory.create(GameClasses.Dirge, 'anthem_of_battle', 'anthem of battle', 'anthem of battle')
    jaels_mysterious_mettle = AbilityLocatorFactory.create(GameClasses.Dirge, 'jaels_mysterious_mettle', 'jael\'s mysterious mettle', 'jael\'s mysterious mettle')


class DruidAbilities:
    howling_with_the_pack = AbilityLocatorFactory.create(GameClasses.Druid, 'howling_with_the_pack', 'howling with the pack', 'howling with the pack')
    rage_of_the_wild = AbilityLocatorFactory.create(GameClasses.Druid, 'rage_of_the_wild', 'rage of the wild', 'rage of the wild')
    rebirth = AbilityLocatorFactory.create(GameClasses.Druid, 'rebirth', 'rebirth', 'rebirth')
    serene_symbol = AbilityLocatorFactory.create(GameClasses.Druid, 'serene_symbol', 'serene symbol', 'serene symbol')
    serenity = AbilityLocatorFactory.create(GameClasses.Druid, 'serenity', 'serenity', 'serenity')
    spirit_of_the_bat = AbilityLocatorFactory.create(GameClasses.Druid, 'spirit_of_the_bat', 'spirit of the bat', 'spirit of the bat')
    sylvan_touch = AbilityLocatorFactory.create(GameClasses.Druid, 'sylvan_touch', 'sylvan touch', 'sylvan touch')
    thunderspike = AbilityLocatorFactory.create(GameClasses.Druid, 'thunderspike', 'thunderspike', 'thunderspike')
    tortoise_shell = AbilityLocatorFactory.create(GameClasses.Druid, 'tortoise_shell', 'tortoise shell', 'tortoise shell')
    tunares_grace = AbilityLocatorFactory.create(GameClasses.Druid, 'tunares_grace', 'tunare\'s grace', 'tunare\'s grace')
    woodward = AbilityLocatorFactory.create(GameClasses.Druid, 'woodward', 'woodward', 'woodward')
    wrath_of_nature = AbilityLocatorFactory.create(GameClasses.Druid, 'wrath_of_nature', 'wrath of nature', 'wrath of nature')


class ElementalistAbilities:
    blistering_waste = AbilityLocatorFactory.create(GameClasses.Elementalist, 'blistering_waste', 'blistering waste', 'blistering waste')
    brittle_armor = AbilityLocatorFactory.create(GameClasses.Elementalist, 'brittle_armor', 'brittle armor', 'brittle armor')
    dominion_of_fire = AbilityLocatorFactory.create(GameClasses.Elementalist, 'dominion_of_fire', 'dominion of fire', 'dominion of fire')
    elemental_amalgamation = AbilityLocatorFactory.create(GameClasses.Elementalist, 'elemental_amalgamation', 'elemental amalgamation', 'elemental amalgamation')
    elemental_overlord = AbilityLocatorFactory.create(GameClasses.Elementalist, 'elemental_overlord', 'elemental overlord', 'elemental overlord')
    fiery_incineration = AbilityLocatorFactory.create(GameClasses.Elementalist, 'fiery_incineration', 'fiery incineration', 'fiery incineration')
    frost_pyre = AbilityLocatorFactory.create(GameClasses.Elementalist, 'frost_pyre', 'frost pyre', 'frost pyre')
    frozen_heavens = AbilityLocatorFactory.create(GameClasses.Elementalist, 'frozen_heavens', 'frozen heavens', 'frozen heavens')
    glacial_freeze = AbilityLocatorFactory.create(GameClasses.Elementalist, 'glacial_freeze', 'glacial freeze', 'glacial freeze')
    phoenix_rising = AbilityLocatorFactory.create(GameClasses.Elementalist, 'phoenix_rising', 'phoenix rising', 'phoenix rising')
    scorched_earth = AbilityLocatorFactory.create(GameClasses.Elementalist, 'scorched_earth', 'scorched earth', 'scorched earth')
    thermal_depletion = AbilityLocatorFactory.create(GameClasses.Elementalist, 'thermal_depletion', 'thermal depletion', 'thermal depletion')
    wildfire = AbilityLocatorFactory.create(GameClasses.Elementalist, 'wildfire', 'wildfire', 'wildfire')


class EnchanterAbilities:
    aura_of_power = AbilityLocatorFactory.create(GameClasses.Enchanter, 'aura_of_power', 'aura of power', 'mana cloak')
    blinding_shock = AbilityLocatorFactory.create(GameClasses.Enchanter, 'blinding_shock', 'blinding shock', 'blinding shock')
    channeled_focus = AbilityLocatorFactory.create(GameClasses.Enchanter, 'channeled_focus', 'channeled focus', 'channeled focus')
    chronosiphoning = AbilityLocatorFactory.create(GameClasses.Enchanter, 'chronosiphoning', 'chronosiphoning', 'chronosiphoning')
    ego_whip = AbilityLocatorFactory.create(GameClasses.Enchanter, 'ego_whip', 'ego whip', 'ego whip')
    enchanted_vigor = AbilityLocatorFactory.create(GameClasses.Enchanter, 'enchanted_vigor', 'enchanted vigor', 'enchanted vigor')
    id_explosion = AbilityLocatorFactory.create(GameClasses.Enchanter, 'id_explosion', 'id explosion', 'id explosion')
    mana_cloak = AbilityLocatorFactory.create(GameClasses.Enchanter, 'mana_cloak', 'mana cloak', 'mana cloak')
    mana_flow = AbilityLocatorFactory.create(GameClasses.Enchanter, 'mana_flow', 'mana flow', 'mana flow')
    manasoul = AbilityLocatorFactory.create(GameClasses.Enchanter, 'manasoul', 'manasoul', 'manasoul')
    nullifying_staff = AbilityLocatorFactory.create(GameClasses.Enchanter, 'nullifying_staff', 'nullifying staff', 'nullifying staff')
    peace_of_mind = AbilityLocatorFactory.create(GameClasses.Enchanter, 'peace_of_mind', 'peace of mind', 'peace of mind')
    spellblades_counter = AbilityLocatorFactory.create(GameClasses.Enchanter, 'spellblades_counter', 'spellblade\'s counter', 'spellblade\'s counter')
    temporal_mimicry = AbilityLocatorFactory.create(GameClasses.Enchanter, 'temporal_mimicry', 'temporal mimicry', 'temporal mimicry')
    touch_of_empathy = AbilityLocatorFactory.create(GameClasses.Enchanter, 'touch_of_empathy', 'touch of empathy', 'touch of empathy')


class EtherealistAbilities:
    cascading_force = AbilityLocatorFactory.create(GameClasses.Etherealist, 'cascading_force', 'cascading force', 'cascading force')
    compounding_force = AbilityLocatorFactory.create(GameClasses.Etherealist, 'compounding_force', 'compounding force', 'compounding force')
    essence_of_magic = AbilityLocatorFactory.create(GameClasses.Etherealist, 'essence_of_magic', 'essence of magic', 'essence of magic')
    ethereal_conduit = AbilityLocatorFactory.create(GameClasses.Etherealist, 'ethereal_conduit', 'ethereal conduit', 'ethereal conduit')
    ethereal_gift = AbilityLocatorFactory.create(GameClasses.Etherealist, 'ethereal_gift', 'ethereal gift', 'ethereal gift')
    etherflash = AbilityLocatorFactory.create(GameClasses.Etherealist, 'etherflash', 'etherflash', 'etherflash')
    ethershadow_assassin = AbilityLocatorFactory.create(GameClasses.Etherealist, 'ethershadow_assassin', 'ethershadow assassin', 'ethershadow assassin')
    feedback_loop = AbilityLocatorFactory.create(GameClasses.Etherealist, 'feedback_loop', 'feedback loop', 'feedback loop')
    focused_blast = AbilityLocatorFactory.create(GameClasses.Etherealist, 'focused_blast', 'focused blast', 'focused blast')
    implosion = AbilityLocatorFactory.create(GameClasses.Etherealist, 'implosion', 'implosion', 'implosion')
    levinbolt = AbilityLocatorFactory.create(GameClasses.Etherealist, 'levinbolt', 'levinbolt', 'levinbolt')
    mana_schism = AbilityLocatorFactory.create(GameClasses.Etherealist, 'mana_schism', 'mana schism', 'mana schism')
    recapture = AbilityLocatorFactory.create(GameClasses.Etherealist, 'recapture', 'recapture', 'recapture')
    touch_of_magic = AbilityLocatorFactory.create(GameClasses.Etherealist, 'touch_of_magic', 'touch of magic', 'touch of magic')


class FighterAbilities:
    balanced_synergy = AbilityLocatorFactory.create(GameClasses.Fighter, 'balanced_synergy', 'balanced synergy', 'balanced synergy')
    bulwark_of_order = AbilityLocatorFactory.create(GameClasses.Fighter, 'bulwark_of_order', 'bulwark of order', 'bulwark of order')
    fighting_chance = AbilityLocatorFactory.create(GameClasses.Fighter, 'fighting_chance', 'fighting chance', 'fighting chance')
    intercept = AbilityLocatorFactory.create(GameClasses.Fighter, 'intercept', 'intercept', 'intercept')
    provocation = AbilityLocatorFactory.create(GameClasses.Fighter, 'provocation', 'provocation', 'provocation')
    rescue = AbilityLocatorFactory.create(GameClasses.Fighter, 'rescue', 'rescue', 'rescue')
    strike_of_consistency = AbilityLocatorFactory.create(GameClasses.Fighter, 'strike_of_consistency', 'strike of consistency', 'strike of consistency')
    goading_gesture = AbilityLocatorFactory.create(GameClasses.Fighter, 'goading_gesture', 'goading gesture', 'goading gesture')


class FuryAbilities:
    abolishment = AbilityLocatorFactory.create(GameClasses.Fury, 'abolishment', 'abolishment', 'abolishment')
    animal_form = AbilityLocatorFactory.create(GameClasses.Fury, 'animal_form', 'animal form', 'animal form')
    autumns_kiss = AbilityLocatorFactory.create(GameClasses.Fury, 'autumns_kiss', 'autumn\'s kiss', 'autumn\'s kiss')
    death_swarm = AbilityLocatorFactory.create(GameClasses.Fury, 'death_swarm', 'death swarm', 'death swarm')
    devour = AbilityLocatorFactory.create(GameClasses.Fury, 'devour', 'devour', 'devour')
    embodiment_of_nature = AbilityLocatorFactory.create(GameClasses.Fury, 'embodiment_of_nature', 'embodiment of nature', 'embodiment of nature')
    energy_vortex = AbilityLocatorFactory.create(GameClasses.Fury, 'energy_vortex', 'energy vortex', 'energy vortex')
    fae_fire = AbilityLocatorFactory.create(GameClasses.Fury, 'fae_fire', 'fae fire', 'fae fire')
    feral_pulse = AbilityLocatorFactory.create(GameClasses.Fury, 'feral_pulse', 'feral pulse', 'feral pulse')
    feral_tenacity = AbilityLocatorFactory.create(GameClasses.Fury, 'feral_tenacity', 'feral tenacity', 'feral tenacity')
    force_of_nature = AbilityLocatorFactory.create(GameClasses.Fury, 'force_of_nature', 'force of nature', 'force of nature')
    heart_of_the_storm = AbilityLocatorFactory.create(GameClasses.Fury, 'heart_of_the_storm', 'heart of the storm', 'heart of the storm')
    hibernation = AbilityLocatorFactory.create(GameClasses.Fury, 'hibernation', 'hibernation', 'hibernation')
    intimidation = AbilityLocatorFactory.create(GameClasses.Fury, 'intimidation', 'intimidation', 'intimidation')
    lucidity = AbilityLocatorFactory.create(GameClasses.Fury, 'lucidity', 'lucidity', 'lucidity')
    maddening_swarm = AbilityLocatorFactory.create(GameClasses.Fury, 'maddening_swarm', 'maddening swarm', 'maddening swarm')
    natural_cleanse = AbilityLocatorFactory.create(GameClasses.Fury, 'natural_cleanse', 'natural cleanse', 'natural cleanse')
    natural_regeneration = AbilityLocatorFactory.create(GameClasses.Fury, 'natural_regeneration', 'natural regeneration', 'natural regeneration')
    natures_elixir = AbilityLocatorFactory.create(GameClasses.Fury, 'natures_elixir', 'nature\'s elixir', 'nature\'s elixir')
    natures_salve = AbilityLocatorFactory.create(GameClasses.Fury, 'natures_salve', 'nature\'s salve', 'nature\'s salve')
    pact_of_nature = AbilityLocatorFactory.create(GameClasses.Fury, 'pact_of_nature', 'pact of nature', 'pact of nature')
    pact_of_the_cheetah = AbilityLocatorFactory.create(GameClasses.Fury, 'pact_of_the_cheetah', 'pact of the cheetah', 'pact of the cheetah')
    porcupine = AbilityLocatorFactory.create(GameClasses.Fury, 'porcupine', 'porcupine', 'porcupine')
    primal_fury = AbilityLocatorFactory.create(GameClasses.Fury, 'primal_fury', 'primal fury', 'primal fury')
    raging_whirlwind = AbilityLocatorFactory.create(GameClasses.Fury, 'raging_whirlwind', 'raging whirlwind', 'raging whirlwind')
    regrowth = AbilityLocatorFactory.create(GameClasses.Fury, 'regrowth', 'regrowth', 'regrowth')
    ring_of_fire = AbilityLocatorFactory.create(GameClasses.Fury, 'ring_of_fire', 'ring of fire', 'ring of fire')
    starnova = AbilityLocatorFactory.create(GameClasses.Fury, 'starnova', 'starnova', 'starnova')
    stormbearers_fury = AbilityLocatorFactory.create(GameClasses.Fury, 'stormbearers_fury', 'stormbearer\'s fury', 'stormbearer\'s fury')
    thornskin = AbilityLocatorFactory.create(GameClasses.Fury, 'thornskin', 'thornskin', 'thornskin')
    thunderbolt = AbilityLocatorFactory.create(GameClasses.Fury, 'thunderbolt', 'thunderbolt', 'thunderbolt')
    untamed_regeneration = AbilityLocatorFactory.create(GameClasses.Fury, 'untamed_regeneration', 'untamed regeneration', 'untamed regeneration')
    wraths_blessing = AbilityLocatorFactory.create(GameClasses.Fury, 'wraths_blessing', 'wrath\'s blessing', 'wrath\'s blessing')
    vortex_of_nature = AbilityLocatorFactory.create(GameClasses.Fury, 'vortex_of_nature', 'vortex of nature', 'vortex of nature')


class GeomancerAbilities:
    bastion_of_iron = AbilityLocatorFactory.create(GameClasses.Geomancer, 'bastion_of_iron', 'bastion of iron', 'bastion of iron')
    domain_of_earth = AbilityLocatorFactory.create(GameClasses.Geomancer, 'domain_of_earth', 'domain of earth', 'domain of earth')
    earthen_phalanx = AbilityLocatorFactory.create(GameClasses.Geomancer, 'earthen_phalanx', 'earthen phalanx', 'earthen phalanx')
    erosion = AbilityLocatorFactory.create(GameClasses.Geomancer, 'erosion', 'erosion', 'erosion')
    geotic_rampage = AbilityLocatorFactory.create(GameClasses.Geomancer, 'geotic_rampage', 'geotic rampage', 'geotic rampage')
    granite_protector = AbilityLocatorFactory.create(GameClasses.Geomancer, 'granite_protector', 'granite protector', 'granite protector')
    mudslide = AbilityLocatorFactory.create(GameClasses.Geomancer, 'mudslide', 'mudslide', 'mudslide')
    obsidian_mind = AbilityLocatorFactory.create(GameClasses.Geomancer, 'obsidian_mind', 'obsidian mind', 'obsidian mind')
    stone_hammer = AbilityLocatorFactory.create(GameClasses.Geomancer, 'stone_hammer', 'stone hammer', 'stone hammer')
    telluric_rending = AbilityLocatorFactory.create(GameClasses.Geomancer, 'telluric_rending', 'telluric rending', 'telluric rending')
    terrene_destruction = AbilityLocatorFactory.create(GameClasses.Geomancer, 'terrene_destruction', 'terrene destruction', 'terrene destruction')
    terrestrial_coffin = AbilityLocatorFactory.create(GameClasses.Geomancer, 'terrestrial_coffin', 'terrestrial coffin', 'terrestrial coffin')
    xenolith = AbilityLocatorFactory.create(GameClasses.Geomancer, 'xenolith', 'xenolith', 'xenolith')


class IllusionistAbilities:
    arms_of_imagination = AbilityLocatorFactory.create(GameClasses.Illusionist, 'arms_of_imagination', 'arms of imagination', 'arms of imagination')
    bewilderment = AbilityLocatorFactory.create(GameClasses.Illusionist, 'bewilderment', 'bewilderment', 'bewilderment')
    brainburst = AbilityLocatorFactory.create(GameClasses.Illusionist, 'brainburst', 'brainburst', 'brainburst')
    chromatic_illusion = AbilityLocatorFactory.create(GameClasses.Illusionist, 'chromatic_illusion', 'chromatic illusion', 'chromatic illusion')
    chromatic_shower = AbilityLocatorFactory.create(GameClasses.Illusionist, 'chromatic_shower', 'chromatic shower', 'chromatic shower')
    chromatic_storm = AbilityLocatorFactory.create(GameClasses.Illusionist, 'chromatic_storm', 'chromatic storm', 'chromatic storm')
    entrance = AbilityLocatorFactory.create(GameClasses.Illusionist, 'entrance', 'entrance', 'entrance')
    extract_mana = AbilityLocatorFactory.create(GameClasses.Illusionist, 'extract_mana', 'extract mana', 'extract mana')
    flash_of_brilliance = AbilityLocatorFactory.create(GameClasses.Illusionist, 'flash_of_brilliance', 'flash of brilliance', 'flash of brilliance')
    illusionary_instigation = AbilityLocatorFactory.create(GameClasses.Illusionist, 'illusionary_instigation', 'illusionary instigation', 'illusionary instigation')
    illusory_barrier = AbilityLocatorFactory.create(GameClasses.Illusionist, 'illusory_barrier', 'illusory barrier', 'illusory barrier')
    manatap = AbilityLocatorFactory.create(GameClasses.Illusionist, 'manatap', 'manatap', 'manatap')
    nightmare = AbilityLocatorFactory.create(GameClasses.Illusionist, 'nightmare', 'nightmare', 'nightmare')
    paranoia = AbilityLocatorFactory.create(GameClasses.Illusionist, 'paranoia', 'paranoia', 'paranoia')
    personae_reflection = AbilityLocatorFactory.create(GameClasses.Illusionist, 'personae_reflection', 'personae reflection', 'personae reflection')
    phantom_troupe = AbilityLocatorFactory.create(GameClasses.Illusionist, 'phantom_troupe', 'phantom troupe', 'phantom troupe')
    phase = AbilityLocatorFactory.create(GameClasses.Illusionist, 'phase', 'phase', 'phase')
    prismatic_chaos = AbilityLocatorFactory.create(GameClasses.Illusionist, 'prismatic_chaos', 'prismatic chaos', 'prismatic chaos')
    rapidity = AbilityLocatorFactory.create(GameClasses.Illusionist, 'rapidity', 'rapidity', 'rapidity')
    savante = AbilityLocatorFactory.create(GameClasses.Illusionist, 'savante', 'savante', 'savante')
    speechless = AbilityLocatorFactory.create(GameClasses.Illusionist, 'speechless', 'speechless', 'speechless')
    support = AbilityLocatorFactory.create(GameClasses.Illusionist, 'support', 'support', 'support')
    synergism = AbilityLocatorFactory.create(GameClasses.Illusionist, 'synergism', 'synergism', 'synergism')
    time_compression = AbilityLocatorFactory.create(GameClasses.Illusionist, 'time_compression', 'time compression', 'time compression')
    time_warp = AbilityLocatorFactory.create(GameClasses.Illusionist, 'time_warp', 'time warp', 'time warp')
    timelord = AbilityLocatorFactory.create(GameClasses.Illusionist, 'timelord', 'timelord', 'timelord')
    ultraviolet_beam = AbilityLocatorFactory.create(GameClasses.Illusionist, 'ultraviolet_beam', 'ultraviolet beam', 'ultraviolet beam')
    rune_of_thought = AbilityLocatorFactory.create(GameClasses.Illusionist, 'rune_of_thought', 'rune of thought', 'rune of thought')
    chronal_mastery = AbilityLocatorFactory.create(GameClasses.Illusionist, 'chronal_mastery', 'chronal mastery', 'chronal mastery')


class InquisitorAbilities:
    alleviation = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'alleviation', 'alleviation', 'alleviation')
    chilling_invigoration = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'chilling_invigoration', 'chilling invigoration', 'chilling invigoration')
    cleansing_of_the_soul = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'cleansing_of_the_soul', 'cleansing of the soul', 'cleansing of the soul')
    condemn = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'condemn', 'condemn', 'condemn')
    deny = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'deny', 'deny', 'deny')
    divine_armor = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'divine_armor', 'divine armor', 'divine armor')
    divine_aura = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'divine_aura', 'divine aura', 'divine aura')
    divine_provenance = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'divine_provenance', 'divine provenance', 'inquisition')
    divine_recovery = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'divine_recovery', 'divine recovery', 'divine recovery')
    divine_righteousness = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'divine_righteousness', 'divine righteousness', 'divine righteousness')
    evidence_of_faith = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'evidence_of_faith', 'evidence of faith', 'evidence of faith')
    fanatics_inspiration = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'fanatics_inspiration', 'fanatic\'s inspiration', 'fanatic\'s inspiration')
    fanatics_protection = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'fanatics_protection', 'fanatic\'s protection', 'fanatic\'s protection')
    fanaticism = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'fanaticism', 'fanaticism', 'fanaticism')
    forced_obedience = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'forced_obedience', 'forced obedience', 'forced obedience')
    heresy = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'heresy', 'heresy', 'heresy')
    inquest = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'inquest', 'inquest', 'inquest')
    inquisition = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'inquisition', 'inquisition', 'inquisition')
    invocation_strike = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'invocation_strike', 'invocation strike', 'invocation strike')
    litany_circle = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'litany_circle', 'litany circle', 'litany circle')
    malevolent_diatribe = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'malevolent_diatribe', 'malevolent diatribe', 'malevolent diatribe')
    penance = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'penance', 'penance', 'penance')
    redemption = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'redemption', 'redemption', 'redemption')
    repentance = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'repentance', 'repentance', 'repentance')
    resolute_flagellant = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'resolute_flagellant', 'resolute flagellant', 'resolute flagellant')
    strike_of_flames = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'strike_of_flames', 'strike of flames', 'strike of flames')
    tenacity = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'tenacity', 'tenacity', 'tenacity')
    vengeance = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'vengeance', 'vengeance', 'vengeance')
    verdict = AbilityLocatorFactory.create(GameClasses.Inquisitor, 'verdict', 'verdict', 'verdict')


class ItemsAbilities:
    call_of_the_veteran = AbilityLocatorFactory.create(GameClasses.Items, 'call_of_the_veteran', 'call of the veteran', 'call of the veteran')
    critical_thinking = AbilityLocatorFactory.create(GameClasses.Items, 'critical_thinking', 'critical thinking', 'critical thinking')
    forgiveness_potion = AbilityLocatorFactory.create(GameClasses.Items, 'forgiveness_potion', 'forgiveness potion', 'forgiveness potion')
    quelule_cocktail = AbilityLocatorFactory.create(GameClasses.Items, 'quelule_cocktail', 'quel\'ule cocktail', 'quel\'ule cocktail')
    noxious_effusion = AbilityLocatorFactory.create(GameClasses.Items, 'noxious_effusion', 'noxious effusion', 'noxious effusion')
    poison_fingers = AbilityLocatorFactory.create(GameClasses.Items, 'poison_fingers', 'poison fingers', 'poison fingers')
    embrace_of_frost = AbilityLocatorFactory.create(GameClasses.Items, 'embrace_of_frost', 'embrace of frost', 'embrace of frost')
    flames_of_yore = AbilityLocatorFactory.create(GameClasses.Items, 'flames_of_yore', 'flames of yore', 'flames of yore')
    divine_embrace = AbilityLocatorFactory.create(GameClasses.Items, 'divine_embrace', 'divine embrace', 'divine embrace')
    mindworms = AbilityLocatorFactory.create(GameClasses.Items, 'mindworms', 'mindworms', 'mindworms')
    voidlink = AbilityLocatorFactory.create(GameClasses.Items, 'voidlink', 'voidlink', 'voidlink')
    essence_of_smash = AbilityLocatorFactory.create(GameClasses.Items, 'essence_of_smash', 'essence of smash', 'essence of smash')
    prepaded_cutdown = AbilityLocatorFactory.create(GameClasses.Items, 'prepaded_cutdown', 'prepaded cutdown', 'prepaded cutdown')
    piercing_gaze = AbilityLocatorFactory.create(GameClasses.Items, 'piercing_gaze', 'piercing gaze', 'piercing gaze')


class JewelerAbilities:
    center_of_spirit = AbilityLocatorFactory.create(GameClasses.Jeweler, 'center_of_spirit', 'center of spirit', 'focus of spirit')
    faceting = AbilityLocatorFactory.create(GameClasses.Jeweler, 'faceting', 'faceting', 'faceting')
    focus_of_spirit = AbilityLocatorFactory.create(GameClasses.Jeweler, 'focus_of_spirit', 'focus of spirit', 'focus of spirit')
    mind_over_matter = AbilityLocatorFactory.create(GameClasses.Jeweler, 'mind_over_matter', 'mind over matter', 'mind over matter')
    round_cut = AbilityLocatorFactory.create(GameClasses.Jeweler, 'round_cut', 'round cut', 'faceting')
    sixth_sense = AbilityLocatorFactory.create(GameClasses.Jeweler, 'sixth_sense', 'sixth sense', 'mind over matter')


class LocalAbilities:
    prepare = AbilityLocatorFactory.create(GameClasses.Local, 'prepare', 'prepare', 'prepare')


class MageAbilities:
    absorb_magic = AbilityLocatorFactory.create(GameClasses.Mage, 'absorb_magic', 'absorb magic', 'absorb magic')
    arcane_augur = AbilityLocatorFactory.create(GameClasses.Mage, 'arcane_augur', 'arcane augur', 'arcane augur')
    balanced_synergy = AbilityLocatorFactory.create(GameClasses.Mage, 'balanced_synergy', 'balanced synergy', 'balanced synergy')
    cure_magic = AbilityLocatorFactory.create(GameClasses.Mage, 'cure_magic', 'cure magic', 'cure magic')
    scaled_protection = AbilityLocatorFactory.create(GameClasses.Mage, 'scaled_protection', 'scaled protection', 'scaled protection')
    smite_of_consistency = AbilityLocatorFactory.create(GameClasses.Mage, 'smite_of_consistency', 'smite of consistency', 'smite of consistency')
    unda_arcanus_spiritus = AbilityLocatorFactory.create(GameClasses.Mage, 'unda_arcanus_spiritus', 'unda arcanus spiritus', 'unda arcanus spiritus')
    undeath = AbilityLocatorFactory.create(GameClasses.Mage, 'undeath', 'undeath', 'undeath')
    magis_shielding = AbilityLocatorFactory.create(GameClasses.Mage, 'magis_shielding', 'magi\'s shielding', 'magi\'s shielding')


class MonkAbilities:
    arctic_talon = AbilityLocatorFactory.create(GameClasses.Monk, 'arctic_talon', 'arctic talon', 'arctic talon')
    bob_and_weave = AbilityLocatorFactory.create(GameClasses.Monk, 'bob_and_weave', 'bob and weave', 'bob and weave')
    body_like_mountain = AbilityLocatorFactory.create(GameClasses.Monk, 'body_like_mountain', 'body like mountain', 'body like mountain')
    challenge = AbilityLocatorFactory.create(GameClasses.Monk, 'challenge', 'challenge', 'challenge')
    charging_tiger = AbilityLocatorFactory.create(GameClasses.Monk, 'charging_tiger', 'charging tiger', 'charging tiger')
    crescent_strike = AbilityLocatorFactory.create(GameClasses.Monk, 'crescent_strike', 'crescent strike', 'crescent strike')
    dragonfire = AbilityLocatorFactory.create(GameClasses.Monk, 'dragonfire', 'dragonfire', 'dragonfire')
    evasion = AbilityLocatorFactory.create(GameClasses.Monk, 'evasion', 'evasion', 'evasion')
    fall_of_the_phoenix = AbilityLocatorFactory.create(GameClasses.Monk, 'fall_of_the_phoenix', 'fall of the phoenix', 'fall of the phoenix')
    feign_death = AbilityLocatorFactory.create(GameClasses.Monk, 'feign_death', 'feign death', 'feign death')
    five_rings = AbilityLocatorFactory.create(GameClasses.Monk, 'five_rings', 'five rings', 'five rings')
    fluid_combination = AbilityLocatorFactory.create(GameClasses.Monk, 'fluid_combination', 'fluid combination', 'fluid combination')
    flying_scissors = AbilityLocatorFactory.create(GameClasses.Monk, 'flying_scissors', 'flying scissors', 'roundhouse kick')
    frozen_palm = AbilityLocatorFactory.create(GameClasses.Monk, 'frozen_palm', 'frozen palm', 'frozen palm')
    hidden_openings = AbilityLocatorFactory.create(GameClasses.Monk, 'hidden_openings', 'hidden openings', 'hidden openings')
    lightning_palm = AbilityLocatorFactory.create(GameClasses.Monk, 'lightning_palm', 'lightning palm', 'lightning palm')
    mend = AbilityLocatorFactory.create(GameClasses.Monk, 'mend', 'mend', 'mend')
    mountain_stance = AbilityLocatorFactory.create(GameClasses.Monk, 'mountain_stance', 'mountain stance', 'mountain stance')
    outward_calm = AbilityLocatorFactory.create(GameClasses.Monk, 'outward_calm', 'outward calm', 'outward calm')
    peel = AbilityLocatorFactory.create(GameClasses.Monk, 'peel', 'peel', 'peel')
    perfect_form = AbilityLocatorFactory.create(GameClasses.Monk, 'perfect_form', 'perfect form', 'perfect form')
    provoking_stance = AbilityLocatorFactory.create(GameClasses.Monk, 'provoking_stance', 'provoking stance', 'provoking stance')
    reprimand = AbilityLocatorFactory.create(GameClasses.Monk, 'reprimand', 'reprimand', 'reprimand')
    rising_dragon = AbilityLocatorFactory.create(GameClasses.Monk, 'rising_dragon', 'rising dragon', 'rising dragon')
    rising_phoenix = AbilityLocatorFactory.create(GameClasses.Monk, 'rising_phoenix', 'rising phoenix', 'rising phoenix')
    roundhouse_kick = AbilityLocatorFactory.create(GameClasses.Monk, 'roundhouse_kick', 'roundhouse kick', 'roundhouse kick')
    silent_palm = AbilityLocatorFactory.create(GameClasses.Monk, 'silent_palm', 'silent palm', 'silent palm')
    silent_threat = AbilityLocatorFactory.create(GameClasses.Monk, 'silent_threat', 'silent threat', 'goading gesture')
    striking_cobra = AbilityLocatorFactory.create(GameClasses.Monk, 'striking_cobra', 'striking cobra', 'striking cobra')
    superior_guard = AbilityLocatorFactory.create(GameClasses.Monk, 'superior_guard', 'superior guard', 'superior guard')
    tsunami = AbilityLocatorFactory.create(GameClasses.Monk, 'tsunami', 'tsunami', 'tsunami')
    waking_dragon = AbilityLocatorFactory.create(GameClasses.Monk, 'waking_dragon', 'waking dragon', 'waking dragon')
    will_of_the_heavens = AbilityLocatorFactory.create(GameClasses.Monk, 'will_of_the_heavens', 'will of the heavens', 'will of the heavens')
    winds_of_salvation = AbilityLocatorFactory.create(GameClasses.Monk, 'winds_of_salvation', 'winds of salvation', 'winds of salvation')


class MysticAbilities:
    ancestral_avatar = AbilityLocatorFactory.create(GameClasses.Mystic, 'ancestral_avatar', 'ancestral avatar', 'ancestral avatar')
    ancestral_balm = AbilityLocatorFactory.create(GameClasses.Mystic, 'ancestral_balm', 'ancestral balm', 'ancestral balm')
    ancestral_bolster = AbilityLocatorFactory.create(GameClasses.Mystic, 'ancestral_bolster', 'ancestral bolster', 'bolster')
    ancestral_savior = AbilityLocatorFactory.create(GameClasses.Mystic, 'ancestral_savior', 'ancestral savior', 'ancestral savior')
    ancestral_support = AbilityLocatorFactory.create(GameClasses.Mystic, 'ancestral_support', 'ancestral support', 'ancestral support')
    ancestral_ward = AbilityLocatorFactory.create(GameClasses.Mystic, 'ancestral_ward', 'ancestral ward', 'ancestral ward')
    ancestry = AbilityLocatorFactory.create(GameClasses.Mystic, 'ancestry', 'ancestry', 'ancestry')
    bolster = AbilityLocatorFactory.create(GameClasses.Mystic, 'bolster', 'bolster', 'bolster')
    chilling_strike = AbilityLocatorFactory.create(GameClasses.Mystic, 'chilling_strike', 'chilling strike', 'chilling strike')
    circle_of_the_ancients = AbilityLocatorFactory.create(GameClasses.Mystic, 'circle_of_the_ancients', 'circle of the ancients', 'circle of the ancients')
    ebbing_spirit = AbilityLocatorFactory.create(GameClasses.Mystic, 'ebbing_spirit', 'ebbing spirit', 'ebbing spirit')
    echoes_of_the_ancients = AbilityLocatorFactory.create(GameClasses.Mystic, 'echoes_of_the_ancients', 'echoes of the ancients', 'echoes of the ancients')
    haze = AbilityLocatorFactory.create(GameClasses.Mystic, 'haze', 'haze', 'haze')
    immunization = AbilityLocatorFactory.create(GameClasses.Mystic, 'immunization', 'immunization', 'immunization')
    lamenting_soul = AbilityLocatorFactory.create(GameClasses.Mystic, 'lamenting_soul', 'lamenting soul', 'lamenting soul')
    lunar_attendant = AbilityLocatorFactory.create(GameClasses.Mystic, 'lunar_attendant', 'lunar attendant', 'lunar attendant')
    oberon = AbilityLocatorFactory.create(GameClasses.Mystic, 'oberon', 'oberon', 'oberon')
    plague = AbilityLocatorFactory.create(GameClasses.Mystic, 'plague', 'plague', 'plague')
    polar_fire = AbilityLocatorFactory.create(GameClasses.Mystic, 'polar_fire', 'polar fire', 'polar fire')
    premonition = AbilityLocatorFactory.create(GameClasses.Mystic, 'premonition', 'premonition', 'premonition')
    prophetic_ward = AbilityLocatorFactory.create(GameClasses.Mystic, 'prophetic_ward', 'prophetic ward', 'prophetic ward')
    rejuvenation = AbilityLocatorFactory.create(GameClasses.Mystic, 'rejuvenation', 'rejuvenation', 'rejuvenation')
    ritual_healing = AbilityLocatorFactory.create(GameClasses.Mystic, 'ritual_healing', 'ritual healing', 'ritual healing')
    ritual_of_alacrity = AbilityLocatorFactory.create(GameClasses.Mystic, 'ritual_of_alacrity', 'ritual of alacrity', 'ritual of alacrity')
    spirit_tap = AbilityLocatorFactory.create(GameClasses.Mystic, 'spirit_tap', 'spirit tap', 'spirit tap')
    stampede_of_the_herd = AbilityLocatorFactory.create(GameClasses.Mystic, 'stampede_of_the_herd', 'stampede of the herd', 'stampede of the herd')
    torpor = AbilityLocatorFactory.create(GameClasses.Mystic, 'torpor', 'torpor', 'torpor')
    transcendence = AbilityLocatorFactory.create(GameClasses.Mystic, 'transcendence', 'transcendence', 'transcendence')
    umbral_barrier = AbilityLocatorFactory.create(GameClasses.Mystic, 'umbral_barrier', 'umbral barrier', 'umbral barrier')
    wards_of_the_eidolon = AbilityLocatorFactory.create(GameClasses.Mystic, 'wards_of_the_eidolon', 'wards of the eidolon', 'wards of the eidolon')
    strength_of_the_ancestors = AbilityLocatorFactory.create(GameClasses.Mystic, 'strength_of_the_ancestors', 'strength of the ancestors', 'strength of the ancestors')
    runic_armor = AbilityLocatorFactory.create(GameClasses.Mystic, 'runic_armor', 'runic armor', 'runic armor')


class PriestAbilities:
    balanced_synergy = AbilityLocatorFactory.create(GameClasses.Priest, 'balanced_synergy', 'balanced synergy', 'balanced synergy')
    cloak_of_divinity = AbilityLocatorFactory.create(GameClasses.Priest, 'cloak_of_divinity', 'cloak of divinity', 'cloak of divinity')
    cure = AbilityLocatorFactory.create(GameClasses.Priest, 'cure', 'cure', 'cure')
    cure_curse = AbilityLocatorFactory.create(GameClasses.Priest, 'cure_curse', 'cure curse', 'cure curse')
    divine_providence = AbilityLocatorFactory.create(GameClasses.Priest, 'divine_providence', 'divine providence', 'divine providence')
    reprieve = AbilityLocatorFactory.create(GameClasses.Priest, 'reprieve', 'reprieve', 'reprieve')
    smite_of_consistency = AbilityLocatorFactory.create(GameClasses.Priest, 'smite_of_consistency', 'smite of consistency', 'smite of consistency')
    undaunted = AbilityLocatorFactory.create(GameClasses.Priest, 'undaunted', 'undaunted', 'undaunted')
    wrath = AbilityLocatorFactory.create(GameClasses.Priest, 'wrath', 'wrath', 'wrath')


class ProvisionerAbilities:
    awareness = AbilityLocatorFactory.create(GameClasses.Provisioner, 'awareness', 'awareness', 'awareness')
    constant_heat = AbilityLocatorFactory.create(GameClasses.Provisioner, 'constant_heat', 'constant heat', 'constant heat')
    pinch_of_salt = AbilityLocatorFactory.create(GameClasses.Provisioner, 'pinch_of_salt', 'pinch of salt', 'seasoning')
    realization = AbilityLocatorFactory.create(GameClasses.Provisioner, 'realization', 'realization', 'awareness')
    seasoning = AbilityLocatorFactory.create(GameClasses.Provisioner, 'seasoning', 'seasoning', 'seasoning')
    slow_simmer = AbilityLocatorFactory.create(GameClasses.Provisioner, 'slow_simmer', 'slow simmer', 'constant heat')


class RemoteAbilities:
    combat = AbilityLocatorFactory.create(GameClasses.Remote, 'combat', 'combat', 'combat')
    combat_autoface = AbilityLocatorFactory.create(GameClasses.Remote, 'combat_autoface', 'combat autoface', 'combat autoface')
    crouch = AbilityLocatorFactory.create(GameClasses.Remote, 'crouch', 'crouch', 'crouch')
    dps = AbilityLocatorFactory.create(GameClasses.Remote, 'dps', 'dps', 'dps')
    feign_death = AbilityLocatorFactory.create(GameClasses.Remote, 'feign_death', 'feign death', 'feign death')
    follow = AbilityLocatorFactory.create(GameClasses.Remote, 'follow', 'follow', 'follow')
    jump = AbilityLocatorFactory.create(GameClasses.Remote, 'jump', 'jump', 'jump')
    reset_zones = AbilityLocatorFactory.create(GameClasses.Remote, 'reset_zones', 'reset zones', 'reset zones')
    sprint = AbilityLocatorFactory.create(GameClasses.Remote, 'sprint', 'sprint', 'sprint')
    stop_combat = AbilityLocatorFactory.create(GameClasses.Remote, 'stop_combat', 'stop combat', 'stop combat')
    stop_follow = AbilityLocatorFactory.create(GameClasses.Remote, 'stop_follow', 'stop follow', 'stop follow')


class SageAbilities:
    calligraphy = AbilityLocatorFactory.create(GameClasses.Sage, 'calligraphy', 'calligraphy', 'lettering')
    incantation = AbilityLocatorFactory.create(GameClasses.Sage, 'incantation', 'incantation', 'spellbinding')
    lettering = AbilityLocatorFactory.create(GameClasses.Sage, 'lettering', 'lettering', 'lettering')
    notation = AbilityLocatorFactory.create(GameClasses.Sage, 'notation', 'notation', 'notation')
    scripting = AbilityLocatorFactory.create(GameClasses.Sage, 'scripting', 'scripting', 'notation')
    spellbinding = AbilityLocatorFactory.create(GameClasses.Sage, 'spellbinding', 'spellbinding', 'spellbinding')


class ScoutAbilities:
    balanced_synergy = AbilityLocatorFactory.create(GameClasses.Scout, 'balanced_synergy', 'balanced synergy', 'balanced synergy')
    cheap_shot = AbilityLocatorFactory.create(GameClasses.Scout, 'cheap_shot', 'cheap shot', 'cheap shot')
    dagger_storm = AbilityLocatorFactory.create(GameClasses.Scout, 'dagger_storm', 'dagger storm', 'dagger storm')
    dozekars_resilience = AbilityLocatorFactory.create(GameClasses.Scout, 'dozekars_resilience', 'dozekar\'s resilience', 'dozekar\'s resilience')
    evade = AbilityLocatorFactory.create(GameClasses.Scout, 'evade', 'evade', 'evade')
    lucky_break = AbilityLocatorFactory.create(GameClasses.Scout, 'lucky_break', 'lucky break', 'lucky break')
    persistence = AbilityLocatorFactory.create(GameClasses.Scout, 'persistence', 'persistence', 'persistence')
    strike_of_consistency = AbilityLocatorFactory.create(GameClasses.Scout, 'strike_of_consistency', 'strike of consistency', 'strike of consistency')
    trick_of_the_hunter = AbilityLocatorFactory.create(GameClasses.Scout, 'trick_of_the_hunter', 'trick of the hunter', 'trick of the hunter')


class PaladinAbilities:
    faithful_cry = AbilityLocatorFactory.create(GameClasses.Paladin, 'faithful_cry', 'faithful cry', 'faithful cry')
    power_cleave = AbilityLocatorFactory.create(GameClasses.Paladin, 'power_cleave', 'power cleave', 'power cleave')
    holy_strike = AbilityLocatorFactory.create(GameClasses.Paladin, 'holy_strike', 'holy strike', 'holy strike')
    harbinger_of_justice = AbilityLocatorFactory.create(GameClasses.Paladin, 'harbinger_of_justice', 'harbinger of justice', 'harbinger of justice')
    clarion = AbilityLocatorFactory.create(GameClasses.Paladin, 'clarion', 'clarion', 'clarion')
    righteousness = AbilityLocatorFactory.create(GameClasses.Paladin, 'righteousness', 'righteousness', 'righteousness')
    divine_vengeance = AbilityLocatorFactory.create(GameClasses.Paladin, 'divine_vengeance', 'divine vengeance', 'divine vengeance')
    demonstration_of_faith = AbilityLocatorFactory.create(GameClasses.Paladin, 'demonstration_of_faith', 'demonstration of faith', 'demonstration of faith')
    divine_will = AbilityLocatorFactory.create(GameClasses.Paladin, 'divine_will', 'divine will', 'divine will')
    faith_strike = AbilityLocatorFactory.create(GameClasses.Paladin, 'faith_strike', 'faith strike', 'faith strike')
    penitent_kick = AbilityLocatorFactory.create(GameClasses.Paladin, 'penitent_kick', 'penitent kick', 'penitent kick')
    heroic_dash = AbilityLocatorFactory.create(GameClasses.Paladin, 'heroic_dash', 'heroic dash', 'heroic dash')
    decree = AbilityLocatorFactory.create(GameClasses.Paladin, 'decree', 'decree', 'decree')
    holy_aid = AbilityLocatorFactory.create(GameClasses.Paladin, 'holy_aid', 'holy aid', 'holy aid')
    judgment = AbilityLocatorFactory.create(GameClasses.Paladin, 'judgment', 'judgment', 'judgment')
    prayer_of_healing = AbilityLocatorFactory.create(GameClasses.Paladin, 'prayer_of_healing', 'prayer of healing', 'prayer of healing')
    holy_circle = AbilityLocatorFactory.create(GameClasses.Paladin, 'holy_circle', 'holy circle', 'holy circle')
    ancient_wrath = AbilityLocatorFactory.create(GameClasses.Paladin, 'ancient_wrath', 'ancient wrath', 'ancient wrath')
    crusaders_judgement = AbilityLocatorFactory.create(GameClasses.Paladin, 'crusaders_judgement', 'crusader\'s judgement', 'crusader\'s judgement')


class ShamanAbilities:
    ancestral_channeling = AbilityLocatorFactory.create(GameClasses.Shaman, 'ancestral_channeling', 'ancestral channeling', 'ancestral channeling')
    ancestral_palisade = AbilityLocatorFactory.create(GameClasses.Shaman, 'ancestral_palisade', 'ancestral palisade', 'ancestral palisade')
    eidolic_ward = AbilityLocatorFactory.create(GameClasses.Shaman, 'eidolic_ward', 'eidolic ward', 'eidolic ward')
    malady = AbilityLocatorFactory.create(GameClasses.Shaman, 'malady', 'malady', 'malady')
    scourge = AbilityLocatorFactory.create(GameClasses.Shaman, 'scourge', 'scourge', 'scourge')
    soul_shackle = AbilityLocatorFactory.create(GameClasses.Shaman, 'soul_shackle', 'soul shackle', 'soul shackle')
    spirit_aegis = AbilityLocatorFactory.create(GameClasses.Shaman, 'spirit_aegis', 'spirit aegis', 'spirit aegis')
    summon_spirit_companion = AbilityLocatorFactory.create(GameClasses.Shaman, 'summon_spirit_companion', 'summon spirit companion', 'summon spirit companion')
    totemic_protection = AbilityLocatorFactory.create(GameClasses.Shaman, 'totemic_protection', 'totemic protection', 'totemic protection')
    umbral_trap = AbilityLocatorFactory.create(GameClasses.Shaman, 'umbral_trap', 'umbral trap', 'umbral trap')
    immunities = AbilityLocatorFactory.create(GameClasses.Shaman, 'immunities', 'immunities', 'immunities')


class SummonerAbilities:
    blightfire = AbilityLocatorFactory.create(GameClasses.Summoner, 'blightfire', 'blightfire', 'blightfire')
    elemental_toxicity = AbilityLocatorFactory.create(GameClasses.Summoner, 'elemental_toxicity', 'elemental toxicity', 'elemental toxicity')


class SwashbucklerAbilities:
    privateers_flourish = AbilityLocatorFactory.create(GameClasses.Swashbuckler, 'privateers_flourish', 'privateers flourish', 'privateers flourish')


class TailorAbilities:
    binding = AbilityLocatorFactory.create(GameClasses.Tailor, 'binding', 'binding', 'knots')
    dexterous = AbilityLocatorFactory.create(GameClasses.Tailor, 'dexterous', 'dexterous', 'nimble')
    hem = AbilityLocatorFactory.create(GameClasses.Tailor, 'hem', 'hem', 'stitching')
    knots = AbilityLocatorFactory.create(GameClasses.Tailor, 'knots', 'knots', 'knots')
    nimble = AbilityLocatorFactory.create(GameClasses.Tailor, 'nimble', 'nimble', 'nimble')
    stitching = AbilityLocatorFactory.create(GameClasses.Tailor, 'stitching', 'stitching', 'stitching')


class ThaumaturgistAbilities:
    anti_life = AbilityLocatorFactory.create(GameClasses.Thaumaturgist, 'anti_life', 'anti-life', 'anti-life')
    bloatfly = AbilityLocatorFactory.create(GameClasses.Thaumaturgist, 'bloatfly', 'bloatfly', 'bloatfly')
    blood_contract = AbilityLocatorFactory.create(GameClasses.Thaumaturgist, 'blood_contract', 'blood contract', 'blood contract')
    blood_parasite = AbilityLocatorFactory.create(GameClasses.Thaumaturgist, 'blood_parasite', 'blood parasite', 'blood parasite')
    bonds_of_blood = AbilityLocatorFactory.create(GameClasses.Thaumaturgist, 'bonds_of_blood', 'bonds of blood', 'bonds of blood')
    desiccation = AbilityLocatorFactory.create(GameClasses.Thaumaturgist, 'desiccation', 'desiccation', 'desiccation')
    exsanguination = AbilityLocatorFactory.create(GameClasses.Thaumaturgist, 'exsanguination', 'exsanguination', 'exsanguination')
    necrotic_consumption = AbilityLocatorFactory.create(GameClasses.Thaumaturgist, 'necrotic_consumption', 'necrotic consumption', 'necrotic consumption')
    oblivion_link = AbilityLocatorFactory.create(GameClasses.Thaumaturgist, 'oblivion_link', 'oblivion link', 'oblivion link')
    revocation_of_life = AbilityLocatorFactory.create(GameClasses.Thaumaturgist, 'revocation_of_life', 'revocation of life', 'revocation of life')
    septic_strike = AbilityLocatorFactory.create(GameClasses.Thaumaturgist, 'septic_strike', 'septic strike', 'septic strike')
    tainted_mutation = AbilityLocatorFactory.create(GameClasses.Thaumaturgist, 'tainted_mutation', 'tainted mutation', 'tainted mutation')
    virulent_outbreak = AbilityLocatorFactory.create(GameClasses.Thaumaturgist, 'virulent_outbreak', 'virulent outbreak', 'virulent outbreak')


class ThugAbilities:
    change_of_engagement = AbilityLocatorFactory.create(GameClasses.Thug, 'change_of_engagement', 'change of engagement', 'change of engagement')
    danse_macabre = AbilityLocatorFactory.create(GameClasses.Thug, 'danse_macabre', 'danse macabre', 'danse macabre')
    detect_weakness = AbilityLocatorFactory.create(GameClasses.Thug, 'detect_weakness', 'detect weakness', 'detect weakness')
    pris_de_fer = AbilityLocatorFactory.create(GameClasses.Thug, 'pris_de_fer', 'pris de fer', 'pris de fer')
    shadow = AbilityLocatorFactory.create(GameClasses.Thug, 'shadow', 'shadow', 'shadow')
    thieving_essence = AbilityLocatorFactory.create(GameClasses.Thug, 'thieving_essence', 'thieving essence', 'thieving essence')
    torporous_strike = AbilityLocatorFactory.create(GameClasses.Thug, 'torporous_strike', 'torporous strike', 'torporous strike')
    traumatic_swipe = AbilityLocatorFactory.create(GameClasses.Thug, 'traumatic_swipe', 'traumatic swipe', 'traumatic swipe')
    walk_the_plank = AbilityLocatorFactory.create(GameClasses.Thug, 'walk_the_plank', 'walk the plank', 'walk the plank')


class TroubadorAbilities:
    abhorrent_verse = AbilityLocatorFactory.create(GameClasses.Troubador, 'abhorrent_verse', 'abhorrent verse', 'abhorrent verse')
    bagpipe_solo = AbilityLocatorFactory.create(GameClasses.Troubador, 'bagpipe_solo', 'bagpipe solo', 'bagpipe solo')
    breathtaking_bellow = AbilityLocatorFactory.create(GameClasses.Troubador, 'breathtaking_bellow', 'breathtaking bellow', 'breathtaking bellow')
    ceremonial_blade = AbilityLocatorFactory.create(GameClasses.Troubador, 'ceremonial_blade', 'ceremonial blade', 'ceremonial blade')
    chaos_anthem = AbilityLocatorFactory.create(GameClasses.Troubador, 'chaos_anthem', 'chaos anthem', 'chaos anthem')
    countersong = AbilityLocatorFactory.create(GameClasses.Troubador, 'countersong', 'countersong', 'countersong')
    dancing_blade = AbilityLocatorFactory.create(GameClasses.Troubador, 'dancing_blade', 'dancing blade', 'dancing blade')
    demoralizing_processional = AbilityLocatorFactory.create(GameClasses.Troubador, 'demoralizing_processional', 'demoralizing processional', 'demoralizing processional')
    depressing_chant = AbilityLocatorFactory.create(GameClasses.Troubador, 'depressing_chant', 'depressing chant', 'depressing chant')
    discordant_verse = AbilityLocatorFactory.create(GameClasses.Troubador, 'discordant_verse', 'discordant verse', 'sandra\'s deafening strike')
    energizing_ballad = AbilityLocatorFactory.create(GameClasses.Troubador, 'energizing_ballad', 'energizing ballad', 'energizing ballad')
    jesters_cap = AbilityLocatorFactory.create(GameClasses.Troubador, 'jesters_cap', 'jester\'s cap', 'jester\'s cap')
    lullaby = AbilityLocatorFactory.create(GameClasses.Troubador, 'lullaby', 'lullaby', 'lullaby')
    maelstrom_of_sound = AbilityLocatorFactory.create(GameClasses.Troubador, 'maelstrom_of_sound', 'maelstrom of sound', 'maelstrom of sound')
    maestros_harmony = AbilityLocatorFactory.create(GameClasses.Troubador, 'maestros_harmony', 'maestros harmony', 'perfection of the maestro')
    painful_lamentations = AbilityLocatorFactory.create(GameClasses.Troubador, 'painful_lamentations', 'painful lamentations', 'painful lamentations')
    perfect_shrill = AbilityLocatorFactory.create(GameClasses.Troubador, 'perfect_shrill', 'perfect shrill', 'perfect shrill')
    perfection_of_the_maestro = AbilityLocatorFactory.create(GameClasses.Troubador, 'perfection_of_the_maestro', 'perfection of the maestro', 'perfection of the maestro')
    reverberation = AbilityLocatorFactory.create(GameClasses.Troubador, 'reverberation', 'reverberation', 'reverberation')
    sandras_deafening_strike = AbilityLocatorFactory.create(GameClasses.Troubador, 'sandras_deafening_strike', 'sandra\'s deafening strike', 'sandra\'s deafening strike')
    singing_shot = AbilityLocatorFactory.create(GameClasses.Troubador, 'singing_shot', 'singing shot', 'singing shot')
    sonic_interference = AbilityLocatorFactory.create(GameClasses.Troubador, 'sonic_interference', 'sonic interference', 'sonic interference')
    support = AbilityLocatorFactory.create(GameClasses.Troubador, 'support', 'support', 'support')
    tap_essence = AbilityLocatorFactory.create(GameClasses.Troubador, 'tap_essence', 'tap essence', 'tap essence')
    thunderous_overture = AbilityLocatorFactory.create(GameClasses.Troubador, 'thunderous_overture', 'thunderous overture', 'thunderous overture')
    upbeat_tempo = AbilityLocatorFactory.create(GameClasses.Troubador, 'upbeat_tempo', 'upbeat tempo', 'upbeat tempo')
    vexing_verses = AbilityLocatorFactory.create(GameClasses.Troubador, 'vexing_verses', 'vexing verses', 'vexing verses')
    resonance = AbilityLocatorFactory.create(GameClasses.Troubador, 'resonance', 'resonance', 'resonance')
    impassioned_rousing = AbilityLocatorFactory.create(GameClasses.Troubador, 'impassioned_rousing', 'impassioned rousing', 'impassioned rousing')
    raxxyls_rousing_tune = AbilityLocatorFactory.create(GameClasses.Troubador, 'raxxyls_rousing_tune', 'raxxyl\'s rousing tune', 'raxxyl\'s rousing tune')
    aria_of_magic = AbilityLocatorFactory.create(GameClasses.Troubador, 'aria_of_magic', 'aria of magic', 'aria of magic')
    allegretto = AbilityLocatorFactory.create(GameClasses.Troubador, 'allegretto', 'allegretto', 'allegretto')


class WardenAbilities:
    aspect_of_the_forest = AbilityLocatorFactory.create(GameClasses.Warden, 'aspect_of_the_forest', 'aspect of the forest', 'aspect of the forest')
    clearwater_current = AbilityLocatorFactory.create(GameClasses.Warden, 'clearwater_current', 'clearwater current', 'clearwater current')
    cyclone = AbilityLocatorFactory.create(GameClasses.Warden, 'cyclone', 'cyclone', 'cyclone')
    frostbite = AbilityLocatorFactory.create(GameClasses.Warden, 'frostbite', 'frostbite', 'frostbite')
    frostbite_slice = AbilityLocatorFactory.create(GameClasses.Warden, 'frostbite_slice', 'frostbite slice', 'frostbite slice')
    healing_grove = AbilityLocatorFactory.create(GameClasses.Warden, 'healing_grove', 'healing grove', 'healing grove')
    healstorm = AbilityLocatorFactory.create(GameClasses.Warden, 'healstorm', 'healstorm', 'healstorm')
    hierophantic_genesis = AbilityLocatorFactory.create(GameClasses.Warden, 'hierophantic_genesis', 'hierophantic genesis', 'hierophantic genesis')
    icefall = AbilityLocatorFactory.create(GameClasses.Warden, 'icefall', 'icefall', 'icefall')
    infuriating_thorns = AbilityLocatorFactory.create(GameClasses.Warden, 'infuriating_thorns', 'infuriating thorns', 'infuriating thorns')
    instinct = AbilityLocatorFactory.create(GameClasses.Warden, 'instinct', 'instinct', 'instinct')
    natures_embrace = AbilityLocatorFactory.create(GameClasses.Warden, 'natures_embrace', 'nature\'s embrace', 'nature\'s embrace')
    natures_renewal = AbilityLocatorFactory.create(GameClasses.Warden, 'natures_renewal', 'nature\'s renewal', 'nature\'s renewal')
    photosynthesis = AbilityLocatorFactory.create(GameClasses.Warden, 'photosynthesis', 'photosynthesis', 'photosynthesis')
    regenerating_spores = AbilityLocatorFactory.create(GameClasses.Warden, 'regenerating_spores', 'regenerating spores', 'regenerating spores')
    sandstorm = AbilityLocatorFactory.create(GameClasses.Warden, 'sandstorm', 'sandstorm', 'sandstorm')
    shatter_infections = AbilityLocatorFactory.create(GameClasses.Warden, 'shatter_infections', 'shatter infections', 'shatter infections')
    spirit_of_the_wolf = AbilityLocatorFactory.create(GameClasses.Warden, 'spirit_of_the_wolf', 'spirit of the wolf', 'spirit of the wolf')
    storm_of_shale = AbilityLocatorFactory.create(GameClasses.Warden, 'storm_of_shale', 'storm of shale', 'sandstorm')
    sylvan_bloom = AbilityLocatorFactory.create(GameClasses.Warden, 'sylvan_bloom', 'sylvan bloom', 'sylvan bloom')
    sylvan_embrace = AbilityLocatorFactory.create(GameClasses.Warden, 'sylvan_embrace', 'sylvan embrace', 'sylvan embrace')
    thorncoat = AbilityLocatorFactory.create(GameClasses.Warden, 'thorncoat', 'thorncoat', 'thorncoat')
    tunares_chosen = AbilityLocatorFactory.create(GameClasses.Warden, 'tunares_chosen', 'tunare\'s chosen', 'tunare\'s chosen')
    tunares_watch = AbilityLocatorFactory.create(GameClasses.Warden, 'tunares_watch', 'tunare\'s watch', 'tunare\'s watch')
    verdant_whisper = AbilityLocatorFactory.create(GameClasses.Warden, 'verdant_whisper', 'verdant whisper', 'verdant whisper')
    ward_of_the_untamed = AbilityLocatorFactory.create(GameClasses.Warden, 'ward_of_the_untamed', 'ward of the untamed', 'ward of the untamed')
    whirl_of_permafrost = AbilityLocatorFactory.create(GameClasses.Warden, 'whirl_of_permafrost', 'whirl of permafrost', 'winds of permafrost')
    winds_of_growth = AbilityLocatorFactory.create(GameClasses.Warden, 'winds_of_growth', 'winds of growth', 'winds of growth')
    winds_of_healing = AbilityLocatorFactory.create(GameClasses.Warden, 'winds_of_healing', 'winds of healing', 'winds of healing')
    winds_of_permafrost = AbilityLocatorFactory.create(GameClasses.Warden, 'winds_of_permafrost', 'winds of permafrost', 'winds of permafrost')


class WeaponsmithAbilities:
    anneal = AbilityLocatorFactory.create(GameClasses.Weaponsmith, 'anneal', 'anneal', 'anneal')
    compress = AbilityLocatorFactory.create(GameClasses.Weaponsmith, 'compress', 'compress', 'anneal')
    hardening = AbilityLocatorFactory.create(GameClasses.Weaponsmith, 'hardening', 'hardening', 'hardening')
    set = AbilityLocatorFactory.create(GameClasses.Weaponsmith, 'set', 'set', 'hardening')
    strengthening = AbilityLocatorFactory.create(GameClasses.Weaponsmith, 'strengthening', 'strengthening', 'tempering')
    tempering = AbilityLocatorFactory.create(GameClasses.Weaponsmith, 'tempering', 'tempering', 'tempering')


class WoodworkerAbilities:
    calibrate = AbilityLocatorFactory.create(GameClasses.Woodworker, 'calibrate', 'calibrate', 'measure')
    carving = AbilityLocatorFactory.create(GameClasses.Woodworker, 'carving', 'carving', 'carving')
    chiselling = AbilityLocatorFactory.create(GameClasses.Woodworker, 'chiselling', 'chiselling', 'carving')
    handwork = AbilityLocatorFactory.create(GameClasses.Woodworker, 'handwork', 'handwork', 'handwork')
    measure = AbilityLocatorFactory.create(GameClasses.Woodworker, 'measure', 'measure', 'measure')
    whittling = AbilityLocatorFactory.create(GameClasses.Woodworker, 'whittling', 'whittling', 'handwork')


ability_collection_classes = {
    'Alchemist': AlchemistAbilities,
    'Armorer': ArmorerAbilities,
    'Artisan': ArtisanAbilities,
    'Bard': BardAbilities,
    'Brawler': BrawlerAbilities,
    'Brigand': BrigandAbilities,
    'Carpenter': CarpenterAbilities,
    'Cleric': ClericAbilities,
    'Coercer': CoercerAbilities,
    'Commoner': CommonerAbilities,
    'Conjuror': ConjurorAbilities,
    'Crusader': CrusaderAbilities,
    'Defiler': DefilerAbilities,
    'Dirge': DirgeAbilities,
    'Druid': DruidAbilities,
    'Elementalist': ElementalistAbilities,
    'Enchanter': EnchanterAbilities,
    'Etherealist': EtherealistAbilities,
    'Fighter': FighterAbilities,
    'Fury': FuryAbilities,
    'Geomancer': GeomancerAbilities,
    'Illusionist': IllusionistAbilities,
    'Inquisitor': InquisitorAbilities,
    'Items': ItemsAbilities,
    'Jeweler': JewelerAbilities,
    'Local': LocalAbilities,
    'Mage': MageAbilities,
    'Monk': MonkAbilities,
    'Mystic': MysticAbilities,
    'Priest': PriestAbilities,
    'Provisioner': ProvisionerAbilities,
    'Remote': RemoteAbilities,
    'Sage': SageAbilities,
    'Scout': ScoutAbilities,
    'Paladin': PaladinAbilities,
    'Shaman': ShamanAbilities,
    'Summoner': SummonerAbilities,
    'Swashbuckler': SwashbucklerAbilities,
    'Tailor': TailorAbilities,
    'Thaumaturgist': ThaumaturgistAbilities,
    'Thug': ThugAbilities,
    'Troubador': TroubadorAbilities,
    'Warden': WardenAbilities,
    'Weaponsmith': WeaponsmithAbilities,
    'Woodworker': WoodworkerAbilities,
}
