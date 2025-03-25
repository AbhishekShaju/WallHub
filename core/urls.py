from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('upload/', views.upload_wallpaper, name='upload_wallpaper'),
    path('wallpaper/<int:pk>/', views.wallpaper_detail, name='wallpaper_detail'),
    path('wallpaper/<int:pk>/download/', views.download_wallpaper, name='download_wallpaper'),
    path('wallpaper/<int:pk>/purchase/', views.purchase_wallpaper, name='purchase_wallpaper'),
    path('profile/', views.profile, name='profile'),
    path('register/', views.register, name='register'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
] 