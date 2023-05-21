from __future__ import annotations

import importlib
import os
from threading import RLock
from typing import Set, Optional, List, Type, Dict, Generator, Callable, Any

from rka.components.cleanup import Closeable
from rka.components.common_events import CommonEvents
from rka.components.events.event_system import EventSystem
from rka.components.io.log_service import LogService
from rka.log_configs import LOG_RESOURCE_MGT

logger = LogService(LOG_RESOURCE_MGT)


class Resource:
    def __init__(self, bundle_id: str, name: str, filename: str):
        self.bundle_id = bundle_id
        self.resource_name = name
        self.resource_id = f'{bundle_id}.{self.resource_name}'
        self.filename = filename
        self.__content = None

    def set_content(self, factory_cb: Callable):
        if self.__content is None:
            self.__content = factory_cb()

    def get_content(self) -> Any:
        assert self.__content
        return self.__content

    def __str__(self):
        return self.resource_id


class ResourceBundleManager:
    __bundles: Dict[str, ResourceBundle] = dict()
    __lock = RLock()

    @staticmethod
    def add_bundle(bundle: ResourceBundle):
        with ResourceBundleManager.__lock:
            assert bundle.bundle_id() not in ResourceBundleManager.__bundles
            ResourceBundleManager.__bundles[bundle.bundle_id()] = bundle
            bus = EventSystem.get_main_bus()
            if bus:
                bus.post(CommonEvents.RESOURCE_BUNDLE_ADDED(bundle_id=bundle.bundle_id()))

    @staticmethod
    def remove_bundle(bundle: ResourceBundle):
        with ResourceBundleManager.__lock:
            assert bundle.bundle_id() in ResourceBundleManager.__bundles
            del ResourceBundleManager.__bundles[bundle.bundle_id()]
            bus = EventSystem.get_main_bus()
            if bus:
                bus.post(CommonEvents.RESOURCE_BUNDLE_REMOVED(bundle_id=bundle.bundle_id()))

    @staticmethod
    def get_bundle(bundle_id: str) -> ResourceBundle:
        with ResourceBundleManager.__lock:
            return ResourceBundleManager.__bundles[bundle_id]

    @staticmethod
    def iter_bundles() -> Generator[ResourceBundle, None, None]:
        with ResourceBundleManager.__lock:
            for bundle in ResourceBundleManager.__bundles.values():
                yield bundle


class ResourceBundle(Closeable):
    def __init__(self, _file_: str, included_extensions: Optional[str] = None):
        Closeable.__init__(self, explicit_close=False)
        self.__bundle_id = f'{self.__module__}.{self.__class__.__name__}'
        self.__bundle_location = f'{os.path.dirname(os.path.realpath(_file_))}'
        self.__resources: Dict[str, Resource] = dict()
        dir_entries = os.listdir(self.__bundle_location)
        filenames = [dir_entry for dir_entry in dir_entries if os.path.isfile(os.path.join(self.__bundle_location, dir_entry))]
        for filename in filenames:
            filepath = os.path.join(self.__bundle_location, filename)
            filename_upper = filename.upper()
            included = True
            if included_extensions:
                included = False
                for extension in included_extensions.split(';,'):
                    extension_upper = extension.upper()
                    if filename_upper.endswith(extension_upper):
                        included = True
                        break
                    if included:
                        break
            if not included:
                continue
            # some extesions are excluded
            excluded = False
            for extension in ['.py', '.pyi']:
                extension_upper = extension.upper()
                if filename_upper.endswith(extension_upper):
                    excluded = True
                    break
            if excluded:
                continue
            resource_name = filename_upper[:filename_upper.rindex('.')]
            self.__resources[resource_name] = Resource(self.__bundle_id, resource_name, filepath)
        ResourceBundleManager.add_bundle(self)

    def __getattr__(self, item) -> Resource:
        if item not in self.__resources:
            raise ValueError(item)
        return self.__resources[item]

    def __getitem__(self, item) -> Resource:
        if isinstance(item, str) and len(item) > len(self.__bundle_id):
            if item.startswith(self.__bundle_id):
                item = item[len(self.__bundle_id) + 1:]
        return self.__resources[item]

    def __contains__(self, item) -> bool:
        return item in self.__resources

    def bundle_id(self) -> str:
        return self.__bundle_id

    def bundle_name(self) -> str:
        return self.__class__.__name__

    def list_resources(self) -> List[Resource]:
        return list(self.__resources.values())

    def close(self):
        Closeable.close(self)
        ResourceBundleManager.remove_bundle(self)

    __stub_files_built: Set[str] = set()

    @staticmethod
    def __update_stub_file(module_name, required_imports: Set[Type], stub_code: List[str]):
        if module_name == ResourceBundle.__module__:
            return
        module = importlib.import_module(module_name)
        stub_file_name = module.__file__.replace('.py', '.pyi')
        if stub_file_name in ResourceBundle.__stub_files_built:
            stub_file = open(stub_file_name, 'at')
        else:
            stub_file = open(stub_file_name, 'wt')
        imports_added = False
        required_import_list = sorted(required_imports, key=lambda t: t.__name__)
        for req_import in required_import_list:
            if req_import.__module__ == 'builtins':
                continue
            stub_file.write(f'from {req_import.__module__} import {req_import.__name__}')
            stub_file.write('\n')
            imports_added = True
        if imports_added:
            stub_file.write('\n\n')
        for stub_code_line in stub_code:
            stub_file.write(stub_code_line)
            stub_file.write('\n')
        stub_file.close()
        ResourceBundle.__stub_files_built.add(stub_file_name)

    def update_stub_file(self):
        stub_code = list()
        required_imports: Set[Type] = set()
        required_imports.add(Resource)
        required_imports.add(ResourceBundle)
        stub_code.append(f'class {self.__class__.__name__} ({ResourceBundle.__name__}):')
        stub_code.append('\tdef __init__(self, *args, **kwargs):')
        stub_code.append(f'\t\t{ResourceBundle.__name__}.__init__(self, *args, **kwargs)')
        stub_code.append('')
        for resource_name in sorted(self.__resources.keys()):
            resource = self.__resources[resource_name]
            stub_code.append(f'\t{resource.resource_name}: {Resource.__name__} = None')
        self.__update_stub_file(self.__class__.__module__, required_imports, stub_code)
