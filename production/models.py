# production/models.py
from django.db import models
from django.contrib.auth.models import User

class Department(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    def __str__(self): return self.name

class UserProfile(models.Model):
    ROLE_CHOICES = [('admin','Admin'),('staff','Staff'),('viewer','Viewer')]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='viewer')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    def __str__(self): return f'{self.user.username} ({self.role})'

class Lot(models.Model):
    lot_no = models.CharField(max_length=100, unique=True)
    part_no = models.CharField(max_length=100, blank=True, null=True)
    customer = models.CharField(max_length=100, blank=True, null=True)
    description = models.CharField(max_length=255, blank=True, null=True)

    production_quantity = models.IntegerField(default=0)
    pieces_per_box = models.IntegerField(default=0)
    target = models.IntegerField(default=0)

    department = models.CharField(max_length=100, blank=True, null=True)
    machine_no = models.CharField(max_length=100, blank=True, null=True)
    type = models.CharField(max_length=50, blank=True, null=True)

    first_scan = models.DateTimeField(null=True, blank=True)
    last_scan  = models.DateTimeField(null=True, blank=True)

class ScanRecord(models.Model):
    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name='scans')
    machine_no = models.CharField(max_length=100, blank=True)
    qty = models.IntegerField(default=0)
    scanned_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return f"{self.lot.lot_no} +{self.qty} @ {self.machine_no}"
