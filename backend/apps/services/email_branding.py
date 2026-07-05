import os
from email.mime.image import MIMEImage

from django.conf import settings

# Content-ID the templates reference as ``src="cid:btf-logo"`` (via LOGO_URL).
LOGO_CID = "btf-logo"

# Logo ships inside the backend so embedding never depends on the frontend
# being deployed/reachable. White variant for the dark brand strip.
_LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "btf-logo-white.png")
_logo_bytes = None


def brand_context() -> dict:
    """Shared chrome for every transactional email (logo + brand name).

    Merge into each email's render context. ``LOGO_URL`` points at the inline
    ``cid:`` part attached by :func:`attach_inline_logo`, so the logo renders
    with no external image host.
    """
    return {
        "LOGO_URL": f"cid:{LOGO_CID}",
        "BRAND_NAME": getattr(settings, "BRAND_NAME", "BIOTech Futures"),
        "BRAND_CONNECT": getattr(settings, "BRAND_CONNECT", "BIOTech Connect"),
        # CONTACT_EMAIL: mailbox users write to; SENDER_EMAIL: mailbox we send
        # from ("add to your address book" copy). Deliberately different.
        "CONTACT_EMAIL": getattr(settings, "SUPPORT_EMAIL", "support@biotechfutures.org"),
        "SENDER_EMAIL": getattr(settings, "EMAIL_FROM_ADDRESS", "info@biotechfutures.org"),
    }


def attach_inline_logo(msg) -> None:
    """Embed the brand logo as an inline image on an ``EmailMultiAlternatives``.

    The image travels inside the message (multipart/related), so clients render
    it offline without fetching anything. Best-effort: a missing asset must not
    break the send — the email just falls back to the ``alt`` text.
    """
    global _logo_bytes
    try:
        if _logo_bytes is None:
            with open(_LOGO_PATH, "rb") as fh:
                _logo_bytes = fh.read()
        img = MIMEImage(_logo_bytes, "png")
        img.add_header("Content-ID", f"<{LOGO_CID}>")
        img.add_header("Content-Disposition", "inline", filename="btf-logo-white.png")
        # Promote the container to multipart/related so the cid reference resolves.
        msg.mixed_subtype = "related"
        msg.attach(img)
    except OSError:
        pass
