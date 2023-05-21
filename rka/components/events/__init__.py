from __future__ import annotations

import importlib
from typing import Dict, Type, FrozenSet, Set, Optional, Any, List, TypeVar, get_origin, get_args

from rka.components.io.log_service import LogService
from rka.log_configs import LOG_EVENTS
from rka.util.util import NameEnum

logger = LogService(LOG_EVENTS)
default_worker_queue_limit = 200


class EventStub:
    __next_id = 1

    @staticmethod
    def generate_next_event_id() -> int:
        event_id = EventStub.__next_id
        EventStub.__next_id += 1
        return event_id

    def __init__(self, event_params: Dict[str, Type]):
        self.event_params = event_params
        self.event_id = EventStub.generate_next_event_id()

    # noinspection PyMethodMayBeStatic
    def get_event_base_class(self) -> Type[Event]:
        return Event


def event(**kwargs) -> EventStub:
    return EventStub(kwargs)


class Event:
    # these fields will be static for each new subclass
    name: str
    value: str
    event_id: int
    param_names: FrozenSet[str]
    _param_types: Dict[str, Type]
    _params_set: Set[str]
    _cached_params: Optional[Dict[str, Any]]

    @classmethod
    def get_param_type(cls: Type[Event], param_name: str) -> Type:
        return cls._param_types[param_name]

    def __init__(self, **kwargs):
        self._params_set: Set[str] = set()
        self._cached_params: Optional[Dict[str, Any]] = None
        for k, v in kwargs.items():
            if k not in self.__class__.__dict__:
                raise AttributeError(f'Excess argument {k}')
            self.__setattr__(k, v)

    def __setattr__(self, key: str, value: Any):
        if key in {'name', 'value', 'event_id', 'param_names'}:
            raise AttributeError(f'{key} cannot be changed')
        if key not in self.__class__.__dict__:
            raise AttributeError(f'{self.name} has no attribute \'{key}\'')
        if key in self.param_names:
            if value is not None:
                t = self._param_types[key]
                origin_t = get_origin(t)
                if origin_t:
                    t = origin_t
                if issubclass(t, NameEnum) and isinstance(value, str):
                    value = t[value]
                if not isinstance(value, t):
                    raise ValueError(f'Expected type {t} for value of "{key}", found {value} ({type(value)})')
            self._params_set.add(key)
            self._cached_params = None
        super().__setattr__(key, value)

    def get_param(self, param_name: str) -> Any:
        if param_name not in self._params_set:
            raise ValueError(f'{param_name} has not been set')
        return self.__getattribute__(param_name)

    def set_param(self, param_name: str, param_value: Any):
        self.__setattr__(param_name, param_value)

    def get_params(self) -> Dict[str, Any]:
        if self._cached_params is None:
            self._cached_params = dict()
            for param_name in self._params_set:
                self._cached_params[param_name] = self.__getattribute__(param_name)
        return self._cached_params.copy()

    def from_params(self, event_params: Dict[str, Any]) -> Event:
        updated_params = self.param_names.intersection(event_params.keys())
        for param_name in updated_params:
            param_value = event_params[param_name]
            self.set_param(param_name, param_value)
        return self

    def get_params_set(self) -> FrozenSet[str]:
        return frozenset(self._params_set)

    def is_param_set(self, param_name: str) -> bool:
        if param_name in self._params_set:
            return True
        if param_name not in self.param_names:
            raise AttributeError(f'{self.name} has no attribute \'{param_name}\'')
        return False

    def equals(self, other_event: Event) -> bool:
        if self.event_id != other_event.event_id:
            return False
        if self._params_set != other_event._params_set:
            return False
        for param_name in self._params_set:
            if self.__getattribute__(param_name) != other_event.__getattribute__(param_name):
                return False
        return True

    def clone(self) -> Event:
        new_event = self.__class__()
        for param_name in self._params_set:
            new_event.__setattr__(param_name, self.get_param(param_name))
        return new_event

    def merge_with(self, other_event: Event) -> Event:
        assert isinstance(other_event, type(self))
        new_event = self.__class__()
        same_params = self._params_set.intersection(other_event._params_set)
        for param_name in same_params:
            v1 = self.__getattribute__(param_name)
            v2 = other_event.__getattribute__(param_name)
            if v1 != v2:
                raise ValueError(f'Cannot merge, conflicting values of {param_name}: {v1} and {v2}')
        for param_name in self._params_set:
            new_event.__setattr__(param_name, self.get_param(param_name))
        for param_name in other_event._params_set:
            new_event.__setattr__(param_name, other_event.get_param(param_name))
        return new_event

    @staticmethod
    def get_event_type_from_name(typename: str) -> Type[Event]:
        try:
            event_type = globals()[typename]
        except KeyError:
            from pydoc import locate
            event_type = locate(typename)
            if not event_type:
                raise
        return event_type

    def __str__(self) -> str:
        attrs = [str(self.event_id)]
        for k, cv in self.__class__.__dict__.items():
            if k in self.param_names:
                if k in self._params_set:
                    v = self.__getattribute__(k)
                    attrs.append(f'{k}={v}')
        return f'{self.value}({", ".join(attrs)})'


EventType = TypeVar('EventType', bound=Event)


class EventsMeta(type):
    __stub_files_built: Set[str] = set()

    @staticmethod
    def __get_full_type_name(some_type: Type) -> str:
        try:
            if not get_origin(some_type):
                # not a generic
                return some_type.__name__
            args = get_args(some_type)
            if not args:
                # not a parametrized generic
                return some_type.__name__
            return f'{some_type.__name__}[{", ".join(map(EventsMeta.__get_full_type_name, args))}]'
        except AttributeError:
            # alias type
            # noinspection PyProtectedMember,PyUnresolvedReferences
            return some_type._name

    @staticmethod
    def __get_unparametrized_type_name(some_type: Type) -> str:
        try:
            return some_type.__name__
        except AttributeError:
            # alias type
            # noinspection PyProtectedMember,PyUnresolvedReferences
            return some_type._name

    @staticmethod
    def __get_parameters_import_types(some_type: Type) -> Set[Type]:
        types = set(get_args(some_type))
        for type_ in types:
            types.update(EventsMeta.__get_parameters_import_types(type_))
        return types

    @staticmethod
    def __save_stub_file(module_name, required_imports: Set[Type], stub_code: List[str], has_fields: bool):
        if module_name == EventsMeta.__module__:
            return
        module = importlib.import_module(module_name)
        stub_file_name = module.__file__.replace('.py', '.pyi')
        if stub_file_name in EventsMeta.__stub_files_built:
            stub_file = open(stub_file_name, 'at')
        else:
            stub_file = open(stub_file_name, 'wt')
        imports_added = False
        if has_fields:
            stub_file.write('from typing import Optional, Type\n')
            imports_added = True
        # add generic parameters to import requirements
        additional_imports = required_imports.copy()
        for required_import in required_imports:
            additional_imports.update(EventsMeta.__get_parameters_import_types(required_import))
        all_required_imports = required_imports.union(additional_imports)
        required_import_list = sorted(all_required_imports, key=lambda t: t.__name__)
        for req_import in required_import_list:
            if req_import.__module__ == 'builtins':
                continue
            import_name = EventsMeta.__get_unparametrized_type_name(req_import)
            stub_file.write(f'from {req_import.__module__} import {import_name}')
            stub_file.write('\n')
            imports_added = True
        if imports_added:
            stub_file.write('\n\n')
        for stub_code_line in stub_code:
            stub_file.write(stub_code_line)
            stub_file.write('\n')
        stub_file.close()
        EventsMeta.__stub_files_built.add(stub_file_name)

    def __new__(mcs, name, bases, dct):
        contained_class_namespace = dict()
        module_name = dct['__module__']
        stub_code = [f'class {name}:']
        required_imports: Set[Type] = set()
        required_imports.add(Event)
        any_fields_exist = False
        event_types: Dict[str, Type] = dict()
        for k, v in dct.items():
            if isinstance(v, EventStub):
                base_class = v.get_event_base_class()
                stub_code.append('\t# noinspection PyPep8Naming')
                stub_code.append(f'\tclass {k}({base_class.__name__}):')
                required_imports.add(base_class)
                event_class_namespace = dict()
                event_name = f'{module_name}.{name}.{k}'
                param_names = frozenset(v.event_params.keys())
                event_class_namespace['name'] = event_name
                event_class_namespace['value'] = k
                event_class_namespace['event_id'] = v.event_id
                event_class_namespace['param_names'] = param_names
                event_class_namespace['_param_types'] = v.event_params
                event_class_namespace['_params_set'] = None
                event_class_namespace['_cached_params'] = None
                fields_exist = False
                args = []
                for field_name, field_type in v.event_params.items():
                    field_type_name = EventsMeta.__get_full_type_name(field_type)
                    stub_code.append(f'\t\t{field_name}: Optional[{field_type_name}]')
                    required_imports.add(field_type)
                    args.append(f'{field_name}: Optional[{field_type_name}] = None')
                    fields_exist = True
                    # just declare the field
                    event_class_namespace[field_name] = None
                if not fields_exist:
                    stub_code.append('\t\tpass')
                else:
                    any_fields_exist = True
                if args:
                    args_str = ', '.join(args)
                    stub_code.append('')
                    stub_code.append('\t\t# noinspection PyMissingConstructor')
                    stub_code.append(f'\t\tdef __init__(self, {args_str}): ...')
                stub_code.append('')
                event_type = type(k, (base_class,), event_class_namespace)
                contained_class_namespace[k] = event_type
                event_types[event_name] = event_type
            else:
                contained_class_namespace[k] = v
        contained_class_namespace['get_by_name'] = lambda p_event_name: event_types[p_event_name]
        contained_class_namespace['contains'] = lambda p_event_name: p_event_name in event_types
        contained_class_namespace['update_stub_file'] = lambda: EventsMeta.__save_stub_file(module_name, required_imports, stub_code, any_fields_exist)
        stub_code.append('\t@staticmethod')
        stub_code.append('\tdef get_by_name(event_name: str) -> Type[Event]: ...')
        stub_code.append('')
        stub_code.append('\t@staticmethod')
        stub_code.append('\tdef contains(event_name: str) -> bool: ...')
        stub_code.append('')
        stub_code.append('\t@staticmethod')
        stub_code.append('\tdef update_stub_file(): ...')
        stub_code.append('')
        inst = type.__new__(mcs, name, bases, contained_class_namespace)
        return inst


class Events(metaclass=EventsMeta):
    def __new__(cls, *args, **kwargs):
        assert False
