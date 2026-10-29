"""Public social profiles; no credentials or external requests."""
from urllib.parse import urlsplit

HOSTS = {
    'youtube': ('youtube.com', 'www.youtube.com', 'youtu.be'),
    'telegram': ('t.me', 'telegram.me'),
    'instagram': ('instagram.com', 'www.instagram.com'),
    'x': ('x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'),
    'discord': ('discord.gg', 'discord.com', 'www.discord.com'),
    'whatsapp': ('wa.me', 'whatsapp.com', 'www.whatsapp.com', 'chat.whatsapp.com'),
    'github': ('github.com', 'www.github.com'),
    'tiktok': ('tiktok.com', 'www.tiktok.com'),
}
DEFAULT_LINKS = dict.fromkeys(HOSTS, '') | {
    'youtube': 'https://www.youtube.com/@ComboList-qe7yy',
    'telegram': 'https://t.me/LionXSec',
}


def validate_links(value):
    if not isinstance(value, dict) or set(value) - set(HOSTS):
        raise ValueError('invalid_social_url')
    result = {}
    for key, raw in value.items():
        if not isinstance(raw, str) or len(raw) > 2000 or any(c.isspace() or ord(c) < 32 for c in raw):
            raise ValueError('invalid_social_url')
        if raw:
            try:
                parsed = urlsplit(raw)
                if (parsed.scheme != 'https' or parsed.hostname not in HOSTS[key]
                        or parsed.username is not None or parsed.password is not None
                        or parsed.port not in (None, 443) or '\\' in raw):
                    raise ValueError('invalid_social_url')
            except ValueError:
                raise ValueError('invalid_social_url') from None
        result[key] = raw
    return result
