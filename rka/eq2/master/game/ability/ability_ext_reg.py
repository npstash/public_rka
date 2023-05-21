from typing import Dict, List, Any

import xlrd

from rka.components.cleanup import Closeable
from rka.eq2.datafiles import ability_ext_data_filepath
from rka.eq2.master.game.ability import generated_ability_classes_filepath
from rka.eq2.master.game.ability.ability_data import AbilityExtConsts
from rka.eq2.master.game.gameclass import GameClass, GameClasses


class AbilityExtConstsRegistry(Closeable):
    def __init__(self):
        Closeable.__init__(self, explicit_close=False)
        self.__ability_properties: List[str] = list()
        self.__default_values: Dict[str, Any] = dict()
        self.__ability_ext_data_reg: Dict[str, Dict[str, Dict[str, Any]]] = dict()
        self.__ability_ext_consts_reg: Dict[str, AbilityExtConsts] = dict()
        self.__ability_filepath = ability_ext_data_filepath()
        self.__generated_ability_filepath = generated_ability_classes_filepath()
        self.__load_ext_data()

    def __load_ext_data(self):
        book = xlrd.open_workbook(rf'{self.__ability_filepath}')
        ability_sheet = book.sheet_by_name('abilities')
        self.__ability_properties = list(filter(lambda head: head != '', ability_sheet.row_values(0)))
        for row_index, row in enumerate(ability_sheet.get_rows()):
            if row_index == 0:
                continue
            if row_index == 1:
                assert row[row_index].value == ''
                for column_index, header in enumerate(self.__ability_properties):
                    value = row[column_index].value
                    self.__default_values[header] = value
                continue
            ability_row: Dict[str, Any] = dict()
            for column_index, header in enumerate(self.__ability_properties):
                value = row[column_index].value
                ability_row[header] = value
            classname = ability_row['classname']
            if classname == '':
                continue
            ability_id = ability_row['ability_id']
            if classname not in self.__ability_ext_data_reg.keys():
                self.__ability_ext_data_reg[classname] = dict()
            self.__ability_ext_data_reg[classname][ability_id] = ability_row

    def generate_ability_ext_code(self):
        from rka.eq2.master.game.ability.ability_locator import AbilityLocatorFactory
        f = open(f'{self.__generated_ability_filepath}', 'wt')
        f.writelines(f'from {GameClasses.__module__} import {GameClasses.__name__}\n')
        f.writelines(f'from {AbilityLocatorFactory.__module__} import {AbilityLocatorFactory.__name__}\n')
        for classname in self.__ability_ext_data_reg.keys():
            f.writelines('\n\n')
            f.writelines(f'class {classname}Abilities:\n')
            for ability_id in self.__ability_ext_data_reg[classname].keys():
                ext_consts = self.get_ability_ext_object(GameClasses.get_class_by_name(classname), ability_id)
                ability_name = ext_consts.ability_name.replace('\'', '\\\'')
                ability_shared_name = ext_consts.shared_name.replace('\'', '\\\'')
                factory_method = f'{AbilityLocatorFactory.__name__}.{AbilityLocatorFactory.create.__name__}'
                arguments = f'{GameClasses.__name__}.{classname}, \'{ability_id}\', \'{ability_name}\', \'{ability_shared_name}\''
                f.writelines(f'    {ability_id} = {factory_method}({arguments})\n')
        f.writelines('\n\n')
        f.writelines('ability_collection_classes = {\n')
        for classname in self.__ability_ext_data_reg.keys():
            f.writelines(f'    \'{classname}\': {classname}Abilities,\n')
        f.writelines('}\n')

    def get_ability_ext_object(self, gameclass: GameClass, ability_id):
        key = f'{gameclass.name}.{ability_id}'
        if key not in self.__ability_ext_consts_reg.keys():
            ext_data = self.__ability_ext_data_reg[gameclass.name][ability_id]
            ext_consts = AbilityExtConsts()
            ext_consts.set_ext_data(ext_data, self.__default_values)
            self.__ability_ext_consts_reg[key] = ext_consts
        else:
            ext_consts = self.__ability_ext_consts_reg[key]
        return ext_consts

    def close(self):
        Closeable.close(self)
        AbilityExtConstsRegistry.__instance = None
