from django import template
from django.urls import NoReverseMatch, reverse

register = template.Library()


@register.simple_tag
def maybe_url(name, *args, **kwargs):
    """
    Reverse a URL name if it is currently registered, otherwise return None.
    Lets templates (like the sidebar in base.html) link to views that are
    planned but not implemented yet for every app without raising
    NoReverseMatch — the link just renders disabled until the real
    urls.py/views.py for that app land, at which point it lights up on its
    own with no template changes needed.
    """
    try:
        return reverse(name, args=args, kwargs=kwargs)
    except NoReverseMatch:
        return None
