from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.logistics.archivist import archive_due_requests, archive_requests_for_date
from apps.logistics.models import ArchivistSettings


class Command(BaseCommand):
    help = "Архивирует старые заявки в ZIP и удаляет их из основной базы."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            help="Архивировать конкретную дату создания заявок в формате YYYY-MM-DD.",
        )

    def handle(self, *args, **options):
        if options["date"]:
            try:
                target_date = date.fromisoformat(options["date"])
            except ValueError as exc:
                raise CommandError("Дата должна быть в формате YYYY-MM-DD.") from exc
            results = [archive_requests_for_date(target_date)]
        else:
            settings = ArchivistSettings.get_solo()
            results = archive_due_requests(settings.retention_days)

        if not results:
            self.stdout.write(self.style.SUCCESS("Нет заявок для архивации."))
            return

        for result in results:
            if result["requests"] == 0:
                self.stdout.write(f"{result['date']}: нет заявок.")
                continue
            self.stdout.write(
                self.style.SUCCESS(
                    f"{result['date']}: архивировано и удалено из БД заявок: {result['requests']}. "
                    f"Архив: {result['archive']}"
                )
            )
