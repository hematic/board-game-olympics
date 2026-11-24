from dataclasses import dataclass
from time import sleep
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from xml.etree import ElementTree

from django.conf import settings


class BGGError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class SearchResult:
    id: int
    title: str
    year: int | None
    min_players: int | None = None
    max_players: int | None = None


def fetch(endpoint: str, **params):
    if not settings.BGG_API_TOKEN:
        raise BGGError("BoardGameGeek is not configured. Set BGG_API_TOKEN or enter a game manually.")
    url = f"https://boardgamegeek.com/xmlapi2/{endpoint}?{urlencode(params)}"
    request = Request(url, headers={"Authorization": f"Bearer {settings.BGG_API_TOKEN}"})
    try:
        with build_opener(NoRedirect).open(request, timeout=5) as response:
            if response.status != 200:
                raise BGGError("BoardGameGeek is not ready to serve this request. Try again shortly.")
            data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise BGGError("BoardGameGeek returned an unsupported response.")
        xml = data.decode("utf-8-sig")
        if "<!DOCTYPE" in xml.upper() or "\0" in xml:
            raise BGGError("BoardGameGeek returned an unsupported response.")
        return ElementTree.fromstring(xml)
    except (OSError, UnicodeError, ElementTree.ParseError) as error:
        raise BGGError("Could not read BoardGameGeek. Check the API token or try again later.") from error


def number(node, tag):
    item = node.find(tag)
    value = item.get("value", "") if item is not None else ""
    return int(value) if value.isascii() and value.isdigit() and len(value) <= 5 and 0 < int(value) <= 32767 else None


def search(query: str, players: int | None = None) -> list[SearchResult]:
    results = []
    for node in fetch("search", query=query, type="boardgame").findall("item")[:30]:
        name = node.find("name")
        game_id = node.get("id", "")
        if name is not None and game_id.isascii() and game_id.isdigit() and len(game_id) <= 9:
            results.append(SearchResult(int(game_id), name.get("value", ""), number(node, "yearpublished")))
    if players is None or not results:
        return results
    player_ranges = {}
    for start in range(0, len(results), 20):
        batch = results[start:start + 20]
        sleep(5)
        nodes = fetch("thing", id=",".join(str(item.id) for item in batch))
        for item in batch:
            node = nodes.find(f"item[@id='{item.id}']")
            if node is None:
                raise BGGError("BoardGameGeek did not return all player counts. Try again shortly.")
            if node.get("type") == "boardgame":
                player_ranges[item.id] = (number(node, "minplayers"), number(node, "maxplayers"))
    filtered = []
    for item in results:
        low, high = player_ranges.get(item.id, (None, None))
        if low is not None and high is not None and low <= players <= high:
            filtered.append(SearchResult(item.id, item.title, item.year, low, high))
    return filtered


def details(game_id: int):
    node = fetch("thing", id=game_id).find("item")
    if node is None or node.get("id") != str(game_id) or node.get("type") != "boardgame":
        raise BGGError("No matching board game was returned.")
    name = node.find("name[@type='primary']")
    title = name.get("value", "") if name is not None else ""
    if not title or len(title) > 255:
        raise BGGError("BoardGameGeek returned an invalid game title.")
    return {
        "title": title,
        "year": number(node, "yearpublished"),
        "description": node.findtext("description", default=""),
        "min_players": number(node, "minplayers"),
        "max_players": number(node, "maxplayers"),
        "playing_time": number(node, "playingtime"),
    }
