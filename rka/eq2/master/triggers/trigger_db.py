from __future__ import annotations

import json
import os
import shutil
import traceback
from json import JSONDecodeError
from json.encoder import JSONEncoder
from threading import RLock
from typing import Dict, List, Iterable, Optional, Set, Union, Any

from rka.eq2.datafiles import saved_triggers_filename, get_all_saved_trigger_zone_keys
from rka.eq2.master import IRuntime
from rka.eq2.master.game import get_canonical_zone_name, get_canonical_zone_name_with_tier
from rka.eq2.master.serialize import EventParamSerializer
from rka.eq2.master.triggers import logger
from rka.eq2.master.triggers.trigger_spec import TriggerSpec


class TriggerDatabase:
    def __init__(self, runtime: IRuntime):
        self.__runtime = runtime
        self.__serializers = EventParamSerializer(runtime)
        self.__lock = RLock()
        self.__loaded_trigger_specs: Dict[str, Dict[str, TriggerSpec]] = dict()

    @staticmethod
    def __get_category_key(category: str) -> str:
        return get_canonical_zone_name(category)

    @staticmethod
    def __get_all_filenames(category: str) -> Set[str]:
        canonical = get_canonical_zone_name(category)
        canonical_with_tier = get_canonical_zone_name_with_tier(category)
        return {saved_triggers_filename(canonical), saved_triggers_filename(canonical_with_tier)}

    @staticmethod
    def __get_filename(category: str) -> str:
        canonical_with_tier = get_canonical_zone_name_with_tier(category)
        return saved_triggers_filename(canonical_with_tier)

    @staticmethod
    def __get_trigger_category_key(trigger_spec: TriggerSpec) -> str:
        category = trigger_spec.zone if trigger_spec.zone else TriggerSpec.DEFAULT_CATEGORY
        return TriggerDatabase.__get_category_key(category)

    def __cache_one_trigger_spec(self, trigger_spec: TriggerSpec):
        category_key = TriggerDatabase.__get_trigger_category_key(trigger_spec)
        self.__loaded_trigger_specs.setdefault(category_key, dict())[trigger_spec.key()] = trigger_spec

    def __json_to_object(self, obj) -> Union[TriggerSpec, Any]:
        if isinstance(obj, dict):
            for k, v in obj.items():
                obj[k] = self.__json_to_object(v)
        if isinstance(obj, dict):
            trigger_spec = TriggerSpec.from_dict(obj)
            if trigger_spec:
                return trigger_spec
        return self.__serializers.json_to_object(obj)

    def __object_to_json(self, **kwargs) -> JSONEncoder:
        return EventParamSerializer(self.__runtime, **kwargs)

    def __load_trigger_specs(self, category: str):
        filenames = TriggerDatabase.__get_all_filenames(category)
        category_key = TriggerDatabase.__get_category_key(category)
        loaded_specs: List[TriggerSpec] = list()
        for filename in filenames:
            try:
                with open(filename, 'r') as f:
                    deserialized_specs = json.load(f, object_hook=self.__json_to_object)
                    loaded_specs.extend(deserialized_specs)
            except FileNotFoundError:
                logger.info(f'triggers file not found: {filename}')
            except IOError as e:
                logger.warn(f'load error: {e}')
                traceback.print_exc()
            except JSONDecodeError as e:
                logger.warn(f'json error: {e}')
                traceback.print_exc()
        with self.__lock:
            self.__loaded_trigger_specs[category_key] = dict()
            for trigger_spec in loaded_specs:
                self.__cache_one_trigger_spec(trigger_spec)

    def __save_trigger_specs(self, category_key: Optional[str]):
        if category_key is None:
            category_keys = list(self.__loaded_trigger_specs.keys())
        else:
            category_keys = [category_key]
        triggers_by_category_key: Dict[str, List[TriggerSpec]] = dict()
        with self.__lock:
            for category_key in category_keys:
                trigger_spec_dict = self.__loaded_trigger_specs[category_key]
                triggers_by_category_key[category_key] = list(trigger_spec_dict.values())
        for category_key, trigger_specs in triggers_by_category_key.items():
            if not trigger_specs:
                continue
            filename = TriggerDatabase.__get_filename(category_key)
            logger.info(f'saving triggers to {filename}')
            sorted_specs = sorted(trigger_specs, key=lambda ts: ts.key())
            try:
                with open(f'{filename}.new', 'wt') as f:
                    all_specs = [trigger_spec.__dict__ for trigger_spec in sorted_specs]
                    # noinspection PyTypeChecker
                    json.dump(all_specs, f, ensure_ascii=True, indent=2, cls=self.__object_to_json)
            except IOError as e:
                logger.error(f'store error {e}')
                continue
            shutil.copy(f'{filename}.new', f'{filename}')
            os.remove(f'{filename}.new')

    def empty_cached_triggers(self):
        with self.__lock:
            self.__loaded_trigger_specs.clear()

    def store_trigger_spec(self, trigger_spec: TriggerSpec):
        trigger_key = trigger_spec.key()
        category = trigger_spec.zone if trigger_spec.zone else TriggerSpec.DEFAULT_CATEGORY
        category_key = TriggerDatabase.__get_category_key(category)
        logger.debug(f'adding trigger: {trigger_key} in {category_key}')
        with self.__lock:
            if category_key not in self.__loaded_trigger_specs:
                self.__load_trigger_specs(category)
            if trigger_key in self.__loaded_trigger_specs[category_key]:
                logger.info(f'overwriting trigger in DB: {trigger_key}')
            self.__cache_one_trigger_spec(trigger_spec)
            self.__save_trigger_specs(category_key)

    def iter_trigger_specs(self, category: Optional[str]) -> Iterable[TriggerSpec]:
        category = category if category else TriggerSpec.DEFAULT_CATEGORY
        category_key = TriggerDatabase.__get_category_key(category)
        with self.__lock:
            if category_key not in self.__loaded_trigger_specs:
                self.__load_trigger_specs(category)
            for trigger_spec in self.__loaded_trigger_specs[category_key].values():
                yield trigger_spec

    def get_all_known_zone_names(self) -> List[str]:
        known_zone_names = set()
        all_zone_categories = get_all_saved_trigger_zone_keys()
        with self.__lock:
            for category_key in all_zone_categories:
                if category_key == TriggerSpec.DEFAULT_CATEGORY:
                    continue
                if category_key not in self.__loaded_trigger_specs:
                    self.__load_trigger_specs(category_key)
                for trigger_spec in self.__loaded_trigger_specs[category_key].values():
                    assert trigger_spec.zone, trigger_spec.short_str()
                    known_zone_names.add(trigger_spec.zone)
        return list(known_zone_names)
