from django.contrib.auth import get_user_model
from rest_framework import serializers

from organizations.fields import OrgScopedPrimaryKeyRelatedField

from .models import CropSeason, Farm, FarmActivity, Field


class FieldSerializer(serializers.ModelSerializer):
    farm = OrgScopedPrimaryKeyRelatedField(queryset=Farm.objects.all(), org_lookup="organization")

    class Meta:
        model = Field
        fields = ['id', 'farm', 'name', 'crop_type', 'area_hectares', 'latitude', 'longitude']

class FarmSerializer(serializers.ModelSerializer):
    # Nested serializer to show fields inside the farm response
    fields = FieldSerializer(many=True, read_only=True)
    # Optional: assign the farm to another member of the org (e.g. a farmer). Defaults to the creator.
    owner = OrgScopedPrimaryKeyRelatedField(
        queryset=get_user_model().objects.all(),
        org_lookup="memberships__organization",
        required=False,
    )

    class Meta:
        model = Farm
        fields = ['id', 'name', 'location', 'total_area_hectares', 'fields',  'owner', 'organization', 'created_at']
        read_only_fields = ['organization']

class FarmActivitySerializer(serializers.ModelSerializer):
    season = OrgScopedPrimaryKeyRelatedField(
        queryset=CropSeason.objects.all(), org_lookup="field__farm__organization"
    )

    class Meta:
        model = FarmActivity
        fields = ['id', 'season', 'activity_type', 'activity_date', 'description', 'cost', 'created_at']
        read_only_fields = ['created_at']

class CropSeasonSerializer(serializers.ModelSerializer):
    field = OrgScopedPrimaryKeyRelatedField(queryset=Field.objects.all(), org_lookup="farm__organization")
    # This nests the activities inside the season so the frontend gets the full timeline at once
    activities = FarmActivitySerializer(many=True, read_only=True)

    class Meta:
        model = CropSeason
        fields = [
            'id', 'field', 'crop_type', 'season_name', 'status',
            'planting_date', 'expected_harvest_date', 'actual_harvest_date',
            'target_yield_kg', 'actual_yield_kg', 'activities', 'created_at',
        ]
        read_only_fields = ['created_at']
