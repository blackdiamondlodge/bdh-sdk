"""Who is using the hub.

The hub signs its owners in as Django staff users. Apps should ask
:func:`is_admin` instead of reading ``request.user`` fields themselves, so
the rule stays the same everywhere and apps never need to touch the user
table.

This module does not import Django.
"""

__all__ = ["is_admin"]


def is_admin(request):
    """True when the request comes from a signed-in, active hub admin.

    Accepts a request (or anything with a ``user`` attribute). Requests
    without a user, e.g. from a test ``RequestFactory``, are not admin.
    """
    user = getattr(request, "user", None)
    return bool(
        user is not None
        and getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
        and getattr(user, "is_staff", False)
    )
