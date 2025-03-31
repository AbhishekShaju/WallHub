from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from .models import Wallpaper, UserProfile, Purchase
from django.contrib.auth.models import User
import os
import razorpay
import json
from django.core.mail import send_mail
from django.utils.crypto import get_random_string
from django.contrib.auth.hashers import make_password
from .forms import PasswordResetRequestForm, PasswordResetForm, UserRegistrationForm
from django.db.models import Sum
from django.contrib.auth import authenticate, login

def get_razorpay_client():
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

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
        title = request.POST.get('title')
        description = request.POST.get('description')
        price = request.POST.get('price')
        image = request.FILES.get('image')
        is_free = request.POST.get('is_free') == 'on'

        if not title or not description or not image:
            messages.error(request, 'Please fill in all required fields.')
            return redirect('upload_wallpaper')

        try:
            wallpaper = Wallpaper.objects.create(
                title=title,
                description=description,
                price=0 if is_free else float(price),
                image=image,
                uploaded_by=request.user
            )
            messages.success(request, 'Wallpaper uploaded successfully!')
            return redirect('wallpaper_detail', pk=wallpaper.pk)
        except Exception as e:
            messages.error(request, f'Error uploading wallpaper: {str(e)}')
            return redirect('upload_wallpaper')

    return render(request, 'core/upload_wallpaper.html')

def wallpaper_detail(request, pk):
    wallpaper = get_object_or_404(Wallpaper, pk=pk, is_approved=True)
    is_purchased = False
    if request.user.is_authenticated:
        is_purchased = Purchase.objects.filter(user=request.user, wallpaper=wallpaper).exists()
    
    context = {
        'wallpaper': wallpaper,
        'is_purchased': is_purchased,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'razorpay_test_mode': settings.RAZORPAY_TEST_MODE
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
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            # Create the user but don't save yet
            user = form.save(commit=False)
            # Set the password
            user.set_password(form.cleaned_data['password'])
            # Now save the user
            user.save()
            messages.success(request, 'Registration successful! You can now log in.')
            return redirect('login')
    else:
        form = UserRegistrationForm()
    return render(request, 'core/register.html', {'form': form})

def is_admin(user):
    return user.is_staff

@user_passes_test(is_admin)
def admin_dashboard(request):
    wallpapers = Wallpaper.objects.all().order_by('-upload_date')
    users = User.objects.all().order_by('-date_joined')
    return render(request, 'admin/custom_admin_dashboard.html', {
        'wallpapers': wallpapers,
        'users': users
    })

@user_passes_test(is_admin)
def admin_delete_wallpaper(request, pk):
    if request.method == 'POST':
        wallpaper = get_object_or_404(Wallpaper, pk=pk)
        wallpaper.delete()
        messages.success(request, 'Wallpaper deleted successfully.')
    return redirect('admin_dashboard')

@login_required
def initiate_payment(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User not authenticated'}, status=401)
        
    try:
        wallpaper = get_object_or_404(Wallpaper, pk=pk, is_approved=True)
        
        if wallpaper.is_free:
            return JsonResponse({'error': 'This wallpaper is free. You can download it directly.'})
        
        if Purchase.objects.filter(user=request.user, wallpaper=wallpaper).exists():
            return JsonResponse({'error': 'You have already purchased this wallpaper.'})
        
        # Create Razorpay client
        try:
            client = get_razorpay_client()
        except Exception as e:
            return JsonResponse({'error': 'Failed to initialize payment gateway'}, status=500)
        
        # Create Razorpay order
        order_amount = int(float(wallpaper.price) * 100)  # Convert to paise
        order_currency = 'INR'
        order_receipt = f'wallpaper_{wallpaper.pk}_{request.user.pk}'
        
        order_data = {
            'amount': order_amount,
            'currency': order_currency,
            'receipt': order_receipt,
            'payment_capture': 1
        }
        
        try:
            order = client.order.create(data=order_data)
            return JsonResponse({
                'id': order['id'],
                'amount': order['amount'],
                'currency': order['currency']
            })
        except Exception as e:
            return JsonResponse({'error': 'Failed to create payment order: ' + str(e)}, status=400)
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def payment_success(request):
    try:
        if not request.body:
            return JsonResponse({'error': 'No payment data received'}, status=400)
            
        # Get payment data from request
        payment_data = json.loads(request.body)
        razorpay_payment_id = payment_data.get('razorpay_payment_id')
        razorpay_order_id = payment_data.get('razorpay_order_id')
        razorpay_signature = payment_data.get('razorpay_signature')
        
        if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature]):
            return JsonResponse({'error': 'Missing payment information'}, status=400)
        
        # Create Razorpay client
        client = get_razorpay_client()
        
        # Verify payment signature
        params_dict = {
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_order_id': razorpay_order_id,
            'razorpay_signature': razorpay_signature
        }
        
        try:
            client.utility.verify_payment_signature(params_dict)
        except Exception as e:
            return JsonResponse({'error': 'Invalid payment signature'}, status=400)
        
        # Get order details
        try:
            order = client.order.fetch(razorpay_order_id)
            wallpaper_id = order['receipt'].split('_')[1]
            wallpaper = get_object_or_404(Wallpaper, pk=wallpaper_id)
            
            # Check if already purchased
            if Purchase.objects.filter(user=request.user, wallpaper=wallpaper).exists():
                return JsonResponse({'error': 'Wallpaper already purchased'}, status=400)
            
            # Create purchase record
            Purchase.objects.create(
                user=request.user,
                wallpaper=wallpaper,
                transaction_id=razorpay_payment_id
            )
            
            return JsonResponse({'status': 'success'})
            
        except Exception as e:
            return JsonResponse({'error': 'Failed to process payment'}, status=400)
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

def search_wallpapers(request):
    query = request.GET.get('q', '')
    if query:
        wallpapers = Wallpaper.objects.filter(title__icontains=query, is_approved=True).order_by('-upload_date')
    else:
        wallpapers = Wallpaper.objects.filter(is_approved=True).order_by('-upload_date')
    
    return render(request, 'core/search_results.html', {
        'wallpapers': wallpapers,
        'query': query
    })

def password_reset_request(request):
    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = User.objects.get(email=email)
                # Generate a temporary password
                temp_password = get_random_string(length=8)
                user.password = make_password(temp_password)
                user.save()
                # Send email with temporary password
                send_mail(
                    'Password Reset Request',
                    f'Your temporary password is: {temp_password}',
                    'noreply@wallhub.com',
                    [email],
                    fail_silently=False,
                )
                messages.success(request, 'A temporary password has been sent to your email.')
                return redirect('login')
            except User.DoesNotExist:
                messages.error(request, 'No account found with that email address.')
    else:
        form = PasswordResetRequestForm()
    return render(request, 'core/password_reset_request.html', {'form': form})

@login_required
def password_reset(request):
    if request.method == 'POST':
        form = PasswordResetForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your password has been reset successfully.')
            return redirect('dashboard')
    else:
        form = PasswordResetForm(user=request.user)
    return render(request, 'core/password_reset.html', {'form': form})

@user_passes_test(is_admin)
def custom_admin_dashboard(request):
    # Get statistics
    total_users = User.objects.count()
    total_wallpapers = Wallpaper.objects.count()
    total_downloads = Wallpaper.objects.aggregate(total=Sum('downloads'))['total'] or 0
    total_purchases = Purchase.objects.count()
    
    # Get recent data
    recent_wallpapers = Wallpaper.objects.all().order_by('-upload_date')[:10]
    recent_users = User.objects.all().order_by('-date_joined')[:10]
    recent_purchases = Purchase.objects.all().order_by('-purchase_date')[:10]
    
    context = {
        'total_users': total_users,
        'total_wallpapers': total_wallpapers,
        'total_downloads': total_downloads,
        'total_purchases': total_purchases,
        'recent_wallpapers': recent_wallpapers,
        'recent_users': recent_users,
        'recent_purchases': recent_purchases,
    }
    
    return render(request, 'admin/custom_admin.html', context)

def admin_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None and user.is_staff:
            login(request, user)
            return redirect('custom_admin_dashboard')
        else:
            messages.error(request, 'Invalid admin credentials.')
    
    return render(request, 'admin/admin_login.html')
