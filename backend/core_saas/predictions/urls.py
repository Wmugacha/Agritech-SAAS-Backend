from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import SoilAnalysisViewSet, DashboardAnalyticsView

router = DefaultRouter()
router.register(r'', SoilAnalysisViewSet, basename='soil-analysis')

urlpatterns = router.urls + [
    path('analytics/dashboard/', DashboardAnalyticsView.as_view(), name='dashboard-analytics'),
]