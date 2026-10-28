from django.urls import path

from .views import CreateCheckoutSessionView, SubscriptionDetailView, stripe_webhook

urlpatterns = [
    path('me/', SubscriptionDetailView.as_view(), name='subscription-detail'),
    path('checkout-session/', CreateCheckoutSessionView.as_view(), name='checkout-session'),
    path('webhook/', stripe_webhook, name='stripe-webhook'),
]