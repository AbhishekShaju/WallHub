from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from .models import Wallpaper, UserProfile, Purchase, Category
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
from django.template.loader import get_template
import pdfkit
from django.views.decorators.http import require_POST
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import method_decorator
from django.views.generic import ListView
from django.urls import reverse_lazy
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView
from django.contrib.auth.views import LoginView
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Count
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.template.loader import render_to_string
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime
from .utils import generate_invoice_number
from .forms import WallpaperForm, UserProfileForm, CustomUserCreationForm, CustomAuthenticationForm

def get_razorpay_client():
    try:
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        client.set_app_details({"title": "WallHub"})
        return client
    except Exception as e:
        print(f"Error initializing Razorpay client: {str(e)}")
        return None

def home(request):
    filter_type = request.GET.get('filter', 'all')
    
    if filter_type == 'free':
        # Only show wallpapers that are marked as free AND have price = 0
        wallpapers = Wallpaper.objects.filter(is_free=True, price=0).order_by('-upload_date')
    elif filter_type == 'paid':
        # Show wallpapers that are either marked as not free OR have price > 0
        wallpapers = Wallpaper.objects.filter(Q(is_free=False) | Q(price__gt=0)).order_by('-upload_date')
    else:
        wallpapers = Wallpaper.objects.all().order_by('-upload_date')
    
    return render(request, 'core/home.html', {
        'wallpapers': wallpapers,
        'current_filter': filter_type
    })

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
            # Convert price to float and ensure it's not negative
            price_value = 0 if is_free else max(0, float(price))
            
            wallpaper = Wallpaper.objects.create(
                title=title,
                description=description,
                price=price_value,
                is_free=is_free,
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
    wallpaper = get_object_or_404(Wallpaper, pk=pk)
    is_purchased = False
    razorpay_order = None

    if request.user.is_authenticated:
        is_purchased = Purchase.objects.filter(user=request.user, wallpaper=wallpaper).exists()

    try:
        if not is_purchased and wallpaper.price > 0:
            client = get_razorpay_client()
            if client:
                amount = int(wallpaper.price * 100)  # Convert to paisa
                currency = settings.RAZORPAY_CURRENCY
                
                # Create Razorpay order
                data = {
                    'amount': amount,
                    'currency': currency,
                    'receipt': f'wallpaper_{wallpaper.id}',
                    'payment_capture': 1,  # Auto capture payment
                    'notes': {
                        'wallpaper_id': str(wallpaper.id),
                        'user_id': str(request.user.id) if request.user.is_authenticated else '',
                        'title': wallpaper.title
                    }
                }
                try:
                    razorpay_order = client.order.create(data=data)
                except razorpay.errors.BadRequestError as e:
                    print(f"Razorpay order creation error: {str(e)}")
                    messages.error(request, "Unable to create payment order. Please try again later.")
                    razorpay_order = None
            else:
                messages.error(request, "Payment system is currently unavailable. Please try again later.")
    except Exception as e:
        print(f"Error in wallpaper_detail: {str(e)}")
        messages.error(request, "Payment system is currently unavailable. Please try again later.")
        razorpay_order = None

    # Find similar wallpapers based on title similarity
    # Get all wallpapers except the current one
    all_wallpapers = Wallpaper.objects.exclude(pk=wallpaper.pk)
    
    # Extract keywords from the current wallpaper title
    current_keywords = wallpaper.title.lower().split()
    
    # Calculate similarity scores for each wallpaper
    similar_wallpapers = []
    for other_wallpaper in all_wallpapers:
        other_keywords = other_wallpaper.title.lower().split()
        
        # Count matching keywords
        matching_keywords = sum(1 for keyword in current_keywords if keyword in other_keywords)
        
        # Calculate similarity score (number of matching keywords / total keywords in current wallpaper)
        if current_keywords:
            similarity_score = matching_keywords / len(current_keywords)
        else:
            similarity_score = 0
            
        # Add to similar wallpapers if similarity score is above threshold
        if similarity_score > 0.3:  # 30% similarity threshold
            similar_wallpapers.append((other_wallpaper, similarity_score))
    
    # Sort by similarity score (highest first) and take top 5
    similar_wallpapers.sort(key=lambda x: x[1], reverse=True)
    similar_wallpapers = [w[0] for w in similar_wallpapers[:5]]

    context = {
        'wallpaper': wallpaper,
        'is_purchased': is_purchased,
        'razorpay_order': razorpay_order,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID if razorpay_order else None,
        'razorpay_test_mode': settings.RAZORPAY_TEST_MODE,
        'similar_wallpapers': similar_wallpapers
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
    purchases = Purchase.objects.filter(user=request.user).order_by('-purchase_date')
    
    # Get earnings from wallpapers uploaded by the user
    earnings = Purchase.objects.filter(wallpaper__uploaded_by=request.user).aggregate(
        total_earnings=Sum('wallpaper__price')
    )['total_earnings'] or 0
    
    # Get wallpapers purchased by others from this user's uploads
    purchased_by_others = Purchase.objects.filter(
        wallpaper__uploaded_by=request.user
    ).exclude(
        user=request.user
    ).select_related('user', 'wallpaper').order_by('-purchase_date')
    
    if request.method == 'POST':
        # Handle profile picture upload
        if 'profile_picture' in request.FILES:
            user_profile.profile_picture = request.FILES['profile_picture']
            user_profile.save()
            messages.success(request, 'Profile picture updated successfully!')
            return redirect('profile')
        
        # Handle other profile updates
        user_profile.bio = request.POST.get('bio', '')
        user_profile.phone = request.POST.get('phone', '')
        user_profile.address = request.POST.get('address', '')
        user_profile.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')
    
    return render(request, 'core/profile.html', {
        'profile': user_profile,
        'user_wallpapers': user_wallpapers,
        'purchases': purchases,
        'earnings': earnings,
        'purchased_by_others': purchased_by_others
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
def initiate_payment(request, wallpaper_id):
    wallpaper = get_object_or_404(Wallpaper, id=wallpaper_id)
    
    if wallpaper.is_free:
        messages.error(request, "This wallpaper is free. No payment required.")
        return redirect('wallpaper_detail', pk=wallpaper_id)
    
    if Purchase.objects.filter(user=request.user, wallpaper=wallpaper).exists():
        messages.error(request, "You have already purchased this wallpaper.")
        return redirect('wallpaper_detail', pk=wallpaper_id)
    
    # Create a purchase record
    purchase = Purchase.objects.create(
        user=request.user,
        wallpaper=wallpaper,
        transaction_id=f"TXN_{int(timezone.now().timestamp())}"
    )
    
    # Redirect to success page
    return redirect('payment_success', purchase_id=purchase.id)

@login_required
def payment_success(request):
    if request.method == 'POST':
        try:
            # Get payment details from POST data
            razorpay_payment_id = request.POST.get('razorpay_payment_id')
            razorpay_order_id = request.POST.get('razorpay_order_id')
            razorpay_signature = request.POST.get('razorpay_signature')
            wallpaper_id = request.POST.get('wallpaper_id')

            if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature, wallpaper_id]):
                messages.error(request, 'Missing payment information. Please try again.')
                return redirect('wallpaper_detail', pk=wallpaper_id)

            # Get the wallpaper
            wallpaper = get_object_or_404(Wallpaper, id=wallpaper_id)

            # Check if already purchased
            if Purchase.objects.filter(user=request.user, wallpaper=wallpaper).exists():
                messages.warning(request, 'You have already purchased this wallpaper.')
                return redirect('wallpaper_detail', pk=wallpaper_id)

            # Verify the payment signature
            client = get_razorpay_client()
            if not client:
                messages.error(request, 'Payment system is currently unavailable. Please try again later.')
                return redirect('wallpaper_detail', pk=wallpaper_id)

            try:
                # Verify signature
                client.utility.verify_payment_signature({
                    'razorpay_payment_id': razorpay_payment_id,
                    'razorpay_order_id': razorpay_order_id,
                    'razorpay_signature': razorpay_signature
                })
                
                # Fetch payment details
                payment = client.payment.fetch(razorpay_payment_id)
                
                if payment['status'] != 'captured':
                    messages.error(request, f'Payment was not successful. Status: {payment["status"]}')
                    return redirect('wallpaper_detail', pk=wallpaper_id)

                # Verify amount matches
                expected_amount = int(wallpaper.price * 100)  # Convert to paisa
                if payment['amount'] != expected_amount:
                    messages.error(request, 'Payment amount mismatch. Please contact support.')
                    return redirect('wallpaper_detail', pk=wallpaper_id)

                # Create purchase record with transaction details
                try:
                    # Start transaction
                    from django.db import transaction
                    with transaction.atomic():
                        # Create purchase record
                        purchase = Purchase.objects.create(
                            user=request.user,
                            wallpaper=wallpaper,
                            transaction_id=razorpay_payment_id,
                            purchase_date=timezone.now()
                        )
                        
                        # Update wallpaper downloads count
                        wallpaper.downloads += 1
                        wallpaper.save()
                        
                        messages.success(request, 'Payment successful! You can now download the wallpaper.')
                        return redirect('wallpaper_detail', pk=wallpaper_id)
                    
                except Exception as e:
                    print(f"Error creating purchase record: {str(e)}")
                    # Try to fetch the payment again to ensure it was captured
                    try:
                        payment = client.payment.fetch(razorpay_payment_id)
                        if payment['status'] == 'captured':
                            # Log the error for debugging
                            print(f"Payment captured but purchase record creation failed. Payment ID: {razorpay_payment_id}")
                            print(f"User: {request.user.id}, Wallpaper: {wallpaper_id}")
                            print(f"Error details: {str(e)}")
                            
                            # Try to create purchase record again without transaction
                            try:
                                purchase = Purchase.objects.create(
                                    user=request.user,
                                    wallpaper=wallpaper,
                                    transaction_id=razorpay_payment_id,
                                    purchase_date=timezone.now()
                                )
                                wallpaper.downloads += 1
                                wallpaper.save()
                                messages.success(request, 'Payment successful! You can now download the wallpaper.')
                                return redirect('wallpaper_detail', pk=wallpaper_id)
                            except Exception as retry_error:
                                print(f"Retry error: {str(retry_error)}")
                                messages.error(request, f'Payment was successful but there was an error recording your purchase. Please contact support with your transaction ID: {razorpay_payment_id}')
                                return redirect('wallpaper_detail', pk=wallpaper_id)
                    except Exception as fetch_error:
                        print(f"Error fetching payment details: {str(fetch_error)}")
                    
                    messages.error(request, 'Error recording your purchase. Please contact support.')
                    return redirect('wallpaper_detail', pk=wallpaper_id)

            except razorpay.errors.SignatureVerificationError:
                print("Payment signature verification failed")
                messages.error(request, 'Payment verification failed. Please contact support.')
                return redirect('wallpaper_detail', pk=wallpaper_id)
            except razorpay.errors.BadRequestError as e:
                print(f"Razorpay error: {str(e)}")
                messages.error(request, f'Payment error: {str(e)}')
                return redirect('wallpaper_detail', pk=wallpaper_id)

        except Exception as e:
            print(f"Payment processing error: {str(e)}")
            messages.error(request, 'An error occurred during payment processing. Please try again.')
            return redirect('wallpaper_detail', pk=wallpaper_id)

    return redirect('home')

@login_required
def download_invoice(request, purchase_id):
    purchase = get_object_or_404(Purchase, id=purchase_id, user=request.user)
    
    # Create the HttpResponse object with PDF headers
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{purchase.id}.pdf"'
    
    # Create the PDF object, using the response object as its "file."
    doc = SimpleDocTemplate(response, pagesize=letter)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    normal_style = styles['Normal']
    
    # Add title
    elements.append(Paragraph("Invoice", title_style))
    elements.append(Spacer(1, 12))
    
    # Add invoice details
    elements.append(Paragraph(f"Transaction ID: {purchase.transaction_id}", normal_style))
    elements.append(Paragraph(f"Date: {purchase.purchase_date.strftime('%Y-%m-%d')}", normal_style))
    elements.append(Spacer(1, 12))
    
    # Add customer details
    elements.append(Paragraph("Customer Details:", title_style))
    elements.append(Paragraph(f"Name: {request.user.get_full_name() or request.user.username}", normal_style))
    elements.append(Paragraph(f"Email: {request.user.email}", normal_style))
    elements.append(Spacer(1, 12))
    
    # Add wallpaper details
    elements.append(Paragraph("Wallpaper Details:", title_style))
    elements.append(Paragraph(f"Title: {purchase.wallpaper.title}", normal_style))
    elements.append(Paragraph(f"Price: ₹{purchase.wallpaper.price}", normal_style))
    
    # Build the PDF
    doc.build(elements)
    
    return response

def search_wallpapers(request):
    query = request.GET.get('q', '')
    filter_type = request.GET.get('filter', 'all')
    
    if query:
        wallpapers = Wallpaper.objects.filter(title__icontains=query)
    else:
        wallpapers = Wallpaper.objects.all()
    
    # Apply filter
    if filter_type == 'free':
        # Only show wallpapers that are marked as free AND have price = 0
        wallpapers = wallpapers.filter(is_free=True, price=0)
    elif filter_type == 'paid':
        # Show wallpapers that are either marked as not free OR have price > 0
        wallpapers = wallpapers.filter(Q(is_free=False) | Q(price__gt=0))
    
    # Order by upload date
    wallpapers = wallpapers.order_by('-upload_date')
    
    return render(request, 'core/search_results.html', {
        'wallpapers': wallpapers,
        'query': query,
        'current_filter': filter_type
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
    # Redirect if user is already logged in as admin
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('custom_admin_dashboard')
        
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if not username or not password:
            messages.error(request, 'Please fill in all fields.')
            return render(request, 'core/admin_login.html')
            
        user = authenticate(request, username=username, password=password)
        
        if user is not None and user.is_staff:
            login(request, user)
            messages.success(request, 'Welcome to the admin dashboard!')
            return redirect('custom_admin_dashboard')
        else:
            messages.error(request, 'Invalid admin credentials or insufficient privileges.')
            return render(request, 'core/admin_login.html')
    
    return render(request, 'core/admin_login.html')

@login_required
def view_invoice(request, purchase_id):
    purchase = get_object_or_404(Purchase, id=purchase_id, user=request.user)
    return render(request, 'core/invoice.html', {'purchase': purchase})
