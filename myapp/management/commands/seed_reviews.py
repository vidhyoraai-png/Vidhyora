from django.core.management.base import BaseCommand

from myapp.seed_data import seed_demo_reviews


class Command(BaseCommand):
    help = "Seeds 54 demo buyer accounts (password: 123456) with a delivered order and a humanized review each, spread across active products."

    def handle(self, *args, **options):
        summary = seed_demo_reviews()
        self.stdout.write(self.style.SUCCESS(summary))
