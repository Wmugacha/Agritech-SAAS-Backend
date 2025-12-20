from django.urls import path
from .views import CurrentOrganizationView, DemoCreateView

urlpatterns = [
    path("organization/", CurrentOrganizationView.as_view()),
    path("demo-create/", DemoCreateView.as_view()),
]
