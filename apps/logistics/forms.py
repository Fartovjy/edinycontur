from django import forms

from apps.accounts.constants import ROLE_OPERATOR

from .models import Client, LogisticsRequest


class DateInput(forms.DateInput):
    input_type = "date"


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
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class LogisticsRequestCreateForm(LogisticsRequestForm):
    skip_supply_to_warehouse = forms.BooleanField(
        label="Товар уже на складе и зарезервирован",
        required=False,
        help_text="Заявка сразу попадёт на этап склада, без обработки отделом снабжения.",
    )

    class Meta(LogisticsRequestForm.Meta):
        fields = [
            "client",
            "client_address",
            "warehouse",
            "cargo_description",
            "skip_supply_to_warehouse",
            "planned_ship_date",
            "planned_delivery_date",
        ]

    def __init__(self, *args, user_role=None, **kwargs):
        super().__init__(*args, can_assign_transport=False, **kwargs)
        self.fields.pop("status_comment", None)
        self.fields["client"].required = True
        if user_role == ROLE_OPERATOR:
            for name in ["warehouse", "planned_ship_date"]:
                self.fields.pop(name, None)
        labels = {
            "client": "Клиент",
            "client_address": "Адрес",
            "warehouse": "Склад",
            "cargo_description": "Описание груза",
            "planned_ship_date": "Плановая дата отгрузки",
            "planned_delivery_date": "Плановая дата доставки",
        }
        for name, label in labels.items():
            if name in self.fields:
                self.fields[name].label = label
