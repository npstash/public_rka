from typing import List, Optional

import regex as re

from rka.eq2.master.game.gameclass import GameClass, GameClasses
from rka.eq2.master.game.scripting.scripts import logger


def _canonicalize_one_word(word: str) -> str:
    return word.strip().lower()


def _compare_words12(word1: str, word2: str) -> bool:
    word1 = _canonicalize_one_word(word1)
    word2 = _canonicalize_one_word(word2)
    if word1 == word2:
        return True
    if word1.endswith('s') and word1[:-1] == word2:
        return True
    if word1.endswith('es') and word1[:-2] == word2:
        return True
    if word1.endswith('ies') and word2.endswith('y'):
        return word1[:-3] == word2[:-1]
    return False


def compare_words(word1: str, word2: str) -> bool:
    if _compare_words12(word1, word2):
        return True
    return _compare_words12(word2, word1)


def strip_prefix(itemname: str, prefix: str) -> str:
    prefix = f'{prefix.strip()} '
    if itemname.startswith(prefix):
        return itemname.replace(prefix, '', 1)
    return itemname


def strip_language_prefixes(itemname: str) -> str:
    itemname = strip_prefix(itemname, 'a')
    itemname = strip_prefix(itemname, 'an')
    itemname = strip_prefix(itemname, 'the')
    return itemname


def guess_items_per_craft(crafter_class: GameClass, target_count: int) -> int:
    items_per_craft = 0
    if crafter_class in (GameClasses.Armorer, GameClasses.Weaponsmith, GameClasses.Tailor):
        items_per_craft = 1
    elif crafter_class in (GameClasses.Sage, GameClasses.Jeweler):
        if target_count in [10, 20, 30]:
            items_per_craft = 10
        else:
            items_per_craft = 1
    elif crafter_class in (GameClasses.Provisioner, GameClasses.Alchemist, GameClasses.Carpenter, GameClasses.Woodworker):
        if target_count in [2, 4, 6]:
            items_per_craft = 2
        elif target_count in [10, 20, 30]:
            items_per_craft = 10
        elif target_count in [12, 18]:
            items_per_craft = 6
        else:
            items_per_craft = 1
    assert items_per_craft > 0
    return items_per_craft


def get_itemname_modifications_for_class(crafter_class: GameClass, crafter_level: int, orig_requested_item: str) -> str:
    difference_keywords = []
    # after lvl 100, there is no imbued/blessed
    if crafter_class in [GameClasses.Weaponsmith] and crafter_level <= 95:
        difference_keywords = ['imbued', 'blessed']
    elif crafter_class in [GameClasses.Tailor, GameClasses.Armorer] and crafter_level <= 95:
        difference_keywords = ['imbued']
    negatives = []
    for difference in difference_keywords:
        if difference in orig_requested_item:
            stripped_requested_item = orig_requested_item.replace(difference, '')
            difference = find_differentiation_word(positive_sentence=stripped_requested_item, negative_sentences=[orig_requested_item], min_length=3)
        else:
            difference = difference[:3]
        negatives.append(difference)
    for negative in negatives:
        orig_requested_item += f' -{negative}'
    return orig_requested_item


def strip_to_minimal_normal_representation(itemname: str) -> str:
    itemname = strip_language_prefixes(itemname)
    # remove internal hyphens '-', but not preceeding ones - they have exclusion meaning (negative match)
    itemname = re.sub(pattern='([^ ])-', repl='\\1 ', string=itemname)
    # remove tier information in []
    itemname = re.sub(pattern=r' ?\[[^]]*\]$', repl='', string=itemname)
    return itemname


def strip_to_minimal_crafing_representation(itemname: str) -> str:
    itemname = strip_language_prefixes(itemname)
    # remove internal hyphens '-', but not preceeding ones - they have exclusion meaning (negative match)
    itemname = re.sub(pattern='([^ ])-', repl='\\1 ', string=itemname)
    itemname = strip_prefix(itemname, 'essence of ')
    itemname = strip_prefix(itemname, 'rune of ')
    itemname = strip_prefix(itemname, 'pristine ')
    # remove tier information in []
    itemname = re.sub(pattern=r' ?\[[^]]*\]$', repl='', string=itemname)
    return itemname


def compare_normal_item_names(first_item: str, second_item: str) -> bool:
    first_item = first_item.strip().lower()
    second_item = second_item.strip().lower()
    if first_item == second_item:
        return True
    crafted_item = strip_to_minimal_normal_representation(first_item)
    requested_item = strip_to_minimal_normal_representation(second_item)
    return crafted_item == requested_item


def compare_crafting_item_names(crafted_item: str, requested_item: str) -> bool:
    crafted_item = crafted_item.strip().lower()
    requested_item = requested_item.strip().lower()
    if crafted_item == requested_item:
        return True
    logger.debug(f'items differ {crafted_item} vs {requested_item}, stripping to minimal crafting representations')
    crafted_item = strip_to_minimal_crafing_representation(crafted_item)
    requested_item = strip_to_minimal_crafing_representation(requested_item)
    if crafted_item == requested_item:
        return True
    logger.debug(f'comparing word lists after stripping: {crafted_item} vs {requested_item}')
    words_req = requested_item.split()
    words_craft = crafted_item.split()
    if len(words_req) != len(words_craft):
        return False
    for i in range(len(words_craft)):
        word_craft = words_craft[i]
        word_req = words_req[i]
        word_compare_result = compare_words(word_craft, word_req)
        if not word_compare_result:
            logger.debug(f'failed to compare {word_craft} vs {word_req}')
        if not word_compare_result:
            return False
    return True


def get_minimal_diff_word(word: str, requested_item: str, min_length=1) -> Optional[str]:
    splits = {word[:i] for i in range(min_length, len(word))}
    splits.update({word[i:] for i in range(len(word) - min_length + 1)})
    subs = sorted({w[:i] for w in splits for i in range(min_length, len(w) + 1)}, key=len)
    for sub in subs:
        if sub not in requested_item:
            assert isinstance(sub, str)
            return sub
    return None


def find_differentiation_word(positive_sentence: str, negative_sentences: List[str], min_length=1) -> Optional[str]:
    positive_sentence = strip_to_minimal_crafing_representation(positive_sentence)
    negative_sentences = [strip_to_minimal_crafing_representation(negative_sentence) for negative_sentence in negative_sentences]
    words_positive = positive_sentence.split()
    words_negative = [word for negative_sentence in negative_sentences for word in negative_sentence.split()]
    i_req = 0
    shortest_diff_word = None
    for i_craft in range(len(words_negative)):
        word_negative = words_negative[i_craft]
        if i_req < len(words_positive) and compare_words(word_negative, words_positive[i_req]):
            i_req += 1
            continue
        if word_negative not in positive_sentence:
            new_diff_word = get_minimal_diff_word(word_negative, positive_sentence, min_length)
            if shortest_diff_word is None or (new_diff_word is not None and len(new_diff_word) < len(shortest_diff_word)):
                shortest_diff_word = new_diff_word
    return shortest_diff_word


def get_itemname_corrected_for_input(requested_item: str) -> str:
    requested_item = strip_to_minimal_crafing_representation(requested_item)
    extra_characters_allowed = r' -\''
    corrected_item = ''
    for a in requested_item:
        if not a.isalpha() and a not in extra_characters_allowed:
            a = ' '
        corrected_item += a
    corrected_item += ' '
    corrected_item = corrected_item.strip().replace('\'s ', ' ')
    corrected_item = corrected_item.strip().replace('\'es ', ' ')
    corrected_item = corrected_item.strip().replace(' of ', ' ')
    return corrected_item


def get_compressed_keywords(requested_item: str, remaining_space: int) -> List[str]:
    words = set(requested_item.strip().split())
    eliminate_words = set()
    # eliminate words which are included in other words
    for word1 in words:
        for word2 in words:
            if word1 in word2 and word1 != word2:
                eliminate_words.add(word1)
    words.difference_update(eliminate_words)
    final_words = []
    # include mandatory discriminator
    for compressed_word in words:
        if compressed_word.startswith('-'):
            final_words.append(compressed_word + ' ')
            remaining_space -= len(compressed_word) + 1
            words.remove(compressed_word)
            break
    # noinspection PyTypeChecker
    sorted_words = list(sorted(words, key=len, reverse=True))
    # include the shortest word (might be Tier numerator)
    if sorted_words and len(sorted_words[-1]) <= 6:
        word = sorted_words.pop()[:5]
        final_words.append(word + ' ')
        remaining_space -= len(word) + 1
    while remaining_space > 0 and sorted_words:
        remaining_required_length = len(' '.join(sorted_words))
        cut_ratio = remaining_space / remaining_required_length
        next_word = sorted_words.pop(0)
        cut_word_len = int(cut_ratio * len(next_word))
        if cut_word_len < 2:
            cut_word_len = 2
        if cut_word_len > len(next_word):
            cut_word_len = len(next_word)
        # find a sub-word that is not contained in already added words
        if final_words:
            compressed_word = None
            for subword in [next_word[i:i + cut_word_len] for i in range(len(next_word) - cut_word_len + 1)]:
                subword_contained = False
                for final_word in final_words:
                    if subword in final_word:
                        subword_contained = True
                        break
                if not subword_contained:
                    compressed_word = subword
                    break
        else:
            compressed_word = next_word
        final_words.append(compressed_word + ' ')
        remaining_space -= len(compressed_word) + 1
    return final_words


if __name__ == '__main__':
    tests = [
        ['roundhouse kick v', 'roundhouse v'],
        ['roundhouse kick v', 'roundhouse v -kick'],
        ['pedestal of roes', 'detailed pedestal of ro'],
        ['totopoes', 'totopo'],
        ['scintillating violet thornvines', 'scintillating thornvine'],
        ['scintillating thornvines', 'scintillating thornvine -io'],
        ['exceptional essence of clarities', 'exceptional essence of clarity'],
        ['bloodlust vii', 'essence of bloodbath vii'],
    ]

    for test in tests:
        match = compare_crafting_item_names(crafted_item=test[0], requested_item=test[1])
        diff = find_differentiation_word(positive_sentence=test[1], negative_sentences=[test[0]])
        compressed = get_compressed_keywords(test[1], 19)
        print(f'comparing: crafted_item={test[0]}, requested_item={test[1]}, match={match}, diff={diff}, words={compressed}')
