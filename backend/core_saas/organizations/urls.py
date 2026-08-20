from django.urls import path
from .views import CurrentOrganizationView, DemoCreateView, CreateOrganizationView

urlpatterns = [
    path("create/", CreateOrganizationView.as_view(), name="create_organization"),
    path("organization/", CurrentOrganizationView.as_view(), name="current_organization"),
    path("demo-create/", DemoCreateView.as_view(), name="demo_create"),
]

