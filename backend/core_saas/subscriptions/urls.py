from django.urls import path
from .views import SubscriptionDetailView, CreateCheckoutSessionView

urlpatterns = [
    path('me/', SubscriptionDetailView.as_view(), name='subscription-detail'),
    path('checkout-session/', CreateCheckoutSessionView.as_view(), name='checkout-session'),
]