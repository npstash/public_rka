import enum
import itertools
import json
import time
from enum import auto
from typing import Set, Iterable, Tuple, List, Optional

import regex as re

from rka.eq2.datafiles import cached_ts_spellchecks_filepath


class Operations(enum.IntFlag):
    DELETE = auto()
    REPLACE = auto()
    TRANSPOSE = auto()
    INSERT = auto()


KNOWN_PHRASES = set()
KNOWN_WORDS = set()
KNOWN_CHARACTERS = set()

__cached_correction_results = dict()
__debug = False


def __load_cached_corrections():
    fname = cached_ts_spellchecks_filepath()
    # noinspection PyBroadException
    try:
        with open(fname, 'r') as f:
            cached_spellchecks = json.load(f)
            global __cached_correction_results
            __cached_correction_results.update(cached_spellchecks)
    except Exception as _e:
        pass


def __save_cached_corrections():
    fname = cached_ts_spellchecks_filepath()
    with open(f'{fname}', 'wt') as f:
        global __cached_correction_results
        json.dump(__cached_correction_results, f, indent=2)


__load_cached_corrections()


def __read_requisition_dictionary(eq2_path: str):
    from rka.eq2.configs.shared.game_constants import EQ2_US_LOCALE_FILE_TEMPLATE
    requisition_dictionary = set()
    dict_file = EQ2_US_LOCALE_FILE_TEMPLATE.format(eq2_path)
    r = re.compile(r'\d+\s+uddt\s+I need to create (.*)$')
    with open(dict_file, 'r', encoding='Latin-1') as file:
        for line in file:
            m = r.match(line)
            if not m:
                continue
            text = m.group(1)
            if text.find(' (') != -1:
                text = text[:text.find(' (')]
            requisition_dictionary.add(text)
    init_dictionary(requisition_dictionary)


def init_dictionary(phrases: Iterable[str]):
    lower_phrases = {phrase.lower() for phrase in phrases}
    KNOWN_PHRASES.update(lower_phrases)
    for phrase in lower_phrases:
        for char in phrase.strip():
            KNOWN_CHARACTERS.add(char)
        for word in phrase.split():
            KNOWN_WORDS.add(word)


def candidates_1(patterns: Set[str], letters: Set[str], phrase: str, ops: Operations, use_original: bool) -> Optional[List[str]]:
    k1 = known(patterns, [phrase])
    if k1:
        return k1
    k2 = known(patterns, edits1(phrase, letters, ops, True))
    if k2:
        return k2
    if use_original:
        return [phrase]
    return None


def candidates_12(patterns: Set[str], letters: Set[str], phrase: str, ops: Operations, use_original: bool) -> Optional[List[str]]:
    k1 = known(patterns, [phrase])
    if k1:
        return k1
    k2 = known(patterns, edits1(phrase, letters, ops, True))
    if k2:
        return k2
    k3 = known(patterns, edits2(phrase, letters, ops, True))
    if k3:
        return k3
    if use_original:
        return [phrase]
    return None


def candidates_123(patterns: Set[str], letters: Set[str], phrase: str, ops: Operations, use_original: bool) -> Optional[List[str]]:
    k1 = known(patterns, [phrase])
    if k1:
        return k1
    k2 = known(patterns, edits1(phrase, letters, ops, True))
    if k2:
        return k2
    k3 = known(patterns, edits2(phrase, letters, ops, True))
    if k3:
        return k3
    k4 = known(patterns, fedits3(phrase))
    if k4:
        return k4
    if use_original:
        return [phrase]
    return None


def known(database: Set[str], phrases: Iterable[str]) -> List[str]:
    return [w for w in phrases if w in database]


letter_similarity = {
    'a': ['e', 'o', 'u', 's', 'c', 'n'],
    'b': ['h', 'k'],
    'c': ['e', 'o', 'a'],
    'd': [],
    'e': ['c', 'o', 'a', 's'],
    'f': ['t', 'l', 'i'],
    'g': ['q', 'y'],
    'h': ['b', 'k'],
    'i': ['l', 'm'],
    'j': ['i', 'y', 'l'],
    'k': ['k', 'b'],
    'l': ['i', 'j'],
    'm': ['n', 'w', 'i', 'r'],
    'o': ['a', 'c', 'e', 'u'],
    'p': [],
    'q': ['g', 'y'],
    'r': ['i', 'm'],
    's': ['a', 'e'],
    't': ['f', 'l', 'i'],
    'u': ['a', 'o', 'n'],
    'v': ['u', 'w'],
    'w': ['m', 'v'],
    'x': ['z'],
    'y': ['g', 'q'],
    'z': ['x'],
}


def similar(r, c):
    return r in letter_similarity and c in letter_similarity[r]


def edits1(phrase: str, letters: Set[str], ops: Operations, similarity: bool) -> Iterable[str]:
    splits = [(phrase[:i], phrase[i:]) for i in range(len(phrase) + 1)]
    if Operations.DELETE in ops:
        deletes = (L + R[1:] for L, R in splits if R)
    else:
        deletes = []
    if Operations.TRANSPOSE in ops:
        transposes = (L + R[1] + R[0] + R[2:] for L, R in splits if len(R) > 1)
    else:
        transposes = []
    if Operations.INSERT in ops:
        inserts = (L + c + R for L, R in splits for c in letters)
    else:
        inserts = []
    if Operations.REPLACE in ops:
        if similarity:
            priority_replaces = (L + c + R[1:] for L, R in splits if R for c in letters if similar(R[0], c))
            normal_replaces = (L + c + R[1:] for L, R in splits if R for c in letters if not similar(R[0], c))
        else:
            priority_replaces = []
            normal_replaces = (L + c + R[1:] for L, R in splits if R for c in letters)
    else:
        priority_replaces = []
        normal_replaces = []
    return itertools.chain(priority_replaces, normal_replaces, inserts, deletes, transposes)


__fast_letters = 'qwertyuiopasdfghjklzxcvbnm\''


def fedits1(phrase: str, letters: str, ops: Operations) -> Iterable[str]:
    splits = [(phrase[:i], phrase[i:]) for i in range(len(phrase) + 1)]
    if Operations.DELETE in ops:
        deletes = [L + R[1:] for L, R in splits if R]
    else:
        deletes = []
    if Operations.TRANSPOSE in ops:
        transposes = [L + R[1] + R[0] + R[2:] for L, R in splits if len(R) > 1]
    else:
        transposes = []
    if Operations.INSERT in ops:
        inserts = [L + c + R for L, R in splits for c in letters]
    else:
        inserts = []
    if Operations.REPLACE in ops:
        replaces = [L + c + R[1:] for L, R in splits if R for c in __fast_letters]
    else:
        replaces = []
    return itertools.chain(inserts, deletes, replaces, transposes)


def edits2(phrase: str, letters: Set[str], ops: Operations, similarity: bool) -> Iterable[str]:
    return (e2 for e1 in edits1(phrase, letters, ops, similarity) for e2 in edits1(e1, letters, ops, similarity))


def fedits3(phrase: str) -> Iterable[str]:
    ops_1: Operations = Operations(Operations.INSERT | Operations.DELETE)
    return (e3 for e1 in fedits1(phrase, __fast_letters, Operations.REPLACE)
            for e2 in fedits1(e1, __fast_letters, Operations.REPLACE)
            for e3 in fedits1(e2, __fast_letters, ops_1))


def __correction(phrase: str, default_ops: Optional[Operations] = None) -> Tuple[int, Optional[str]]:
    if default_ops is None:
        default_ops = Operations.INSERT | Operations.REPLACE

    # no error found
    difficulty = 0
    if phrase in KNOWN_PHRASES:
        return difficulty, phrase

    difficulty += 1
    if __debug:
        print(f'stage {difficulty}')
    ops: Operations = Operations.INSERT
    result_spaces = candidates_1(KNOWN_PHRASES, {' '}, phrase, ops, False)
    if result_spaces:
        return difficulty, result_spaces[0]

    difficulty += 1
    if __debug:
        print(f'stage {difficulty}')
    result_1 = candidates_1(KNOWN_PHRASES, KNOWN_CHARACTERS, phrase, default_ops, False)
    if result_1:
        return difficulty, result_1[0]

    difficulty += 1
    if __debug:
        print(f'stage {difficulty}')
    result_12 = candidates_12(KNOWN_PHRASES, KNOWN_CHARACTERS, phrase, default_ops, False)
    if result_12:
        return difficulty, result_12[0]

    difficulty += 1
    if __debug:
        print(f'stage {difficulty}')
    corrected_words_1 = [candidates_1(KNOWN_WORDS, KNOWN_CHARACTERS, word, default_ops, True)[0] for word in phrase.split()]
    corrected_words_phrase_1 = ' '.join(corrected_words_1)
    result_1_1 = candidates_1(KNOWN_PHRASES, KNOWN_CHARACTERS, corrected_words_phrase_1, default_ops, False)
    if result_1_1:
        return difficulty, result_1_1[0]

    difficulty += 1
    if __debug:
        print(f'stage {difficulty}')
    corrected_words_12 = [candidates_12(KNOWN_WORDS, KNOWN_CHARACTERS, word, default_ops, True)[0] for word in corrected_words_phrase_1.split()]
    corrected_words_phrase_12 = ' '.join(corrected_words_12)
    result_12_1 = candidates_1(KNOWN_PHRASES, KNOWN_CHARACTERS, corrected_words_phrase_12, default_ops, False)
    if result_12_1:
        return difficulty, result_12_1[0]

    difficulty += 1
    if __debug:
        print(f'stage {difficulty}')
    result_12_12 = candidates_12(KNOWN_PHRASES, KNOWN_CHARACTERS, corrected_words_phrase_12, default_ops, False)
    if result_12_12:
        return difficulty, result_12_12[0]

    difficulty += 1
    corrected_words_123 = [candidates_123(KNOWN_WORDS, KNOWN_CHARACTERS, word, default_ops, True)[0] for word in corrected_words_phrase_1.split()]
    corrected_words_phrase_123 = ' '.join(corrected_words_123)
    result_123_1 = candidates_1(KNOWN_PHRASES, KNOWN_CHARACTERS, corrected_words_phrase_123, default_ops, False)
    if result_123_1:
        return difficulty, result_123_1[0]

    difficulty += 1
    result_123_12 = candidates_1(KNOWN_PHRASES, KNOWN_CHARACTERS, corrected_words_phrase_123, default_ops, False)
    if result_123_12:
        return difficulty, result_123_12[0]

    return difficulty, None


def preprocessing(phrase: str) -> str:
    phrase = phrase.replace('!', 'I')
    phrase = phrase.replace(']', 'I')
    phrase = phrase.replace('[', 'I')
    phrase = phrase.replace('1', 'I')
    return phrase.lower()


def correction(phrase: str, default_ops: Optional[Operations] = None) -> Optional[str]:
    if phrase in __cached_correction_results.keys():
        result = __cached_correction_results[phrase]
        print(f'Spellcheck "{phrase}" returning cached result "{result}"')
        return result
    t1 = time.time()
    phrase2 = preprocessing(phrase)
    if default_ops is not None:
        difficulty, result = __correction(phrase2, default_ops)
    else:
        for default_ops in [Operations.INSERT | Operations.REPLACE, Operations.INSERT | Operations.REPLACE | Operations.DELETE]:
            # noinspection PyTypeChecker
            difficulty, result = __correction(phrase2, default_ops)
            if result is not None:
                break
    if __debug:
        print(f'Spellcheck "{phrase}" resolved to "{result}", difficulty {difficulty}, in {time.time() - t1:.4f}s')
    if phrase not in __cached_correction_results.keys() and result is not None and difficulty > 2:
        __cached_correction_results[phrase] = result
        __save_cached_corrections()
    return result

