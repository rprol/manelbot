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
# STYLE: phrases are written short and punchy, closer to how a fan would
# actually post about the result than a formal match report -- dropping the
# explicit subject where Galician's conjugation already makes it clear
# (fine in this pro-drop language, and reads more like a real post), mixing
# singular ("o Celta segue...") and plural ("gañaron...") framing the way
# real match commentary does. Punctuation is deliberate: "!" for anything
# with real excitement or urgency, "." for the flatter/more resigned ones --
# keep that distinction if you add more.
#
# The *_LATE and *_TEN_MEN categories are only reachable when TheSportsDB
# enrichment (goal/card timeline data) is available for that match -- see
# fetch_thesportsdb_match_events() in main.py. Without it, matches fall
# back to the half-time/full-time-only categories above/below as normal.
#
# *_STREAK_2/3 and WIN_ADVANCED_ROUND are chosen by select_category() in
# main.py, not classify_match() -- they're about the competition/season
# context around the match (a win/loss streak, advancing in a cup) rather
# than this match's own shape, so they can override what would otherwise
# be a WIN_STANDARD/LOSS_STANDARD result. See select_category()'s
# docstring for exactly when each one wins out.
#
# WIN_ADVANCED_ROUND and LOSS_ELIMINATED can ALSO be chosen by
# check_other_competitions_result() directly (via _check_two_legged_tie()
# in main.py), overriding select_category()'s result entirely, when a
# same-opponent rematch confirms this was the second leg of a two-legged
# cup tie (Copa del Rey semifinal, Europa League knockout rounds) --
# based on the real two-leg aggregate score, not just this leg's own
# result. LOSS_ELIMINATED specifically is ONLY reachable this way (it has
# no meaning outside a two-legged tie), so don't assume it's about a
# "big"/lopsided single-match loss -- write its phrases around being
# knocked out of the competition, not about this match's own scoreline.

import random

# --- WIN categories --------------------------------------------------------
# Every phrase starts with: "Ben, Celta, ben!"

# Celta were behind at half-time and still won.
WIN_COMEBACK_PHRASES = [
    "Ben, Celta, ben! Perdían e deron a volta, que remontada!",
    "Ben, Celta, ben! Ían por detrás e acabaron gañando, que carácter!",
    "Ben, Celta, ben! Cando parecía perdido, chegou a reacción!",
    "Ben, Celta, ben! Da desvantaxe á vitoria nun pispás!",
]

# Celta won by 3 or more goals.
WIN_BLOWOUT_PHRASES = [
    "Ben, Celta, ben! Goleada sen paliativos!",
    "Ben, Celta, ben! Recital total do equipo celeste!",
    "Ben, Celta, ben! O rival non tivo opción!",
    "Ben, Celta, ben! Vitoria contundente, sen discusión posible!",
]

# Celta won by exactly 1 goal.
WIN_NARROW_PHRASES = [
    "Ben, Celta, ben! Sufrida, pero moi merecida!",
    "Ben, Celta, ben! Gañouse pola mínima, e vale igual!",
    "Ben, Celta, ben! Tres puntos apertados que saben a gloria!",
    "Ben, Celta, ben! Non foi doado, pero suman os tres!",
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
    "Ben, Celta, ben! Vitoria no derradeiro suspiro!",
    "Ben, Celta, ben! Gol no descontado que vale tres puntos!",
    "Ben, Celta, ben! Chegou xusto cando xa non se esperaba!",
    "Ben, Celta, ben! Explosión de alegría no último minuto!",
]

# Celta won despite having a player sent off during the match.
WIN_TEN_MEN_PHRASES = [
    "Ben, Celta, ben! Vitoria heroica xogando con dez!",
    "Ben, Celta, ben! Cun home menos no campo, e aínda así gañaron!",
    "Ben, Celta, ben! Que carácter, gañar cunha expulsión de por medio!",
    "Ben, Celta, ben! Dez homes chegaron e sobraron!",
]

# Second win in a row in the same competition (no other story to tell
# about this particular match -- see select_category() in main.py).
WIN_STREAK_2_PHRASES = [
    "Ben, Celta, ben! Segunda seguida, o equipo colle ritmo!",
    "Ben, Celta, ben! Dúas seguidas, e cada vez con máis confianza!",
    "Ben, Celta, ben! Encadea a súa segunda vitoria!",
    "Ben, Celta, ben! Van dúas, e a afección xa sorrí!",
]

# Third (or more) win in a row in the same competition.
WIN_STREAK_3_PHRASES = [
    "Ben, Celta, ben! Terceira seguida, o Celta está en racha!",
    "Ben, Celta, ben! Xa van varias, isto é un grande momento!",
    "Ben, Celta, ben! O bo momento non para, outra máis!",
    "Ben, Celta, ben! A racha triunfal segue, que ben está o equipo!",
]

# A Copa del Rey win, which (in the current single-match, no-replay
# format) always means advancing to the next round -- see
# select_category() in main.py for why this doesn't apply to the Europa
# League, whose format can't be read off a single match's result.
WIN_ADVANCED_ROUND_PHRASES = [
    "Ben, Celta, ben! Á seguinte rolda!",
    "Ben, Celta, ben! Segue vivo na copa!",
    "Ben, Celta, ben! Billete conseguido para a próxima eliminatoria!",
    "Ben, Celta, ben! O soño copeiro continúa!",
]

# --- DRAW categories --------------------------------------------------------
# Every phrase starts with: "Regular, Celta, regular!"

# Celta were behind at half-time and fought back to level it.
DRAW_RALLY_PHRASES = [
    "Regular, Celta, regular! Ían perdendo e igualaron, non está mal.",
    "Regular, Celta, regular! Sacaron un punto despois de ir por detrás.",
    "Regular, Celta, regular! Remontada parcial que sabe a pouco, pero suma.",
    "Regular, Celta, regular! Loitaron ata o final para non perder.",
]

# Celta were ahead at half-time but only came away with a draw.
DRAW_SQUANDERED_PHRASES = [
    "Regular, Celta, regular! Ían gañando e deixárono escapar.",
    "Regular, Celta, regular! Tiñan a vitoria na man e esvaroulles.",
    "Regular, Celta, regular! Dous puntos perdidos por non pechalo.",
    "Regular, Celta, regular! Non souberon manter a vantaxe.",
]

# Level at half-time, level at full-time -- a flat, uneventful draw.
DRAW_FLAT_PHRASES = [
    "Regular, Celta, regular! Empate que sabe a pouco.",
    "Regular, Celta, regular! Nin se gaña nin se perde, e iso pesa.",
    "Regular, Celta, regular! Punto que non convence.",
    "Regular, Celta, regular! Outra tarde sen brillo.",
]

# The equalizer arrived in the closing minutes, rescuing a point that
# looked lost (see LATE_GOAL_MINUTE).
DRAW_LATE_PHRASES = [
    "Regular, Celta, regular! Empate salvado no derradeiro intre!",
    "Regular, Celta, regular! Gol de última hora que evita a derrota!",
    "Regular, Celta, regular! Cando xa se daba por perdido, chegou a igualada!",
    "Regular, Celta, regular! Punto arrincado nos minutos finais!",
]

# --- LOSS categories --------------------------------------------------------
# Every phrase starts with: "Mal, Celta, mal!"

# Celta were ahead at half-time but ended up losing -- the worst kind.
LOSS_COLLAPSE_PHRASES = [
    "Mal, Celta, mal! Ían gañando e acabaron perdendo, golpe durísimo.",
    "Mal, Celta, mal! Desperdiciaron a vantaxe e pagárono caro.",
    "Mal, Celta, mal! A vitoria esfumouse antes do final.",
    "Mal, Celta, mal! De gañar a perder, final para esquecer.",
]

# Celta lost by 3 or more goals.
LOSS_BLOWOUT_PHRASES = [
    "Mal, Celta, mal! Goleada dolorosa, noite para esquecer.",
    "Mal, Celta, mal! Unha manita que doe moito.",
    "Mal, Celta, mal! Sen resposta ante un rival superior.",
    "Mal, Celta, mal! Derrota abultada que deixa tocada a afección.",
]

# Celta lost by exactly 1 goal.
LOSS_NARROW_PHRASES = [
    "Mal, Celta, mal! Derrota axustada que sabe amarga.",
    "Mal, Celta, mal! Perdeuse por un fío, pero perdeuse.",
    "Mal, Celta, mal! Tan preto e tan lonxe á vez.",
    "Mal, Celta, mal! Mínima, pero doe igual.",
]

# Any other loss (e.g. behind throughout, lost by 2) -- the general-purpose bank.
LOSS_STANDARD_PHRASES = [
    "Mal, Celta, mal! Noite negra para os celestes.",
    "Mal, Celta, mal! Queda o silencio, mágoa profunda.",
    "Mal, Celta, mal! Derrota dura que doe no fondo da alma celeste.",
    "Mal, Celta, mal! A tristeza invade o celtismo hoxe.",
]

# The decisive goal was conceded in the closing minutes -- the cruellest
# kind of loss (see LATE_GOAL_MINUTE).
LOSS_LATE_PHRASES = [
    "Mal, Celta, mal! Golpe no derradeiro minuto, moi doloroso.",
    "Mal, Celta, mal! Todo perdido nos últimos alentos do partido.",
    "Mal, Celta, mal! Mazazo de última hora que ninguén esperaba.",
    "Mal, Celta, mal! Tan preto de sumar, e esvarou nos minutos finais.",
]

# Celta lost after having a player sent off during the match.
LOSS_TEN_MEN_PHRASES = [
    "Mal, Celta, mal! A expulsión pesou demasiado nesta derrota.",
    "Mal, Celta, mal! Cun home menos foi imposible sacar algo positivo.",
    "Mal, Celta, mal! A vermella deixou ao equipo sen opcións.",
    "Mal, Celta, mal! Xogar cun home menos pasou factura hoxe.",
]

# Second loss in a row in the same competition.
LOSS_STREAK_2_PHRASES = [
    "Mal, Celta, mal! Segunda derrota seguida, malos tempos en Vigo.",
    "Mal, Celta, mal! Dúas sen gañar, hai que reaccionar.",
    "Mal, Celta, mal! Encadea a súa segunda derrota.",
    "Mal, Celta, mal! Van dúas seguidas, a preocupación medra.",
]

# Third (or more) loss in a row in the same competition.
LOSS_STREAK_3_PHRASES = [
    "Mal, Celta, mal! Terceira seguida, momento moi delicado.",
    "Mal, Celta, mal! Xa van varias sen gañar, preocupa e moito.",
    "Mal, Celta, mal! A mala racha non para, outra máis.",
    "Mal, Celta, mal! A crise de resultados segue, van xa varias caídas.",
]

# Eliminated on aggregate from a two-legged cup tie (Copa del Rey
# semifinal, Europa League knockout rounds) -- see select_category() in
# main.py. This is about the tie as a whole, not necessarily this leg's
# own scoreline -- Celta could even have won this specific leg and still
# be eliminated on aggregate.
LOSS_ELIMINATED_PHRASES = [
    "Mal, Celta, mal! Eliminados na eliminatoria!",
    "Mal, Celta, mal! Adeus á competición, non deu para máis.",
    "Mal, Celta, mal! O global da eliminatoria deixa fóra ao Celta.",
    "Mal, Celta, mal! O soño remata aquí.",
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
    "WIN_TEN_MEN": WIN_TEN_MEN_PHRASES,
    "WIN_STREAK_2": WIN_STREAK_2_PHRASES,
    "WIN_STREAK_3": WIN_STREAK_3_PHRASES,
    "WIN_ADVANCED_ROUND": WIN_ADVANCED_ROUND_PHRASES,
    "DRAW_RALLY": DRAW_RALLY_PHRASES,
    "DRAW_SQUANDERED": DRAW_SQUANDERED_PHRASES,
    "DRAW_FLAT": DRAW_FLAT_PHRASES,
    "DRAW_LATE": DRAW_LATE_PHRASES,
    "LOSS_COLLAPSE": LOSS_COLLAPSE_PHRASES,
    "LOSS_BLOWOUT": LOSS_BLOWOUT_PHRASES,
    "LOSS_NARROW": LOSS_NARROW_PHRASES,
    "LOSS_STANDARD": LOSS_STANDARD_PHRASES,
    "LOSS_LATE": LOSS_LATE_PHRASES,
    "LOSS_TEN_MEN": LOSS_TEN_MEN_PHRASES,
    "LOSS_STREAK_2": LOSS_STREAK_2_PHRASES,
    "LOSS_STREAK_3": LOSS_STREAK_3_PHRASES,
    "LOSS_ELIMINATED": LOSS_ELIMINATED_PHRASES,
}


def get_random_phrase(category):
    """
    Return a random phrase (a plain string) for the given category.

    category must be one of the keys in the PHRASES dict above -- see
    classify_match() in main.py for how a match gets mapped to one.
    """
    return random.choice(PHRASES[category])


# --- La Liga table-position phrases -----------------------------------------
#
# These are a completely separate system from PHRASES/get_random_phrase()
# above: they're an extra trailing sentence describing where Celta
# currently sits in the La Liga table (see _la_liga_table_zone() and
# _format_table_position_note() in main.py), added after EVERY La Liga
# result -- not a category picked for the result itself, so they do NOT
# follow the "Ben, Celta, ben!"/"Regular, Celta, regular!"/"Mal, Celta,
# mal!" fixed-opener rule that PHRASES' categories do. Deliberately no
# position number in any of these -- just the zone description.
#
# Each zone has three tone variants, keyed by this match's own outcome:
# "WIN" phrases lean optimistic (even a fairly ordinary table spot reads
# more hopefully off the back of a win), "LOSS" phrases lean pessimistic
# (even a decent spot reads more anxiously off the back of a loss), and
# "DRAW" phrases stay neutral, just describing the zone. This is about
# *tone*, not content -- the zone itself (which of the two is used to
# pick from) still reflects the actual, current table position
# independent of the outcome; see _format_table_position_note().
TABLE_POSITION_PHRASES = {
    # Top LA_LIGA_EUROPEAN_POSITIONS.
    "EUROPEAN": {
        "WIN": [
            "Reafírmase con forza en posicións europeas!",
            "Vitoria que consolida ao Celta entre os mellores!",
            "O soño europeo faise cada vez máis forte!",
        ],
        "LOSS": [
            "Aínda en Europa, pero esta derrota acende as alarmas.",
            "O posto europeo tambalea tras esta derrota.",
            "Malos síntomas para un Celta que quere seguir en Europa.",
        ],
        "DRAW": [
            "Segue instalado en posicións europeas.",
            "Mantense entre os postos que dan acceso a Europa.",
            "Continúa na zona europea da táboa.",
        ],
    },
    # Just below the European positions.
    "NEAR_EUROPEAN": {
        "WIN": [
            "Cada vez máis preto de Europa!",
            "Achégase aínda máis á zona europea!",
            "O sprint cara Europa colle forza!",
        ],
        "LOSS": [
            "Esta derrota aleixa ao Celta de Europa.",
            "Oportunidade perdida para achegarse á zona europea.",
            "O soño europeo compícase un pouco máis.",
        ],
        "DRAW": [
            "Achégase ás posicións europeas.",
            "Está a un paso de entrar en Europa.",
            "Ronda a zona europea da clasificación.",
        ],
    },
    # Comfortably clear of both zones.
    "MID_TABLE": {
        "WIN": [
            "Vitoria que reforza unha posición cómoda!",
            "Suma e mira cara arriba na táboa!",
            "Bo momento para un Celta instalado na zona media!",
        ],
        "LOSS": [
            "Segue na zona media, pero esta derrota non axuda.",
            "Non compromete, pero tampouco axuda a medrar.",
            "Estanca na zona media tras esta derrota.",
        ],
        "DRAW": [
            "Segue instalado na zona media da táboa.",
            "Mantense en terreo tranquilo na clasificación.",
            "Lonxe, por agora, tanto de Europa coma do descenso.",
        ],
    },
    # Just above the relegation zone.
    "NEAR_RELEGATION": {
        "WIN": [
            "Vitoria importante que afasta ao Celta do descenso!",
            "Respira tras unha vitoria que sabe case a salvación!",
            "Tres puntos clave para escapar dos postos baixos!",
        ],
        "LOSS": [
            "Esta derrota achégao perigosamente ao descenso.",
            "As alarmas soan cada vez máis forte.",
            "Queda a un paso do descenso tras esta derrota.",
        ],
        "DRAW": [
            "Achégase perigosamente á zona de descenso.",
            "Ronda uns postos baixos que preocupan.",
            "Bota unha ollada cara atrás, preto do descenso.",
        ],
    },
    # Bottom LA_LIGA_RELEGATION_ZONE_SIZE.
    "RELEGATION": {
        "WIN": [
            "Vitoria clave para saír do descenso!",
            "Un triunfo que devolve a esperanza!",
            "Engánchase á loita pola permanencia!",
        ],
        "LOSS": [
            "Afúndese aínda máis nos postos de descenso.",
            "Malos números que agravan a situación.",
            "A crise na loita polo descenso non para.",
        ],
        "DRAW": [
            "Segue instalado en posicións de descenso.",
            "Continúa metido na zona vermella da táboa.",
            "Non sae dos postos de descenso.",
        ],
    },
}


def get_random_table_phrase(zone, outcome):
    """
    Return a random La Liga table-position sentence for the given zone,
    toned to match this match's own outcome (optimistic for a WIN,
    pessimistic for a LOSS, neutral for a DRAW).

    zone must be one of the keys in TABLE_POSITION_PHRASES above -- see
    _la_liga_table_zone() in main.py for how a table position gets
    mapped to one. outcome must be "WIN", "LOSS", or "DRAW".
    """
    return random.choice(TABLE_POSITION_PHRASES[zone][outcome])
