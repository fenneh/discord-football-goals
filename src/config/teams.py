"""Team configuration. Per-competition team dicts are routed via
get_teams_for_competition(); legacy `premier_league_teams` is preserved
for code that still imports it directly."""

from src.config.competitions import EPL

# Premier League teams and their aliases
premier_league_teams = {
    "Arsenal": {
        "name": "Arsenal",
        "aliases": ["Arsenal", "The Arsenal", "The Gunners"],
        "color": 0xFF0000,  # Red
        "logo": "https://resources.premierleague.com/premierleague/badges/t3.png",
    },
    "Aston Villa": {
        "name": "Aston Villa",
        "aliases": ["Aston Villa", "Villa"],
        "color": 0x95BFE5,  # Claret
        "logo": "https://resources.premierleague.com/premierleague/badges/t7.png",
    },
    "Bournemouth": {
        "name": "Bournemouth",
        "aliases": ["Bournemouth", "AFC Bournemouth", "The Cherries"],
        "color": 0xDA291C,  # Red
        "logo": "https://resources.premierleague.com/premierleague/badges/t91.png",
    },
    "Brentford": {
        "name": "Brentford",
        "aliases": ["Brentford", "The Bees"],
        "color": 0xE30613,  # Red
        "logo": "https://resources.premierleague.com/premierleague/badges/t94.png",
    },
    "Brighton": {
        "name": "Brighton",
        "aliases": [
            "Brighton",
            "Brighton & Hove Albion",
            "Brighton and Hove Albion",
            "The Seagulls",
        ],
        "color": 0x0057B8,  # Blue
        "logo": "https://resources.premierleague.com/premierleague/badges/t36.png",
    },
    "Chelsea": {
        "name": "Chelsea",
        "aliases": ["Chelsea", "The Blues", "CFC"],
        "color": 0x034694,  # Blue
        "logo": "https://resources.premierleague.com/premierleague/badges/t8.png",
    },
    "Crystal Palace": {
        "name": "Crystal Palace",
        "aliases": ["Crystal Palace", "Palace", "The Eagles", "CPFC"],
        "color": 0x1B458F,  # Blue
        "logo": "https://resources.premierleague.com/premierleague/badges/t31.png",
    },
    "Coventry City": {
        "name": "Coventry City",
        "aliases": ["Coventry City", "Coventry", "The Sky Blues", "CCFC"],
        "color": 0x69B3E7,
        "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/388.png",
    },
    "Everton": {
        "name": "Everton",
        "aliases": ["Everton", "The Toffees", "EFC"],
        "color": 0x003399,  # Blue
        "logo": "https://resources.premierleague.com/premierleague/badges/t11.png",
    },
    "Fulham": {
        "name": "Fulham",
        "aliases": ["Fulham", "The Cottagers", "FFC"],
        "color": 0xFFFFFF,  # White
        "logo": "https://resources.premierleague.com/premierleague/badges/t54.png",
    },
    "Hull City": {
        "name": "Hull City",
        "aliases": ["Hull City", "Hull", "The Tigers", "HCFC"],
        "color": 0xF5A12D,
        "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/306.png",
    },
    "Ipswich Town": {
        "name": "Ipswich Town",
        "aliases": ["Ipswich Town", "Ipswich", "The Tractor Boys", "ITFC"],
        "color": 0x0033AA,
        "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/373.png",
    },
    "Leeds United": {
        "name": "Leeds United",
        "aliases": ["Leeds", "Leeds United", "Leeds Utd", "The Whites", "LUFC"],
        "color": 0xFFFFFF,  # White
        "logo": "https://resources.premierleague.com/premierleague/badges/t2.png",
    },
    "Liverpool": {
        "name": "Liverpool",
        "aliases": ["Liverpool", "The Reds", "LFC"],
        "color": 0xC8102E,  # Red
        "logo": "https://resources.premierleague.com/premierleague/badges/t14.png",
    },
    "Manchester City": {
        "name": "Manchester City",
        "aliases": ["Manchester City", "Man City", "MCFC", "Man C"],
        "color": 0x6CABDD,  # Sky Blue
        "logo": "https://resources.premierleague.com/premierleague/badges/t43.png",
    },
    "Manchester United": {
        "name": "Manchester United",
        "aliases": [
            "Manchester United",
            "Manchester Utd",
            "Man United",
            "Man Utd",
            "MUFC",
            "Man U",
        ],
        "color": 0xDA291C,  # Red
        "logo": "https://resources.premierleague.com/premierleague/badges/t1.png",
    },
    "Newcastle": {
        "name": "Newcastle United",
        "aliases": [
            "Newcastle",
            "Newcastle Utd",
            "Newcastle United",
            "The Magpies",
            "NUFC",
        ],
        "color": 0x241F20,  # Black
        "logo": "https://resources.premierleague.com/premierleague/badges/t4.png",
    },
    "Nottingham Forest": {
        "name": "Nottingham Forest",
        "aliases": ["Nottingham Forest", "Nottingham", "Forest", "NFFC", "Nott'm Forest"],
        "color": 0xDD0000,  # Red
        "logo": "https://resources.premierleague.com/premierleague/badges/t17.png",
    },
    "Sunderland": {
        "name": "Sunderland",
        "aliases": ["Sunderland", "The Black Cats", "SAFC"],
        "color": 0xEB172B,  # Red
        "logo": "https://resources.premierleague.com/premierleague/badges/t56.png",
    },
    "Tottenham": {
        "name": "Tottenham Hotspur",
        "aliases": ["Tottenham", "Tottenham Hotspur", "Spurs", "THFC"],
        "color": 0x132257,  # Navy Blue
        "logo": "https://resources.premierleague.com/premierleague/badges/t6.png",
    },
}


_TEAMS_BY_COMPETITION = {
    EPL.id: premier_league_teams,
}


def get_teams_for_competition(comp_id: str) -> dict:
    return _TEAMS_BY_COMPETITION[comp_id]
