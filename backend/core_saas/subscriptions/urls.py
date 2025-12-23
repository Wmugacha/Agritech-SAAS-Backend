from django.urls import path
from .views import SubscriptionDetailView

urlpatterns = [
    path('me/', SubscriptionDetailView.as_view(), name='subscription-detail'),
]