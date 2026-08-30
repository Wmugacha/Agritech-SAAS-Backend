import logging
from rest_framework import serializers
from .models import SoilAnalysisJob

logger = logging.getLogger(__name__)

class SoilAnalysisJobListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing prediction jobs.
    Omits massive raw spectral arrays to maintain fast query response times.
    """
    status = serializers.ReadOnlyField()
    predicted_properties = serializers.ReadOnlyField()
    error_message = serializers.ReadOnlyField()
    model_version = serializers.ReadOnlyField()
    is_billable = serializers.ReadOnlyField()

    class Meta:
        model = SoilAnalysisJob
        fields = [
            'id', 'field', 'status', 'predicted_properties',
            'error_message', 'model_version', 'is_billable', 'created_at'
        ]


class SoilAnalysisJobSerializer(serializers.ModelSerializer):
    status = serializers.ReadOnlyField()
    predicted_properties = serializers.ReadOnlyField()
    error_message = serializers.ReadOnlyField()
    model_version = serializers.ReadOnlyField()
    is_billable = serializers.ReadOnlyField()

    spectra_file = serializers.FileField(required=False, allow_null=True)
    spectra = serializers.JSONField(required=False, allow_null=True)

    class Meta:
        model = SoilAnalysisJob
        fields = [
            'id', 'field', 'status', 'spectra', 'spectra_file',
            'predicted_properties', 'error_message', 'model_version',
            'is_billable', 'created_at'
        ]

    def validate(self, data):
        spectra_list = data.get('spectra')
        spectra_file = data.get('spectra_file')

        if not spectra_list and not spectra_file:
            raise serializers.ValidationError("You must provide either 'spectra' JSON array or a 'spectra_file' CSV.")

        return data