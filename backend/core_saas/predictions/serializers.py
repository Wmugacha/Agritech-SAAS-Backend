import logging
import pandas as pd
from rest_framework import serializers
from .models import SoilAnalysisJob

logger = logging.getLogger(__name__)

class SoilAnalysisJobSerializer(serializers.ModelSerializer):
    status = serializers.ReadOnlyField()
    predicted_properties = serializers.ReadOnlyField()
    error_message = serializers.ReadOnlyField()
    model_version = serializers.ReadOnlyField()
    is_billable = serializers.ReadOnlyField()

    spectra_file = serializers.FileField(required=False)
    spectra = serializers.JSONField(required=False, allow_null=True)

    class Meta:
        model = SoilAnalysisJob
        fields = ['id', 'field', 'status', 'spectra', 'spectra_file', 'predicted_properties', 'error_message', 'model_version', 'is_billable', 'created_at']

    def validate_spectra(self, value):
        """
        Custom validation to handle EITHER a JSON array OR a CSV file.
        """
        spectra_list = data.get('spectra')
        spectra_file = data.get('spectra_file')

        if not spectra_list and not spectra_file:
            raise serializers.ValidationError("You must provide either 'spectra' JSON array or a 'spectra_file' CSV.")

        # Parse the file
        if spectra_file:
            try:
                # Read the CSV file into a Pandas DataFrame
                # We assume the CSV has no headers and is just a list/row of numbers
                df = pd.read_csv(spectra_file, header=None)
                
                # Flatten the data into a single Python list of floats
                parsed_spectra = df.values.flatten().tolist()
                
                # Assign it to the spectra data so data validation catches it
                data['spectra'] = parsed_spectra
                
                # Reset file pointer so Django can save the file properly later
                spectra_file.seek(0)
                
            except Exception as e:
                logger.error(f"Failed to parse CSV: {str(e)}")
                raise serializers.ValidationError("Invalid CSV file. Ensure it contains numeric spectral data.")


        """
        Scientific Validation: Ensure spectra is a list of floats.
        """
        if not isinstance(value, list):
            logger.warning("Validation Failed: Spectra is not a list")
            raise serializers.ValidationError("Spectra must be a list of absorbance values.")
        
        if len(value) == 0:
            raise serializers.ValidationError("Spectra array cannot be empty.")

        # Prevent Memory Overload Attacks
        if len(value) > 10000:
             raise serializers.ValidationError("Spectra array exceeds maximum allowed length (10,000).")

        # Check the first few items to ensure they are numbers (To adjust later for heavier datasets)
        if not all(isinstance(x, (int, float)) for x in value):
            logger.warning("Validation Failed: Spectra contains non-numeric values")
            raise serializers.ValidationError("All spectral values must be numbers.")
            
        return value

    def create(self, validated_data):
        """
        Intercepts the final database save to force the parsed CSV data into the ORM,
        bypassing DRF's habit of stripping missing multipart fields.
        """
        spectra_file = validated_data.get('spectra_file')
        
        # Force the parsed data into the database payload
        if spectra_file:
            import pandas as pd
            df = pd.read_csv(spectra_file, header=None)
            validated_data['spectra'] = df.values.flatten().tolist()
            spectra_file.seek(0) # Reset file pointer for the FileField save
            
        # Execute the actual database save
        return super().create(validated_data)