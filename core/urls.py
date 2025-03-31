from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('search/', views.search_wallpapers, name='search_wallpapers'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('upload/', views.upload_wallpaper, name='upload_wallpaper'),
    path('wallpaper/<int:pk>/', views.wallpaper_detail, name='wallpaper_detail'),
    path('wallpaper/<int:pk>/download/', views.download_wallpaper, name='download_wallpaper'),
    path('wallpaper/<int:pk>/initiate-payment/', views.initiate_payment, name='initiate_payment'),
    path('payment/success/', views.payment_success, name='payment_success'),
    path('profile/', views.profile, name='profile'),
    path('register/', views.register, name='register'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/wallpaper/<int:pk>/delete/', views.admin_delete_wallpaper, name='admin_delete_wallpaper'),
    path('admin/custom/', views.custom_admin_dashboard, name='custom_admin_dashboard'),
    path('admin/login/', views.admin_login, name='admin_login'),
    path('password-reset/', views.password_reset_request, name='password_reset_request'),
    path('reset-password/', views.password_reset, name='password_reset'),
] 