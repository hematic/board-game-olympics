import os

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Create the first organizer from environment variables."

    @transaction.atomic
    def handle(self, *args, **options):
        organizers = User.objects.filter(is_active=True, is_superuser=True)
        if any(user.has_usable_password() for user in organizers):
            return

        username = os.environ.get("OLYMPICS_ORGANIZER_USERNAME", "")
        password = os.environ.get("OLYMPICS_ORGANIZER_PASSWORD", "")
        if not username.strip() or not password:
            raise CommandError(
                "Set OLYMPICS_ORGANIZER_USERNAME and OLYMPICS_ORGANIZER_PASSWORD "
                "to create the first organizer."
            )

        form = UserCreationForm({"username": username, "password1": password, "password2": password})
        if not form.is_valid():
            fields = ", ".join(form.errors)
            raise CommandError(
                f"Invalid organizer credentials ({fields}). Use an unused valid username "
                "and a strong, unique password."
            )

        user = form.save(commit=False)
        user.is_staff = True
        user.is_superuser = True
        user.save()
        self.stdout.write("Created the first organizer.")
