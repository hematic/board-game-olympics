from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_safe


@require_safe
def home(request: HttpRequest) -> HttpResponse:
    return render(request, "olympics/home.html", {"organizer": request.member.is_organizer})


@require_safe
def health(request: HttpRequest) -> HttpResponse:
    return HttpResponse("ok\n", content_type="text/plain")
