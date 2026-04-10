from datetime import datetime, timedelta
from azure.storage.blob import (
    BlobServiceClient,
    generate_blob_sas,
    BlobSasPermissions
)
from django.conf import settings


def _get_container_client():
    blob_service = BlobServiceClient(
        f"https://{settings.AZURE_ACCOUNT_NAME}.blob.core.windows.net",
        credential=settings.AZURE_ACCOUNT_KEY
    )
    return blob_service.get_container_client(settings.AZURE_CONTAINER)


def upload_file(local_path: str, blob_name: str):
    container = _get_container_client()
    with open(local_path, "rb") as data:
        container.upload_blob(name=blob_name, data=data, overwrite=True)
    return blob_name


def generate_sas_url(blob_name: str, expiry_minutes: int = 60):
    """Generates a temporary signed URL for a private blob."""
    sas = generate_blob_sas(
        account_name=settings.AZURE_ACCOUNT_NAME,
        container_name=settings.AZURE_CONTAINER,
        blob_name=blob_name,
        account_key=settings.AZURE_ACCOUNT_KEY,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(minutes=expiry_minutes)
    )
    return (
        f"https://{settings.AZURE_ACCOUNT_NAME}.blob.core.windows.net"
        f"/{settings.AZURE_CONTAINER}/{blob_name}?{sas}"
    )