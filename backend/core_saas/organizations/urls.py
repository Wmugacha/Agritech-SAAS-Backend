from django.urls import path
from .views import CurrentOrganizationView

urlpatterns = [
    path("organization/", CurrentOrganizationView.as_view()),
]
