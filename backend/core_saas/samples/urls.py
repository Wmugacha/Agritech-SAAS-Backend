from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SoilSampleViewSet

# 1. Create a router and register viewset with it.
router = DefaultRouter()
router.register(r'soil-samples', SoilSampleViewSet, basename='soil-sample')

# 2. The API URLs are now determined automatically by the router.
urlpatterns = [
    path('', include(router.urls)),
]
