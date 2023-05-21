import os.path

# player stat info
DEFAULT_PLAYER_HEALTH = 2.0 * 1000 * 1000 * 1000  # input local player HP in player config instance
DEFAULT_PLAYER_POWER = 15.0 * 1000 * 1000
CURRENT_MAX_LEVEL = 125

# hidden durations etc.
READYUP_MIN_PERIOD = 80.0

# overseers
MAX_OVERSEER_CHARGED_MISSIONS = 10
MAX_OVERSEER_MISSION_CHARGES = 10
MAX_OVERSEER_DAILY_MISSIONS = 10

# game app
EQ2_WINDOW_NAME = 'Put window name here'
EQ2_LOG_FILE_TEMPLATE = os.path.normpath('{}/logs/{}/eq2log_{}.txt')
EQ2_US_LOCALE_FILE_TEMPLATE = os.path.normpath('{}/locale/en_us_dict.dat')
EQ2_REMOTE_SLAVE_TOOLBAR_PATH = os.path.normpath('TODO')
EQ2_LOCAL_SLAVE_TOOLBAR_PATH = os.path.normpath('TODO')
EQ2_LAUNCHER_BATCH_SLAVE_PATH = os.path.join(EQ2_REMOTE_SLAVE_TOOLBAR_PATH, 'Launcher.bat')
MONGODB_SERVICE_URI = 'TODO'
MONGODB_CERTIFICATE_FILENAME = 'TODO'
MONGODB_DATABASE_NAME = 'TODO'
CENSUS_SERVICE_NAME = 'TODO'

# ability constants and data missing from census
LINK_ABILITY_ID = {
    'powerlink': 339177354,
    'forcelink': 1614089081,
    'painlink': 3449416407,
}
CURRENT_LINK_TIER = 'forlorn'

# convenience for some scripts
ALT1_NAME = ''
ALT2_NAME = ''
ALT3_NAME = ''
ALT4_NAME = ''
ALT5_NAME = ''
