from rest_framework.routers import DefaultRouter
from .views import FarmViewSet, FieldViewSet

router = DefaultRouter()
router.register(r'farms', FarmViewSet, basename='farms')
router.register(r'fields', FieldViewSet, basename='fields')

urlpatterns = router.urls