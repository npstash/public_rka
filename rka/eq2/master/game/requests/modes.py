from typing import Optional

from rka.eq2.master.game.engine.mode import Mode
from rka.eq2.master.game.engine.processor import Processor
from rka.eq2.master.game.gameclass import GameClasses
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.requests import logger
from rka.eq2.master.game.requests.request_factory import RequestFactory


class SoloCombatMode(Mode):
    def __init__(self, processor: Processor, request_factory: RequestFactory, description: str, duration: float):
        Mode.__init__(self, processor, description=description, duration=duration)
        self.add_task_for_running(request_factory.prepare())


class LocalMonkPlayerCombatMode(SoloCombatMode):
    def __init__(self, processor: Processor, request_factory: RequestFactory, duration: float):
        SoloCombatMode.__init__(self, processor, request_factory, description=self.__class__.__name__, duration=duration)
        self.request_factory = request_factory
        self.add_task_for_running(request_factory.local_monk_player_combat())


class LocalFuryPlayerCombatMode(SoloCombatMode):
    def __init__(self, processor: Processor, request_factory: RequestFactory, duration: float):
        SoloCombatMode.__init__(self, processor, request_factory, description=self.__class__.__name__, duration=duration)
        self.add_task_for_running(request_factory.local_fury_player_combat())


class LocalPaladinPlayerCombatMode(SoloCombatMode):
    def __init__(self, processor: Processor, request_factory: RequestFactory, duration: float):
        SoloCombatMode.__init__(self, processor, request_factory, description=self.__class__.__name__, duration=duration)
        self.add_task_for_running(request_factory.local_paladin_player_combat())


class AoeComabatMode(Mode):
    def __init__(self, processor: Processor, request_factory: RequestFactory, duration: float):
        Mode.__init__(self, processor, description='aoe combat', duration=duration)
        self.add_task_for_running(request_factory.aoe_dps())


class BasicGroupCombatMode(Mode):
    def __init__(self, processor: Processor, request_factory: RequestFactory, description: str, duration: float):
        Mode.__init__(self, processor, description=description, duration=duration)
        self.add_task_for_running(request_factory.prepare())
        # basic heals, wards
        self.add_task_for_running(request_factory.single_target_heals_default_target())
        self.add_task_for_running(request_factory.single_target_heals_rotate_target())
        self.add_task_for_running(request_factory.common_group_heals())
        # keep casting while moving
        self.add_task_for_running(request_factory.free_move())
        # buffing
        self.add_task_for_running(request_factory.common_buffs())
        # combat
        self.add_task_for_running(request_factory.support())
        self.add_task_for_closing(request_factory.stop_attack())


class BossGroupComabatMode(Mode):
    def __init__(self, processor: Processor, request_factory: RequestFactory, duration: float):
        Mode.__init__(self, processor, description='boss combat', duration=duration)
        # extra heals, wards, power
        self.add_task_for_running(request_factory.advanced_group_heals())
        self.add_task_for_running(request_factory.advanced_group_power())
        self.add_task_for_running(request_factory.common_group_protections())
        self.add_task_for_running(request_factory.immunities())
        # buffing
        self.add_task_for_running(request_factory.uncommon_buffs())
        self.add_task_for_running(request_factory.non_overlapping_main_group_buffs())
        # debuffing
        self.add_task_for_running(request_factory.common_debuffs())
        self.add_task_for_running(request_factory.non_overlapping_debuffs())
        self.add_task_for_starting(request_factory.drain_power_once())
        # some dps
        self.add_task_for_starting(request_factory.profession_nukes())


class HardGroupComabatMode(Mode):
    def __init__(self, processor: Processor, request_factory: RequestFactory, duration: float):
        Mode.__init__(self, processor, description='hard combat', duration=duration)
        self.add_task_for_running(request_factory.group_aoe_blockers())
        self.add_task_for_running(request_factory.group_strong_heals())


class EmergencyGroupCombatMode(Mode):
    def __init__(self, processor: Processor, request_factory: RequestFactory, duration: float):
        Mode.__init__(self, processor, description='emergency', duration=duration)
        self.add_task_for_running(request_factory.group_aoe_blockers())
        self.add_task_for_running(request_factory.group_strong_heals())
        self.add_task_for_running(request_factory.group_deathsave())
        self.add_task_for_running(request_factory.group_strong_power())
        self.add_task_for_running(request_factory.group_emergency_extras())
        self.add_task_for_running(request_factory.tank_deathsave())
        self.add_task_for_running(request_factory.tank_strong_heals())
        self.add_task_for_running(request_factory.self_immunities())


class ModeFactory:
    @staticmethod
    def create_player_solo_mode(player: Optional[IPlayer], processor: Processor, request_factory: RequestFactory) -> Mode:
        if player:
            if player.is_local():
                if player.is_class(GameClasses.Monk):
                    return LocalMonkPlayerCombatMode(processor, request_factory, RequestFactory.DEFAULT_COMBAT_DURATION)
                if player.is_class(GameClasses.Fury):
                    return LocalFuryPlayerCombatMode(processor, request_factory, RequestFactory.DEFAULT_COMBAT_DURATION)
                if player.is_class(GameClasses.Paladin):
                    return LocalPaladinPlayerCombatMode(processor, request_factory, RequestFactory.DEFAULT_COMBAT_DURATION)
                logger.warn(f'ClassSpecificModeFactory: unsupported class: {player}')
        return SoloCombatMode(processor, request_factory, description=f'Default solo mode for {player}', duration=RequestFactory.DEFAULT_COMBAT_DURATION)

    @staticmethod
    def create_basic_group_mode(processor: Processor, request_factory: RequestFactory) -> Mode:
        return BasicGroupCombatMode(processor, request_factory, f'Basic Main Mode', RequestFactory.DEFAULT_COMBAT_DURATION)

    @staticmethod
    def create_aoe_group_mode(processor: Processor, request_factory: RequestFactory) -> Mode:
        return AoeComabatMode(processor, request_factory, RequestFactory.SHORT_COMBAT_DURATION)

    @staticmethod
    def create_boss_group_mode(processor: Processor, request_factory: RequestFactory) -> Mode:
        return BossGroupComabatMode(processor, request_factory, RequestFactory.DEFAULT_COMBAT_DURATION)

    @staticmethod
    def create_hard_group_mode(processor: Processor, request_factory: RequestFactory) -> Mode:
        return HardGroupComabatMode(processor, request_factory, RequestFactory.DEFAULT_COMBAT_DURATION)

    @staticmethod
    def create_emergency_group_mode(processor: Processor, request_factory: RequestFactory) -> Mode:
        return EmergencyGroupCombatMode(processor, request_factory, RequestFactory.DEFAULT_COMBAT_DURATION)
