from rest_framework import serializers

from .utils import get_request_organization


class OrgScopedPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    """
    A foreign key field that only accepts objects from the requesting user's organization.

    Objects from other organizations fail validation exactly like ids that don't exist,
    so a client can't use the error to discover another tenant's data. Works the same
    on create and update because DRF validates every incoming field.

        farm = OrgScopedPrimaryKeyRelatedField(queryset=Farm.objects.all(), org_lookup="organization")
    """

    def __init__(self, org_lookup, **kwargs):
        self.org_lookup = org_lookup
        super().__init__(**kwargs)

    def get_queryset(self):
        org = get_request_organization(self.context["request"])
        return super().get_queryset().filter(**{self.org_lookup: org})