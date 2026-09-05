from rest_framework import permissions, serializers
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from ..models import GradingSettings
from ..permissions import IsGrader


class GradingSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradingSettings
        fields = [
            "director_1_name",
            "director_1_signature",
            "director_2_name",
            "director_2_signature",
            "marks_summary_template",
            "certificate_template",
            "component_weights",
        ]


class GradingSettingsView(RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/grading/settings/

    Singleton — returns and patches the one ``GradingSettings`` row.
    File fields (signatures, docx templates) use multipart uploads; the JSON
    field (component_weights) accepts a dict via either parser.
    """

    permission_classes = [permissions.IsAuthenticated, IsGrader]
    serializer_class = GradingSettingsSerializer
    # Accept multipart (file uploads) and JSON (director-name patches with no
    # file). Without JSONParser, plain-text PATCHes 415 with "Unsupported
    # media type application/json".
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ["get", "patch"]

    def get_object(self):
        return GradingSettings.load()
