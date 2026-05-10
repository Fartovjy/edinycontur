from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.constants import ROLE_CHOICES
from apps.accounts.models import Role, UserProfile
from apps.problems.models import ProblemReport
from apps.transport.models import Driver, Vehicle

from ...models import Client, LogisticsRequest, RequestStatusHistory, Warehouse


class Command(BaseCommand):
    help = "Creates demo roles, users, profiles, directories and logistics requests."

    def handle(self, *args, **options):
        User = get_user_model()

        roles = {}
        for code, title in ROLE_CHOICES:
            roles[code], _ = Role.objects.update_or_create(code=code, defaults={"title": title})

        users = {
            "admin": ("Админ", "Контур", "admin", "+7 900 000-00-01"),
            "operator": ("Ольга", "Оператор", "operator", "+7 900 000-00-02"),
            "supply": ("Сергей", "Снабжение", "supply", "+7 900 000-00-03"),
            "transport": ("Тимур", "Транспорт", "transport", "+7 900 000-00-04"),
            "warehouse": ("Вера", "Склад", "warehouse", "+7 900 000-00-05"),
            "driver": ("Денис", "Водитель", "driver", "+7 900 777-77-77"),
            "manager": ("Марина", "Руководитель", "manager", "+7 900 000-00-06"),
        }
        created_users = {}
        for username, (first_name, last_name, role_code, phone) in users.items():
            user, created = User.objects.update_or_create(
                username=username,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": f"{username}@example.local",
                    "role": roles[role_code],
                    "is_staff": username == "admin",
                    "is_superuser": username == "admin",
                    "is_active": True,
                },
            )
            if created or not user.has_usable_password():
                user.set_password("admin" if username == "admin" else "password")
                user.save(update_fields=["password"])
            UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    "role": role_code,
                    "phone": phone,
                    "telegram_id": user.telegram_chat_id,
                    "is_active": True,
                },
            )
            created_users[username] = user

        clients = [
            ("БиоВак Север", "Санкт-Петербург", "Ирина Павлова", "+7 900 100-10-10", "Санкт-Петербург, ул. Цветочная, 10"),
            ("МедЛогистика Юг", "Ростов-на-Дону", "Антон Крылов", "+7 900 200-20-20", "Ростов-на-Дону, пр. Стачки, 55"),
            ("ФармСклад Урал", "Екатеринбург", "Мария Белова", "+7 900 300-30-30", "Екатеринбург, ул. Малышева, 90"),
        ]
        client_objs = []
        for name, region, contact, phone, address in clients:
            obj, _ = Client.objects.update_or_create(name=name, defaults={"region": region, "contact_name": contact, "phone": phone})
            obj.demo_address = address
            client_objs.append(obj)

        warehouses = [
            ("Центральный склад", "Москва", "МКАД, 42 км"),
            ("Склад Север", "Санкт-Петербург", "Пулковское шоссе, 12"),
            ("Склад Урал", "Екатеринбург", "ул. Монтажников, 8"),
        ]
        warehouse_objs = []
        for name, region, address in warehouses:
            obj, _ = Warehouse.objects.update_or_create(name=name, defaults={"region": region, "address": address})
            warehouse_objs.append(obj)

        vehicles = [
            ("А123ВС777", "Mercedes Sprinter", 1200, 8.5, "фургон"),
            ("М456ОР777", "ГАЗель Next", 1500, 10.0, "фургон"),
            ("К789ТЕ196", "MAN TGL", 5000, 32.0, "грузовик"),
        ]
        vehicle_objs = []
        for plate, name, max_weight, max_volume, vehicle_type in vehicles:
            obj, _ = Vehicle.objects.update_or_create(
                plate_number=plate,
                defaults={
                    "name": name,
                    "max_weight_kg": max_weight,
                    "max_volume_m3": max_volume,
                    "vehicle_type": vehicle_type,
                    "is_active": True,
                },
            )
            vehicle_objs.append(obj)

        UserProfile.objects.filter(user=created_users["driver"]).update(default_vehicle=vehicle_objs[0])

        driver, _ = Driver.objects.update_or_create(
            full_name="Денис Воронов",
            defaults={"phone": "+7 900 777-77-77", "user": created_users["driver"], "telegram_chat_id": ""},
        )

        today = timezone.localdate()
        demo_requests = [
            {
                "request_number": "EK-20260507-001",
                "client": client_objs[0],
                "warehouse": warehouse_objs[0],
                "cargo_description": "Вакцины, термоконтейнеры",
                "cargo_places_count": 12,
                "cargo_weight_kg": 420,
                "cargo_volume_m3": 3.2,
                "dimensions_text": "12 мест, 80x60x70 см",
                "status": "waiting_supply",
                "priority": LogisticsRequest.PRIORITY_URGENT,
                "cz_required": True,
                "cz_status": LogisticsRequest.CZ_PENDING,
            },
            {
                "request_number": "EK-20260507-002",
                "client": client_objs[1],
                "warehouse": warehouse_objs[0],
                "cargo_description": "Расходные материалы",
                "cargo_places_count": 25,
                "cargo_weight_kg": 980,
                "cargo_volume_m3": 7.5,
                "dimensions_text": "паллеты 120x80",
                "status": "transport_assigned",
                "priority": LogisticsRequest.PRIORITY_NORMAL,
                "cz_required": False,
                "cz_status": LogisticsRequest.CZ_NOT_REQUIRED,
            },
            {
                "request_number": "EK-20260507-003",
                "client": client_objs[2],
                "warehouse": warehouse_objs[2],
                "cargo_description": "Диагностические наборы",
                "cargo_places_count": 8,
                "cargo_weight_kg": 260,
                "cargo_volume_m3": 1.8,
                "dimensions_text": "8 коробов, 60x40x40 см",
                "status": "problem",
                "priority": LogisticsRequest.PRIORITY_URGENT,
                "cz_required": True,
                "cz_status": LogisticsRequest.CZ_PROBLEM,
                "cz_comment": "Не хватает части кодов маркировки.",
            },
        ]
        for index, item in enumerate(demo_requests):
            client = item["client"]
            status = item["status"]
            req, created = LogisticsRequest.objects.update_or_create(
                request_number=item["request_number"],
                defaults={
                    "client_name": client.name,
                    "client_address": client.demo_address,
                    "client_contact": f"{client.contact_name}, {client.phone}",
                    "region": client.region,
                    "warehouse": item["warehouse"],
                    "cargo_description": item["cargo_description"],
                    "cargo_places_count": item["cargo_places_count"],
                    "cargo_weight_kg": item["cargo_weight_kg"],
                    "cargo_volume_m3": item["cargo_volume_m3"],
                    "dimensions_text": item["dimensions_text"],
                    "supply_eta_date": today + timedelta(days=index),
                    "warehouse_arrival_date": today + timedelta(days=index + 1) if index else None,
                    "planned_ship_date": today + timedelta(days=index + 2),
                    "actual_ship_date": today + timedelta(days=index + 2) if status in {"shipped", "in_transit", "delivered"} else None,
                    "planned_delivery_date": today + timedelta(days=index + 4),
                    "actual_delivery_date": None,
                    "assigned_vehicle": vehicle_objs[index],
                    "assigned_driver": driver,
                    "status": status,
                    "priority": item["priority"],
                    "cz_required": item["cz_required"],
                    "cz_checked": item["cz_status"] in {LogisticsRequest.CZ_OK, LogisticsRequest.CZ_PROBLEM},
                    "cz_status": item["cz_status"],
                    "cz_comment": item.get("cz_comment", ""),
                    "cz_problem": item["cz_status"] == LogisticsRequest.CZ_PROBLEM,
                    "created_by": created_users["operator"],
                    "is_archived": False,
                },
            )
            if created or not req.status_history.exists():
                RequestStatusHistory.objects.create(request=req, old_status="", new_status="created", changed_by=created_users["operator"], comment="Демо-заявка создана")
                if status != "created":
                    RequestStatusHistory.objects.create(request=req, old_status="created", new_status=status, changed_by=created_users["transport"], comment="Демо-переход статуса")

        problem_req = LogisticsRequest.objects.get(request_number="EK-20260507-003")
        ProblemReport.objects.update_or_create(
            request=problem_req,
            problem_type=ProblemReport.DOCUMENT_MISMATCH,
            defaults={
                "description": "Не хватает оригинала транспортной накладной.",
                "responsible_user": created_users["supply"],
                "status": ProblemReport.IN_PROGRESS,
                "created_by": created_users["warehouse"],
            },
        )

        self.stdout.write(self.style.SUCCESS("Demo data is ready. Login: admin / admin, users: operator|supply|transport|warehouse|driver|manager / password"))
