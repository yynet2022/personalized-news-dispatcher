from django.conf import settings


def project_context(request):
    """
    Adds project-wide context variables to the template context.
    """
    return {
        "project_name": settings.PROJECT_NAME,
    }
