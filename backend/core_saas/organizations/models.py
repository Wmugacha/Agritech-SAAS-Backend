import uuid
from django.db import models

class Organization(models.Model):
    """
    Represents a tenant in the system.
    Example: A farm, company, or client account.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    name = models.CharField(
        max_length=255,
        unique=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.name


from django.conf import settings

class Membership(models.Model):
    """
    Links a user to an organization.
    This is where roles and permissions are classified.
    """

    # ---- ROLE CONSTANTS ----
    OWNER = "OWNER"
    ORG_ADMIN = "ORG_ADMIN"
    AGRONOMIST = "AGRONOMIST"
    VIEWER = "VIEWER"

    ROLE_CHOICES = (
        (OWNER, "Owner"),
        (ORG_ADMIN, "Organization Admin"),
        (AGRONOMIST, "Agronomist"),
        (VIEWER, "Viewer"),
    )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships"
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships"
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=VIEWER
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'organization'], 
                name='unique_owner_organization'
            )
        ]

    def __str__(self):
        return f"{self.user.email} → {self.organization.name}"
