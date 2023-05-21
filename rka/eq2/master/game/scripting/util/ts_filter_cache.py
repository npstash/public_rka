import json
from typing import Optional

from rka.eq2.datafiles import cached_ts_recipe_filters

__cached_filter_mappings = dict()


def get_cached_recipe_filter(item_name: str) -> Optional[str]:
    __load_cached_filter_mappings()
    if item_name not in __cached_filter_mappings:
        return None
    return __cached_filter_mappings[item_name]


def save_recipe_filter(item_name: str, filter_name: str):
    __cached_filter_mappings[item_name] = filter_name
    __save_cached_filter_mappings()


def __load_cached_filter_mappings():
    fname = cached_ts_recipe_filters()
    # noinspection PyBroadException
    try:
        with open(fname, 'r') as f:
            cached_spellchecks = json.load(f)
            global __cached_filter_mappings
            __cached_filter_mappings.update(cached_spellchecks)
    except Exception as _e:
        pass


def __save_cached_filter_mappings():
    fname = cached_ts_recipe_filters()
    with open(f'{fname}', 'wt') as f:
        global __cached_filter_mappings
        json.dump(__cached_filter_mappings, f, indent=2)


