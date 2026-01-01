from rest_framework.routers import DefaultRouter
from .views import SoilAnalysisViewSet

router = DefaultRouter()
router.register(r'', SoilAnalysisViewSet, basename='soil-analysis')

urlpatterns = router.urls