import os.path
from typing import List

TESTLOGFILES_LOCATION = os.path.dirname(os.path.realpath(__file__))


def get_all_testlog_filepaths() -> List[str]:
    onlyfiles = [f for f in os.listdir(TESTLOGFILES_LOCATION) if os.path.isfile(os.path.join(TESTLOGFILES_LOCATION, f)) and f.endswith('.txt')]
    return [os.path.join(TESTLOGFILES_LOCATION, f) for f in onlyfiles]


def get_testlog_filepath(short_filename: str) -> str:
    return os.path.join(TESTLOGFILES_LOCATION, short_filename)
