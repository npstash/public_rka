from typing import Optional

import regex as re

UNKNOWN_ZONE_PREFIX = 'Unknown Zone'
UNKNOWN_ZONE_PATTERN = f'{UNKNOWN_ZONE_PREFIX}({{}})'


def is_unknown_zone(zone: Optional[str]) -> bool:
    if not zone:
        return True
    return zone.startswith(UNKNOWN_ZONE_PREFIX)


def get_unknown_zone(player_name: str) -> str:
    return UNKNOWN_ZONE_PATTERN.format(player_name)


def __processing_for_filenames(s: str) -> str:
    processed = s.replace(' ', '_')
    processed = ''.join(filter(lambda c: str.isalpha(c) or c == '_', processed))
    processed = processed.strip('_')
    return processed


def get_canonical_zone_name(plain_name: str) -> str:
    if is_unknown_zone(plain_name):
        raise ValueError(plain_name)
    canonical_name = plain_name.lower().strip()
    instance = re.match(r'(.*)( \d+)?', canonical_name)
    if instance:
        canonical_name = instance.group(1).strip()
    tier = re.match(r'(.*)\[(.*)\].*', canonical_name)
    if tier:
        canonical_name = tier.group(1).strip()
    return __processing_for_filenames(canonical_name)


def get_canonical_zone_name_with_tier(plain_name: str) -> str:
    if is_unknown_zone(plain_name):
        raise ValueError(plain_name)
    canonical_name = get_canonical_zone_name(plain_name)
    tier = re.match(r'(.*)\[(.*)\].*', plain_name)
    if not tier:
        return canonical_name
    tier = tier.group(2).lower().strip()
    tier = __processing_for_filenames(tier)
    return f'{canonical_name}_{tier}'
