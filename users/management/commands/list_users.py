import json

from django.core.management.base import BaseCommand

from users.models import User


class Command(BaseCommand):
    help = "List User."

    def handle(self, *args, **options):
        users = User.objects.all()
        for user in users:
            f = [
                "email",
                "is_staff",
                "is_superuser",
                "is_active",
                "username",
                "first_name",
                "last_name",
                "preferred_language",
            ]
            u = {
                field_name: getattr(user, field_name, None) for field_name in f
            }
            d = json.dumps(u, indent=2)
            self.stdout.write(d)
