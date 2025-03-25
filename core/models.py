from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(max_length=500, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    date_joined = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username}'s Profile"

class Wallpaper(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    image = models.ImageField(upload_to='wallpapers/')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_free = models.BooleanField(default=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    upload_date = models.DateTimeField(default=timezone.now)
    downloads = models.IntegerField(default=0)
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-upload_date']

class Purchase(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    wallpaper = models.ForeignKey(Wallpaper, on_delete=models.CASCADE)
    purchase_date = models.DateTimeField(default=timezone.now)
    transaction_id = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.user.username} purchased {self.wallpaper.title}"

    class Meta:
        unique_together = ('user', 'wallpaper')
