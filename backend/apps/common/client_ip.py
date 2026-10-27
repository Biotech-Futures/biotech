"""Resolve the caller's IP address for rate-limit keys and audit fields."""
from django.conf import settings


def client_ip(request) -> str:
    # X-Forwarded-For is attacker-controlled when the app is reachable directly.
    # Only honor it when the deployment terminates at a trusted proxy/CDN
    # (Azure Front Door / App Service ingress / ALB). Production opts in via
    # TRUST_FORWARDED_FOR=true; everywhere else we anchor rate-limit keys to
    # the real socket peer so an attacker can't fan out across spoofed IPs.
    if getattr(settings, "TRUST_FORWARDED_FOR", False):
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if xff:
            return strip_port(xff.split(",")[0])
    return strip_port(request.META.get("REMOTE_ADDR", "") or "")


def strip_port(addr: str) -> str:
    # Azure App Service forwards `IP:PORT` in X-Forwarded-For / REMOTE_ADDR;
    # GenericIPAddressField rejects the port suffix.
    addr = addr.strip()
    if not addr:
        return ""
    if addr.startswith("["):
        end = addr.find("]")
        return addr[1:end] if end != -1 else addr
    if addr.count(":") == 1:
        return addr.split(":", 1)[0]
    return addr
