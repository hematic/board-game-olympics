from django.contrib.auth.views import redirect_to_login
from django.utils.cache import add_never_cache_headers

from .models import Member


class MemberMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path_info != "/healthz/":
            add_never_cache_headers(response)
        return response

    def process_view(self, request, view, args, kwargs):
        if getattr(view, "login_required", True) is False:
            return None
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        request.member, _ = Member.objects.get_or_create(
            user=request.user,
            defaults={
                "issuer": "local",
                "subject": str(request.user.pk),
                "display_name": request.user.get_username(),
            },
        )
        return None
