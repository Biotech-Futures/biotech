from datetime import datetime, timedelta, timezone
from azure.storage.blob import (
    BlobServiceClient,
    generate_blob_sas,
    BlobSasPermissions
)
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from django.conf import settings


def _get_container_client():
    blob_service = BlobServiceClient(
        f"https://{settings.AZURE_ACCOUNT_NAME}.blob.core.windows.net",
        credential=settings.AZURE_ACCOUNT_KEY
    )
    return blob_service.get_container_client(settings.AZURE_CONTAINER)


def _create_container_if_missing(container):
    try:
        container.create_container()
    except ResourceExistsError:
        pass


def upload_file(local_path: str, blob_name: str):
    container = _get_container_client()
    with open(local_path, "rb") as data:
        try:
            container.upload_blob(name=blob_name, data=data, overwrite=True)
        except ResourceNotFoundError:
            _create_container_if_missing(container)
            data.seek(0)
            container.upload_blob(name=blob_name, data=data, overwrite=True)
    return blob_name


def download_file_text(blob_name: str, encoding: str = "utf-8"):
    """Downloads a private text blob and decodes it."""
    container = _get_container_client()
    data = container.download_blob(blob_name).readall()
    return data.decode(encoding, errors="replace")


def download_file_bytes(blob_name: str):
    """Downloads a private blob as bytes."""
    container = _get_container_client()
    return container.download_blob(blob_name).readall()


def generate_sas_url(blob_name: str, expiry_minutes: int = 60):
    """Generates a temporary signed URL for a private blob."""
    sas = generate_blob_sas(
        account_name=settings.AZURE_ACCOUNT_NAME,
        container_name=settings.AZURE_CONTAINER,
        blob_name=blob_name,
        account_key=settings.AZURE_ACCOUNT_KEY,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)
    )
    return (
        f"https://{settings.AZURE_ACCOUNT_NAME}.blob.core.windows.net"
        f"/{settings.AZURE_CONTAINER}/{blob_name}?{sas}"
    )
