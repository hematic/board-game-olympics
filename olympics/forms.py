import re
from urllib.parse import parse_qs, urlsplit

from django import forms

from .models import Edition, Game, Nomination


class EditionForm(forms.ModelForm):
    class Meta:
        model = Edition
        fields = ["year", "slots", "historical", "history_notes"]
        help_texts = {"historical": "Enter a past lineup and known records without opening a vote."}

    def clean_slots(self):
        slots = self.cleaned_data["slots"]
        if not 1 <= slots <= 50:
            raise forms.ValidationError("Choose between 1 and 50 lineup slots.")
        return slots


class GameForm(forms.ModelForm):
    class Meta:
        model = Game
        fields = ["title", "year", "notes", "min_players", "max_players", "playing_time", "video_url"]
        labels = {"playing_time": "Listed playing time (minutes)", "video_url": "YouTube rules video"}

    def clean_video_url(self):
        url = self.cleaned_data["video_url"]
        if not url:
            return ""
        parts = urlsplit(url)
        video = ""
        if parts.hostname in {"www.youtube.com", "youtube.com", "m.youtube.com"}:
            if parts.path == "/watch":
                video = parse_qs(parts.query).get("v", [""])[0]
            elif parts.path.startswith("/shorts/"):
                video = parts.path.removeprefix("/shorts/")
        elif parts.hostname == "youtu.be":
            video = parts.path.removeprefix("/")
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video):
            raise forms.ValidationError("Enter a YouTube video URL.")
        return f"https://www.youtube.com/watch?v={video}"

    def clean(self):
        data = super().clean()
        low, high = data.get("min_players"), data.get("max_players")
        if low is not None and high is not None and low > high:
            self.add_error("max_players", "Maximum must be at least the minimum.")
        return data


class BallotForm(forms.Form):
    def __init__(self, nominations, slots, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [("", "Choose a game"), *((str(game.pk), game.title) for game in nominations)]
        for index in range(min(slots, len(nominations))):
            self.fields[f"rank_{index + 1}"] = forms.TypedChoiceField(
                label=f"Rank {index + 1} ({slots - index} points)", choices=choices, coerce=int
            )

    def clean(self):
        data = super().clean()
        if not self.errors and len(set(data.values())) != len(self.fields):
            raise forms.ValidationError("Rank each game only once.")
        return data


class ScoringForm(forms.Form):
    mode = forms.ChoiceField(choices=Nomination.Scoring.choices)
    awards = forms.CharField(max_length=400, help_text="Comma-separated points starting with first place, e.g. 10, 6, 3.")

    def clean_awards(self):
        parts = [part.strip() for part in self.cleaned_data["awards"].split(",")]
        if any(not re.fullmatch(r"[0-9]{1,6}", part) for part in parts):
            raise forms.ValidationError("Enter whole points from 0 to 999999, separated by commas.")
        return [int(part) for part in parts]

    def clean(self):
        data = super().clean()
        if data.get("mode") == Nomination.Scoring.WINNER and len(data.get("awards", [])) > 1:
            self.add_error("awards", "Enter only one award for winner-take-all.")
        return data


class ResultsForm(forms.Form):
    def __init__(self, competitors, *args, historical=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.historical = historical
        for person in competitors:
            self.fields[str(person.pk)] = forms.IntegerField(
                label=person.name, min_value=1,
                max_value=32767 if historical else len(competitors), required=False,
            )

    def clean(self):
        data = super().clean()
        if self.errors:
            return data
        entered = sorted(place for place in data.values() if place is not None)
        if not entered:
            raise forms.ValidationError("Enter at least one result.")
        for index, place in enumerate(entered):
            if (index == 0 or entered[index - 1] != place) and (
                place < index + 1 or (not self.historical and place != index + 1)
            ):
                raise forms.ValidationError("Use consecutive places, skipping occupied places after ties (1, 1, 3).")
        return data
