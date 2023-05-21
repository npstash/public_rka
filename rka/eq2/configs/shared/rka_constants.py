# game lag (used in scripting framework)
from rka.components.io.log_service import LogService
from rka.log_configs import LOG_APPCONTROL

# general delays and frequencies
GAME_LAG = 0.12
VPN_LAG = 0.02
CLICK_DELAY = 0.3
UI_REACT_DELAY = 0.5
SERVER_REACT_DELAY = 0.8 + GAME_LAG
AUTOCOMBAT_TICK = 0.4
PROCESSOR_TICK = 0.25

# ability constants
PARSE_CENSUS_EFFECTS = False
ABILITY_CASTING_SAFETY = VPN_LAG + GAME_LAG
ABILITY_RECOVERY_SAFETY = GAME_LAG + 0.1
ABILITY_REUSE_SAFETY = 0.2
ABILITY_INJECTION_DURATION = 3.0 + VPN_LAG
ABILITY_GRANT_DELAY = 2.0 + GAME_LAG

# action delay measurements
ACTION_MEASURE_DELAY = True
ACTION_OVERHEAD_DEFAULT = 0.0

# parser constants
LOG_PARSER_SKIPCHARS = 39
DPSPARSE_NEW_ENCOUNTER_GAP = 6.0

# UI constants
KEY_REPEAT = 0.05
MAX_OVERLAY_STATUS_SLOTS = 9
STAY_IN_VOICE = 10 * 60.0

logger = LogService(LOG_APPCONTROL)
logger.warn(f'setting GAME_LAG = {GAME_LAG}') if GAME_LAG else logger.info(f'GAME_LAG = {GAME_LAG}')

# paths
LOCAL_ABILITY_INJECTOR_PATH = r'\\.\pipe\LOCAL\ability_list_1'
LOCAL_COMMAND_INJECTOR_PATH = r'\\.\pipe\LOCAL\ability_list_2'
REMOTE_INJECTOR_PATH = r'\\.\pipe\LOCAL\ability_list_5'
