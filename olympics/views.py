from django import forms
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe

from . import bgg, competition
from .forms import BallotForm, EditionForm, GameForm, ResultsForm, ScoringForm
from .models import Competitor, Edition, Game, Member, Nomination, Result, Voter

Phase = Edition.Phase


def organizer(request):
    if not request.member.is_organizer:
        raise PermissionDenied


def get_edition(request, year):
    edition = get_object_or_404(Edition, year=year)
    if edition.phase == Phase.DRAFT and not request.member.is_organizer:
        raise Http404
    return edition


def build_form(fields, data=None, initial=None):
    form = forms.Form(data, initial=initial)
    form.fields.update(fields)
    return form


def form_page(request, title, form, **context):
    return render(request, "olympics/form.html", {"title": title, "form": form, **context})


@require_safe
def home(request: HttpRequest) -> HttpResponse:
    editions = Edition.objects.all()
    if not request.member.is_organizer:
        editions = editions.exclude(phase=Phase.DRAFT)
    return render(request, "olympics/home.html", {
        "organizer": request.member.is_organizer, "editions": editions,
    })


@require_safe
def health(request: HttpRequest) -> HttpResponse:
    return HttpResponse("ok\n", content_type="text/plain")


@require_http_methods(["GET", "POST"])
def create_edition(request):
    organizer(request)
    form = EditionForm(request.POST if request.method == "POST" else None)
    if form.is_valid():
        return redirect("edition", year=form.save().year)
    return form_page(request, "New edition", form)


@require_safe
def edition_page(request, year):
    edition = get_edition(request, year)
    is_organizer = request.member.is_organizer
    revealed = not edition.historical and edition.phase in {Phase.CUTOFF, Phase.PLAY, Phase.ARCHIVED}
    games = list(edition.nomination_set.select_related("game", "edition").prefetch_related(
        "result_set__competitor"
    ))
    if revealed:
        games.sort(key=lambda game: (game.total_votes, game.vote_breakdown), reverse=True)
    return render(request, "olympics/edition.html", {
        "edition": edition,
        "organizer": is_organizer,
        "games": games,
        "revealed": revealed,
        "ballots": competition.revealed_ballots(edition) if revealed else [],
        "turnout": competition.turnout(edition) if is_organizer and edition.phase == Phase.OPEN else None,
        "eligible": edition.voter_set.count() if is_organizer else None,
        "can_vote": edition.phase == Phase.OPEN and edition.voter_set.filter(member=request.member).exists(),
        "standings": competition.standings(edition),
    })


@require_http_methods(["GET", "POST"])
@transaction.atomic
def manage_edition(request, year, action):
    organizer(request)
    edition = get_edition(request, year)
    data = request.POST if request.method == "POST" else None
    nominees = edition.nomination_set.all()
    if edition.phase == Phase.DRAFT and action == "setup":
        form = build_form({
            "slots": forms.IntegerField(min_value=1, max_value=50),
            "history_notes": forms.CharField(required=False, widget=forms.Textarea),
        }, data, {"slots": edition.slots, "history_notes": edition.history_notes})
        if form.is_valid():
            edition.slots = form.cleaned_data["slots"]
            edition.history_notes = form.cleaned_data["history_notes"]
            edition.save(update_fields=["slots", "history_notes"])
    elif edition.phase == Phase.DRAFT and action == "voters" and not edition.historical:
        form = build_form({
            "members": forms.ModelMultipleChoiceField(
                Member.objects.filter(issuer=request.member.issuer).order_by("display_name", "pk"),
                widget=forms.CheckboxSelectMultiple, required=False,
                help_text="Invitees appear here after they sign in for the first time.",
            ),
        }, data, {"members": list(edition.voters.values_list("pk", flat=True))})
        if form.is_valid():
            edition.voter_set.all().delete()
            Voter.objects.bulk_create([
                Voter(edition=edition, member=member, name=str(member))
                for member in form.cleaned_data["members"]
            ])
    elif edition.phase == Phase.DRAFT and action == "competitors":
        form = build_form({
            "names": forms.CharField(widget=forms.Textarea, max_length=10000, help_text="One name per line."),
        }, data, {"names": "\n".join(edition.competitor_set.values_list("name", flat=True))})
        if form.is_valid():
            names = [name.strip() for name in form.cleaned_data["names"].splitlines() if name.strip()]
            if not names or len(names) != len(set(names)) or any(len(name) > 255 for name in names):
                form.add_error("names", "Enter distinct names, each at most 255 characters.")
            else:
                edition.competitor_set.all().delete()
                Competitor.objects.bulk_create([Competitor(edition=edition, name=name) for name in names])
    elif edition.phase == Phase.DRAFT and action == "nominees":
        form = build_form({
            "games": forms.ModelMultipleChoiceField(Game.objects.all(), widget=forms.CheckboxSelectMultiple,
                                                    required=False),
        }, data, {"games": list(nominees.values_list("game_id", flat=True))})
        if form.is_valid():
            games = list(form.cleaned_data["games"])
            nominees.exclude(game__in=games).delete()
            for game in games:
                edition.nomination_set.get_or_create(
                    game=game, defaults={"title": str(game), "selected": edition.historical},
                )
    elif edition.phase == Phase.DRAFT and action == "start":
        label = "Lock the historical lineup" if edition.historical else "Open voting"
        form = build_form({}, data)
        if form.is_valid():
            if not nominees.exists() or not edition.competitor_set.exists() or (
                not edition.historical and not edition.voters.exists()
            ):
                form.add_error(None, "Set the lineup and competitors, plus eligible voters for a live edition.")
            else:
                edition.phase = Phase.PLAY if edition.historical else Phase.OPEN
                edition.save(update_fields=["phase"])
        action = label
    elif edition.phase == Phase.OPEN and action == "close":
        form = build_form({}, data)
        if form.is_valid():
            competition.close_voting(edition)
    elif edition.phase == Phase.CUTOFF and action == "cutoff":
        needed = edition.slots - nominees.filter(selected=True).count()
        tied = nominees.filter(cutoff_tied=True)
        form = build_form({
            "games": forms.ModelMultipleChoiceField(
                tied, widget=forms.CheckboxSelectMultiple, label=f"Choose exactly {needed}"
            ),
            "reason": forms.CharField(widget=forms.Textarea, max_length=2000),
        }, data)
        if form.is_valid():
            games = form.cleaned_data["games"]
            if len(games) != needed:
                form.add_error("games", f"Choose exactly {needed} games.")
            else:
                tied.filter(pk__in=[game.pk for game in games]).update(selected=True)
                edition.cutoff_reason = form.cleaned_data["reason"]
                edition.phase = Phase.PLAY
                edition.save(update_fields=["cutoff_reason", "phase"])
    elif edition.phase == Phase.PLAY and action == "archive":
        form = build_form({}, data)
        if form.is_valid():
            if not edition.historical and nominees.filter(selected=True, scored=False).exists():
                form.add_error(None, "Record results for every selected game before archiving.")
            else:
                edition.phase = Phase.ARCHIVED
                edition.save(update_fields=["phase"])
    else:
        raise Http404("That action is not available in this phase.")
    if form.is_bound and not form.errors:
        return redirect("edition", year=year)
    hint = "Closing is final. All signed-in members will be able to see the named ballots." if action == "close" else ""
    return form_page(request, f"{year}: {action.replace('-', ' ').capitalize()}", form,
                     edition=edition, hint=hint)


@require_http_methods(["GET", "POST"])
@transaction.atomic
def ballot(request, year):
    edition = get_edition(request, year)
    if edition.phase != Phase.OPEN:
        raise Http404("Voting is not open.")
    voter = get_object_or_404(edition.voter_set, member=request.member)
    initial = {f"rank_{index}": game for index, game in enumerate(voter.ranking or [], 1)}
    form = BallotForm(
        list(edition.nomination_set.all()), edition.slots,
        request.POST if request.method == "POST" else None, initial=initial,
    )
    if form.is_valid():
        voter.ranking = list(form.cleaned_data.values())
        voter.save(update_fields=["ranking"])
        return redirect("ballot", year=year)
    return form_page(request, "Your ranked ballot", form, edition=edition, hint=(
        "You can replace your ballot until voting closes. After close, all signed-in members "
        "can see your name and rankings. Your ballot is saved." if voter.ranking else
        "After the vote closes, all signed-in members can see your name and rankings."
    ))


@require_http_methods(["GET", "POST"])
@transaction.atomic
def manage_game(request, year, pk, action):
    organizer(request)
    edition = get_edition(request, year)
    if edition.phase != Phase.PLAY:
        raise Http404
    game = get_object_or_404(edition.nomination_set, pk=pk, selected=True)
    data = request.POST if request.method == "POST" else None
    hint = ""
    if action == "scoring" and not game.scored:
        form = ScoringForm(data, initial={"mode": game.mode, "awards": ", ".join(map(str, game.awards))})
        if form.is_valid():
            game.mode = form.cleaned_data["mode"]
            game.awards = form.cleaned_data["awards"]
            game.save(update_fields=["mode", "awards"])
    elif action == "results" and game.awards:
        hint = "Leave a competitor blank if they did not play or their placement is unknown."
        initial = {str(record.competitor_id): record.place for record in game.result_set.all()}
        form = ResultsForm(list(edition.competitor_set.all()), data, initial=initial,
                           historical=edition.historical)
        if form.is_valid():
            game.result_set.all().delete()
            Result.objects.bulk_create([
                Result(nomination=game, competitor_id=int(person), place=place,
                       points=game.awards[place - 1] if place <= len(game.awards) else 0)
                for person, place in form.cleaned_data.items() if place is not None
            ])
            game.scored = True
            game.save(update_fields=["scored"])
    elif action == "historical-votes" and edition.historical:
        hint = "Enter any known named votes in their original format. Note gaps explicitly."
        form = build_form({
            "votes": forms.CharField(widget=forms.Textarea, max_length=10000, required=False),
        }, data, {"votes": game.historical_votes})
        if form.is_valid():
            game.historical_votes = form.cleaned_data["votes"]
            game.save(update_fields=["historical_votes"])
    else:
        raise Http404
    if form.is_bound and not form.errors:
        return redirect("edition", year=year)
    return form_page(request, f"{game.title}: {action.replace('-', ' ')}", form, edition=edition, hint=hint)


@require_safe
def catalog(request):
    return render(request, "olympics/catalog.html", {
        "games": Game.objects.all(), "organizer": request.member.is_organizer,
    })


@require_safe
def game_detail(request, pk):
    game = get_object_or_404(Game, pk=pk)
    history = game.nomination_set.filter(edition__phase=Phase.ARCHIVED).select_related(
        "edition"
    ).prefetch_related("result_set__competitor").order_by("-edition__year")
    archived = []
    for entry in history:
        votes = None
        if not entry.edition.historical:
            votes = []
            for voter in entry.edition.voter_set.order_by("name", "pk"):
                ranking = voter.ranking
                if ranking is None:
                    vote = "Abstained"
                elif entry.pk in ranking:
                    index = ranking.index(entry.pk)
                    vote = f"Rank {index + 1} ({entry.edition.slots - index} points)"
                else:
                    vote = "Unranked"
                votes.append((voter.name, vote))
        archived.append((entry, votes))
    return render(request, "olympics/game.html", {
        "game": game, "history": archived, "organizer": request.member.is_organizer,
    })


@require_http_methods(["GET", "POST"])
def edit_game(request, pk=None):
    organizer(request)
    game = get_object_or_404(Game, pk=pk) if pk is not None else None
    form = GameForm(request.POST if request.method == "POST" else None, instance=game)
    if game is not None and game.bgg_id:
        for field in ("title", "year", "min_players", "max_players", "playing_time"):
            form.fields[field].disabled = True
    if form.is_valid():
        return redirect("game", pk=form.save().pk)
    return form_page(request, "Edit game" if game else "Add game manually", form)


@require_http_methods(["GET", "POST"])
def bgg_search(request):
    organizer(request)
    results = []
    error = ""
    query = request.GET.get("q", "").strip()
    if request.method == "POST":
        form = build_form({"id": forms.IntegerField(min_value=1, max_value=999999999)}, request.POST)
        if not form.is_valid():
            error = "Choose a valid BoardGameGeek game to import."
        else:
            game_id = form.cleaned_data["id"]
            try:
                game = Game.objects.filter(bgg_id=game_id).first()
                if game is None:
                    game, _ = Game.objects.get_or_create(bgg_id=game_id, defaults=bgg.details(game_id))
                return redirect("game", pk=game.pk)
            except bgg.BGGError as failure:
                error = str(failure)
    elif query:
        if len(query) > 100:
            error = "Searches must be at most 100 characters."
        else:
            try:
                results = bgg.search(query)
            except bgg.BGGError as failure:
                error = str(failure)
    return render(request, "olympics/bgg.html", {"results": results, "query": query, "error": error})
