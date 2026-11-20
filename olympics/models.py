from django.conf import settings
from django.db import models


class Member(models.Model):
    issuer = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.display_name or f"Member {self.pk}"

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["issuer", "subject"], name="unique_member_identity")
        ]

    @property
    def is_organizer(self) -> bool:
        return (
            self.issuer == settings.POCKET_ID_ISSUER
            and self.subject in settings.ORGANIZER_SUBJECTS
        )


class Game(models.Model):
    title = models.CharField(max_length=255)
    bgg_id = models.PositiveIntegerField(null=True, blank=True, unique=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    min_players = models.PositiveSmallIntegerField(null=True, blank=True)
    max_players = models.PositiveSmallIntegerField(null=True, blank=True)
    playing_time = models.PositiveSmallIntegerField(null=True, blank=True)
    video_url = models.URLField(blank=True)

    class Meta:
        ordering = ["title", "pk"]

    def __str__(self):
        return f"{self.title} ({self.year})" if self.year else self.title


class Edition(models.Model):
    class Phase(models.TextChoices):
        DRAFT = "draft", "Draft"
        OPEN = "open", "Voting open"
        CUTOFF = "cutoff", "Cutoff decision pending"
        PLAY = "play", "Competition"
        ARCHIVED = "archived", "Archived"

    year = models.PositiveSmallIntegerField(unique=True)
    slots = models.PositiveSmallIntegerField()
    phase = models.CharField(max_length=10, choices=Phase, default=Phase.DRAFT)
    historical = models.BooleanField(default=False)
    history_notes = models.TextField(blank=True)
    cutoff_reason = models.TextField(blank=True)
    voters = models.ManyToManyField(Member, through="Voter")

    class Meta:
        ordering = ["-year"]


class Voter(models.Model):
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE)
    member = models.ForeignKey(Member, on_delete=models.PROTECT)
    name = models.CharField(max_length=255)
    # Ordered nomination IDs; accepted ballots are replaced as a unit.
    ranking = models.JSONField(null=True, blank=True, default=None)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["edition", "member"], name="unique_edition_voter")
        ]


class Competitor(models.Model):
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)

    class Meta:
        ordering = ["name", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["edition", "name"], name="unique_edition_competitor")
        ]

    def __str__(self):
        return self.name


class Nomination(models.Model):
    class Scoring(models.TextChoices):
        WINNER = "winner", "Winner takes all"
        PLACEMENT = "placement", "Placement"

    edition = models.ForeignKey(Edition, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.PROTECT)
    title = models.CharField(max_length=263)
    selected = models.BooleanField(default=False)
    cutoff_tied = models.BooleanField(default=False)
    vote_breakdown = models.JSONField(default=list, blank=True)
    mode = models.CharField(max_length=10, choices=Scoring, default=Scoring.WINNER)
    awards = models.JSONField(default=list, blank=True)
    scored = models.BooleanField(default=False)
    historical_votes = models.TextField(blank=True)

    class Meta:
        ordering = ["title", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["edition", "game"], name="unique_edition_game")
        ]

    @property
    def total_votes(self):
        return sum((self.edition.slots - index) * count
                   for index, count in enumerate(self.vote_breakdown))


class Result(models.Model):
    nomination = models.ForeignKey(Nomination, on_delete=models.CASCADE)
    competitor = models.ForeignKey(Competitor, on_delete=models.PROTECT)
    place = models.PositiveSmallIntegerField()
    points = models.PositiveIntegerField()

    class Meta:
        ordering = ["place", "competitor__name"]
        constraints = [
            models.UniqueConstraint(fields=["nomination", "competitor"], name="unique_game_result")
        ]
