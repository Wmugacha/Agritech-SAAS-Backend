from rest_framework import serializers
from .models import Farm, Field, CropSeason, FarmActivity

class FieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = Field
        fields = ['id', 'farm', 'name', 'crop_type', 'area_hectares', 'latitude', 'longitude']

class FarmSerializer(serializers.ModelSerializer):
    # Nested serializer to show fields inside the farm response
    fields = FieldSerializer(many=True, read_only=True)

    class Meta:
        model = Farm
        fields = ['id', 'name', 'location', 'total_area_hectares', 'fields',  'owner', 'organization', 'created_at']
        read_only_fields = ['owner', 'organization']

class FarmActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = FarmActivity
        fields = '__all__'
        read_only_fields = ['created_at']

class CropSeasonSerializer(serializers.ModelSerializer):
    # This nests the activities inside the season so the frontend gets the full timeline at once
    activities = FarmActivitySerializer(many=True, read_only=True)

    class Meta:
        model = CropSeason
        fields = '__all__'
        read_only_fields = ['created_at']