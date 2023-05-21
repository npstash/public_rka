from __future__ import annotations

import time
from typing import Optional

from rka.components.events.event_system import EventSystem
from rka.eq2.configs.shared.game_constants import CURRENT_MAX_LEVEL
from rka.eq2.configs.shared.rka_constants import LOCAL_ABILITY_INJECTOR_PATH, LOCAL_COMMAND_INJECTOR_PATH, REMOTE_INJECTOR_PATH
from rka.eq2.master import BuilderTools, logger
from rka.eq2.master.control import IClientConfig, InputConfig
from rka.eq2.master.game import get_unknown_zone
from rka.eq2.master.game.effect import EffectScopeType
from rka.eq2.master.game.effect.effects import GeneralEffects
from rka.eq2.master.game.events.combat import CombatEvents
from rka.eq2.master.game.events.combat_parser import CombatParserEvents
from rka.eq2.master.game.events.object_state import ObjectStateEvents
from rka.eq2.master.game.events.player_info import PlayerInfoEvents
from rka.eq2.master.game.gameclass import GameClass, GameClasses
from rka.eq2.master.game.interfaces import IAbility, IPlayer, IPlayerManager, IEffectsManager
from rka.eq2.master.game.player import PlayerStatus, PlayerInfo, logger
from rka.eq2.master.game.player.player_config import PlayerConfigFactory
from rka.eq2.shared import ClientFlags, GameServer, ClientConfigData


class DummyPlayer(IPlayer):
    def __init__(self, player_mgr: IPlayerManager, client_config: IClientConfig):
        IPlayer.__init__(self)
        self.__player_mgr = player_mgr
        self.__player_name = client_config.get_client_config_data().player_name
        self.__player_info = PlayerInfo()
        self.__last_cast_ability: Optional[IAbility] = None
        self.__client_cfg = client_config

    def __str__(self) -> str:
        return self.__player_name

    def build_player_effects(self, effects_mgr: IEffectsManager):
        source = self.as_effect_target()
        self.effects.add_effect(GeneralEffects.CASTING_SPEED(100.0).build_effect(effects_mgr, sustain_target=source, sustain_source=source))
        self.effects.add_effect(GeneralEffects.REUSE_SPEED(100.0).build_effect(effects_mgr, sustain_target=source, sustain_source=source))

    def get_client_config(self) -> IClientConfig:
        return self.__client_cfg

    def get_client_config_data(self) -> ClientConfigData:
        return self.__client_cfg.get_client_config_data()

    def get_client_flags(self) -> ClientFlags:
        return self.__client_cfg.get_client_config_data()

    def get_host_id(self) -> int:
        return 0

    def get_client_id(self) -> str:
        return 'unknown'

    def get_player_manager(self) -> IPlayerManager:
        return self.__player_mgr

    def get_server(self) -> GameServer:
        return GameServer.unknown

    def get_inputs(self) -> InputConfig:
        logger.error('DummyPlayer.get_inputs() should not be called')
        # noinspection PyTypeChecker
        return None

    def get_ability_injector_name(self) -> str:
        return 'unknown'

    def get_command_injector_name(self) -> str:
        return 'unknown'

    def get_player_name(self) -> str:
        return self.__player_name

    def get_player_id(self) -> str:
        return self.__player_name

    def get_player_info(self) -> PlayerInfo:
        return self.__player_info

    def is_busy(self) -> bool:
        return False

    def is_busier_than(self, other: IPlayer) -> bool:
        return False

    def interrupted(self):
        pass

    def get_last_cast_ability(self) -> Optional[IAbility]:
        return self.__last_cast_ability

    def set_last_cast_ability(self, ability: Optional[IAbility]):
        self.__last_cast_ability = ability

    def is_class(self, game_class: GameClass) -> bool:
        return False

    def get_adventure_class(self) -> Optional[GameClass]:
        return GameClasses.Commoner

    def get_crafter_class(self) -> Optional[GameClass]:
        return None

    def get_ascension_class(self) -> Optional[GameClass]:
        return None

    def get_level(self, game_class: GameClass) -> Optional[int]:
        return CURRENT_MAX_LEVEL

    def is_in_group_with(self, player: IPlayer) -> bool:
        return self.get_client_config().get_client_config_data().group_id.is_same_group(player)

    def is_main_player(self) -> bool:
        return False

    def is_alive(self) -> bool:
        return True

    def set_alive(self, alive: bool):
        pass

    def get_status(self) -> PlayerStatus:
        return PlayerStatus.Zoned

    def set_status(self, status: PlayerStatus):
        pass

    def get_zone(self) -> str:
        return ''

    def set_zone(self, zone: str):
        pass


class Player(IPlayer):
    def __init__(self, player_manager: IPlayerManager, client_config: IClientConfig):
        IPlayer.__init__(self)
        self.__player_mgr = player_manager
        self.__client_cfg = client_config
        self.__client_cfg_data = client_config.get_client_config_data()
        self.__player_name = self.__client_cfg_data.player_name
        self.__client_id = self.__client_cfg_data.client_id
        self.__player_id = self.__client_cfg_data.player_id
        self.__group_id = self.__client_cfg_data.group_id
        self.__player_cfg = PlayerConfigFactory.produce_player_config(client_config)
        self.__client_flags = self.__client_cfg_data.client_flags
        self.__last_cast_ability = None
        self.__last_interrupt = 0.0
        self.__zone = get_unknown_zone(self.__player_cfg.player_name)
        self.__alive = True
        self.__status = PlayerStatus.Offline
        EventSystem.get_main_bus().subscribe(CombatParserEvents.PLAYER_INTERRUPTED(player_name=self.get_player_name()), lambda *args: self.interrupted())

    def build_player_abilities(self, builder_tools: BuilderTools):
        self.__player_cfg.build_all_classes_abilities(player=self, builder_tools=builder_tools)

    def build_player_info(self, builder_tools: BuilderTools):
        if self.__player_cfg.has_census:
            player_census_data = builder_tools.census_cache.get_player_census_data(self.get_server().servername, self.get_player_name())
            assert player_census_data, self.get_player_name()
            self.__player_cfg.player_info.fill_from_census(player_census_data)
            if self.__player_cfg.player_info.base_reuse_speed < 100.0:
                logger.warn(f'Player {self.__player_cfg.player_name} has only {self.__player_cfg.player_info.base_reuse_speed} base reuse speed')
            if self.__player_cfg.player_info.base_casting_speed < 100.0:
                logger.warn(f'Player {self.__player_cfg.player_name} has only {self.__player_cfg.player_info.base_casting_speed} base casting speed')

    def build_player_effects(self, builder_tools: BuilderTools):
        if self.get_player_info().base_casting_speed:
            self.__player_cfg.player_effects.append(GeneralEffects.CASTING_SPEED(self.get_player_info().base_casting_speed))
        if self.get_player_info().base_reuse_speed:
            self.__player_cfg.player_effects.append(GeneralEffects.REUSE_SPEED(self.get_player_info().base_reuse_speed))
        if self.get_player_info().base_recovery_speed:
            self.__player_cfg.player_effects.append(GeneralEffects.RECOVERY_SPEED(self.get_player_info().base_recovery_speed))
        effect_source = self.as_effect_target()
        for effect_builder in self.__player_cfg.player_effects:
            effect = effect_builder.build_effect(effect_mgr=builder_tools.effects_mgr, sustain_target=effect_source, sustain_source=effect_source)
            self.effects.add_effect(effect)

    def __str__(self) -> str:
        return self.__player_cfg.player_name

    def __hash__(self) -> int:
        return self.get_player_name().__hash__()

    def __eq__(self, other) -> bool:
        if not isinstance(other, IPlayer):
            return False
        if other is self:
            return True
        return self.get_player_name() == other.get_player_name() and self.get_server() == other.get_server()

    def get_client_id(self) -> str:
        return self.__client_id

    def get_host_id(self) -> Optional[int]:
        return self.__client_cfg.get_current_host_id()

    def get_client_config(self) -> IClientConfig:
        return self.__client_cfg

    def get_client_config_data(self) -> ClientConfigData:
        return self.__client_cfg_data

    def get_client_flags(self) -> ClientFlags:
        return self.__client_flags

    def get_server(self) -> GameServer:
        return self.__client_cfg_data.game_server

    def get_player_manager(self) -> IPlayerManager:
        return self.__player_mgr

    def get_inputs(self) -> InputConfig:
        return self.__client_cfg.get_inputs_config()

    def get_command_injector_name(self) -> str:
        if self.is_local():
            return LOCAL_COMMAND_INJECTOR_PATH
        return REMOTE_INJECTOR_PATH

    def get_ability_injector_name(self) -> str:
        if self.is_local():
            return LOCAL_ABILITY_INJECTOR_PATH
        return REMOTE_INJECTOR_PATH

    def is_main_player(self) -> bool:
        return self.is_local() and self.get_status() >= PlayerStatus.Online

    def get_player_name(self) -> str:
        return self.__player_cfg.player_name

    def get_player_id(self) -> str:
        return self.__player_id

    def get_player_info(self) -> PlayerInfo:
        return self.__player_cfg.player_info

    def is_class(self, classes: GameClass) -> bool:
        return self.get_level(classes) is not None

    def __get_first_subtype(self, archetype_class: GameClass) -> Optional[GameClass]:
        subtypes = list()
        for ability_store in self.__player_cfg.iter_ability_stores():
            if ability_store.game_class.is_subclass_of(archetype_class):
                subtypes.append(ability_store.game_class)
        if not subtypes:
            return None
        disjoint_subtypes = list()
        for i, subtype in enumerate(subtypes):
            is_disjoint = True
            for other_subtype in subtypes[i + 1:]:
                if other_subtype.is_subclass_of(subtype):
                    is_disjoint = False
                    break
            if is_disjoint:
                disjoint_subtypes.append(subtype)
        if disjoint_subtypes:
            return disjoint_subtypes[0]
        return None

    def get_adventure_class(self) -> Optional[GameClass]:
        for archetype in [GameClasses.Priest, GameClasses.Fighter, GameClasses.Scout, GameClasses.Mage]:
            cls = self.__get_first_subtype(archetype)
            if cls:
                return cls
        return None

    def get_crafter_class(self) -> Optional[GameClass]:
        return self.__get_first_subtype(GameClasses.Artisan)

    def get_ascension_class(self) -> Optional[GameClass]:
        return self.__get_first_subtype(GameClasses.Ascension)

    def has_archetype(self, archetypeclass: GameClass) -> bool:
        for game_class in self.__player_cfg.iter_classes():
            assert isinstance(game_class, GameClass)
            if game_class.is_subclass_of(archetypeclass):
                return True
        return False

    def get_level(self, game_class: GameClass) -> Optional[int]:
        assert isinstance(game_class, GameClass)
        for ability_store in self.__player_cfg.iter_ability_stores():
            if ability_store.game_class == game_class:
                return ability_store.class_level
            if ability_store.game_class.is_subclass_of(game_class):
                return ability_store.class_level
        return None

    def is_alive(self) -> bool:
        return self.__alive

    def set_alive(self, alive: bool):
        old_alive = self.__alive
        self.__alive = alive
        if old_alive != alive:
            if alive:
                logger.info(f'player {self.get_player_name()} revived')
                event = CombatEvents.PLAYER_REVIVED(player=self)
            else:
                logger.info(f'player {self.get_player_name()} died')
                self.interrupted()
                event = CombatEvents.PLAYER_DIED(player=self)
            EventSystem.get_main_bus().post(event)
        elif alive:
            logger.info(f'player {self.get_player_name()} deathsaved')
            EventSystem.get_main_bus().post(CombatEvents.PLAYER_DEATHSAVED(player=self))

    def get_status(self) -> PlayerStatus:
        return self.__status

    def set_status(self, to_status: PlayerStatus):
        from_status = self.__status
        if from_status == to_status:
            return
        if to_status <= PlayerStatus.Offline:
            self.set_zone(get_unknown_zone(self.__player_cfg.player_name))
        self.__status = to_status
        event = ObjectStateEvents.PLAYER_STATUS_CHANGED(player=self, from_status=from_status, to_status=to_status)
        EventSystem.get_main_bus().post(event)
        if to_status >= PlayerStatus.Logged and from_status <= PlayerStatus.Online:
            self.effects.start_effects_by_scope(EffectScopeType.PLAYER)
            self.effects.start_effects_by_scope(EffectScopeType.ABILITY)
        if to_status >= PlayerStatus.Zoned and from_status <= PlayerStatus.Logged:
            self.effects.start_effects_by_scope(EffectScopeType.RAID)
            self.effects.start_effects_by_scope(EffectScopeType.GROUP)
        if to_status <= PlayerStatus.Online and from_status >= PlayerStatus.Logged:
            self.effects.cancel_effects_by_scope(EffectScopeType.PLAYER)
            self.effects.cancel_effects_by_scope(EffectScopeType.ABILITY)
        if to_status <= PlayerStatus.Logged and from_status >= PlayerStatus.Zoned:
            self.effects.cancel_effects_by_scope(EffectScopeType.RAID)
            self.effects.cancel_effects_by_scope(EffectScopeType.GROUP)

    def get_zone(self) -> str:
        return self.__zone

    def set_zone(self, zone: str):
        old_zone = self.__zone
        self.__zone = zone
        if old_zone != zone:
            event = PlayerInfoEvents.PLAYER_ZONE_CHANGED(player=self, from_zone=old_zone, to_zone=zone)
            EventSystem.get_main_bus().post(event)

    def get_last_cast_ability(self) -> Optional[IAbility]:
        return self.__last_cast_ability

    def set_last_cast_ability(self, ability: Optional[IAbility]):
        self.__last_cast_ability = ability

    def interrupted(self):
        now = time.time()
        if now - self.__last_interrupt < 1.0:
            return
        self.__last_interrupt = now
        last_ability = self.__last_cast_ability
        if last_ability is not None:
            last_ability.interrupted()

    def is_busy(self) -> bool:
        if self.__last_cast_ability is None:
            return False
        return not self.__last_cast_ability.is_after_recovery()

    def is_busier_than(self, other: IPlayer) -> bool:
        self_busy = self.is_busy()
        other_busy = other.is_busy()
        if self_busy == other_busy and isinstance(other, Player):
            return self.__player_cfg.get_class_business() > other.__player_cfg.get_class_business()
        return self_busy

    def is_in_group_with(self, player: IPlayer) -> bool:
        return self.__group_id.is_same_group(player.get_client_config().get_client_config_data().group_id)
