from django import forms

from apps.accounts.constants import ROLE_OPERATOR

from .models import Client, LogisticsRequest, Supplier, SupplyPickupRequest


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, attrs=None, format=None):
        super().__init__(attrs=attrs, format=format or "%Y-%m-%d")


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ["name", "region", "contact_name", "phone", "email"]
        labels = {
            "name": "Клиент",
            "region": "Регион",
            "contact_name": "Контактное лицо",
            "phone": "Телефон",
            "email": "Email",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "region", "contact_name", "phone", "email", "notes"]
        labels = {
            "name": "Поставщик",
            "region": "Регион",
            "contact_name": "Контактное лицо",
            "phone": "Телефон",
            "email": "Email",
            "notes": "Заметки",
        }
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class SupplyPickupRequestForm(forms.ModelForm):
    class Meta:
        model = SupplyPickupRequest
        fields = ["supplier", "pickup_date", "weight_kg", "cargo_notes"]
        labels = {
            "supplier": "Поставщик",
            "pickup_date": "Дата забора",
            "weight_kg": "Вес, кг",
            "cargo_notes": "Перечень товаров (комментарий)",
        }
        widgets = {
            "pickup_date": DateInput(),
            "cargo_notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].queryset = Supplier.objects.order_by("name")
        self.fields["supplier"].empty_label = "Выберите поставщика"
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-select")
            else:
                field.widget.attrs.setdefault("class", "form-control")


class SupplyPickupAssignForm(forms.ModelForm):
    class Meta:
        model = SupplyPickupRequest
        fields = ["assigned_vehicle", "assigned_driver"]
        labels = {
            "assigned_vehicle": "Автомобиль",
            "assigned_driver": "Водитель",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.transport.models import Driver, Vehicle
        self.fields["assigned_vehicle"].queryset = Vehicle.objects.filter(is_active=True).order_by("plate_number")
        self.fields["assigned_vehicle"].empty_label = "Выберите автомобиль"
        self.fields["assigned_driver"].queryset = Driver.objects.filter(is_active=True).order_by("full_name")
        self.fields["assigned_driver"].empty_label = "Выберите водителя"
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-select")


class LogisticsRequestForm(forms.ModelForm):
    client = forms.ModelChoiceField(
        label="Клиент",
        queryset=Client.objects.none(),
        required=False,
        empty_label="Выберите клиента",
    )
    status_comment = forms.CharField(
        label="Комментарий к смене статуса",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    class Meta:
        model = LogisticsRequest
        fields = [
            "request_number",
            "client",
            "client_address",
            "client_contact",
            "client_phone",
            "region",
            "warehouse",
            "cargo_description",
            "cargo_places_count",
            "cargo_weight_kg",
            "cargo_volume_m3",
            "dimensions_text",
            "supply_eta_date",
            "warehouse_arrival_date",
            "planned_ship_date",
            "actual_ship_date",
            "planned_delivery_date",
            "actual_delivery_date",
            "status",
            "priority",
            "cz_required",
            "cz_checked",
            "cz_status",
            "cz_comment",
            "cz_problem",
            "assigned_vehicle",
            "assigned_driver",
            "is_archived",
        ]
        widgets = {
            "cargo_description": forms.Textarea(attrs={"rows": 3}),
            "cz_comment": forms.Textarea(attrs={"rows": 2}),
            "supply_eta_date": DateInput(),
            "warehouse_arrival_date": DateInput(),
            "planned_ship_date": DateInput(),
            "actual_ship_date": DateInput(),
            "planned_delivery_date": DateInput(),
            "actual_delivery_date": DateInput(),
        }

    def __init__(self, *args, can_assign_transport=False, editable_fields=None, status_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        if "client" in self.fields:
            self.fields["client"].queryset = Client.objects.order_by("name")
            if self.instance and self.instance.client_name:
                matched_client = Client.objects.filter(name=self.instance.client_name).first()
                if matched_client:
                    self.initial["client"] = matched_client

        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-select")
            else:
                field.widget.attrs.setdefault("class", "form-control")

        if "client_address" in self.fields:
            self.fields["client_address"].label = "Адрес клиента или GPS-точка"
            self.fields["client_address"].help_text = "Можно указать адрес текстом или координаты, например 55.755864, 37.617698."
            self.fields["client_address"].widget.attrs.setdefault("placeholder", "Адрес или GPS: 55.755864, 37.617698")

        if status_choices is not None and "status" in self.fields:
            self.fields["status"].choices = status_choices

        if not can_assign_transport and "assigned_vehicle" in self.fields and "assigned_driver" in self.fields:
            self.fields["assigned_vehicle"].disabled = True
            self.fields["assigned_driver"].disabled = True
            self.fields["assigned_vehicle"].help_text = "Назначать транспорт может только транспортный отдел или администратор."
            self.fields["assigned_driver"].help_text = "Назначать водителя может только транспортный отдел или администратор."

        if editable_fields is not None:
            editable_fields = set(editable_fields)
            for name in list(self.fields):
                if name not in editable_fields:
                    self.fields.pop(name)

    def save(self, commit=True):
        instance = super().save(commit=False)
        client = self.cleaned_data.get("client")
        if client:
            instance.client_name = client.name
            instance.region = client.region
            contact_parts = [client.contact_name, client.phone]
            contact = ", ".join(part for part in contact_parts if part)
            if contact:
                instance.client_contact = contact
        if not instance.region and instance.route_direction_label:
            instance.region = instance.route_direction_label
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class LogisticsRequestCreateForm(LogisticsRequestForm):
    """
    Форма создания заявки.
    Упрощённый набор полей: no warehouse / volume / dims / skip_supply.
    Наблюдатель передаётся отдельно через viewer_user_id (не через M2M поле формы).
    """

    class Meta(LogisticsRequestForm.Meta):
        fields = [
            "request_number",
            "client",
            "client_address",
            "client_contact",
            "client_phone",
            "planned_delivery_date",
            "cargo_places_count",
            "cargo_weight_kg",
            "cargo_description",
        ]

    def __init__(self, *args, user_role=None, from_pdf=False, **kwargs):
        super().__init__(*args, can_assign_transport=False, **kwargs)
        self.fields.pop("status_comment", None)

        # При создании из PDF клиент вводится текстом напрямую — FK не нужен
        self.fields["client"].required = not from_pdf

        # Необязательные поля
        for name in ["request_number", "client_contact", "client_phone",
                     "cargo_description", "cargo_places_count", "cargo_weight_kg"]:
            if name in self.fields:
                self.fields[name].required = False

        # Метки
        labels = {
            "request_number":    "Номер заявки",
            "client":            "Клиент",
            "client_address":    "Адрес клиента или GPS-точка",
            "client_contact":    "ФИО контактного лица",
            "client_phone":      "Телефон / Email",
            "planned_delivery_date": "Плановая дата доставки",
            "cargo_places_count": "Количество мест",
            "cargo_weight_kg":   "Вес груза, кг",
            "cargo_description": "Примечание",
        }
        for name, label in labels.items():
            if name in self.fields:
                self.fields[name].label = label

        if "request_number" in self.fields:
            self.fields["request_number"].help_text = (
                "Оставьте пустым — номер сформируется автоматически. "
                "При создании из файла подставляется номер документа клиента."
            )
