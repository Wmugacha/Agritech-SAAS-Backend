from rest_framework import serializers
from .models import Farm, Field

class FieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = Field
        fields = ['id', 'farm', 'name', 'crop_type', 'area_hectares', 'latitude', 'longitude']

class FarmSerializer(serializers.ModelSerializer):
    # Nested serializer to show fields inside the farm response
    fields = FieldSerializer(many=True, read_only=True)

    class Meta:
        model = Farm
        fields = ['id', 'name', 'location', 'total_area_hectares', 'fields', 'created_at']