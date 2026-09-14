# phrases.py
#
# Galician phrase banks used by the bot when it posts a match result.
#
# *** IMPORTANT ***
# These phrases (except the original WIN phrase the user provided: "Ben,
# Celta, ben! Partido gañado con mérito!") were drafted by an AI and have
# NOT been checked by a native Galician speaker. Please read through every
# list below -- and ideally have a Galician speaker review them -- and edit
# anything that sounds off before the bot goes live. This file is
# intentionally simple so you can tweak, add, or remove phrases at any time.
#
# CATEGORIES
# main.py doesn't just know WIN/DRAW/LOSS -- it looks at the half-time score
# alongside the full-time score to work out the *shape* of the match (see
# classify_match() in main.py), and picks phrases from the matching category
# below. Every phrase in a category still starts with the same fixed opener
# for that outcome ("Ben, Celta, ben!" / "Regular, Celta, regular!" / "Mal,
# Celta, mal!"), as required -- only the continuation changes.
#
# The *_LATE categories are only reachable when TheSportsDB enrichment
# (goal-by-goal timeline data) is available for that match -- see
# fetch_thesportsdb_goals() in main.py. Without it, matches fall back to the
# half-time/full-time-only categories above/below as normal.

import random

# --- WIN categories --------------------------------------------------------
# Every phrase starts with: "Ben, Celta, ben!"

# Celta were behind at half-time and still won.
WIN_COMEBACK_PHRASES = [
    "Ben, Celta, ben! Ían perdendo e deron a volta ao marcador!",
    "Ben, Celta, ben! Remontada de carácter para levarse os tres puntos!",
    "Ben, Celta, ben! Cando parecía perdido, o Celta sacou forzas para gañar!",
    "Ben, Celta, ben! Da desvantaxe á vitoria, que remontada!",
]

# Celta won by 3 or more goals.
WIN_BLOWOUT_PHRASES = [
    "Ben, Celta, ben! Goleada sen paliativos!",
    "Ben, Celta, ben! Un auténtico recital do equipo celeste!",
    "Ben, Celta, ben! Vitoria contundente, sen discusión posible!",
    "Ben, Celta, ben! O rival non tivo opción esta tarde!",
]

# Celta won by exactly 1 goal.
WIN_NARROW_PHRASES = [
    "Ben, Celta, ben! Vitoria sufrida pero moi merecida!",
    "Ben, Celta, ben! Gañouse pola mínima, pero gañouse!",
    "Ben, Celta, ben! Tres puntos apertados que saben a gloria!",
    "Ben, Celta, ben! Non foi doado, pero o Celta levou os tres puntos!",
]

# Any other win (e.g. led throughout, won by 2) -- the general-purpose bank.
WIN_STANDARD_PHRASES = [
    "Ben, Celta, ben! Partido gañado con mérito!",
    "Ben, Celta, ben! Tres puntos para casa!",
    "Ben, Celta, ben! Outra vitoria para os celestes!",
    "Ben, Celta, ben! Que ledicia, meu!",
]

# The goal that won it came in the closing minutes (see LATE_GOAL_MINUTE).
WIN_LATE_PHRASES = [
    "Ben, Celta, ben! Vitoria no derradeiro suspiro do partido!",
    "Ben, Celta, ben! Gol no tempo de desconto que vale tres puntos!",
    "Ben, Celta, ben! Agonía e gloria, o gol chegou cando xa non se esperaba!",
    "Ben, Celta, ben! Explosión de alegría cun gol de última hora!",
]

# --- DRAW categories --------------------------------------------------------
# Every phrase starts with: "Regular, Celta, regular!"

# Celta were behind at half-time and fought back to level it.
DRAW_RALLY_PHRASES = [
    "Regular, Celta, regular! Ían perdendo e conseguiron igualalo.",
    "Regular, Celta, regular! Sacaron un punto despois de ir por detrás.",
    "Regular, Celta, regular! Remontada parcial que soubo a pouco, pero é un punto.",
    "Regular, Celta, regular! Loitaron para escapar da derrota.",
]

# Celta were ahead at half-time but only came away with a draw.
DRAW_SQUANDERED_PHRASES = [
    "Regular, Celta, regular! Ían gañando e deixárono escapar.",
    "Regular, Celta, regular! Tiñan a vitoria na man e esvaroulles.",
    "Regular, Celta, regular! Dous puntos perdidos por non pechar o partido.",
    "Regular, Celta, regular! Unha vantaxe que non souberon manter.",
]

# Level at half-time, level at full-time -- a flat, uneventful draw.
DRAW_FLAT_PHRASES = [
    "Regular, Celta, regular! Un empate que sabe a pouco.",
    "Regular, Celta, regular! Nin se gaña nin se perde, e iso pesa.",
    "Regular, Celta, regular! Puntos que non acaban de convencer.",
    "Regular, Celta, regular! Outra tarde sen brillo no marcador.",
]

# The equalizer arrived in the closing minutes, rescuing a point that
# looked lost (see LATE_GOAL_MINUTE).
DRAW_LATE_PHRASES = [
    "Regular, Celta, regular! Empate salvado no derradeiro intre!",
    "Regular, Celta, regular! Gol de última hora que evita a derrota!",
    "Regular, Celta, regular! Cando xa se daba por perdido, chegou a igualada!",
    "Regular, Celta, regular! Un punto arrincado nos minutos finais!",
]

# --- LOSS categories --------------------------------------------------------
# Every phrase starts with: "Mal, Celta, mal!"

# Celta were ahead at half-time but ended up losing -- the worst kind.
LOSS_COLLAPSE_PHRASES = [
    "Mal, Celta, mal! Ían gañando e acabaron perdendo, un golpe durísimo.",
    "Mal, Celta, mal! Desperdiciaron unha vantaxe e pagárono caro.",
    "Mal, Celta, mal! Unha vitoria que se esfumou antes do final.",
    "Mal, Celta, mal! De ir gañando a perder, un final para esquecer.",
]

# Celta lost by 3 or more goals.
LOSS_BLOWOUT_PHRASES = [
    "Mal, Celta, mal! Goleada dolorosa, noite para esquecer.",
    "Mal, Celta, mal! Unha manita que doe moito.",
    "Mal, Celta, mal! Sen resposta posible ante un rival superior hoxe.",
    "Mal, Celta, mal! Derrota abultada que deixa tocada a afección.",
]

# Celta lost by exactly 1 goal.
LOSS_NARROW_PHRASES = [
    "Mal, Celta, mal! Derrota axustada que sabe amarga.",
    "Mal, Celta, mal! Perdeuse por un fío, pero perdeuse.",
    "Mal, Celta, mal! Tan preto e tan lonxe á vez.",
    "Mal, Celta, mal! Unha derrota mínima que igualmente doe.",
]

# Any other loss (e.g. behind throughout, lost by 2) -- the general-purpose bank.
LOSS_STANDARD_PHRASES = [
    "Mal, Celta, mal! Unha noite negra para os celestes.",
    "Mal, Celta, mal! Queda o silencio celeste, mágoa profunda.",
    "Mal, Celta, mal! Derrota dura que doe no fondo da alma celeste.",
    "Mal, Celta, mal! A tristeza invade o celtismo hoxe.",
]

# The decisive goal was conceded in the closing minutes -- the cruellest
# kind of loss (see LATE_GOAL_MINUTE).
LOSS_LATE_PHRASES = [
    "Mal, Celta, mal! Golpe no derradeiro minuto, moi doloroso.",
    "Mal, Celta, mal! Todo perdido nos últimos alentos do partido.",
    "Mal, Celta, mal! Un mazazo de última hora que ninguén esperaba.",
    "Mal, Celta, mal! Tan preto de sumar e todo esvarou nos minutos finais.",
]

# All phrase banks in one place, keyed by category. main.py's
# classify_match() works out which key applies to a given match, and
# get_random_phrase() below looks it up here.
PHRASES = {
    "WIN_COMEBACK": WIN_COMEBACK_PHRASES,
    "WIN_BLOWOUT": WIN_BLOWOUT_PHRASES,
    "WIN_NARROW": WIN_NARROW_PHRASES,
    "WIN_STANDARD": WIN_STANDARD_PHRASES,
    "WIN_LATE": WIN_LATE_PHRASES,
    "DRAW_RALLY": DRAW_RALLY_PHRASES,
    "DRAW_SQUANDERED": DRAW_SQUANDERED_PHRASES,
    "DRAW_FLAT": DRAW_FLAT_PHRASES,
    "DRAW_LATE": DRAW_LATE_PHRASES,
    "LOSS_COLLAPSE": LOSS_COLLAPSE_PHRASES,
    "LOSS_BLOWOUT": LOSS_BLOWOUT_PHRASES,
    "LOSS_NARROW": LOSS_NARROW_PHRASES,
    "LOSS_STANDARD": LOSS_STANDARD_PHRASES,
    "LOSS_LATE": LOSS_LATE_PHRASES,
}


def get_random_phrase(category):
    """
    Return a random phrase (a plain string) for the given category.

    category must be one of the keys in the PHRASES dict above -- see
    classify_match() in main.py for how a match gets mapped to one.
    """
    return random.choice(PHRASES[category])
