import uuid
import random
import time
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from organizations.models import Organization, Membership
from subscriptions.models import Subscription
from farms.models import Farm, Field, CropSeason, FarmActivity
from samples.models import SoilSample
from predictions.models import SoilAnalysisJob

User = get_user_model()

class Command(BaseCommand):
    help = "Populates the database with large-scale benchmark data (default: 2k users + related records)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=2000,
            help='Total number of users to create (default: 2,000)'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Batch size for bulk insertion (default: 1,000)'
        )

    def handle(self, *args, **options):
        total_users = options['users']
        batch_size = options['batch_size']

        self.stdout.write(self.style.WARNING(f"Starting database seed for {total_users:,} users..."))
        start_time = time.time()

        # ----------------------------------------------------
        # 1. GENERATE USERS IN BATCHES
        # ----------------------------------------------------
        self.stdout.write("1/8 Generating Users...")
        user_ids = []
        now = timezone.now()

        for i in range(0, total_users, batch_size):
            chunk_size = min(batch_size, total_users - i)
            users_batch = []
            
            for j in range(chunk_size):
                u_id = uuid.uuid4()
                user_ids.append(u_id)
                users_batch.append(
                    User(
                        id=u_id,
                        email=f"user_{i + j + 1}@agritech-saas.internal",
                        is_active=True,
                        is_staff=False,
                        date_joined=now - timedelta(days=random.randint(0, 365))
                    )
                )

            User.objects.bulk_create(users_batch, batch_size=batch_size)
            self.stdout.write(f"   Created {i + chunk_size:,} / {total_users:,} users")

        # ----------------------------------------------------
        # 2. GENERATE ORGANIZATIONS (~1 org per 10 users)
        # ----------------------------------------------------
        total_orgs = max(1, total_users // 10)
        self.stdout.write(f"2/8 Generating {total_orgs:,} Organizations...")
        org_objs = []
        
        for i in range(total_orgs):
            org_objs.append(
                Organization(
                    id=uuid.uuid4(),
                    name=f"Agri Coop {i + 1} - {uuid.uuid4().hex[:6]}"
                )
            )

        Organization.objects.bulk_create(org_objs, batch_size=batch_size)
        orgs = list(Organization.objects.all())

        # ----------------------------------------------------
        # 3. GENERATE SUBSCRIPTIONS (1 per Org)
        # ----------------------------------------------------
        self.stdout.write("3/8 Generating Subscriptions...")
        subscriptions = []
        for org in orgs:
            subscriptions.append(
                Subscription(
                    id=uuid.uuid4(),
                    organization=org,
                    plan=random.choice([Subscription.PlanType.FREE, Subscription.PlanType.PRO]),
                    status=Subscription.Status.ACTIVE,
                    is_active=True
                )
            )

        Subscription.objects.bulk_create(subscriptions, batch_size=batch_size)

        # ----------------------------------------------------
        # 4. GENERATE MEMBERSHIPS
        # ----------------------------------------------------
        self.stdout.write("4/8 Generating Memberships...")
        memberships = []
        
        # Assign members to organizations
        for i, u_id in enumerate(user_ids):
            target_org = orgs[i % total_orgs]
            role = Membership.OWNER if (i % 10 == 0) else random.choice([
                Membership.ORG_ADMIN, Membership.AGRONOMIST, Membership.VIEWER
            ])
            memberships.append(
                Membership(
                    id=uuid.uuid4(),
                    user_id=u_id,
                    organization=target_org,
                    role=role
                )
            )

            if len(memberships) >= batch_size:
                Membership.objects.bulk_create(memberships, ignore_conflicts=True, batch_size=batch_size)
                memberships = []

        if memberships:
            Membership.objects.bulk_create(memberships, ignore_conflicts=True, batch_size=batch_size)

        # ----------------------------------------------------
        # 5. GENERATE FARMS & FIELDS
        # ----------------------------------------------------
        total_farms = max(1, total_orgs * 2)
        self.stdout.write(f"5/8 Generating {total_farms:,} Farms and Fields...")
        
        farms = []
        for i in range(total_farms):
            assigned_org = orgs[i % total_orgs]
            owner_user_id = user_ids[(i * 5) % len(user_ids)]
            farms.append(
                Farm(
                    id=uuid.uuid4(),
                    organization=assigned_org,
                    owner_id=owner_user_id,
                    name=f"Farm Plot {i + 1}",
                    location=random.choice(["Nakuru", "Eldoret", "Kitale", "Narok", "Nyeri", "Meru"]),
                    total_area_hectares=round(random.uniform(1.5, 50.0), 2)
                )
            )

        Farm.objects.bulk_create(farms, batch_size=batch_size)
        all_farms = list(Farm.objects.all())

        fields = []
        crop_choices = [c[0] for c in Field.CropType.choices]
        for farm in all_farms:
            # Cast Decimal total_area_hectares to float to avoid TypeError in random.uniform()
            farm_area = float(farm.total_area_hectares)
            for j in range(random.randint(1, 3)):
                fields.append(
                    Field(
                        id=uuid.uuid4(),
                        farm=farm,
                        name=f"Field Block {j + 1}",
                        crop_type=random.choice(crop_choices),
                        area_hectares=round(random.uniform(0.5, farm_area), 2),
                        latitude=round(random.uniform(-1.5, 1.5), 6),
                        longitude=round(random.uniform(34.5, 38.0), 6)
                    )
                )

        Field.objects.bulk_create(fields, batch_size=batch_size)
        all_fields = list(Field.objects.all())

        # ----------------------------------------------------
        # 6. GENERATE CROP SEASONS & ACTIVITIES
        # ----------------------------------------------------
        self.stdout.write("6/8 Generating Crop Seasons and Farm Activities...")
        seasons = []
        for field in all_fields:
            seasons.append(
                CropSeason(
                    field=field,
                    crop_type=field.crop_type,
                    season_name=random.choice(["Long Rains 2024", "Short Rains 2024", "Long Rains 2025"]),
                    status=random.choice(['PLANNED', 'GROWING', 'HARVESTED']),
                    planting_date=(now - timedelta(days=random.randint(30, 180))).date(),
                    expected_harvest_date=(now + timedelta(days=random.randint(30, 90))).date(),
                    target_yield_kg=round(random.uniform(1000.0, 6000.0), 2)
                )
            )

        CropSeason.objects.bulk_create(seasons, batch_size=batch_size)
        all_seasons = list(CropSeason.objects.all()[:100000])

        activities = []
        activity_types = ['SOIL_TEST', 'PLANTING', 'FERTILIZER', 'WEEDING', 'HARVESTING']
        for season in all_seasons:
            activities.append(
                FarmActivity(
                    season=season,
                    activity_type=random.choice(activity_types),
                    activity_date=(now - timedelta(days=random.randint(1, 60))).date(),
                    description="Standard seasonal management task",
                    cost=round(random.uniform(50.0, 500.0), 2)
                )
            )

        FarmActivity.objects.bulk_create(activities, batch_size=batch_size)

        # ----------------------------------------------------
        # 7. GENERATE SOIL SAMPLES
        # ----------------------------------------------------
        self.stdout.write("7/8 Generating Soil Samples...")
        soil_samples = []
        for i in range(min(total_users, 300000)):
            target_org = orgs[i % total_orgs]
            uploader_id = user_ids[i]
            
            # Bulk creation bypasses full_clean() so clean() logic won't fail during seed
            soil_samples.append(
                SoilSample(
                    id=uuid.uuid4(),
                    organization=target_org,
                    uploaded_by_id=uploader_id,
                    label=f"Sample Point #{i + 1}",
                    latitude=round(random.uniform(-1.5, 1.5), 6),
                    longitude=round(random.uniform(34.5, 38.0), 6),
                    depth_cm=random.choice([15, 30, 45]),
                    crop_type=random.choice(crop_choices),
                    ph=round(random.uniform(5.2, 7.5), 2),
                    nitrogen=round(random.uniform(10.0, 80.0), 2),
                    phosphorus=round(random.uniform(5.0, 45.0), 2),
                    potassium=round(random.uniform(80.0, 300.0), 2)
                )
            )

            if len(soil_samples) >= batch_size:
                SoilSample.objects.bulk_create(soil_samples, batch_size=batch_size)
                soil_samples = []

        if soil_samples:
            SoilSample.objects.bulk_create(soil_samples, batch_size=batch_size)

        # ----------------------------------------------------
        # 8. GENERATE SOIL ANALYSIS JOBS
        # ----------------------------------------------------
        self.stdout.write("8/8 Generating Soil Analysis Prediction Jobs...")
        jobs = []
        statuses = [SoilAnalysisJob.Status.SUCCESS, SoilAnalysisJob.Status.RUNNING, SoilAnalysisJob.Status.PENDING]
        
        for i in range(min(total_users, 200000)):
            target_org = orgs[i % total_orgs]
            req_user_id = user_ids[i]
            field_obj = all_fields[i % len(all_fields)]

            jobs.append(
                SoilAnalysisJob(
                    id=uuid.uuid4(),
                    organization=target_org,
                    requested_by_id=req_user_id,
                    field=field_obj,
                    status=random.choice(statuses),
                    predicted_properties={
                        "nitrogen_ppm": round(random.uniform(20.0, 60.0), 1),
                        "phosphorus_ppm": round(random.uniform(15.0, 35.0), 1),
                        "recommended_urea_kg_per_ha": round(random.uniform(50.0, 180.0), 1)
                    },
                    model_version="v1.0.2",
                    is_billable=True
                )
            )

            if len(jobs) >= batch_size:
                SoilAnalysisJob.objects.bulk_create(jobs, batch_size=batch_size)
                jobs = []

        if jobs:
            SoilAnalysisJob.objects.bulk_create(jobs, batch_size=batch_size)

        elapsed = time.time() - start_time
        self.stdout.write(
            self.style.SUCCESS(f"Successfully populated database in {elapsed:.2f} seconds!")
        )

