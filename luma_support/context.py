"""Custom template context processors."""


def brand(request):
    """Brand colors / metadata exposed to every template."""
    return {
        "BRAND": {
            "name": "Luma Support",
            "company": "Luma Tech Solutions",
            "url": "https://lumatechsolutions.co.uk",
            "primary": "#14b8a6",
            "primary_dark": "#0f766e",
            "background": "#0f172a",
            "surface": "#1e293b",
            "border": "#334155",
            "text": "#f1f5f9",
            "muted": "#94a3b8",
        }
    }
