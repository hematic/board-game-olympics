from itertools import groupby

from django.db.models import Sum

from .models import Edition, Nomination, Voter


def close_voting(edition: Edition) -> None:
    nominations = {game.pk: game for game in edition.nomination_set.select_related("edition")}
    width = min(edition.slots, len(nominations))
    for game in nominations.values():
        game.vote_breakdown = [0] * width
    for ranking in edition.voter_set.exclude(ranking__isnull=True).values_list("ranking", flat=True):
        for index, game_id in enumerate(ranking):
            nominations[game_id].vote_breakdown[index] += 1

    def key(game: Nomination):
        return game.total_votes, game.vote_breakdown

    remaining = edition.slots
    edition.phase = Edition.Phase.PLAY
    for _, tied in groupby(sorted(nominations.values(), key=key, reverse=True), key=key):
        group = list(tied)
        if remaining == 0:
            break
        if remaining < len(group):
            for game in group:
                game.cutoff_tied = True
            edition.phase = Edition.Phase.CUTOFF
            break
        for game in group:
            game.selected = True
        remaining -= len(group)
    Nomination.objects.bulk_update(nominations.values(), ["vote_breakdown", "selected", "cutoff_tied"])
    edition.save(update_fields=["phase"])


def revealed_ballots(edition: Edition):
    titles = dict(edition.nomination_set.values_list("pk", "title"))
    return [
        (voter.name, [
            (titles[game_id], edition.slots - index)
            for index, game_id in enumerate(voter.ranking)
        ] if voter.ranking is not None else None)
        for voter in edition.voter_set.order_by("name", "pk")
    ]


def standings(edition: Edition):
    ordered = edition.competitor_set.annotate(total=Sum("result__points", default=0)).order_by(
        "-total", "name", "pk"
    )
    rows = []
    rank = 1
    for total, group in groupby(ordered, key=lambda person: person.total):
        people = list(group)
        rows.extend((rank, person.name, total) for person in people)
        rank += len(people)
    return rows


def turnout(edition: Edition) -> int:
    return Voter.objects.filter(edition=edition, ranking__isnull=False).count()
