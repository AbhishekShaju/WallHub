# Wallhub - Wallpaper E-commerce Platform

A Django-based e-commerce platform for users to buy and sell wallpapers.

## Features
- User Authentication (Register/Login)
- User Dashboard
- Admin Dashboard
- Wallpaper Upload/Download
- Paid/Free Wallpapers
- Admin Moderation

## Setup Instructions

1. Create a virtual environment:
```bash
python -m venv venv
```

2. Activate virtual environment:
- Windows:
```bash
venv\Scripts\activate
```
- Linux/Mac:
```bash
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run migrations:
```bash
python manage.py makemigrations
python manage.py migrate
```

5. Create superuser:
```bash
python manage.py createsuperuser
```

6. Run development server:
```bash
python manage.py runserver
```

Visit http://127.0.0.1:8000/ to access the website. 