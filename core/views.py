from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from .models import Wallpaper, UserProfile, Purchase
from django.contrib.auth.models import User
from django.http import HttpResponse
import os

def home(request):
    wallpapers = Wallpaper.objects.filter(is_approved=True).order_by('-upload_date')
    return render(request, 'core/home.html', {'wallpapers': wallpapers})

@login_required
def dashboard(request):
    user_wallpapers = Wallpaper.objects.filter(uploaded_by=request.user)
    purchased_wallpapers = Wallpaper.objects.filter(purchase__user=request.user)
    return render(request, 'core/dashboard.html', {
        'user_wallpapers': user_wallpapers,
        'purchased_wallpapers': purchased_wallpapers
    })

@login_required
def upload_wallpaper(request):
    if request.method == 'POST':
        try:
            title = request.POST.get('title')
            description = request.POST.get('description')
            price = request.POST.get('price', '0')
            image = request.FILES.get('image')
            
            if not title:
                messages.error(request, 'Title is required.')
                return render(request, 'core/upload_wallpaper.html')
            
            if not description:
                messages.error(request, 'Description is required.')
                return render(request, 'core/upload_wallpaper.html')
            
            if not image:
                messages.error(request, 'Please select an image.')
                return render(request, 'core/upload_wallpaper.html')
            
            # Validate image file type
            if not image.content_type.startswith('image/'):
                messages.error(request, 'Please upload a valid image file.')
                return render(request, 'core/upload_wallpaper.html')
            
            # Validate image size (max 5MB)
            if image.size > 5 * 1024 * 1024:  # 5MB in bytes
                messages.error(request, 'Image size should be less than 5MB.')
                return render(request, 'core/upload_wallpaper.html')
            
            # Convert price to float and handle potential errors
            try:
                price = float(price)
                if price < 0:
                    price = 0
            except ValueError:
                price = 0
            
            # Create the wallpaper
            wallpaper = Wallpaper.objects.create(
                title=title,
                description=description,
                image=image,
                price=price,
                is_free=price == 0,
                uploaded_by=request.user,
                is_approved=True
            )
            
            messages.success(request, 'Wallpaper uploaded successfully!')
            return redirect('dashboard')
            
        except Exception as e:
            messages.error(request, f'Error uploading wallpaper: {str(e)}')
            return render(request, 'core/upload_wallpaper.html')
    
    return render(request, 'core/upload_wallpaper.html')

def wallpaper_detail(request, pk):
    wallpaper = get_object_or_404(Wallpaper, pk=pk, is_approved=True)
    has_purchased = False
    if request.user.is_authenticated:
        has_purchased = Purchase.objects.filter(user=request.user, wallpaper=wallpaper).exists()
    
    context = {
        'wallpaper': wallpaper,
        'has_purchased': has_purchased,
        'can_download': wallpaper.is_free or has_purchased
    }
    return render(request, 'core/wallpaper_detail.html', context)

@login_required
def download_wallpaper(request, pk):
    wallpaper = get_object_or_404(Wallpaper, pk=pk, is_approved=True)
    
    if not wallpaper.is_free:
        # Check if user has purchased
        if not Purchase.objects.filter(user=request.user, wallpaper=wallpaper).exists():
            messages.error(request, 'You need to purchase this wallpaper first.')
            return redirect('wallpaper_detail', pk=pk)
    
    wallpaper.downloads += 1
    wallpaper.save()
    
    file_path = wallpaper.image.path
    with open(file_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type='image/jpeg')
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
        return response

@login_required
def purchase_wallpaper(request, pk):
    wallpaper = get_object_or_404(Wallpaper, pk=pk, is_approved=True)
    
    if wallpaper.is_free:
        messages.error(request, 'This wallpaper is free. You can download it directly.')
        return redirect('wallpaper_detail', pk=pk)
    
    if Purchase.objects.filter(user=request.user, wallpaper=wallpaper).exists():
        messages.error(request, 'You have already purchased this wallpaper.')
        return redirect('wallpaper_detail', pk=pk)
    
    # Here you would typically integrate with a payment processor
    # For now, we'll just create the purchase record
    Purchase.objects.create(
        user=request.user,
        wallpaper=wallpaper,
        transaction_id='DEMO-' + str(pk)  # This would be replaced with actual transaction ID
    )
    
    messages.success(request, 'Purchase successful! You can now download the wallpaper.')
    return redirect('wallpaper_detail', pk=pk)

@login_required
def profile(request):
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    user_wallpapers = Wallpaper.objects.filter(uploaded_by=request.user)
    
    if request.method == 'POST':
        # Handle profile picture upload
        if 'profile_picture' in request.FILES:
            user_profile.profile_picture = request.FILES['profile_picture']
        
        # Handle bio update
        user_profile.bio = request.POST.get('bio', '')
        user_profile.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')
    
    return render(request, 'core/profile.html', {
        'profile': user_profile,
        'user_wallpapers': user_wallpapers
    })

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            UserProfile.objects.create(user=user)
            messages.success(request, 'Registration successful! Please login.')
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'core/register.html', {'form': form})

@user_passes_test(lambda u: u.is_staff)
def admin_dashboard(request):
    pending_wallpapers = Wallpaper.objects.filter(is_approved=False)
    approved_wallpapers = Wallpaper.objects.filter(is_approved=True)
    return render(request, 'core/admin_dashboard.html', {
        'pending_wallpapers': pending_wallpapers,
        'approved_wallpapers': approved_wallpapers
    })
