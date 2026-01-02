from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Updates the site domain and name for the current SITE_ID. "
        "If no options are provided, it displays the current settings."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--domain",
            type=str,
            help='The new domain name for the site (e.g., "example.com").',
        )
        parser.add_argument(
            "--name",
            type=str,
            help='The new display name for the site (e.g., "My Site").',
        )

    def handle(self, *args, **options):
        try:
            site = Site.objects.get(pk=settings.SITE_ID)
        except Site.DoesNotExist:
            raise CommandError(
                f"Site with ID {settings.SITE_ID} does not exist. "
                "Please create it in the admin."
            )

        domain = options["domain"]
        name = options["name"]

        # If no arguments are provided, display the current settings
        if not domain and not name:
            self.stdout.write(self.style.SUCCESS("Current site settings:"))
            self.stdout.write(f"  ID:     {site.pk}")
            self.stdout.write(f"  Domain: {site.domain}")
            self.stdout.write(f"  Name:   {site.name}")
            return

        # If arguments are provided, update the settings
        if domain:
            site.domain = domain
            self.stdout.write(f"Updating site domain to: {domain}")

        if name:
            site.name = name
            self.stdout.write(f"Updating site name to: {name}")

        site.save()

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully updated site "{site.name}" (ID: {site.pk}).'
            )
        )
