from django.db import DatabaseError, OperationalError, ProgrammingError

from .models import SiteBranding


def site_branding(request):
    try:
        branding = SiteBranding.current()
    except (DatabaseError, OperationalError, ProgrammingError):
        return {"company_logo_url": ""}

    logo_url = branding.company_logo.url if branding.company_logo else ""
    return {"company_logo_url": logo_url}
