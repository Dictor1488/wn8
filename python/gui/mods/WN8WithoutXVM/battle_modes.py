from constants import ARENA_GUI_TYPE, ARENA_BONUS_TYPE

ALLOWED_GUI_TYPES = frozenset((
    ARENA_GUI_TYPE.RANDOM,
    ARENA_GUI_TYPE.STRONGHOLD_BATTLES,
    ARENA_GUI_TYPE.SORTIE,
    ARENA_GUI_TYPE.FORT_BATTLE,
    ARENA_GUI_TYPE.BATTLE_ROYALE,
    ARENA_GUI_TYPE.MAPBOX,
))

ALLOWED_BONUS_TYPES = frozenset((
    ARENA_BONUS_TYPE.REGULAR,
    ARENA_BONUS_TYPE.RANDOM_NP2,
    ARENA_BONUS_TYPE.SORTIE_2,
    ARENA_BONUS_TYPE.FORT_BATTLE_2,
    ARENA_BONUS_TYPE.COMP7,
    ARENA_BONUS_TYPE.TOURNAMENT_COMP7,
    ARENA_BONUS_TYPE.TRAINING_COMP7,
    ARENA_BONUS_TYPE.COMP7_LIGHT,
))


def is_supported(arena):
    if arena is None:
        return False
    guiType = getattr(arena, 'guiType', None)
    bonusType = getattr(arena, 'bonusType', None)
    if guiType in ALLOWED_GUI_TYPES:
        return True
    if bonusType in ALLOWED_BONUS_TYPES:
        return True
    return False
