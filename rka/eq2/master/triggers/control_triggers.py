from rka.components.events.event_system import EventSystem
from rka.eq2.master import IRuntime
from rka.eq2.master.game import get_unknown_zone
from rka.eq2.master.game.events.chat import ChatEvents
from rka.eq2.master.game.events.player_info import PlayerInfoEvents
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.location import Location
from rka.eq2.master.game.player import PlayerStatus, TellType
from rka.eq2.master.triggers import logger, ITrigger
from rka.eq2.master.triggers.trigger_factory import PlayerTriggerFactory
from rka.eq2.master.triggers.trigger_util import TriggerUtil
from rka.eq2.parsing.parsing_util import ANY_PLAYER_G, ANY_PLAYER_INCL_YOU_G, ANY_PLAYER_INCL_SELF_G, SELF, YOU
from rka.eq2.shared import ClientFlags
from rka.eq2.shared.client_events import ClientEvents


class ControlTriggers(PlayerTriggerFactory):
    def __init__(self, runtime: IRuntime, player: IPlayer):
        PlayerTriggerFactory.__init__(self, runtime, player)

    def local_trigger__player_found_in_zone(self) -> ITrigger:
        runtime = self.get_runtime()
        remote_player_names = runtime.player_mgr.get_player_names(and_flags=ClientFlags.Remote, min_status=PlayerStatus.Offline)

        def action(event: ClientEvents.PARSER_MATCH):
            player_name = event.match().group(2)
            runtime.zonestate.add_player_in_zone(player_name)
            if player_name in remote_player_names:
                runtime.playerstate.notify_player_zoned_to_main(player_name)
            runtime.current_dps.recheck_combatant_type(player_name)

        trigger = self.new_trigger()
        trigger.add_parser_events(fr'\[(Anonymous|\d\d?\d? [A-Za-z]+)\] ({ANY_PLAYER_G}).*')
        trigger.add_action(action)
        return trigger

    def local_trigger__player_found_in_group(self) -> ITrigger:
        def action(event: ClientEvents.PARSER_MATCH):
            player_name = event.match().group(1)
            self.get_runtime().zonestate.player_found_in_main_group_with_who(player_name)

        trigger = self.new_trigger()
        trigger.add_parser_events(fr'({ANY_PLAYER_G}) Lvl \d+ .*')
        trigger.add_action(action)
        return trigger

    def local_trigger__player_found_in_raid(self) -> ITrigger:
        def action(event: ClientEvents.PARSER_MATCH):
            player_name = event.match().group(1)
            self.get_runtime().zonestate.player_found_in_raid_with_who(player_name)

        trigger = self.new_trigger()
        trigger.add_parser_events(fr'\[\d+ [A-Za-z]+\] ({ANY_PLAYER_G}) .*')
        trigger.add_action(action)
        return trigger

    def local_trigger__local_player_changed_zone(self) -> ITrigger:
        def action(event: ClientEvents.PARSER_MATCH):
            zone_name = event.match().group(1)
            self.get_runtime().playerstate.notify_main_player_zoned(zone_name)

        trigger = self.new_trigger()
        trigger.add_parser_events(r'You have entered (.+)\.')
        # allow resetting zone triggers using the /who command, useful in case of problems
        trigger.add_parser_events(r'/who search results for (.+):')
        trigger.add_action(action)
        return trigger

    def remote_trigger__remote_player_changed_zone(self) -> ITrigger:
        def action(event: ClientEvents.PARSER_MATCH):
            zone = event.match().group(1)
            self.get_runtime().playerstate.notify_player_zoned(self.get_player(), zone)

        trigger = self.new_trigger()
        trigger.add_parser_events(r'You have entered (.+)\.')
        trigger.add_parser_events(r'/who search results for (.+):')
        trigger.add_action(action)
        return trigger

    def remote_trigger__commission_offered(self) -> ITrigger:
        def action(event: ClientEvents.PARSER_MATCH):
            player_name = event.match().group(1)
            item_name = event.match().group(2)
            is_my = self.get_runtime().player_mgr.get_player_by_name(player_name) is not None
            event = PlayerInfoEvents.COMMISSION_OFFERED(crafter_name=player_name, crafter_is_my_player=is_my, offered_player=self.get_player(), item_name=item_name)
            EventSystem.get_main_bus().post(event)

        trigger = self.new_trigger()
        trigger.add_parser_events(rf'({ANY_PLAYER_G}) has offered to craft (.*) with your materials\.')
        trigger.add_action(action)
        return trigger

    def trigger__friend_logged(self) -> ITrigger:
        def action(event: ClientEvents.PARSER_MATCH):
            match = event.match()
            player_name = match.group(1)
            login_action = match.group(2)
            EventSystem.get_main_bus().call(PlayerInfoEvents.FRIEND_LOGGED(friend_name=player_name, login=login_action == 'in'))

        trigger = self.new_trigger()
        trigger.add_parser_events(fr'Friend: ({ANY_PLAYER_G}) has logged (in|out)')
        trigger.add_action(action)
        return trigger

    def trigger__player_died(self) -> ITrigger:
        def action(_event: ClientEvents.PARSER_MATCH):
            self.get_player().set_alive(False)

        trigger = self.new_trigger()
        trigger.add_parser_events(r'You cannot cast a spell while dead\.')
        trigger.add_parser_events(r'You cannot perform an art while dead\.')
        trigger.add_parser_events(r'Alas, you have died from pain and suffering\.')
        trigger.add_action(action)
        return trigger

    def trigger__player_revived(self) -> ITrigger:
        def action(_event: ClientEvents.PARSER_MATCH):
            player = self.get_player()
            if player.is_alive():
                logger.info(f'player {player} revived or deathsaved')
            player.set_alive(True)

        trigger = self.new_trigger()
        trigger.add_parser_events(r'You regain consciousness!')
        trigger.add_action(action)
        return trigger

    def local_trigger__player_joined_group(self) -> ITrigger:
        def action(event: ClientEvents.PARSER_MATCH):
            player_name = event.match().group(1)
            if player_name in YOU.split('|'):
                player_name = self.get_player().get_player_name()
            player = self.get_runtime().player_mgr.get_player_by_name(player_name)
            event = PlayerInfoEvents.PLAYER_JOINED_GROUP(player_name=player_name, player=player, my_player=player is not None)
            EventSystem.get_main_bus().call(event)

        trigger = self.new_trigger()
        trigger.add_parser_events(fr'({ANY_PLAYER_INCL_YOU_G}) ha(?:s|ve) joined the group\.')
        trigger.add_parser_events(fr'You form a group with ({ANY_PLAYER_G})\.')
        trigger.add_action(action)
        return trigger

    def local_trigger__player_left_group(self) -> ITrigger:
        def action(event: ClientEvents.PARSER_MATCH):
            match = event.match()
            player_name = match.group(1)
            if player_name in YOU.split('|'):
                player_name = self.get_player().get_player_name()
            player = self.get_runtime().player_mgr.get_player_by_name(player_name)
            event = PlayerInfoEvents.PLAYER_LEFT_GROUP(player_name=player_name, player=player, my_player=player is not None)
            EventSystem.get_main_bus().call(event)

        trigger = self.new_trigger()
        trigger.add_parser_events(fr'({ANY_PLAYER_INCL_YOU_G})(?: have)? left the group\.')
        trigger.add_action(action)
        return trigger

    def local_trigger__group_disbanded(self) -> ITrigger:
        def action(_event: ClientEvents.PARSER_MATCH):
            EventSystem.get_main_bus().call(PlayerInfoEvents.PLAYER_GROUP_DISBANDED(main_player=self.get_player()))

        trigger = self.new_trigger()
        trigger.add_parser_events(fr'The group has disbanded\.')
        trigger.add_action(action)
        return trigger

    def local_trigger__player_linkdead(self) -> ITrigger:
        def action(event: ClientEvents.PARSER_MATCH):
            player_name = event.match().group(1)
            player = self.get_runtime().player_mgr.get_player_by_name(player_name)
            assert player, player_name
            event = PlayerInfoEvents.PLAYER_LINKDEAD(player=player)
            EventSystem.get_main_bus().call(event)

        trigger = self.new_trigger()
        remote_players = self.get_runtime().player_mgr.get_players(and_flags=ClientFlags.Remote, min_status=PlayerStatus.Offline)
        remote_player_names = TriggerUtil.regex_for_player_names(remote_players)
        trigger.add_parser_events(fr'({remote_player_names}) has gone linkdead')
        trigger.add_action(action)
        return trigger

    def local_trigger__act_trigger_found(self) -> ITrigger:
        def action(event: ChatEvents.PLAYER_TELL):
            event = ChatEvents.ACT_TRIGGER_FOUND(actxml=event.tell, from_player_name=event.from_player_name, to_player=event.to_player)
            EventSystem.get_main_bus().call(event)

        trigger = self.new_trigger()
        trigger.add_bus_event(ChatEvents.PLAYER_TELL(to_local=True), filter_cb=lambda event: event.tell.startswith('<Trigger'))
        trigger.add_action(action)
        return trigger

    def trigger__colored_emotes(self) -> ITrigger:
        def action(event: ClientEvents.PARSER_MATCH):
            emote = event.matched_text
            # event is generated from zonestate
            self.get_runtime().zonestate.add_emote(self.get_player(), emote)

        trigger = self.new_trigger()
        trigger.add_parser_events(rf'{TriggerUtil.regex_for_any_combatant_anpc_g1()} .*')
        trigger.add_parser_events(r'\\#[0-9A-Fa-f]{6}.*')
        trigger.add_action(action)
        return trigger

    def trigger__item_received(self) -> ITrigger:
        def action(event: ClientEvents.PARSER_MATCH):
            item = event.match().group(1)
            container = event.match().group(2)
            logger.info(f'{self.get_player()} received an item: {item}')
            event = PlayerInfoEvents.ITEM_RECEIVED(player=self.get_player(), item_name=item, container=container)
            # post, not call - possibly many items one after another, dont block the bus
            EventSystem.get_main_bus().post(event)

        trigger = self.new_trigger()
        trigger.add_parser_events(r'(?:You (?:acquire|receive|loot|buy)) (?:\d+ )?\\aITEM -?\d+ -?\d+:(.*)\\/a(?: from ([^.]+))?.*')
        trigger.add_action(action)
        return trigger

    def trigger__item_found_in_inventory(self) -> ITrigger:
        def action(event: ClientEvents.PARSER_MATCH):
            item = event.match().group(1)
            bag = int(event.match().group(2))
            slot = int(event.match().group(3))
            logger.info(f'{self.get_player()} found an item: {item} in bag {bag}, slot {slot}')
            event = PlayerInfoEvents.ITEM_FOUND_IN_INVENTORY(player=self.get_player(), item_name=item, bag=bag, slot=slot)
            # post, not call - possibly many items one after another, dont block the bus
            EventSystem.get_main_bus().post(event)

        trigger = self.new_trigger()
        trigger.add_parser_events(r'Found (?:\d+ )?\\aITEM -?\d+ -?\d+:(.*)\\/a in inventory bag (\d+), slot (\d+)\.')
        trigger.add_action(action)
        return trigger

    def trigger__location(self) -> ITrigger:
        def action(event: ClientEvents.PARSER_MATCH):
            match = event.match()
            loc_x = float(match.group(1).replace(',', ''))
            loc_y = float(match.group(2).replace(',', ''))
            loc_z = float(match.group(3).replace(',', ''))
            angle = float(match.group(4).replace(',', ''))
            location = Location(x=loc_x, y=loc_y, z=loc_z, axz=angle)
            logger.info(f'{self.get_player()} location is : {location}')
            event = PlayerInfoEvents.LOCATION(player=self.get_player(), location=location)
            EventSystem.get_main_bus().call(event)

        trigger = self.new_trigger()
        coord_re = r'-?[\d,]+\.\d+'
        location_re = rf'Your location is ({coord_re}), ({coord_re}), ({coord_re})\.  Your orientation is ({coord_re}), {coord_re}, {coord_re}'
        trigger.add_parser_events(location_re)
        trigger.add_action(action)
        return trigger

    def trigger__autofollow_broken(self) -> ITrigger:
        def action(event: ClientEvents.PARSER_MATCH):
            match = event.match()
            followed_player_name = match.group(1)
            new_event = PlayerInfoEvents.AUTOFOLLOW_BROKEN(player=self.get_player(), followed_player_name=followed_player_name)
            EventSystem.get_main_bus().call(new_event)

        trigger = self.new_trigger()
        trigger.add_parser_events(fr'({ANY_PLAYER_G}) is too far away\.  You are no longer following {ANY_PLAYER_G}\.')
        trigger.add_action(action)
        return trigger

    def trigger__cannot_autofollow(self) -> ITrigger:
        def action(_event: ClientEvents.PARSER_MATCH):
            new_event = PlayerInfoEvents.AUTOFOLLOW_IMPOSSIBLE(player=self.get_player())
            EventSystem.get_main_bus().call(new_event)

        trigger = self.new_trigger()
        trigger.add_parser_events(r'Cannot follow\.  You are too far away\.')
        trigger.add_action(action)
        return trigger

    def local_trigger__cannot_accept_quest(self) -> ITrigger:
        def action(event: ClientEvents.PARSER_MATCH):
            player_name = event.match().group(1)
            player = self.get_runtime().player_mgr.get_player_by_name(player_name)
            assert player, player_name
            new_event = PlayerInfoEvents.QUEST_OFFERED(player=player, accepted=False, failed=True)
            EventSystem.get_main_bus().call(new_event)

        trigger = self.new_trigger()
        remote_players = self.get_runtime().player_mgr.get_players(and_flags=ClientFlags.Remote, min_status=PlayerStatus.Offline)
        remote_player_names = TriggerUtil.regex_for_player_names(remote_players)
        trigger.add_parser_events(fr'({remote_player_names}) is busy and cannot yet be offered a Quest\.')
        trigger.add_action(action)
        return trigger

    def trigger__camping(self) -> ITrigger:
        def action(_event: ClientEvents.PARSER_MATCH):
            unknown_zone = get_unknown_zone(self.get_player().get_player_name())
            self.get_runtime().playerstate.notify_player_zoned(self.get_player(), unknown_zone)
            self.get_player().set_status(PlayerStatus.Online)

        trigger = self.new_trigger()
        trigger.add_parser_events(r'It will take about 5 more seconds to prepare your camp\.')
        trigger.add_action(action)
        return trigger

    def trigger__player_tell(self) -> ITrigger:
        def action(event: ClientEvents.PARSER_MATCH):
            match = event.match()
            teller_is_you = False
            if match.group(2) is not None:
                # You -> use owning player's name instead
                teller_name = self.get_player().get_player_name()
                teller_is_you = True
            else:
                teller_name = match.group(1)
            tell_verb = match.group(3)
            tell_target_name = match.group(4)
            channel_name = match.group(5)
            message = match.group(6)
            tell_type = None
            if tell_verb.startswith('shout'):
                tell_type = TellType.shout
            elif tell_verb.startswith('auction'):
                tell_type = TellType.auction
            elif tell_verb.startswith('say') and tell_target_name is None:
                tell_type = TellType.say
            elif tell_verb.startswith('tell') and channel_name == 'General':
                tell_type = TellType.general
            elif tell_verb.startswith('tell') and channel_name == 'LFG':
                tell_type = TellType.lfg
            elif tell_verb.startswith('tell') and channel_name is not None:
                tell_type = TellType.custom
            elif tell_verb.startswith('tell') and tell_target_name == 'you':
                tell_type = TellType.tell
            elif tell_target_name == 'to the raid party':
                tell_type = TellType.raid
            elif tell_target_name == 'to the group':
                tell_type = TellType.group
            elif tell_target_name == 'to the guild':
                tell_type = TellType.guild
            elif tell_target_name == 'out of character':
                tell_type = TellType.ooc
            if not tell_type:
                logger.warn(f'Unknown tell type {tell_verb} from {teller_name}: {message}')
                tell_type = TellType.unknown
            logger.detail(f'{teller_name} {tell_type}: {message}')
            event = ChatEvents.PLAYER_TELL(from_player_name=teller_name, tell_type=tell_type, teller_is_you=teller_is_you,
                                           channel_name=channel_name, tell=message,
                                           to_player=self.get_player(), to_player_name=self.get_player().get_player_name(),
                                           to_local=self.get_player().is_local())
            EventSystem.get_main_bus().call(event)

        trigger = self.new_trigger()
        # https://regex101.com/r/2a4IlO/1
        rgx_teller_name = rf'(?:\\aPC -?\d+ ({ANY_PLAYER_G}):\1\\/a|(You))'
        # say/says - include own messages, except tell - do not send events for own outgoing tells
        rgx_tell_verb = r'(says?|tells|shouts?|auctions?)'
        rgx_tell_target_name = r'(to the raid party|to the group|to the guild|you|(\w+)(?: \(\d\))?|out of character)'
        rgx_message = r'\"(.*)\"'
        rgx_pattern = fr'{rgx_teller_name} {rgx_tell_verb}(?: {rgx_tell_target_name})?, {rgx_message}'
        trigger.add_parser_events(rgx_pattern)
        trigger.add_action(action)
        return trigger

    def local_trigger__points_at(self) -> ITrigger:
        def action(event: ClientEvents.PARSER_MATCH):
            pointing_player_name = event.match().group(1)
            pointing_player = self.get_runtime().player_mgr.get_player_by_name(pointing_player_name)
            if not pointing_player or not pointing_player_name:
                logger.error(f'pointing_player_name failed with {pointing_player_name}: {pointing_player}')
                return
            pointed_player_name = event.match().group(2)
            if pointed_player_name == '%v':
                logger.warn(f'pointed_player_name failed with {pointed_player_name}')
                return
            if not pointed_player_name or pointed_player_name in SELF.split('|'):
                pointed_player_name = pointing_player_name
            pointed_player = self.get_runtime().player_mgr.get_player_by_name(pointed_player_name)
            new_event = ChatEvents.POINT_AT_PLAYER(pointing_player=pointing_player, pointed_player_name=pointed_player_name, pointed_player=pointed_player)
            EventSystem.get_main_bus().call(new_event)

        trigger = self.new_trigger()
        remote_players = self.get_runtime().player_mgr.get_players(and_flags=ClientFlags.Local, min_status=PlayerStatus.Offline)
        remote_player_names = TriggerUtil.regex_for_player_names(remote_players)
        trigger.add_parser_events(fr'({remote_player_names}) points(?: at ({ANY_PLAYER_INCL_SELF_G}))?.')
        trigger.add_action(action)
        return trigger
