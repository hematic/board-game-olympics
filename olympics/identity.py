from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.utils.cache import add_never_cache_headers

from .models import Member


class ProxyIdentityMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.path_info == "/healthz/":
            return self.get_response(request)

        subject = request.headers.get("Remote-Sub", "")
        # A combined header value must not be interpreted as a single identity.
        if not (0 < len(subject) <= 255) or not subject.isascii() or any(
            not char.isprintable() or char.isspace() or char == "," for char in subject
        ):
            response = HttpResponseForbidden("A verified Pocket ID identity is required.")
        else:
            name = request.headers.get("Remote-Name", "").strip()[:255]
            request.member, _ = Member.objects.get_or_create(
                issuer=settings.POCKET_ID_ISSUER, subject=subject,
                defaults={"display_name": name},
            )
            if name and request.member.display_name != name:
                request.member.display_name = name
                request.member.save(update_fields=["display_name"])
            response = self.get_response(request)

        add_never_cache_headers(response)
        return response
