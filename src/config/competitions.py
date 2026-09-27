"""Competition registry. Each competition drives a parallel pipeline:
team matching, ESPN fixture polling, deduplication scope, Discord embed branding."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Competition:
    id: str
    name: str
    espn_league: str
    color: int
    logo: str
    schedule_title: str


EPL = Competition(
    id="epl",
    name="Premier League",
    espn_league="eng.1",
    color=0x37003C,
    logo="https://resources.premierleague.com/premierleague/competitions/competition_1_small.png",
    schedule_title="Premier League",
)


_REGISTRY: dict[str, Competition] = {
    EPL.id: EPL,
}


def list_competitions() -> list[Competition]:
    return list(_REGISTRY.values())


def get_competition(comp_id: str) -> Competition:
    return _REGISTRY[comp_id]
