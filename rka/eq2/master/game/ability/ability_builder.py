from __future__ import annotations

from typing import Dict, List, Any, Tuple, Optional, Set, Callable

from rka.components.events import Event
from rka.components.io.log_service import LogLevel, LogService
from rka.eq2.configs.shared.rka_constants import ABILITY_INJECTION_DURATION, PARSE_CENSUS_EFFECTS
from rka.eq2.master import BuilderTools
from rka.eq2.master.control import IAction
from rka.eq2.master.control.action import action_factory, ActionDelegate
from rka.eq2.master.game.ability import AbilityTier, AbilityEffectTarget
from rka.eq2.master.game.ability import injection_useability_template, injection_useabilityonplayer_template
from rka.eq2.master.game.ability.ability_data import AbilityCensusConsts, AbilityExtConsts
from rka.eq2.master.game.ability.ability_effect_parser import AbilityCensusEffectParser
from rka.eq2.master.game.ability.ability_monitors import EventAbilityCastingStartedMonitor, EventAbilityCastingCompletedMonitor, AbstractAbilityMonitor, EventAbilityExpirationMonitor, \
    DefaultMonitorsFactory
from rka.eq2.master.game.ability.generated_abilities import ability_collection_classes
from rka.eq2.master.game.census.census_bridge import ICensusBridge
from rka.eq2.master.game.events.combat_parser import CombatParserEvents
from rka.eq2.master.game.gameclass import GameClass
from rka.eq2.master.game.interfaces import IAbilityMonitor, IAbility, IAbilityLocator, IPlayer, IEffectBuilder, TAbilityBuildTarget, TOptionalTarget, \
    is_ability_build_target, AbilityTarget, IAbilityFactory, TValidTarget
from rka.log_configs import LOG_ABILITY_BUILDER

logger = LogService(LOG_ABILITY_BUILDER)


class PrototypeInjectorAction(ActionDelegate):
    def __init__(self, ability_builder: AbilityBuilder, player: IPlayer, ability: IAbility):
        ActionDelegate.__init__(self, {}, f'Prototype action for {ability}')
        self.__ability_builder = ability_builder
        self.__player = player
        self.__ability = ability

    def prototype(self, target: TOptionalTarget) -> IAction:
        return self.__ability_builder.new_prototyped_action(player=self.__player, ability=self.__ability, target_name=AbilityTarget.get_opt_target_name(target))


class AbilityBuilder:
    def __init__(self, ability_locator: IAbilityLocator):
        self.locator = ability_locator
        self.__tier: Optional[AbilityTier] = None
        self.__action: Optional[IAction] = None
        self.__pre_action: Optional[IAction] = None
        self.__post_action: Optional[IAction] = None
        self.__head_injections: Set[str] = set()
        self.__tail_injections: Set[str] = set()
        self.__effect_builder: Optional[IEffectBuilder] = None
        self.__monitors: List[IAbilityMonitor] = []
        self.__target: TAbilityBuildTarget = None
        self.__is_command = False
        self.__census_data: Optional[AbilityCensusConsts] = None
        self.__class_level: Optional[int] = None
        self.__has_action_withdrawer = False
        self.__injection_passthrough_override: Optional[bool] = None
        self.__modifiers_set: List[Tuple[str, Any]] = list()
        self.__modifiers_fn: List[Tuple[str, Callable[[AbilityCensusConsts, AbilityExtConsts], Any]]] = list()
        self.__non_census_injection_use_ability_str: Optional[str] = None
        self.__non_census_injection_use_ability_on_target_builder_fn: Optional[Callable[[str], str]] = None
        self.__disable_by_default = False
        self.__optional = False
        self.__is_built = False

    def build(self, optional=False):
        assert not self.__is_built, f'{self.locator} had been already built'
        self.__is_built = True
        self.__optional = optional

    def is_built(self) -> bool:
        return self.__is_built

    def get_ability_id(self) -> str:
        return self.locator.get_ext_object().ability_id

    def class_level(self, class_level: int) -> AbilityBuilder:
        assert self.__class_level is None
        self.__class_level = class_level
        return self

    def default_tier(self, ability_tier: AbilityTier) -> AbilityBuilder:
        if self.__tier is None:
            self.__tier = ability_tier
        return self

    def tier(self, ability_tier: AbilityTier) -> AbilityBuilder:
        assert isinstance(ability_tier, AbilityTier)
        if self.__tier:
            logger.warn(f'tier of {self} already set to {self.__tier}, overriding with {ability_tier}')
        self.__tier = ability_tier
        return self

    def casting_start_confirm_event(self, event: Event) -> AbilityBuilder:
        self.__has_action_withdrawer = True
        self.__monitors.append(EventAbilityCastingStartedMonitor(event))
        return self

    def casting_end_confirm_event(self, event: Event) -> AbilityBuilder:
        self.__has_action_withdrawer = True
        self.__monitors.append(EventAbilityCastingCompletedMonitor(event))
        return self

    def casting_confirm_by_combat_event(self, player: IPlayer) -> AbilityBuilder:
        event = CombatParserEvents.COMBAT_HIT(attacker_name=player.get_player_name(), ability_name=self.locator.get_canonical_name(),
                                              is_multi=False, is_autoattack=False, is_dot=False)
        self.casting_end_confirm_event(event)
        return self

    def casting_monitor(self, monitor: AbstractAbilityMonitor) -> AbilityBuilder:
        self.__has_action_withdrawer = True
        self.__monitors.append(monitor)
        return self

    def expiration_event(self, event: Event) -> AbilityBuilder:
        self.__monitors.append(EventAbilityExpirationMonitor(event))
        return self

    def expiration_monitor(self, monitor: AbstractAbilityMonitor) -> AbilityBuilder:
        self.__monitors.append(monitor)
        return self

    def add_head_injection(self, injection: str) -> AbilityBuilder:
        assert injection not in self.__head_injections, f'{self.locator}, {injection}'
        self.__head_injections.add(injection)
        return self

    def add_tail_injection(self, injection: str) -> AbilityBuilder:
        assert injection not in self.__tail_injections, f'{self.locator}, {injection}'
        self.__tail_injections.add(injection)
        return self

    def override_passthrough(self, passthrough: bool) -> AbilityBuilder:
        self.__injection_passthrough_override = passthrough
        return self

    def effect_builder(self, effect_builder: IEffectBuilder) -> AbilityBuilder:
        self.__effect_builder = effect_builder
        return self

    def action(self, action: IAction) -> AbilityBuilder:
        assert isinstance(action, IAction)
        self.__action = action
        return self

    def pre_action(self, action: IAction) -> AbilityBuilder:
        assert isinstance(action, IAction)
        self.__pre_action = action
        return self

    def post_action(self, action: IAction) -> AbilityBuilder:
        assert isinstance(action, IAction)
        self.__post_action = action
        return self

    def recast_maintained(self) -> AbilityBuilder:
        self.add_head_injection(f'cancel_maintained {self.locator.get_canonical_name()}')
        self.modify_census_by_fn('casting', lambda ext_data_, census_data_: census_data_.casting + min(max(census_data_.reuse, 0.0), 5.0))
        return self

    def cancel_spellcast(self) -> AbilityBuilder:
        self.add_head_injection('cancel_spellcast')
        self.modify_set('cancel_spellcast', True)
        return self

    def target(self, target: TAbilityBuildTarget) -> AbilityBuilder:
        assert self.__target is None
        assert is_ability_build_target(target)
        self.__target = target
        return self

    def command(self) -> AbilityBuilder:
        self.__is_command = True
        return self

    def disabled(self) -> AbilityBuilder:
        self.__disable_by_default = True
        return self

    def census_error(self, prop: str, value: float) -> AbilityBuilder:
        self.modify_set(prop, value)
        return self

    def effect_duration(self, value: float) -> AbilityBuilder:
        self.modify_set('duration', value)
        return self

    def untracked_triggers(self, average_duration: float) -> AbilityBuilder:
        self.modify_set('duration', average_duration)
        return self

    def direct_heal_delay(self) -> AbilityBuilder:
        self.modify_set('duration', 2.0)
        return self

    def modify_set(self, prop: str, value: Any) -> AbilityBuilder:
        self.__modifiers_set.append((prop, value))
        return self

    def modify_census_by_fn(self, prop: str, fn: Callable[[AbilityExtConsts, AbilityCensusConsts], Any]) -> AbilityBuilder:
        self.__modifiers_fn.append((prop, fn))
        return self

    def census_data(self, casting: float, reuse: float, recovery: float, duration=0.0, beneficial=True, **kwargs) -> AbilityBuilder:
        census_data = AbilityCensusConsts()
        census_data.name = self.locator.get_canonical_name()
        census_data.casting = casting
        census_data.reuse = reuse
        census_data.recovery = recovery
        census_data.duration = duration
        census_data.beneficial = beneficial
        census_data.does_not_expire = duration < 0.0
        for arg_name, arg_value in kwargs.items():
            assert hasattr(census_data, arg_name), arg_name
            census_data.__setattr__(arg_name, arg_value)
        self.__census_data = census_data
        return self

    def __add_extra_prerecovery(self, delay: float):
        self.modify_census_by_fn('casting', lambda ext_data_, census_data_: census_data_.casting + delay)
        self.pre_action(action_factory.new_action().delay(delay))

    def item_id(self, item_id: int) -> AbilityBuilder:
        # item use command will not work at all if recovery is still not finished for some reason, like lag;
        # give it more time to recover to make it reliable
        self.__add_extra_prerecovery(1.2)
        return self.non_census_injection_use_ability_str(f'use_itemvdl {item_id}')

    def charm_1(self) -> AbilityBuilder:
        self.__add_extra_prerecovery(0.8)
        return self.non_census_injection_use_ability_str('use_equipped_item 20')

    def charm_2(self) -> AbilityBuilder:
        self.__add_extra_prerecovery(0.8)
        return self.non_census_injection_use_ability_str('use_equipped_item 21')

    def non_census_injection_use_ability_str(self, injection_str: Optional[str]) -> AbilityBuilder:
        self.__non_census_injection_use_ability_str = injection_str
        return self

    def non_census_injection_use_ability_on_target_builder_fn(self, builder_fn: Callable[[str], str]) -> AbilityBuilder:
        self.__non_census_injection_use_ability_on_target_builder_fn = builder_fn
        return self

    # noinspection PyMethodMayBeStatic
    def __get_census_ability_injection_str(self, crc: int, target_name: Optional[str]) -> Optional[str]:
        if target_name:
            return injection_useabilityonplayer_template.format(target_name, crc) + '\n'
        else:
            return injection_useability_template.format(crc) + '\n'

    def __get_non_census_ability_injection_str(self, target_name: Optional[str]) -> Optional[str]:
        if target_name:
            if not self.__non_census_injection_use_ability_on_target_builder_fn:
                return None
            return self.__non_census_injection_use_ability_on_target_builder_fn(target_name) + '\n'
        else:
            if not self.__non_census_injection_use_ability_str:
                return None
            return self.__non_census_injection_use_ability_str + '\n'

    def __get_ability_injection_str(self, ability: IAbility, target_name: Optional[str]) -> str:
        if ability.census.crc:
            return self.__get_census_ability_injection_str(ability.census.crc, target_name)
        else:
            return self.__get_non_census_ability_injection_str(target_name)

    def __get_injector_name(self, player: IPlayer) -> str:
        if self.__is_command:
            injector_name = player.get_command_injector_name()
        else:
            injector_name = player.get_ability_injector_name()
        return injector_name

    def __apply_injections(self, action: IAction, player: IPlayer, injections: Set[str]) -> Tuple[IAction, bool]:
        added_injections = False
        if injections:
            injector_name = self.__get_injector_name(player)
            action = action.inject_command(injector_name=injector_name, injected_command='\n'.join(injections) + '\n', passthrough=True, once=True)
            added_injections = True
        return action, added_injections

    def __get_consume_action(self, player: IPlayer) -> IAction:
        if self.__is_command:
            consume_action = player.get_inputs().special.consume_command_injection
        else:
            consume_action = player.get_inputs().special.consume_ability_injection
        return consume_action

    def __append_consume_action(self, action: IAction, player: IPlayer) -> IAction:
        # append action which invokes the injector actually
        consume_action = self.__get_consume_action(player)
        action = action.append(consume_action)
        return action

    def __create_injections_action(self, action: IAction, player: IPlayer, ability: IAbility, target_name: Optional[str]) -> Tuple[IAction, bool]:
        added_injections = False
        injector_name = self.__get_injector_name(player)
        ability_injection_str = self.__get_ability_injection_str(ability, target_name)
        ability_injection_str_debug = ability_injection_str.strip() if ability_injection_str else ability_injection_str
        logger.debug(f'Preparing injection action for {self.locator}, injector: ({injector_name}, ability_injection_str: {ability_injection_str_debug})')
        if ability_injection_str:
            # remote injections are always one-time. local only if maintained
            single_injection = player.is_remote() or ability.ext.maintained or self.__is_command
            if self.__injection_passthrough_override is None:
                # action, which will be automatically withdrawn, can be blocking
                # also one-time actions should not passthrough to improve chance of casting
                passthrough = not self.__has_action_withdrawer and not single_injection
            else:
                passthrough = self.__injection_passthrough_override
            action = action.inject_command(injector_name=injector_name, injected_command=ability_injection_str, once=single_injection,
                                           passthrough=passthrough, command_id=ability.ext.ability_name, duration=ABILITY_INJECTION_DURATION)
            added_injections = True
        else:
            if ability.ext.has_census:
                log_level = LogLevel.ERROR
            elif self.__non_census_injection_use_ability_str or self.__non_census_injection_use_ability_on_target_builder_fn:
                log_level = LogLevel.DEBUG
            else:
                log_level = LogLevel.INFO
            logger.log(f'No ability_injection_str for {player}\'s {self.locator}, leaving blank', log_level)
        return action, added_injections

    def __add_injections_to_existing_action(self, action: IAction, player: IPlayer) -> IAction:
        new_action = action_factory.new_action()
        new_action, added_injections_p1 = self.__apply_injections(action=new_action, player=player, injections=self.__head_injections)
        if added_injections_p1:
            new_action = self.__append_consume_action(action=new_action, player=player)
        new_action = new_action.append(action)
        new_action, added_injections_p2 = self.__apply_injections(action=new_action, player=player, injections=self.__tail_injections)
        if added_injections_p2:
            new_action = self.__append_consume_action(action=new_action, player=player)
        if added_injections_p1 or added_injections_p2:
            logger.info(f'Added injections to {self.locator}, existing action: {action}, injections: head:{self.__head_injections}, tail:{self.__tail_injections}')
            return new_action
        return action

    def __verify_modifiers(self, ext_data: AbilityExtConsts, census_data: AbilityCensusConsts):
        for (prop, value) in self.__modifiers_set:
            if not hasattr(ext_data, prop) and not hasattr(census_data, prop):
                assert False, (prop, value, ext_data.ability_name)
        for (prop, value) in self.__modifiers_fn:
            if hasattr(ext_data, prop) or not hasattr(census_data, prop):
                assert False, (prop, value, ext_data.ability_name)

    def __apply_modifiers(self, ext_data: AbilityExtConsts, census_data: AbilityCensusConsts):
        self.__verify_modifiers(ext_data, census_data)
        for (prop, value) in self.__modifiers_set:
            if hasattr(ext_data, prop):
                ext_data.__setattr__(prop, value)
            if hasattr(census_data, prop):
                census_data.__setattr__(prop, value)
        for (prop, fn) in self.__modifiers_fn:
            if hasattr(census_data, prop):
                new_value = fn(ext_data, census_data)
                census_data.__setattr__(prop, new_value)

    def __new_ext_data_object(self) -> Optional[AbilityExtConsts]:
        """
            creates new ext data, it can be modified for different players
        """
        return self.locator.get_ext_object().make_copy()

    def __new_census_data_object(self, player: IPlayer, has_census: bool) -> Optional[AbilityCensusConsts]:
        """
            creates new census data, it can be modified for different players
        """
        if has_census:
            assert self.__class_level is not None
            if self.__tier is None:
                orig_census_consts = self.locator.get_census_object_for_player(player)
                if orig_census_consts:
                    self.__tier = AbilityTier(orig_census_consts.tier_int)
                else:
                    # fall-through to a check for none later
                    pass
            else:
                orig_census_consts = self.locator.get_census_object_by_tier(self.__class_level, self.__tier)
            if orig_census_consts is None:
                return None
            # make a copy to allow modifications for different players
            census_consts = orig_census_consts.make_copy()
        else:
            assert isinstance(self.__census_data, AbilityCensusConsts)
            census_consts = AbilityCensusConsts()
            census_consts.set_census_data(self.__census_data)
        return census_consts

    def __parse_census_effects(self, player: IPlayer, census_cache: ICensusBridge, ext_consts: AbilityExtConsts, census_object: AbilityCensusConsts):
        if not PARSE_CENSUS_EFFECTS:
            return
        if not ext_consts.has_census:
            return
        if self.__tier is None:
            logger.warn(f'__parse_census_effects: Ability tier not found for {self.locator}, player {player}')
            return None
        census_data = census_cache.get_ability_census_data_by_tier(self.locator.get_gameclass(), self.__class_level,
                                                                   self.locator.get_canonical_name(), self.__tier)
        AbilityCensusEffectParser.parse_census_effects(ext_consts, census_data, census_object)

    def __resolve_targets(self, player: IPlayer, ext_consts: AbilityExtConsts) -> List[TValidTarget]:
        needs_target = ext_consts.effect_target in [AbilityEffectTarget.Ally, AbilityEffectTarget.GroupMember, AbilityEffectTarget.Any]
        assert not (needs_target and self.__target is None), f'{player.get_player_id()}, {self.locator}, needs_target {needs_target}, target {self.__target}'
        resolved_targets = player.get_player_manager().resolve_targets(self.__target, lambda target_player: target_player.get_server() == player.get_server())
        if resolved_targets and not needs_target:
            logger.warn(f'{self.locator} needs no target, but has resolved target(s)')
        if len(resolved_targets) > 1:
            if self.__action:
                logger.info(f'Ignoring predefined action on multi-target ability {self.locator}, targets: {resolved_targets}')
            self.__action = None
        elif not resolved_targets:
            if needs_target:
                logger.warn(f'No targets resolved for {ext_consts.ability_name}, player {player.get_player_id()}, preset target {self.__target}. Ignore the spell')
                return []
            assert self.__target is None, self.__target
            resolved_targets = [self.__target]
        return resolved_targets

    def __create_action(self, player: IPlayer, ability: IAbility, target_name: Optional[str]) -> IAction:
        action = action_factory.new_action()
        action, added_injections_head = self.__apply_injections(action=action, player=player, injections=self.__head_injections)
        action, added_injections = self.__create_injections_action(action=action, player=player, ability=ability, target_name=target_name)
        action, added_injections_tail = self.__apply_injections(action=action, player=player, injections=self.__tail_injections)
        if added_injections or added_injections_head or added_injections_tail:
            action = self.__append_consume_action(action=action, player=player)
        logger.debug(f'{self.locator} created action: {action}')
        return action

    def __adorn_action(self, action: IAction) -> IAction:
        if self.__pre_action:
            action = self.__pre_action.append(action)
        if self.__post_action:
            action = action.append(self.__post_action)
        return action

    def new_prototyped_action(self, player: IPlayer, ability: IAbility, target_name: Optional[str]) -> IAction:
        action = self.__create_action(player, ability, target_name)
        return self.__adorn_action(action)

    def __build_target_action(self, player: IPlayer, ability: IAbility, resolved_target: TValidTarget) -> IAction:
        if self.__action is None:
            # always creates new action
            target_action = self.__create_action(player=player, ability=ability, target_name=AbilityTarget.get_opt_target_name(resolved_target))
        else:
            # may create new action; in case of multi-target abilities, self.__action must be None anyway, so self.__action wont be reused
            target_action = self.__add_injections_to_existing_action(action=self.__action, player=player)
        target_action = self.__adorn_action(target_action)
        if resolved_target is not None:
            # this delegate will allow to change target for ability prototypes later
            # lack of this delegate will cause assert (from Action default impl) when trying to set target
            prototype_action = PrototypeInjectorAction(self, player=player, ability=ability)
            target_action = prototype_action.set_action(target_action)
        return target_action

    def build_ability(self, player: IPlayer, builder_tools: BuilderTools, ability_factory: IAbilityFactory) -> List[IAbility]:
        ext_consts = self.__new_ext_data_object()
        census_consts = self.__new_census_data_object(player, ext_consts.has_census)
        if not census_consts:
            level = LogLevel.DEBUG if self.__optional else LogLevel.WARN
            logger.log(f'No census data found for {ext_consts.ability_name}, player {player.get_player_id()}. Ignore the spell', level)
            return []
        self.__apply_modifiers(ext_consts, census_consts)
        self.__parse_census_effects(player, builder_tools.census_cache, ext_consts, census_consts)
        resolved_targets = self.__resolve_targets(player, ext_consts)
        abilities_built = list()
        for resolved_target in resolved_targets:
            # factory internally creates a copy of Ext data object to allow modifications
            ability = ability_factory.create_ability(self.locator, player, census_consts, ext_consts)
            if resolved_target:
                ability.set_target(resolved_target)
            target_action = self.__build_target_action(player, ability, resolved_target)
            ability.set_action(target_action)
            if self.__effect_builder:
                ability.set_effect_builder(self.__effect_builder)
            monitors = list(self.__monitors)
            monitors.extend(DefaultMonitorsFactory.create_default_monitors(ability))
            if monitors:
                ability.set_monitors(monitors)
            logger.debug(f'ability built for {player.get_player_id()}: {census_consts.name}, tier {census_consts.tier_int}')
            abilities_built.append(ability)
        if abilities_built:
            shared_vals = abilities_built[0].shared
            if self.__disable_by_default:
                shared_vals.enabled_at = None
            logger.info(f'ability built for {player.get_player_id()}: {census_consts.name}, tier {census_consts.tier_int}, level {census_consts.level}, crc {census_consts.crc}')
        return abilities_built


class AbilityStore:
    def __init__(self, game_class: GameClass, class_level: int):
        self.game_class = game_class
        self.class_level = class_level
        self.__abilities_built: List[IAbility] = list()
        self.__abilities_not_built: List[AbilityBuilder] = list()
        self.__builders: Dict[str, AbilityBuilder] = dict()

    def builder(self, ability_locator: IAbilityLocator) -> AbilityBuilder:
        ability_key = ability_locator.locator_key()
        if ability_key in self.__builders.keys():
            builder = self.__builders[ability_key]
        else:
            assert ability_locator.get_gameclass() is self.game_class, f'{ability_locator} vs {self.game_class}'
            builder = AbilityBuilder(ability_locator)
            self.__builders[ability_key] = builder
        return builder

    def fill_missing_ability_tiers(self, default_tier: AbilityTier):
        for _, builder in self.__builders.items():
            builder.default_tier(default_tier)

    def __build_all(self, player: IPlayer, builder_tools: BuilderTools, ability_factory: IAbilityFactory):
        for builder_key, builder in self.__builders.items():
            if not builder.is_built():
                self.__abilities_not_built.append(builder)
                continue
            builder.class_level(self.class_level)
            try:
                abilities = builder.build_ability(player=player, builder_tools=builder_tools, ability_factory=ability_factory)
            except Exception as e:
                logger.error(f'Error building ability {builder_key} for player {player.get_player_id()}, error {e}')
                raise
            if not abilities:
                # logger.error(f'{player.get_player_id()}: no abilities built for {builder_key}')
                self.__abilities_not_built.append(builder)
                continue
            self.__abilities_built.extend(abilities)

    def __cleanup_builders(self):
        self.__builders = dict()

    def __verify(self, player: IPlayer):
        if self.game_class.name not in ability_collection_classes.keys():
            assert len(self.__abilities_built) == 0
            logger.debug(f'No ability info for {self.game_class.name} class -> No abilities defined for this class')
            return
        collection_class = ability_collection_classes[self.game_class.name]
        generated_ability_ids = [attr for attr in dir(collection_class) if
                                 attr[:2] + attr[-2:] != '____' and not callable(getattr(collection_class, attr))]
        # check if all ability built belong to the generated ability container
        built_ability_ids = {ability.ext.ability_id for ability in self.__abilities_built}
        for ability_id in built_ability_ids:
            if ability_id not in generated_ability_ids:
                logger.error(f'{player.get_player_id()} excess ability {ability_id} in {AbilityStore.__name__} not present in collection {collection_class}')
        # check if all abilities in the generated containers have a builder
        builder_ability_ids = {builder.locator.get_ability_id() for builder in self.__builders.values()}
        no_builder_abilities = {ability_id for ability_id in generated_ability_ids if ability_id not in builder_ability_ids}
        if no_builder_abilities:
            abilities_str = ', '.join(no_builder_abilities)
            logger.warn(f'{player.get_player_id()} / {self.game_class}: no builders for: {abilities_str}')
        # print all unfinalized builders for the information
        unbuilt_ability_ids = {builder.get_ability_id() for builder in self.__abilities_not_built}
        if unbuilt_ability_ids:
            abilities_str = ', '.join(unbuilt_ability_ids)
            logger.warn(f'{player.get_player_id()} / {self.game_class}: incomplete builders for: {abilities_str}')

    def __pop_abilities_from_stores(self) -> List[IAbility]:
        abilities = self.__abilities_built
        self.__abilities_built = []
        self.__abilities_not_built = []
        return abilities

    def build_stored_abilities(self, player: IPlayer, builder_tools: BuilderTools, ability_factory: IAbilityFactory) -> List[IAbility]:
        self.__build_all(player=player, builder_tools=builder_tools, ability_factory=ability_factory)
        self.__verify(player)
        abilities = self.__pop_abilities_from_stores()
        self.__cleanup_builders()
        return abilities
