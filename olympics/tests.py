from io import StringIO
from unittest.mock import patch
from xml.etree import ElementTree

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from . import bgg, competition
from .models import Edition, Game, Member, Result, Voter


class BGGSearchTests(SimpleTestCase):
    @patch("olympics.bgg.sleep")
    @patch("olympics.bgg.fetch")
    def test_player_filter_includes_boundaries_and_excludes_unknown_ranges(self, fetch, sleep):
        fetch.side_effect = [
            ElementTree.fromstring(
                '<items>' + ''.join(
                    f'<item id="{game_id}"><name value="Game {game_id}"/></item>'
                    for game_id in range(1, 8)
                ) + '</items>'
            ),
            ElementTree.fromstring(
                '<items>'
                '<item id="1" type="boardgame"><minplayers value="4"/><maxplayers value="6"/></item>'
                '<item id="2" type="boardgame"><minplayers value="2"/><maxplayers value="4"/></item>'
                '<item id="3" type="boardgame"><minplayers value="1"/><maxplayers value="3"/></item>'
                '<item id="4" type="boardgame"><minplayers value="5"/><maxplayers value="8"/></item>'
                '<item id="5" type="boardgame"><minplayers value="2"/></item>'
                '<item id="6" type="boardgame"><minplayers value="unknown"/><maxplayers value="6"/></item>'
                '<item id="7" type="boardgameexpansion"><minplayers value="2"/><maxplayers value="6"/></item>'
                '</items>'
            ),
        ]
        results = bgg.search("Game", players=4)
        self.assertEqual([(item.id, item.min_players, item.max_players) for item in results],
                         [(1, 4, 6), (2, 2, 4)])
        self.assertEqual(fetch.call_args.kwargs, {"id": "1,2,3,4,5,6,7"})
        sleep.assert_called_once_with(5)

    @patch("olympics.bgg.sleep")
    @patch("olympics.bgg.fetch")
    def test_filtered_search_batches_at_most_twenty_and_checks_first_thirty(self, fetch, sleep):
        fetch.side_effect = [
            ElementTree.fromstring(
                '<items>' + ''.join(
                    f'<item id="{game_id}"><name value="Game {game_id}"/></item>'
                    for game_id in range(1, 36)
                ) + '</items>'
            ),
            *[
                ElementTree.fromstring(
                    '<items>' + ''.join(
                        f'<item id="{game_id}" type="boardgame">'
                        '<minplayers value="2"/><maxplayers value="4"/></item>'
                        for game_id in game_ids
                    ) + '</items>'
                )
                for game_ids in (range(1, 21), range(21, 31))
            ],
        ]
        results = bgg.search("Game", players=3)
        self.assertEqual([item.id for item in results], list(range(1, 31)))
        self.assertEqual(
            [call.kwargs["id"] for call in fetch.call_args_list[1:]],
            [",".join(map(str, range(1, 21))), ",".join(map(str, range(21, 31)))],
        )
        self.assertEqual(sleep.call_count, 2)

    @patch("olympics.bgg.sleep")
    @patch("olympics.bgg.fetch")
    def test_unfiltered_and_empty_searches_do_not_fetch_details(self, fetch, sleep):
        fetch.side_effect = [
            ElementTree.fromstring('<items><item id="42"><name value="Example"/></item></items>'),
            ElementTree.fromstring('<items/>'),
        ]
        self.assertEqual(bgg.search("Example"), [bgg.SearchResult(42, "Example", None)])
        self.assertEqual(bgg.search("Missing", players=4), [])
        self.assertEqual(fetch.call_count, 2)
        sleep.assert_not_called()

    @patch("olympics.bgg.sleep")
    @patch("olympics.bgg.fetch")
    def test_missing_details_and_api_failures_are_not_reported_as_no_matches(self, fetch, sleep):
        for response in (ElementTree.fromstring('<items/>'), bgg.BGGError("Try again later.")):
            with self.subTest(response=response):
                fetch.side_effect = [
                    ElementTree.fromstring('<items><item id="42"><name value="Example"/></item></items>'),
                    response,
                ]
                with self.assertRaises(bgg.BGGError):
                    bgg.search("Example", players=4)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class OrganizerBootstrapTests(TestCase):
    def bootstrap(self, username="", password=""):
        with patch.dict("os.environ", {
            "OLYMPICS_ORGANIZER_USERNAME": username,
            "OLYMPICS_ORGANIZER_PASSWORD": password,
        }):
            call_command("bootstrap_organizer", stdout=StringIO())

    def test_creates_first_organizer_without_overwriting_on_restart(self):
        self.bootstrap("host", "initial-family-passphrase")
        self.bootstrap("another-host", "changed-family-passphrase")
        self.bootstrap()
        organizer = User.objects.get()
        self.assertEqual(organizer.username, "host")
        self.assertTrue(organizer.is_active and organizer.is_superuser)
        self.assertTrue(organizer.check_password("initial-family-passphrase"))

    def test_missing_weak_or_colliding_credentials_do_not_create_an_organizer(self):
        with self.assertRaisesMessage(CommandError, "Set OLYMPICS_ORGANIZER_USERNAME"):
            self.bootstrap("host")
        with self.assertRaisesMessage(CommandError, "Invalid organizer credentials"):
            self.bootstrap("host", "123")
        family = User.objects.create_user("family", password="previous-family-passphrase")
        with self.assertRaisesMessage(CommandError, "Invalid organizer credentials"):
            self.bootstrap("FAMILY", "changed-family-passphrase")
        family.refresh_from_db()
        self.assertFalse(family.is_superuser)
        self.assertTrue(family.check_password("previous-family-passphrase"))
        self.assertEqual(User.objects.count(), 1)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class LocalAccountTests(TestCase):
    def test_proxy_headers_no_longer_grant_access(self):
        response = self.client.get("/games/", secure=True, headers={"Remote-Sub": "organizer-id"})
        self.assertRedirects(response, "/login/?next=/games/", fetch_redirect_response=False)
        self.assertFalse(Member.objects.exists())

    def test_organizer_creates_account_and_links_previous_ballot(self):
        organizer = User.objects.create_superuser("organizer", password="start-organizer-pass")
        legacy = Member.objects.create(issuer="https://id.example.invalid", subject="legacy", display_name="Pat")
        edition = Edition.objects.create(year=2027, slots=1, phase=Edition.Phase.OPEN)
        game = Game.objects.create(title="Legacy ballot game")
        nominee = edition.nomination_set.create(game=game, title=game.title)
        edition.voter_set.create(member=legacy, name="Pat", ranking=[nominee.pk])
        self.client.force_login(organizer)
        self.assertContains(self.client.get("/accounts/", secure=True), "Create an account")
        self.assertRedirects(self.client.post("/accounts/new/", {
            "username": "pat", "password1": "an-initial-family-pass",
            "password2": "an-initial-family-pass", "existing_member": legacy.pk,
        }, secure=True), "/accounts/", fetch_redirect_response=False)
        legacy.refresh_from_db()
        self.assertEqual(legacy.user.username, "pat")
        family = Client(enforce_csrf_checks=True)
        self.assertEqual(family.post("/login/", {}, secure=True).status_code, 403)
        self.assertContains(family.get("/login/", secure=True), "Sign in")
        csrf = family.cookies["csrftoken"].value
        self.assertEqual(family.post("/login/", {
            "username": "pat", "password": "an-initial-family-pass",
            "csrfmiddlewaretoken": csrf,
        }, secure=True, headers={"Referer": "https://testserver/login/"}).status_code, 302)
        page = family.get("/editions/2027/", secure=True)
        self.assertContains(page, "Your ballot is saved.")
        self.assertIn("no-store", page.headers["Cache-Control"])
        self.assertEqual(family.get("/accounts/new/", secure=True).status_code, 403)
        self.assertRedirects(self.client.post(f"/accounts/{legacy.user_id}/password/", {
            "new_password1": "another-family-pass", "new_password2": "another-family-pass",
        }, secure=True), "/accounts/", fetch_redirect_response=False)
        self.assertRedirects(family.get("/editions/2027/", secure=True),
                             "/login/?next=/editions/2027/", fetch_redirect_response=False)
        self.assertTrue(Client().login(username="pat", password="another-family-pass"))

    def test_new_family_account_is_available_on_voter_roster_before_sign_in(self):
        self.client.force_login(User.objects.create_superuser("organizer"))
        edition = Edition.objects.create(year=2027, slots=8)
        self.assertEqual(self.client.post("/accounts/new/", {
            "username": "family", "display_name": "Family member",
            "password1": "an-initial-family-pass", "password2": "an-initial-family-pass",
        }, secure=True).status_code, 302)
        roster = self.client.get(reverse("manage-edition", args=[edition.year, "voters"]), secure=True)
        self.assertContains(roster, "Family member")
        self.assertEqual(self.client.get("/logout/", secure=True).status_code, 405)
        self.assertRedirects(self.client.post("/logout/", secure=True), "/login/", fetch_redirect_response=False)
        self.assertRedirects(self.client.get("/accounts/", secure=True), "/login/?next=/accounts/",
                             fetch_redirect_response=False)

    def test_health_is_accessible_without_https_or_a_member(self):
        self.assertContains(self.client.get("/healthz/"), "ok")
        self.assertFalse(Member.objects.exists())


class EditionWorkflowTests(TestCase):
    def request(self, route, data=None, *, member="organizer-id", **kwargs):
        url = reverse(route, kwargs=kwargs)
        user, _ = User.objects.get_or_create(username=member, defaults={"is_superuser": member == "organizer-id"})
        self.client.force_login(user)
        options = {"secure": True}
        return (self.client.get(url, **options) if data is None
                else self.client.post(url, data, **options))

    def manage(self, action, data, year=2026):
        return self.request("manage-edition", data, year=year, action=action)

    def draft(self, slots, count, *, historical=False):
        for member in ("Alice voter", "Bob voter"):
            self.request("home", member=member.replace(" ", "-"))
        self.assertEqual(self.request("create-edition", {
            "year": 2026, "slots": slots, "historical": historical,
        }).status_code, 302)
        edition = Edition.objects.get()
        games = [Game.objects.create(title=f"Game {index:02}") for index in range(count)]
        if not historical:
            self.assertEqual(self.manage("voters", {
                "members": list(Member.objects.exclude(user__username="organizer-id").values_list("pk", flat=True))
            }).status_code, 302)
        self.assertEqual(self.manage("competitors", {"names": "Pat\nQuinn\nSam"}).status_code, 302)
        self.assertEqual(self.manage("nominees", {"games": [game.pk for game in games]}).status_code, 302)
        return edition, list(edition.nomination_set.all())

    def test_vote_privacy_cutoff_resolution_tied_scoring_and_archive(self):
        edition, (first, second, third) = self.draft(2, 3)
        self.assertEqual(self.request("edition", year=2026, member="Alice-voter").status_code, 404)
        self.assertEqual(self.manage("start", {}).status_code, 302)
        self.assertEqual(self.manage("nominees", {"games": []}).status_code, 404)
        self.assertRedirects(self.request("ballot", year=2026, member="Alice-voter"),
                             "/editions/2026/#ballot", fetch_redirect_response=False)
        self.assertNotContains(self.request("edition", year=2026), "Save ballot")
        self.assertEqual(self.request("edition", {}, year=2026).status_code, 404)
        self.assertEqual(self.request("manage-edition", {}, year=2026, action="close",
                                      member="Alice-voter").status_code, 403)
        duplicate = self.request("edition", {f"game_{first.pk}": 2, f"game_{second.pk}": 2},
                                 year=2026, member="Alice-voter")
        self.assertContains(duplicate, "Use each point value only once")
        self.assertEqual(self.request("edition", {f"game_{second.pk}": 2, f"game_{third.pk}": 1},
                                      year=2026, member="Alice-voter").status_code, 302)
        self.assertEqual(self.request("edition", {f"game_{first.pk}": 2, f"game_{second.pk}": 1},
                                      year=2026, member="Alice-voter").status_code, 302)
        saved = self.request("edition", year=2026, member="Alice-voter")
        self.assertContains(saved, "Your ballot is saved.")
        self.assertContains(saved, f'name="game_{first.pk}"')
        self.assertContains(saved, '<option value="2" selected>2 points</option>', html=True)
        self.assertNotContains(self.request("edition", year=2026, member="Bob-voter"),
                               '<option value="2" selected>2 points</option>', html=True)
        preclose = self.request("edition", year=2026)
        self.assertContains(preclose, "Ballots submitted: 1 / 2")
        self.assertNotContains(preclose, "Alice-voter")
        self.assertNotContains(preclose, "Ballot points:")
        self.assertNotContains(self.request("edition", year=2026, member="Bob-voter"), "Ballots submitted:")
        self.assertNotContains(self.request("game", pk=first.game_id, member="Bob-voter"), "Alice-voter")
        self.assertEqual(self.request("edition", {f"game_{first.pk}": 2, f"game_{third.pk}": 1},
                                      year=2026, member="Bob-voter").status_code, 302)
        self.assertEqual(self.manage("close", {}).status_code, 302)
        edition.refresh_from_db()
        self.assertEqual(edition.phase, Edition.Phase.CUTOFF)
        self.assertContains(self.request("edition", year=2026, member="Future-member"), "Alice-voter")
        self.assertEqual(self.request("edition", {f"game_{third.pk}": 2, f"game_{first.pk}": 1},
                                      year=2026, member="Alice-voter").status_code, 404)
        self.assertContains(self.manage("cutoff", {"games": [first.pk], "reason": "Not eligible"}),
                            "Select a valid choice")
        self.assertEqual(self.manage("cutoff", {"games": [second.pk], "reason": "Shorter game"}).status_code, 302)
        edition_page = self.request("edition", year=2026)
        for section in ("standings", "game-results", "revealed-ballots"):
            self.assertContains(edition_page, f'href="#{section}"')
            self.assertContains(edition_page, f'id="{section}"')
        self.assertContains(edition_page, "Configure scoring", count=3)
        self.assertNotContains(self.request("edition", year=2026, member="Alice-voter"), "Configure scoring")
        players = list(edition.competitor_set.all())
        ranks = {str(person.pk): place for person, place in zip(players, (1, 1, 3))}

        def game_action(entry, action, data):
            return self.request("manage-game", data, year=2026, pk=entry.pk, action=action)

        scoring = game_action(first, "scoring", None)
        self.assertContains(scoring, "Winner takes all")
        self.assertContains(scoring, "Placement")
        self.assertEqual(game_action(first, "scoring", {"mode": "placement", "awards": "10,6,3"}).status_code, 302)
        self.assertEqual(game_action(first, "results", ranks).status_code, 302)
        self.assertEqual(game_action(second, "scoring", {"mode": "winner", "awards": "5"}).status_code, 302)
        self.assertContains(self.request("edition", year=2026), "first place: 5 points")
        self.assertContains(game_action(second, "results", {**ranks, str(players[2].pk): 2}),
                            "skipping occupied places")
        self.assertEqual(game_action(second, "results", ranks).status_code, 302)
        self.assertEqual(competition.standings(edition), [(1, "Pat", 15), (1, "Quinn", 15), (3, "Sam", 3)])
        self.assertEqual(game_action(first, "scoring", {"mode": "winner", "awards": "1"}).status_code, 302)
        self.assertEqual(competition.standings(edition), [(1, "Pat", 6), (1, "Quinn", 6), (3, "Sam", 0)])
        self.assertEqual(self.manage("archive", {}).status_code, 302)
        self.assertEqual(game_action(first, "scoring", {"mode": "placement", "awards": "4,2,1"}).status_code, 302)
        self.assertEqual(list(first.result_set.values_list("place", "points")), [(1, 4), (1, 4), (3, 1)])
        self.assertEqual(competition.standings(edition), [(1, "Pat", 9), (1, "Quinn", 9), (3, "Sam", 1)])
        history = self.request("game", pk=second.game_id, member="Future-member")
        self.assertContains(history, "Alice-voter: Rank 2")
        self.assertContains(history, "Bob-voter: Unranked")
        self.assertEqual(game_action(second, "results", ranks).status_code, 404)

    def test_scoring_is_visible_and_editable_during_voting_without_changing_ballots(self):
        edition, (game,) = self.draft(1, 1)
        scoring = {"year": 2026, "pk": game.pk, "action": "scoring"}
        self.assertContains(self.request("edition", year=2026), "Configure scoring")
        self.assertEqual(self.request("manage-game", {"mode": "winner", "awards": "10"},
                                      **scoring).status_code, 302)
        self.assertEqual(self.manage("start", {}).status_code, 302)
        voter = {"year": 2026, "member": "Alice-voter"}
        self.assertContains(self.request("edition", **voter), "first place: 10 points")
        self.assertEqual(self.request("edition", {f"game_{game.pk}": 1}, **voter).status_code, 302)
        update = {"mode": "placement", "awards": "8,4,2"}
        self.assertEqual(self.request("manage-game", update, member="Alice-voter", **scoring).status_code, 403)
        self.assertEqual(self.request("manage-game", update, **scoring).status_code, 302)
        ballot = self.request("edition", **voter)
        self.assertContains(ballot, "Competition scoring: Placement")
        self.assertContains(ballot, "points by place: 8, 4, 2")
        self.assertContains(ballot, "Your ballot is saved.")
        self.assertEqual(edition.voter_set.get(member__user__username="Alice-voter").ranking, [game.pk])

    def test_delete_archived_edition_requires_organizer_and_matching_year(self):
        edition, (game,) = self.draft(1, 1)
        edition.phase = Edition.Phase.ARCHIVED
        edition.save(update_fields=["phase"])
        voter = edition.voter_set.first()
        voter.ranking = [game.pk]
        voter.save(update_fields=["ranking"])
        result = game.result_set.create(competitor=edition.competitor_set.first(), place=1, points=5)
        other = Edition.objects.create(year=2027, slots=1)
        other_game = other.nomination_set.create(game=game.game, title=game.title)
        other_result = other_game.result_set.create(
            competitor=other.competitor_set.create(name="Pat"), place=1, points=9,
        )

        self.assertNotContains(self.request("edition", year=2026, member="Alice-voter"), "Delete this year")
        self.assertContains(self.manage("delete", None), "Type 2026 to confirm")
        self.assertEqual(self.request("manage-edition", {"confirmation": "2026"}, year=2026,
                                      action="delete", member="Alice-voter").status_code, 403)
        self.assertContains(self.manage("delete", {"confirmation": "2027"}), "Enter 2026 to delete")
        self.assertTrue(Result.objects.filter(pk=result.pk).exists())
        self.assertRedirects(self.manage("delete", {"confirmation": "2026"}),
                             reverse("home"), fetch_redirect_response=False)
        self.assertFalse(Edition.objects.filter(year=2026).exists())
        self.assertFalse(Voter.objects.filter(pk=voter.pk).exists())
        self.assertFalse(Result.objects.filter(pk=result.pk).exists())
        self.assertTrue(Result.objects.filter(pk=other_result.pk, points=9).exists())
        self.assertTrue(Game.objects.filter(pk=game.game_id).exists())
        self.assertTrue(Member.objects.filter(pk=voter.member_id, user__isnull=False).exists())
        self.assertEqual(self.request("create-edition", {"year": 2026, "slots": 1}).status_code, 302)

    def test_what_if_counts_only_reachable_awards_in_remaining_selected_games(self):
        edition, (finished, winner, placement, unknown, excluded) = self.draft(4, 5)
        edition.phase = Edition.Phase.PLAY
        edition.save(update_fields=["phase"])
        finished.selected, finished.scored, finished.awards = True, True, [30]
        finished.save()
        finished.result_set.create(competitor=edition.competitor_set.get(name="Pat"), place=1, points=30)
        winner.selected, winner.awards = True, [10]
        winner.save()
        placement.selected, placement.mode, placement.awards = True, "placement", [6, 8, 3, 99]
        placement.save()
        unknown.selected = True
        unknown.save()
        excluded.awards = [100]
        excluded.save()

        page = self.request("edition", year=2026, member="Alice-voter")
        self.assertContains(page, 'href="#what-if"')
        self.assertContains(page, "Up to 18 more points per player")
        self.assertContains(page, f"<strong>Scoring not configured:</strong> {unknown.title}")
        self.assertEqual(page.context["scenario_rows"], [(1, "Pat", 30, 48), (2, "Quinn", 0, 18), (2, "Sam", 0, 18)])
        self.assertEqual(page.context["scenario_games"], [winner, placement])
        edition.phase = Edition.Phase.ARCHIVED
        edition.save(update_fields=["phase"])
        self.assertNotContains(self.request("edition", year=2026), 'id="what-if"')

    def test_eight_slot_ballots_and_fewer_nominees_than_slots(self):
        create = self.request("create-edition")
        self.assertEqual(create.context["form"]["slots"].value(), 8)
        edition, games = self.draft(8, 9)
        self.assertEqual(self.manage("start", {}).status_code, 302)
        ballot = self.request("edition", year=2026, member="Alice-voter")
        self.assertContains(ballot, "Give 8 points to your favorite and 1 point to your last pick.")
        self.assertContains(self.request("edition", {f"game_{games[0].pk}": 8}, year=2026,
                                         member="Alice-voter"), "Assign points to exactly 8 games")
        self.assertEqual(self.request("edition", {
            f"game_{game.pk}": points for points, game in zip(range(8, 0, -1), games[:8])
        }, year=2026, member="Alice-voter").status_code, 302)
        self.assertEqual(self.manage("close", {}).status_code, 302)
        self.assertEqual(
            [(game.pk, game.total_votes) for game in edition.nomination_set.filter(selected=True)],
            [(game.pk, points) for game, points in zip(games[:8], range(8, 0, -1))],
        )

        edition = Edition.objects.create(year=2027, slots=10, phase=Edition.Phase.OPEN)
        for game in games[:2]:
            edition.nomination_set.create(game=game.game, title=game.title)
        edition.voter_set.create(member=Member.objects.get(user__username="Alice-voter"), name="Alice")
        first, second = list(edition.nomination_set.all())
        self.assertContains(self.request("edition", {f"game_{first.pk}": 10, f"game_{second.pk}": 1},
                                         year=2027, member="Alice-voter"), "Select a valid choice")
        self.assertEqual(self.request("edition", {f"game_{first.pk}": 10, f"game_{second.pk}": 9},
                                      year=2027, member="Alice-voter").status_code, 302)
        self.assertEqual(self.manage("close", {}, year=2027).status_code, 302)
        self.assertEqual([game.total_votes for game in edition.nomination_set.all()], [10, 9])

    def test_cutoff_uses_later_rank_when_first_place_counts_match(self):
        edition, (a, b, c, d, e) = self.draft(3, 5)
        # A and B have four points and no firsts; A has more seconds.
        for index, ranks in enumerate(((c, a, b), (c, a, b), (d, b, e), (d, c, e))):
            member = Member.objects.create(issuer="https://id.example.invalid", subject=f"extra-{index}")
            edition.voter_set.create(member=member, name=str(index), ranking=[game.pk for game in ranks])
        edition.phase = Edition.Phase.OPEN
        edition.save(update_fields=["phase"])
        self.assertEqual(self.manage("close", {}).status_code, 302)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual((a.total_votes, b.total_votes), (4, 4))
        self.assertTrue(a.selected)
        self.assertFalse(b.selected)

    def test_historical_records_can_have_gaps(self):
        edition, (first, second) = self.draft(1, 2, historical=True)
        self.assertEqual(self.manage("start", {}).status_code, 302)
        self.assertEqual(self.request("manage-game", {"votes": "Pat: Yes\nQuinn: No"},
                                      year=2026, pk=first.pk, action="historical-votes").status_code, 302)
        self.assertEqual(self.manage("archive", {}).status_code, 302)
        history = self.request("edition", year=2026, member="Future-member")
        self.assertContains(history, "Pat: Yes")
        self.assertContains(history, "No voting record available")
        self.assertContains(history, "No results on record", count=2)

    @patch("olympics.bgg.fetch")
    def test_bgg_import_reuse_and_youtube_link(self, fetch):
        fetch.side_effect = [
            ElementTree.fromstring('<items><item id="42"><name value="Example"/></item></items>'),
            ElementTree.fromstring(
                '<items><item id="42" type="boardgame"><name type="primary" value="Example"/>'
                '<minplayers value="2"/><maxplayers value="4"/><playingtime value="30"/>'
                '<description>A summary.</description></item></items>'
            ),
        ]
        self.request("home")
        result = self.client.get(reverse("bgg-search"), {"q": "Example"}, secure=True)
        self.assertContains(result, "Import Example")
        self.assertEqual(self.request("bgg-search", {"id": 42}).status_code, 302)
        self.assertEqual(self.request("bgg-search", {"id": 42}).status_code, 302)
        self.assertEqual(fetch.call_count, 2)
        game = Game.objects.get(bgg_id=42)
        self.assertEqual(self.request("edit-game", {"video_url": "https://youtu.be/AbC123def45"},
                                      pk=game.pk).status_code, 302)
        page = self.request("game", pk=game.pk, member="new-member")
        for text in ("A summary.", "2–4", "30 minutes", "https://www.youtube.com/watch?v=AbC123def45"):
            self.assertContains(page, text)

    @patch("olympics.bgg.search")
    def test_bgg_search_passes_player_filter_and_displays_range(self, search):
        search.return_value = [bgg.SearchResult(42, "Example", 2024, 2, 4)]
        self.request("home")
        page = self.client.get(reverse("bgg-search"), {"q": " Example ", "players": "4"}, secure=True)
        search.assert_called_once_with("Example", players=4)
        self.assertContains(page, "Import Example (2024)")
        self.assertContains(page, "2&ndash;4 players")
        self.assertContains(page, 'value="4"')
        search.return_value = []
        page = self.client.get(reverse("bgg-search"), {"q": "Example", "players": "5"}, secure=True)
        self.assertContains(page, "No matches found among the first 30 name matches for 5 players")
        search.side_effect = bgg.BGGError("Try again later.")
        page = self.client.get(reverse("bgg-search"), {"q": "Example", "players": "5"}, secure=True)
        self.assertContains(page, "Try again later.")
        self.assertNotContains(page, "No matches found")

    @patch("olympics.bgg.search")
    def test_bgg_search_validates_inputs_before_calling_api(self, search):
        self.request("home")
        for params in (
            {"q": "Example", "players": "0"},
            {"q": "Example", "players": "-1"},
            {"q": "Example", "players": "1.5"},
            {"q": "Example", "players": "many"},
            {"q": "Example", "players": "32768"},
            {"q": "x" * 101},
            {"players": "4"},
        ):
            with self.subTest(params=params):
                page = self.client.get(reverse("bgg-search"), params, secure=True)
                self.assertTrue(page.context["search_form"].errors)
                self.assertNotContains(page, "No matches found")
        search.assert_not_called()
        self.assertEqual(self.request("bgg-search", member="family-member").status_code, 403)

    def test_old_wikidata_links_are_gone_but_imported_games_remain(self):
        game = Game.objects.create(title="Azul", wikidata_id="Q44367843")
        self.request("home")
        for path in ("/games/wikidata/", "/games/wikidata/Q44367843/"):
            self.assertEqual(self.client.get(
                path, secure=True,
            ).status_code, 404)
        self.assertNotContains(self.request("catalog"), "Search Wikidata")
        self.assertContains(self.request("game", pk=game.pk), "https://www.wikidata.org/wiki/Q44367843")

    def test_catalog_displays_optional_https_box_art(self):
        image = "https://publisher.example/cover.png"
        starter_count = Game.objects.count()
        self.assertEqual(self.request("create-game", {"title": "Covered", "cover_url": image}).status_code, 302)
        Game.objects.create(title="Uncovered")
        page = self.request("catalog", member="a-member")
        self.assertContains(page, f'src="{image}"', count=1)
        self.assertContains(page, 'class="game-cover"', count=starter_count + 2)
        self.assertContains(self.request("create-game", {
            "title": "Insecure cover", "cover_url": "http://publisher.example/cover.png",
        }), "Enter an HTTPS image URL")
