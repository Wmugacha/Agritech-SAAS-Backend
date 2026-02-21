from rest_framework import serializers
from .models import Subscription

class SubscriptionSerializer(serializers.ModelSerializer):
    limits = serializers.DictField(read_only=True)

    class Meta:
        model = Subscription
        fields = ['id', 'plan', 'status', 'limits', 'current_period_end']