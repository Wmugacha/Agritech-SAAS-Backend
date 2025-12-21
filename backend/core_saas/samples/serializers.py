from rest_framework import serializers
from .models import SoilSample

class SoilSampleSerializer(serializers.ModelSerializer):
    # These are marked as read_only because we set them 
    # automatically in the perform_create method of the view.
    organization = serializers.StringRelatedField(read_only=True)
    uploaded_by_email = serializers.EmailField(source='uploaded_by.email', read_only=True)

    class Meta:
        model = SoilSample
        fields = [
            'id', 'label', 'organization', 'uploaded_by_email',
            'latitude', 'longitude', 'depth_cm', 'crop_type',
            'ph', 'nitrogen', 'phosphorus', 'potassium',
            'metadata', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def validate(self, data):
        """
        Add any cross-field validation here.
        Ensure longitude/latitude are provided together.
        """
        lat = data.get('latitude')
        lon = data.get('longitude')
        
        if (lat and not lon) or (lon and not lat):
            raise serializers.ValidationError(
                "Both Latitude and Longitude must be provided together."
            )
        return data