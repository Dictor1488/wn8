from constants import ARENA_GUI_TYPE, ARENA_BONUS_TYPE


def _safe_get(cls, name):
    val = getattr(cls, name, None)
    if val is None:
        return object()  # уникальный объект который никогда не совпадёт
    return val


ALLOWED_GUI_TYPES = frozenset(filter(None, (
    getattr(ARENA_GUI_TYPE, 'RANDOM', None),
    getattr(ARENA_GUI_TYPE, 'STRONGHOLD_BATTLES', None),
    getattr(ARENA_GUI_TYPE, 'SORTIE', None),
    getattr(ARENA_GUI_TYPE, 'FORT_BATTLE', None),
    getattr(ARENA_GUI_TYPE, 'BATTLE_ROYALE', None),
    getattr(ARENA_GUI_TYPE, 'MAPBOX', None),
    # новые режимы в WoT 2.x
    getattr(ARENA_GUI_TYPE, 'RANDOM_TRAINING', None),
    getattr(ARENA_GUI_TYPE, 'TRAINING', None),
    getattr(ARENA_GUI_TYPE, 'RANKED', None),
    getattr(ARENA_GUI_TYPE, 'EPIC_BATTLE', None),
)))

ALLOWED_BONUS_TYPES = frozenset(filter(None, (
    getattr(ARENA_BONUS_TYPE, 'REGULAR', None),
    getattr(ARENA_BONUS_TYPE, 'RANDOM_NP2', None),
    getattr(ARENA_BONUS_TYPE, 'SORTIE_2', None),
    getattr(ARENA_BONUS_TYPE, 'FORT_BATTLE_2', None),
    getattr(ARENA_BONUS_TYPE, 'COMP7', None),
    getattr(ARENA_BONUS_TYPE, 'TOURNAMENT_COMP7', None),
    getattr(ARENA_BONUS_TYPE, 'TRAINING_COMP7', None),
    getattr(ARENA_BONUS_TYPE, 'COMP7_LIGHT', None),
)))


def is_supported(arena):
    if arena is None:
        return False
    guiType = getattr(arena, 'guiType', None)
    bonusType = getattr(arena, 'bonusType', None)
    if guiType is not None and guiType in ALLOWED_GUI_TYPES:
        return True
    if bonusType is not None and bonusType in ALLOWED_BONUS_TYPES:
        return True
    return False
