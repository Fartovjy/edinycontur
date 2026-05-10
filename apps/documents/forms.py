from pathlib import Path

from django import forms
from django.conf import settings

from .models import Attachment


ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}


class AttachmentForm(forms.ModelForm):
    class Meta:
        model = Attachment
        fields = ["file_type", "description", "file"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            "file_type": "Тип файла",
            "description": "Описание",
            "file": "Файл",
        }
        for name, label in labels.items():
            self.fields[name].label = label
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-select")
            else:
                field.widget.attrs.setdefault("class", "form-control")

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]
        extension = Path(uploaded_file.name).suffix.lower()
        if extension not in ALLOWED_UPLOAD_EXTENSIONS:
            raise forms.ValidationError("Разрешены только PDF, JPG, PNG и WEBP.")

        max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if uploaded_file.size > max_size:
            raise forms.ValidationError(f"Файл больше {settings.MAX_UPLOAD_SIZE_MB} МБ.")

        return uploaded_file
