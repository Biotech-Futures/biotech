from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.core.cache import cache
from django.db import connection
import os

from .file_scanner import FileScanError, scan_uploaded_file


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    健康检查端点 - 验证所有服务是否正常运行
    不需要认证即可访问
    """
    status = {
        'status': 'healthy',
        'services': {}
    }

    # 检查数据库连接
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        status['services']['database'] = 'connected'
    except Exception as e:
        status['services']['database'] = f'error: {str(e)}'
        status['status'] = 'unhealthy'

    # 检查 Redis 连接
    try:
        cache.set('health_check', 'ok', 10)
        result = cache.get('health_check')
        if result == 'ok':
            status['services']['redis'] = 'connected'
        else:
            status['services']['redis'] = 'error: cache verification failed'
            status['status'] = 'unhealthy'
    except Exception as e:
        status['services']['redis'] = f'error: {str(e)}'
        status['status'] = 'unhealthy'

    # 返回环境信息
    status['environment'] = {
        'debug': os.getenv('DEBUG', 'False'),
        'django_version': __import__('django').get_version(),
    }

    # 根据健康状态返回不同的 HTTP 状态码
    http_status = 200 if status['status'] == 'healthy' else 503

    return Response(status, status=http_status)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def upload_file(request):
    """
    Upload a file to the configured object storage and return its public URL.
    """

    uploaded_file = request.FILES.get('file')
    if uploaded_file is None:
        return Response(
            {'detail': 'No file provided.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    extension = os.path.splitext(uploaded_file.name)[1]
    storage_path = f'uploads/{uuid4().hex}{extension}'

    try:
        scan_uploaded_file(uploaded_file)
    except ValidationError as exc:
        detail = None
        if hasattr(exc, "message_dict"):
            messages = exc.message_dict.get("file")
            if isinstance(messages, (list, tuple)) and messages:
                detail = messages[0]
            elif isinstance(messages, str):
                detail = messages
        if detail is None and hasattr(exc, "messages") and exc.messages:
            detail = exc.messages[0]
        if detail is None:
            detail = str(exc)
        return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
    except FileScanError as exc:
        return Response({"detail": f"Upload blocked: {exc}"}, status=status.HTTP_400_BAD_REQUEST)

    stored_path = default_storage.save(storage_path, uploaded_file)
    file_url = default_storage.url(stored_path)

    return Response(
        {
            'url': file_url,
            'filename': uploaded_file.name,
            'size': uploaded_file.size,
            'mimeType': uploaded_file.content_type or 'application/octet-stream',
        },
        status=status.HTTP_201_CREATED,
    )
