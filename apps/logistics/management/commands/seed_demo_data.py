from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.constants import (
    ROLE_ADMIN,
    ROLE_CHOICES,
    ROLE_DRIVER,
    ROLE_MANAGER,
    ROLE_OPERATOR,
    ROLE_SUPPLY,
    ROLE_TRANSPORT,
    ROLE_WAREHOUSE,
)
from apps.accounts.models import Role, UserProfile
from apps.logistics.constants import (
    STATUS_CLOSED,
    STATUS_CANCELLED,
    STATUS_CREATED,
    STATUS_CZ_CHECK,
    STATUS_DELIVERED,
    STATUS_IN_TRANSIT,
    STATUS_IN_WAREHOUSE,
    STATUS_PROBLEM,
    STATUS_READY_TO_SHIP,
    STATUS_SHIPPED,
    STATUS_TRANSPORT_ASSIGNED,
    STATUS_WAITING_ARRIVAL,
    STATUS_WAITING_SUPPLY,
)
from apps.logistics.models import Client, LogisticsRequest, RequestStatusHistory, Warehouse
from apps.problems.models import ProblemReport
from apps.transport.models import Driver, Vehicle


class Command(BaseCommand):
    help = "Creates extended demo data: users, vehicles, drivers, requests, problems and CZ cases."

    def handle(self, *args, **options):
        with transaction.atomic():
            roles = self._seed_roles()
            users = self._seed_users(roles)
            vehicles = self._seed_vehicles()
            drivers = self._seed_drivers(users, vehicles)
            clients = self._seed_clients()
            warehouses = self._seed_warehouses()
            requests = self._seed_requests(users, vehicles, drivers, clients, warehouses)
            self._seed_problems(users, requests)

        self.stdout.write(
            self.style.SUCCESS(
                "Demo data is ready. Login: admin / admin, users: operator|supply|transport|warehouse|driver|manager / password, extra drivers: driver2..driver5 / password"
            )
        )

    def _seed_roles(self):
        roles = {}
        for code, title in ROLE_CHOICES:
            roles[code], _ = Role.objects.update_or_create(code=code, defaults={"title": title})
        return roles

    def _seed_users(self, roles):
        User = get_user_model()
        base_users = {
            "admin": ("Админ", "Контур", ROLE_ADMIN, "+7 900 000-00-01", True),
            "operator": ("Ольга", "Оператор", ROLE_OPERATOR, "+7 900 000-00-02", False),
            "supply": ("Сергей", "Снабжение", ROLE_SUPPLY, "+7 900 000-00-03", False),
            "transport": ("Тимур", "Транспорт", ROLE_TRANSPORT, "+7 900 000-00-04", False),
            "warehouse": ("Вера", "Склад", ROLE_WAREHOUSE, "+7 900 000-00-05", False),
            "manager": ("Марина", "Руководитель", ROLE_MANAGER, "+7 900 000-00-06", False),
        }
        driver_users = {
            "driver": ("Денис", "Воронов", ROLE_DRIVER, "+7 900 777-77-71", False),
            "driver2": ("Илья", "Соколов", ROLE_DRIVER, "+7 900 777-77-72", False),
            "driver3": ("Павел", "Ким", ROLE_DRIVER, "+7 900 777-77-73", False),
            "driver4": ("Андрей", "Мельников", ROLE_DRIVER, "+7 900 777-77-74", False),
            "driver5": ("Руслан", "Галеев", ROLE_DRIVER, "+7 900 777-77-75", False),
        }

        users = {}
        for username, (first_name, last_name, role_code, phone, is_admin) in {**base_users, **driver_users}.items():
            user, created = User.objects.update_or_create(
                username=username,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": f"{username}@example.local",
                    "role": roles[role_code],
                    "is_staff": is_admin,
                    "is_superuser": is_admin,
                    "is_active": True,
                },
            )
            if created or not user.has_usable_password():
                user.set_password("admin" if username == "admin" else "password")
                user.save(update_fields=["password"])

            profile, _ = UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    "role": role_code,
                    "phone": phone,
                    "telegram_id": user.telegram_chat_id,
                    "is_active": True,
                },
            )
            users[username] = user
            if role_code == ROLE_DRIVER:
                users[f"{username}_profile"] = profile
        return users

    def _seed_vehicles(self):
        vehicle_data = [
            ("А123ВС777", "Mercedes Sprinter", 1200, "8.500", "фургон"),
            ("М456ОР777", "ГАЗель Next", 1500, "10.000", "фургон"),
            ("К789ТЕ196", "MAN TGL", 5000, "32.000", "грузовик"),
            ("О321РА799", "Ford Transit", 1300, "9.200", "рефрижератор"),
            ("Н654КМ777", "Volvo FL", 7000, "38.000", "грузовик"),
        ]
        vehicles = []
        for plate, name, weight, volume, vehicle_type in vehicle_data:
            vehicle, _ = Vehicle.objects.update_or_create(
                plate_number=plate,
                defaults={
                    "name": name,
                    "max_weight_kg": weight,
                    "max_volume_m3": Decimal(volume),
                    "vehicle_type": vehicle_type,
                    "is_active": True,
                },
            )
            vehicles.append(vehicle)
        return vehicles

    def _seed_drivers(self, users, vehicles):
        drivers = []
        driver_usernames = ["driver", "driver2", "driver3", "driver4", "driver5"]
        for index, username in enumerate(driver_usernames, start=1):
            user = users[username]
            vehicle = vehicles[index - 1]
            driver, _ = Driver.objects.update_or_create(
                full_name=user.get_full_name(),
                defaults={
                    "phone": user.profile.phone,
                    "user": user,
                    "telegram_chat_id": user.telegram_chat_id,
                    "is_active": True,
                },
            )
            UserProfile.objects.filter(user=user).update(default_vehicle=vehicle)
            drivers.append(driver)
        return drivers

    def _seed_clients(self):
        client_data = [
            ("БиоВак Север", "Санкт-Петербург", "Ирина Павлова", "+7 900 100-10-10"),
            ("МедЛогистика Юг", "Ростов-на-Дону", "Антон Крылов", "+7 900 200-20-20"),
            ("ФармСклад Урал", "Екатеринбург", "Мария Белова", "+7 900 300-30-30"),
            ("Клиника Восток", "Казань", "Дамир Нуриев", "+7 900 400-40-40"),
            ("Лаборатория Центр", "Москва", "Елена Морозова", "+7 900 500-50-50"),
        ]
        clients = []
        for name, region, contact, phone in client_data:
            client, _ = Client.objects.update_or_create(
                name=name,
                defaults={"region": region, "contact_name": contact, "phone": phone},
            )
            clients.append(client)
        return clients

    def _seed_warehouses(self):
        warehouse_data = [
            ("Центральный склад", "Москва", "МКАД, 42 км"),
            ("Склад Север", "Санкт-Петербург", "Пулковское шоссе, 12"),
            ("Склад Урал", "Екатеринбург", "ул. Монтажников, 8"),
            ("Склад Юг", "Ростов-на-Дону", "ул. Доватора, 144"),
        ]
        warehouses = []
        for name, region, address in warehouse_data:
            warehouse, _ = Warehouse.objects.update_or_create(
                name=name,
                defaults={"region": region, "address": address},
            )
            warehouses.append(warehouse)
        return warehouses

    def _seed_requests(self, users, vehicles, drivers, clients, warehouses):
        today = timezone.localdate()
        statuses = [
            STATUS_CANCELLED,
            STATUS_WAITING_SUPPLY,
            STATUS_WAITING_ARRIVAL,
            STATUS_IN_WAREHOUSE,
            STATUS_CZ_CHECK,
            STATUS_READY_TO_SHIP,
            STATUS_TRANSPORT_ASSIGNED,
            STATUS_SHIPPED,
            STATUS_IN_TRANSIT,
            STATUS_DELIVERED,
            STATUS_PROBLEM,
            STATUS_CLOSED,
            STATUS_WAITING_SUPPLY,
            STATUS_WAITING_ARRIVAL,
            STATUS_READY_TO_SHIP,
            STATUS_IN_TRANSIT,
            STATUS_PROBLEM,
            STATUS_TRANSPORT_ASSIGNED,
            STATUS_DELIVERED,
            STATUS_CREATED,
        ]
        overdue_indexes = {3, 7, 11, 14}
        cz_indexes = {2, 5, 9, 13, 17}
        without_transport_indexes = {1, 2, 13, 20}

        demo_requests = []
        for index, status in enumerate(statuses, start=1):
            client = clients[(index - 1) % len(clients)]
            warehouse = warehouses[(index - 1) % len(warehouses)]
            has_transport = index not in without_transport_indexes
            is_overdue = index in overdue_indexes
            is_closed = status == STATUS_CLOSED
            is_delivered = status == STATUS_DELIVERED
            is_shipped = status in {STATUS_SHIPPED, STATUS_IN_TRANSIT, STATUS_DELIVERED, STATUS_CLOSED}
            cz_required = index in cz_indexes

            planned_delivery_date = today - timedelta(days=index % 4 + 1) if is_overdue else today + timedelta(days=(index % 6) - 1)
            if is_delivered and index == 19:
                planned_delivery_date = today

            request, _ = LogisticsRequest.objects.update_or_create(
                request_number=f"EK-DEMO-{index:05d}",
                defaults={
                    "client_name": client.name,
                    "client_address": f"{client.region}, демо-адрес {index}",
                    "client_contact": f"{client.contact_name}, {client.phone}",
                    "region": client.region,
                    "warehouse": warehouse,
                    "cargo_description": self._cargo_description(index),
                    "cargo_places_count": 4 + index,
                    "cargo_weight_kg": Decimal("120.00") + Decimal(index * 37),
                    "cargo_volume_m3": Decimal("0.800") + Decimal(index) / Decimal("10"),
                    "dimensions_text": f"{4 + index} мест, коробки 60x40x40",
                    "supply_eta_date": today + timedelta(days=(index % 5) - 2),
                    "warehouse_arrival_date": today - timedelta(days=2) if status in {STATUS_IN_WAREHOUSE, STATUS_CZ_CHECK, STATUS_READY_TO_SHIP, STATUS_TRANSPORT_ASSIGNED, STATUS_SHIPPED, STATUS_IN_TRANSIT, STATUS_DELIVERED, STATUS_PROBLEM, STATUS_CLOSED, STATUS_CANCELLED} else None,
                    "planned_ship_date": today + timedelta(days=(index % 5) - 1),
                    "actual_ship_date": today - timedelta(days=1) if is_shipped else None,
                    "planned_delivery_date": planned_delivery_date,
                    "actual_delivery_date": today if is_delivered else (today - timedelta(days=1) if is_closed else None),
                    "status": status,
                    "priority": self._priority(index),
                    "cz_required": cz_required,
                    "cz_checked": cz_required and index % 2 == 1,
                    "cz_status": self._cz_status(cz_required, index),
                    "cz_comment": "Демо: требуется проверка маркировки." if cz_required else "",
                    "cz_problem": cz_required and index in {17},
                    "assigned_vehicle": vehicles[(index - 1) % len(vehicles)] if has_transport else None,
                    "assigned_driver": drivers[(index - 1) % len(drivers)] if has_transport else None,
                    "created_by": users["operator"],
                    "is_archived": False,
                },
            )
            self._reset_history(request, status, users)
            demo_requests.append(request)
        return demo_requests

    def _seed_problems(self, users, requests):
        ProblemReport.objects.filter(request__request_number__startswith="EK-DEMO-").delete()
        problem_map = {
            3: (ProblemReport.TRANSPORT_DELAY, "Просрочена плановая доставка, требуется решение по приоритету.", users["manager"], ProblemReport.IN_PROGRESS),
            7: (ProblemReport.TRANSPORT_DELAY, "Маршрут требует ручного согласования с транспортным отделом.", users["transport"], ProblemReport.OPEN),
            11: (ProblemReport.DOCUMENT_MISMATCH, "Не хватает части документов для отгрузки.", users["supply"], ProblemReport.IN_PROGRESS),
            17: (ProblemReport.DAMAGED_PACKAGING, "Водитель сообщил о повреждении части упаковки.", users["warehouse"], ProblemReport.OPEN),
        }
        for request_index, (problem_type, description, responsible, status) in problem_map.items():
            ProblemReport.objects.create(
                request=requests[request_index - 1],
                problem_type=problem_type,
                description=description,
                status=status,
                responsible_user=responsible,
                created_by=users["operator"],
            )

    def _reset_history(self, request, status, users):
        request.status_history.all().delete()
        RequestStatusHistory.objects.create(
            request=request,
            old_status="",
            new_status=STATUS_CREATED,
            changed_by=users["operator"],
            comment="Демо-заявка создана",
        )
        if status != STATUS_CREATED:
            RequestStatusHistory.objects.create(
                request=request,
                old_status=STATUS_CREATED,
                new_status=status,
                changed_by=self._history_user(status, users),
                comment="Демо-переход статуса",
            )

    def _history_user(self, status, users):
        if status in {STATUS_WAITING_SUPPLY, STATUS_WAITING_ARRIVAL}:
            return users["supply"]
        if status in {STATUS_IN_WAREHOUSE, STATUS_CZ_CHECK, STATUS_READY_TO_SHIP}:
            return users["warehouse"]
        if status in {STATUS_TRANSPORT_ASSIGNED, STATUS_SHIPPED, STATUS_IN_TRANSIT, STATUS_DELIVERED}:
            return users["transport"]
        if status == STATUS_PROBLEM:
            return users["manager"]
        return users["operator"]

    def _cargo_description(self, index):
        cargo = [
            "Вакцины в термоконтейнерах",
            "Диагностические наборы",
            "Расходные материалы",
            "Лабораторные реагенты",
            "Медицинские изделия",
        ]
        return cargo[(index - 1) % len(cargo)]

    def _priority(self, index):
        priorities = [
            LogisticsRequest.PRIORITY_NORMAL,
            LogisticsRequest.PRIORITY_URGENT,
            LogisticsRequest.PRIORITY_VIP,
            LogisticsRequest.PRIORITY_CRITICAL,
        ]
        return priorities[(index - 1) % len(priorities)]

    def _cz_status(self, cz_required, index):
        if not cz_required:
            return LogisticsRequest.CZ_NOT_REQUIRED
        return LogisticsRequest.CZ_PROBLEM if index in {17} else (LogisticsRequest.CZ_OK if index % 2 else LogisticsRequest.CZ_PENDING)
