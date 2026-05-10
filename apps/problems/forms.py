from pathlib import Path

from django import forms
from django.conf import settings

from apps.documents.forms import ALLOWED_UPLOAD_EXTENSIONS
from apps.logistics.constants import STATUS_CHOICES

from .models import ProblemReport


class ProblemReportForm(forms.ModelForm):
    evidence_file = forms.FileField(label="Файл/фото", required=False)

    class Meta:
        model = ProblemReport
        fields = ["problem_type", "description", "responsible_user", "evidence_file"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["responsible_user"].required = True
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-select")
            elif isinstance(field.widget, forms.FileInput):
                field.widget.attrs.setdefault("class", "form-control")
            else:
                field.widget.attrs.setdefault("class", "form-control")

    def clean_evidence_file(self):
        uploaded_file = self.cleaned_data.get("evidence_file")
        if not uploaded_file:
            return uploaded_file

        extension = Path(uploaded_file.name).suffix.lower()
        if extension not in ALLOWED_UPLOAD_EXTENSIONS:
            raise forms.ValidationError("Разрешены только PDF, JPG, PNG и WEBP.")

        max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if uploaded_file.size > max_size:
            raise forms.ValidationError(f"Файл больше {settings.MAX_UPLOAD_SIZE_MB} МБ.")

        return uploaded_file


class CloseProblemForm(forms.Form):
    resolution_comment = forms.CharField(
        label="Комментарий решения",
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    new_status = forms.ChoiceField(label="Новый статус заявки")

    def __init__(self, *args, allowed_statuses=None, **kwargs):
        super().__init__(*args, **kwargs)
        status_labels = dict(STATUS_CHOICES)
        allowed_statuses = allowed_statuses or []
        self.fields["new_status"].choices = [(status, status_labels.get(status, status)) for status in allowed_statuses]
