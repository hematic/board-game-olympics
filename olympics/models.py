from django.conf import settings
from django.db import models


class Member(models.Model):
    issuer = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)

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
