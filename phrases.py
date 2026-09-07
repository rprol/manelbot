# phrases.py
#
# Galician phrase banks used by the bot when it posts a match result.
#
# *** IMPORTANT ***
# These phrases (except the WIN one you gave us) were drafted by an AI and
# have NOT been checked by a native Galician speaker. Please read through
# every list below -- and ideally have a Galician speaker review them -- and
# edit anything that sounds off before the bot goes live. This file is
# intentionally simple so you can tweak, add, or remove phrases at any time.

import random

# Phrases used when Celta WINS the match.
# Every phrase starts with the same fixed opener: "Ben, Celta, ben!"
WIN_PHRASES = [
    "Ben, Celta, ben! Partido gañado con mérito!",
    "Ben, Celta, ben! Que ledicia, meu!",
    "Ben, Celta, ben! Tres puntos para casa!",
    "Ben, Celta, ben! Balaídos esperta feliz!",
    "Ben, Celta, ben! Outra vitoria para os celestes!",
    "Ben, Celta, ben! Que xogada, que equipo!",
]

# Phrases used when the match ends in a DRAW. Tone is deliberately flat and
# unenthusiastic -- a draw is not something to celebrate.
# Every phrase starts with the same fixed opener: "Regular, Celta, regular!"
DRAW_PHRASES = [
    "Regular, Celta, regular! Un empate que sabe a pouco.",
    "Regular, Celta, regular! Nin se gaña nin se perde, e iso pesa.",
    "Regular, Celta, regular! Puntos que non acaban de convencer.",
    "Regular, Celta, regular! Outra tarde sen brillo en Balaídos.",
    "Regular, Celta, regular! Un punto que sabe amargo.",
    "Regular, Celta, regular! Faltou algo máis para gañar.",
]

# Phrases used when Celta LOSES the match. Tone is deliberately dramatic and
# pessimistic.
# Every phrase starts with the same fixed opener: "Mal, Celta, mal!"
LOSS_PHRASES = [
    "Mal, Celta, mal! Unha noite negra para os celestes.",
    "Mal, Celta, mal! Balaídos queda en silencio, mágoa profunda.",
    "Mal, Celta, mal! Derrota dura que doe no fondo da alma celeste.",
    "Mal, Celta, mal! Outro golpe que custa dixerir.",
    "Mal, Celta, mal! A tristeza invade o celtismo hoxe.",
    "Mal, Celta, mal! Unha tarde para esquecer canto antes.",
]

# All phrase banks in one place, keyed by outcome. main.py looks up the
# right list here based on whether Celta won, drew, or lost.
PHRASES = {
    "WIN": WIN_PHRASES,
    "DRAW": DRAW_PHRASES,
    "LOSS": LOSS_PHRASES,
}


def get_random_phrase(outcome):
    """
    Return a random phrase (a plain string) for the given outcome.

    outcome must be one of "WIN", "DRAW", "LOSS" -- this matches the keys
    in the PHRASES dict above.
    """
    return random.choice(PHRASES[outcome])
