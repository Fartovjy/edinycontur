import json
import logging
import shutil
import zipfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.documents.models import Attachment

from .models import LogisticsRequest


ARCHIVE_FOLDER_NAME = "archives"
WORK_FOLDER_NAME = "archive_work"
logger = logging.getLogger(__name__)


def _json_default(value):
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _archive_root():
    return Path(getattr(settings, "ARCHIVE_ROOT", settings.BASE_DIR / ARCHIVE_FOLDER_NAME))


def _work_root():
    return Path(getattr(settings, "ARCHIVE_WORK_ROOT", settings.BASE_DIR / WORK_FOLDER_NAME))


def _unique_path(path):
    if not path.exists():
        return path

    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem}-{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _unique_filename(used_names, filename):
    path = Path(filename)
    name = path.name or "file"
    candidate = name
    counter = 2

    while candidate in used_names:
        candidate = f"{path.stem}_{counter}{path.suffix}"
        counter += 1

    used_names.add(candidate)
    return candidate


def _user_payload(user):
    if not user:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.get_full_name(),
    }


def _request_payload(request_obj, attachment_payloads):
    return {
        "id": request_obj.id,
        "request_number": request_obj.request_number,
        "client_name": request_obj.client_name,
        "client_address": request_obj.client_address,
        "client_contact": request_obj.client_contact,
        "region": request_obj.region,
        "warehouse": str(request_obj.warehouse),
        "cargo_description": request_obj.cargo_description,
        "cargo_places_count": request_obj.cargo_places_count,
        "cargo_weight_kg": request_obj.cargo_weight_kg,
        "cargo_volume_m3": request_obj.cargo_volume_m3,
        "dimensions_text": request_obj.dimensions_text,
        "supply_eta_date": request_obj.supply_eta_date,
        "warehouse_arrival_date": request_obj.warehouse_arrival_date,
        "planned_ship_date": request_obj.planned_ship_date,
        "actual_ship_date": request_obj.actual_ship_date,
        "planned_delivery_date": request_obj.planned_delivery_date,
        "actual_delivery_date": request_obj.actual_delivery_date,
        "status": request_obj.status,
        "status_display": request_obj.get_status_display(),
        "priority": request_obj.priority,
        "priority_display": request_obj.get_priority_display(),
        "cz_required": request_obj.cz_required,
        "cz_checked": request_obj.cz_checked,
        "cz_status": request_obj.cz_status,
        "cz_comment": request_obj.cz_comment,
        "cz_problem": request_obj.cz_problem,
        "assigned_vehicle": str(request_obj.assigned_vehicle) if request_obj.assigned_vehicle else None,
        "assigned_driver": str(request_obj.assigned_driver) if request_obj.assigned_driver else None,
        "created_by": _user_payload(request_obj.created_by),
        "created_at": request_obj.created_at,
        "updated_at": request_obj.updated_at,
        "attachments": attachment_payloads,
        "status_history": [
            {
                "old_status": item.old_status,
                "new_status": item.new_status,
                "changed_by": _user_payload(item.changed_by),
                "comment": item.comment,
                "created_at": item.created_at,
            }
            for item in request_obj.status_history.all()
        ],
        "problems": [
            {
                "problem_type": item.problem_type,
                "problem_type_display": item.get_problem_type_display(),
                "description": item.description,
                "status": item.status,
                "status_display": item.get_status_display(),
                "responsible_user": _user_payload(item.responsible_user),
                "created_by": _user_payload(item.created_by),
                "created_at": item.created_at,
                "resolved_at": item.resolved_at,
                "resolution_comment": item.resolution_comment,
            }
            for item in request_obj.problems.all()
        ],
    }


def _copy_attachments(requests, files_dir):
    copied_files = []
    payloads_by_request = {}
    used_names = set()

    for request_obj in requests:
        payloads_by_request[request_obj.id] = []
        for attachment in request_obj.attachments.all():
            original_name = Path(attachment.file.name).name
            archived_name = _unique_filename(used_names, original_name)
            archived_path = files_dir / archived_name
            source_path = Path(attachment.file.path)

            payload = {
                "id": attachment.id,
                "file_type": attachment.file_type,
                "file_type_display": attachment.get_file_type_display(),
                "description": attachment.description,
                "uploaded_by": _user_payload(attachment.uploaded_by),
                "uploaded_at": attachment.uploaded_at,
                "original_file": attachment.file.name,
                "archived_file": f"files/{archived_name}",
                "copied": False,
            }

            if source_path.exists():
                shutil.copy2(source_path, archived_path)
                payload["copied"] = True
                copied_files.append(source_path)

            payloads_by_request[request_obj.id].append(payload)

    return payloads_by_request, copied_files


def _write_zip(folder, zip_path):
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in folder.rglob("*"):
            if item.is_file():
                archive.write(item, item.relative_to(folder.parent))


def archive_requests_for_date(target_date):
    requests = list(
        LogisticsRequest.objects.filter(created_at__date=target_date)
        .select_related("warehouse", "assigned_vehicle", "assigned_driver", "created_by")
        .prefetch_related("attachments", "status_history", "problems")
        .order_by("request_number")
    )
    if not requests:
        return {"date": target_date, "requests": 0, "archive": None}

    work_folder = _work_root() / target_date.strftime("%Y-%m-%d")
    files_dir = work_folder / "files"
    if work_folder.exists():
        shutil.rmtree(work_folder)
    files_dir.mkdir(parents=True, exist_ok=True)

    archive_dir = _archive_root()
    archive_dir.mkdir(parents=True, exist_ok=True)
    zip_path = _unique_path(archive_dir / f"{target_date:%d%m%Y}.zip")

    copied_files = []
    try:
        payloads_by_request, copied_files = _copy_attachments(requests, files_dir)
        requests_payload = [
            _request_payload(request_obj, payloads_by_request.get(request_obj.id, []))
            for request_obj in requests
        ]
        with (work_folder / "requests.json").open("w", encoding="utf-8") as archive_file:
            json.dump(
                {
                    "archive_date": timezone.localdate(),
                    "requests_date": target_date,
                    "requests": requests_payload,
                },
                archive_file,
                ensure_ascii=False,
                indent=2,
                default=_json_default,
            )

        _write_zip(work_folder, zip_path)

        request_ids = [request_obj.id for request_obj in requests]
        with transaction.atomic():
            Attachment.objects.filter(request_id__in=request_ids).delete()
            LogisticsRequest.objects.filter(id__in=request_ids).delete()

        for source_path in copied_files:
            source_path.unlink(missing_ok=True)

        return {"date": target_date, "requests": len(requests), "archive": zip_path}
    except Exception:
        logger.exception("Failed to archive requests for date %s", target_date)
        raise
    finally:
        if work_folder.exists():
            shutil.rmtree(work_folder)


def archive_due_requests(retention_days):
    cutoff_date = timezone.localdate() - timedelta(days=retention_days + 1)
    dates = list(
        LogisticsRequest.objects.filter(created_at__date__lte=cutoff_date)
        .dates("created_at", "day", order="ASC")
    )
    return [archive_requests_for_date(target_date) for target_date in dates]
