import logging
from rest_framework import serializers
from .models import SoilAnalysisJob

logger = logging.getLogger(__name__)

class SoilAnalysisJobSerializer(serializers.ModelSerializer):
    status = serializers.ReadOnlyField()
    predicted_properties = serializers.ReadOnlyField()
    error_message = serializers.ReadOnlyField()

    class Meta:
        model = SoilAnalysisJob
        fields = ['id', 'status', 'spectra', 'predicted_properties', 'error_message', 'created_at']

    def validate_spectra(self, value):
        """
        Scientific Validation: Ensure spectra is a list of floats.
        """
        if not isinstance(value, list):
            logger.warning("Validation Failed: Spectra is not a list")
            raise serializers.ValidationError("Spectra must be a list of absorbance values.")
        
        if len(value) == 0:
            raise serializers.ValidationError("Spectra array cannot be empty.")

        # Check the first few items to ensure they are numbers (To adjust later for heavier datasets)
        if not all(isinstance(x, (int, float)) for x in value):
            logger.warning("Validation Failed: Spectra contains non-numeric values")
            raise serializers.ValidationError("All spectral values must be numbers.")
            
        return value