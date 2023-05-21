import sys

from rka.eq2.master import IRuntime
from rka.eq2.master.game.ability import AbilityTier
from rka.eq2.master.game.player import PlayerStatus


def print_ability_data(runtime: IRuntime):
    print('------ DUMP ABILITY DATA START ------')
    import pyperclip
    clipstr = ''
    abilities = runtime.ability_reg.find_abilities(lambda a: a.player.get_status() >= PlayerStatus.Zoned)
    ability_debug_str = list()
    printed_keys = set()
    for ability in abilities:
        ability.player.get_player_name()
        key = ability.ability_unique_key()
        if key in printed_keys:
            continue
        else:
            printed_keys.add(key)
        debug_str = ability.debug_str()
        ability_debug_str.append(debug_str)
    sorted_ability_debug_str = sorted(ability_debug_str)
    for line in sorted_ability_debug_str:
        clipstr += line + '\n'
        print(line)
    pyperclip.copy(clipstr)
    print('------ DUMP ABILITY DATA END ------')


def print_parser_data(runtime: IRuntime):
    print('------ DUMP PARSER DATA START ------')
    players = runtime.player_mgr.get_players(min_status=PlayerStatus.Online)
    for player in players:
        parser = runtime.parser_mgr.get_parser(player.get_client_id())
        print(f'Dumping parser for player {player} / client ID {player.get_client_id()}')
        for parser_filter in parser.iter_filters():
            print(parser_filter)
    print('------ DUMP PARSER DATA END ------')


def print_player_effects(runtime: IRuntime):
    print('------ DUMP PLAYER EFFECTS START ------')
    players = runtime.player_mgr.get_players(min_status=PlayerStatus.Logged)
    for player in players:
        print(f'Effects for {player}')
        effects = runtime.effects_mgr.get_effects(apply_target=player.as_effect_target())
        for effect in effects:
            print(effect)
    print('------ DUMP PLAYER EFFECTS END ------')


def print_running_spells(runtime: IRuntime):
    print('------ DUMP RUNNING SPELLS START ------')
    players = runtime.player_mgr.get_players(min_status=PlayerStatus.Logged)
    for player in players:
        print(f'Spells for {player}')
        for spell in runtime.ability_reg.find_abilities(lambda a: a.player == player and not a.is_duration_expired()):
            tier_int = spell.census.tier_int
            print(f'{spell}({AbilityTier(tier_int).name})')
    print('------ DUMP RUNNING SPELLS END ------')


def print_mouse_info():
    from rka.components.impl.factories import AutomationFactory
    pos = AutomationFactory.create_automation().get_mouse_pos()
    print(f'mouse position is {pos}', file=sys.stderr)
    from rka.components.impl.factories import CursorCaptureFactory
    fingerprint = CursorCaptureFactory.create_cursor_capture().get_cursor_fingerprint()
    print(f'cursor fingerprint is {fingerprint}', file=sys.stderr)
