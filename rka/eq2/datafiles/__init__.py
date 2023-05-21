import os
from os.path import isfile, join
from typing import List

DATAFILES_LOCATION = f'{os.path.dirname(os.path.realpath(__file__))}'


def cached_ts_spellchecks_filepath() -> str:
    return os.path.join(DATAFILES_LOCATION, 'cached_ts_spellchecks.json')


def cached_ts_recipe_filters() -> str:
    return os.path.join(DATAFILES_LOCATION, 'cached_ts_recipe_filters.json')


def ability_ext_data_filepath():
    return os.path.join(DATAFILES_LOCATION, 'abilities.xlsx')


def ability_saved_shared_data_filepath():
    return os.path.join(DATAFILES_LOCATION, 'saved_ability_vars.json')


def zone_map_filename(zone_name: str):
    return os.path.join(DATAFILES_LOCATION, 'maps', f'{zone_name}.txt')


def saved_triggers_filename(zone_name: str):
    return os.path.join(DATAFILES_LOCATION, 'triggers', f'{zone_name}.json')


def get_all_saved_trigger_zone_keys() -> List[str]:
    directory = os.path.join(DATAFILES_LOCATION, 'triggers')
    files = [f.replace('.json', '') for f in os.listdir(directory) if isfile(join(directory, f)) and f.endswith('.json')]
    return files


def saved_formations_filename(zone_name: str):
    return os.path.join(DATAFILES_LOCATION, 'formations', f'{zone_name}.json')


def saved_detriments_filename(zone_name: str):
    return os.path.join(DATAFILES_LOCATION, 'detriments', f'{zone_name}.json')
