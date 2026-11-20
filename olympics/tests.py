from django.test import TestCase, override_settings

from .models import Member


@override_settings(
    POCKET_ID_ISSUER="https://id.example.invalid",
    ORGANIZER_SUBJECTS={"organizer-id"},
)
class ProxyIdentityTests(TestCase):
    def test_requires_a_single_valid_subject_even_if_a_username_is_present(self):
        for subject in ("", "user-id, organizer-id", "contains space", "x" * 256):
            with self.subTest(subject=subject):
                response = self.client.get(
                    "/", secure=True, headers={"Remote-Sub": subject, "Remote-User": "organizer"}
                )
                self.assertEqual(response.status_code, 403)
        self.assertFalse(Member.objects.exists())

    def test_subject_identifies_the_member_across_renames(self):
        for name in ("before", "after"):
            response = self.client.get(
                "/", secure=True, headers={"Remote-Sub": "member-id", "Remote-User": name}
            )
            self.assertContains(response, "Signed in as a member")
            self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertEqual(Member.objects.get().subject, "member-id")

    def test_organizer_is_selected_by_subject_not_name_or_group(self):
        response = self.client.get(
            "/", secure=True, headers={"Remote-Sub": "member-id", "Remote-Groups": "organizers"}
        )
        self.assertContains(response, "Signed in as a member")
        response = self.client.get("/", secure=True, headers={"Remote-Sub": "organizer-id"})
        self.assertContains(response, "Signed in as an organizer")

    def test_health_is_accessible_without_https_or_a_member(self):
        self.assertContains(self.client.get("/healthz/"), "ok")
        self.assertFalse(Member.objects.exists())
