from rest_framework.routers import DefaultRouter
from .views import FarmViewSet, FieldViewSet, CropSeasonViewSet, FarmActivityViewSet

router = DefaultRouter()
router.register(r'farms', FarmViewSet, basename='farms')
router.register(r'fields', FieldViewSet, basename='fields')
router.register(r'seasons', CropSeasonViewSet, basename='cropseason')
router.register(r'activities', FarmActivityViewSet, basename='farmactivity')

urlpatterns = router.urls