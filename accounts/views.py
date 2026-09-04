import json
import time
from itertools import permutations

import requests
import math

from django.shortcuts import render, redirect
from django.db import connection
from django.contrib.auth.hashers import make_password, check_password
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .sslcommerz import initiate_sslcommerz_payment, validate_sslcommerz_payment


def home(request):
    return render(request, 'mama-jaben-landing.html')


def user_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        with connection.cursor() as cursor:
            # 1. Passenger Check
            cursor.execute("SELECT user_id, password FROM accounts_passenger WHERE email = %s", [email])
            passenger = cursor.fetchone()

            if passenger:
                db_user_id, db_password = passenger
                if check_password(password, db_password):
                    messages.success(request, 'Passenger Login Successful!')
                    request.session['user_id'] = db_user_id
                    request.session['role'] = 'passenger'
                    return redirect('passenger_dashboard')
                else:
                    messages.error(request, 'Password Incorrect')
                    return redirect('home')

            # 2. Driver Check
            cursor.execute("SELECT driver_id, password FROM accounts_driver WHERE email = %s", [email])
            driver = cursor.fetchone()

            if driver:
                db_driver_id, db_password = driver
                if check_password(password, db_password):
                    messages.success(request, 'Driver Login Successful!')
                    request.session['user_id'] = db_driver_id
                    request.session['role'] = 'driver'
                    return redirect('driver_dashboard')
                else:
                    messages.error(request, 'Password Incorrect')
                    return redirect('home')

        messages.error(request, 'No passenger or driver found with this email')
        return redirect('home')

    return render(request, "mama-jaben-landing.html")


def user_logout(request):
    request.session.flush()
    messages.success(request, 'Logged out successfully')
    return redirect('home')


def passenger_register(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        raw_password = request.POST.get('password')

        with connection.cursor() as cursor:

            cursor.execute("SELECT 1 FROM accounts_passenger WHERE email = %s OR phone = %s", [email, phone])
            if cursor.fetchone():
                messages.info(request, 'Email already exists or Phone already exists')
                return redirect('home')

            hashed_password = make_password(raw_password)

            cursor.execute(
                "INSERT INTO accounts_passenger (name, phone, email, password) VALUES (%s, %s, %s, %s)",
                [name, phone, email, hashed_password]
            )

        messages.success(request, 'Passenger Registration Successful')
        return redirect('home')

    return render(request, "mama-jaben-landing.html")


def driver_register(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        password = request.POST.get('password')
        license_no = request.POST.get('license_no')
        license_image = request.FILES.get('license_image')

        with connection.cursor() as cursor:

            cursor.execute("SELECT 1 FROM accounts_driver WHERE email = %s OR phone = %s", [email, phone])
            if cursor.fetchone():
                messages.error(request, 'Email or Phone already exists')
                return redirect('home')

            image_path = None
            if license_image:
                fs = FileSystemStorage()
                filename = fs.save(license_image.name, license_image)
                image_path = fs.url(filename)

            hashed_password = make_password(password)

            cursor.execute(
                "INSERT INTO accounts_driver (name, phone, email, password, license_no, license_image, joining_date, status) VALUES (%s, %s, %s, %s, %s, %s, CURRENT_DATE, 'Pending')",
                [name, phone, email, hashed_password, license_no, image_path]
            )

        messages.success(request,
                         'Driver Registration Ongoing: Your account is pending approval. You will be notified once approved.')
        return redirect('home')

    return render(request, "mama-jaben-landing.html")


def passenger_dashboard(request):
    if request.session.get('role') != 'passenger':
        messages.error(request, 'Please log in as a passenger first')
        return redirect('home')

    user_id = request.session.get('user_id')

    with connection.cursor() as cursor:
        # Profile
        cursor.execute(
            "SELECT name, phone, email FROM accounts_passenger WHERE user_id = %s",
            [user_id]
        )
        profile_row = cursor.fetchone()

        # Previous / pending ride requests — driver name comes through once a Ride is attached
        cursor.execute("""
                       SELECT rr.ride_request_id,
                              rr.status,
                              rr.start_location,
                              rr.end_location,
                              rr.estimated_fare,
                              rr.date,
                              rr.time,
                              rr.requested_vehicle_type,
                              rr.requested_capacity,
                              d.name,
                              rr.payment_method,
                              pay.status AS payment_status
                       FROM accounts_riderequest rr
                                LEFT JOIN accounts_ride r ON rr.ride_id = r.ride_id
                                LEFT JOIN accounts_driver d ON r.driver_id = d.driver_id
                                LEFT JOIN accounts_payment pay
                                          ON pay.passenger_id = rr.passenger_id AND pay.ride_id = rr.ride_id AND
                                             pay.payment_type = 'ride_fare' AND pay.status = 'Paid'
                       WHERE rr.passenger_id = %s
                       ORDER BY rr.date DESC, rr.time DESC
                       """, [user_id])
        ride_rows = cursor.fetchall()

        # Coupons that belong to this passenger and haven't expired
        cursor.execute("""
                       SELECT code, discount, expire_date
                       FROM accounts_coupon
                       WHERE passenger_id = %s
                         AND expire_date >= CURRENT_DATE
                       ORDER BY expire_date ASC
                       """, [user_id])
        coupon_rows = cursor.fetchall()

    profile = None
    if profile_row:
        profile = {'name': profile_row[0], 'phone': profile_row[1], 'email': profile_row[2]}

    rides = [
        {
            'request_id': row[0],
            'status': row[1],
            'start_location': row[2],
            'end_location': row[3],
            'fare': row[4],
            'date': row[5],
            'time': row[6],
            'vehicle_type': row[7],
            'capacity': row[8],
            'driver_name': row[9],
            'payment_method': row[10],
            'is_paid': (row[11] == 'Paid'),
        }
        for row in ride_rows
    ]

    coupons = [
        {'code': row[0], 'discount': row[1], 'expire_date': row[2]}
        for row in coupon_rows
    ]

    context = {
        'profile': profile,
        'rides': rides,
        'coupons': coupons,
    }
    return render(request, 'passenger/passenger-dashboard.html', context)


# key used in the frontend <-> what gets stored on RideRequest
VEHICLE_OPTIONS = {
    'bike': {'label': 'Bike', 'type': 'Bike', 'capacity': None, 'base': 20, 'per_km': 8, 'per_min': 0.5},
    'car4': {'label': 'Car (4-seat)', 'type': 'Car', 'capacity': 4, 'base': 50, 'per_km': 20, 'per_min': 1.0},
    'car8': {'label': 'Car (8-seat)', 'type': 'Car', 'capacity': 8, 'base': 80, 'per_km': 25, 'per_min': 1.5},
}


def book_ride(request):
    if request.session.get('role') != 'passenger':
        messages.error(request, 'Please log in as a passenger first')
        return redirect('home')

    user_id = request.session.get('user_id')

    with connection.cursor() as cursor:
        cursor.execute("""
                       SELECT code, discount, expire_date
                       FROM accounts_coupon
                       WHERE passenger_id = %s
                         AND expire_date >= CURRENT_DATE
                       ORDER BY expire_date ASC
                       """, [user_id])
        coupon_rows = cursor.fetchall()

    coupons = [
        {'code': row[0], 'discount': row[1], 'expire_date': row[2]}
        for row in coupon_rows
    ]

    context = {
        'coupons': coupons,
    }
    return render(request, 'passenger/passenger-booking.html', context)


def geocode_search(request):
    """AJAX endpoint: proxies OpenStreetMap Nominatim search (free, no key) so the
    browser doesn't call it directly — keeps a proper User-Agent and avoids CORS."""
    if request.session.get('role') != 'passenger':
        return JsonResponse({'error': 'Please log in as a passenger first'}, status=403)

    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'results': []})

    try:
        response = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={'q': query, 'format': 'json', 'limit': 6, 'countrycodes': 'bd'},
            headers={'User-Agent': 'MamaJabenRideShare/1.0'},
            timeout=10,
        )
        data = response.json()
    except requests.RequestException:
        return JsonResponse({'error': 'Could not reach search service'}, status=502)

    results = [
        {'label': item['display_name'], 'lat': float(item['lat']), 'lng': float(item['lon'])}
        for item in data
    ]
    return JsonResponse({'results': results})


def geocode_reverse(request):
    """AJAX endpoint: turns a lat/lng (e.g. from 'use current location') into an address,
    via Nominatim's reverse lookup — same proxy pattern as geocode_search."""
    if request.session.get('role') != 'passenger':
        return JsonResponse({'error': 'Please log in as a passenger first'}, status=403)

    lat = request.GET.get('lat')
    lng = request.GET.get('lng')
    if not (lat and lng):
        return JsonResponse({'error': 'Missing coordinates'}, status=400)

    try:
        response = requests.get(
            'https://nominatim.openstreetmap.org/reverse',
            params={'lat': lat, 'lon': lng, 'format': 'json'},
            headers={'User-Agent': 'MamaJabenRideShare/1.0'},
            timeout=10,
        )
        data = response.json()
    except requests.RequestException:
        return JsonResponse({'error': 'Could not reach search service'}, status=502)

    return JsonResponse({'label': data.get('display_name', f'{lat}, {lng}')})


def geocode_location(address):
    """Convert a place name/address to (lat, lng) using OpenStreetMap Nominatim —
    the same free service already used by the geocode_search view.
    Returns (lat, lng) as floats, or (None, None) on failure."""
    if not address:
        return None, None
    try:
        response = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={'q': address, 'format': 'json', 'limit': 1, 'countrycodes': 'bd'},
            headers={'User-Agent': 'MamaJabenRideShare/1.0'},
            timeout=10,
        )
        data = response.json()
        if data:
            return float(data[0]['lat']), float(data[0]['lon'])
    except Exception:
        pass
    return None, None


def calculate_fare(request):
    """AJAX endpoint: takes pickup/destination lat-lng, calls Open Source Routing Machine (OSRM)
    for real road distance, and returns a fare estimate per vehicle type."""
    if request.session.get('role') != 'passenger':
        return JsonResponse({'error': 'Please log in as a passenger first'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
        pickup_lat = data['pickup_lat']
        pickup_lng = data['pickup_lng']
        dest_lat = data['dest_lat']
        dest_lng = data['dest_lng']
    except (ValueError, KeyError):
        return JsonResponse({'error': 'Missing pickup/destination coordinates'}, status=400)

    try:
        # OSRM expects coordinates in lng,lat format
        osrm_url = f"http://router.project-osrm.org/route/v1/driving/{pickup_lng},{pickup_lat};{dest_lng},{dest_lat}?overview=false"
        headers = {'User-Agent': 'MamaJabenRideShare/1.0'}
        response = requests.get(osrm_url, headers=headers, timeout=10)
        result = response.json()
    except requests.RequestException:
        return JsonResponse({'error': 'Could not reach routing service'}, status=502)

    if result.get('code') != 'Ok' or not result.get('routes'):
        return JsonResponse({'error': 'No route found between these points'}, status=400)

    try:
        route = result['routes'][0]
        distance_km = route['distance'] / 1000  # meters to km
        duration_min = route['duration'] / 60  # seconds to minutes
    except (KeyError, IndexError):
        return JsonResponse({'error': 'Could not read distance from routing service'}, status=400)

    fares = {}
    for key, opt in VEHICLE_OPTIONS.items():
        fare = opt['base'] + (opt['per_km'] * distance_km) + (opt['per_min'] * duration_min)
        fares[key] = round(fare)

    return JsonResponse({
        'distance_km': round(distance_km, 1),
        'duration_min': round(duration_min),
        'fares': fares,
    })


def confirm_booking(request):
    if request.session.get('role') != 'passenger':
        messages.error(request, 'Please log in as a passenger first')
        return redirect('home')

    if request.method != 'POST':
        return redirect('book_ride')

    user_id = request.session.get('user_id')
    start_location = request.POST.get('start_location')
    end_location = request.POST.get('end_location')
    vehicle_key = request.POST.get('vehicle_option')
    estimated_fare = request.POST.get('estimated_fare')
    coupon_code = request.POST.get('coupon_code') or None  # treat empty string as None

    payment_method = request.POST.get('payment_method', 'cash')
    if payment_method not in ['cash', 'online']:
        payment_method = 'cash'

    # Resolve coordinates server-side via OpenStreetMap Nominatim
    start_lat = request.POST.get('start_lat')
    start_lng = request.POST.get('start_lng')
    end_lat = request.POST.get('end_lat')
    end_lng = request.POST.get('end_lng')

    try:
        start_lat = float(start_lat)
        start_lng = float(start_lng)
        end_lat = float(end_lat)
        end_lng = float(end_lng)
    except (TypeError, ValueError):
        messages.error(request, 'Invalid route coordinates')
        return redirect('book_ride')

    option = VEHICLE_OPTIONS.get(vehicle_key)
    if not (start_location and end_location and option and estimated_fare):
        messages.error(request, 'Please complete the route and vehicle selection first')
        return redirect('book_ride')

    with connection.cursor() as cursor:
        # A coupon is only honoured if it's really this passenger's and still valid —
        # never trust the vehicle/fare pairing coming from the client alone.
        if coupon_code:
            cursor.execute(
                "SELECT 1 FROM accounts_coupon WHERE code = %s AND passenger_id = %s AND expire_date >= CURRENT_DATE",
                [coupon_code, user_id]
            )
            if not cursor.fetchone():
                coupon_code = None
        # ride also needs this info(modification)
        cursor.execute(
            "INSERT INTO accounts_ride (status, start_location, end_location, date, time, driver_id, vehicle_id) "
            "VALUES (%s, %s, %s, CURRENT_DATE, CURRENT_TIME, NULL, NULL)"
            "RETURNING ride_id",
            ['Pending', start_location, end_location]
        )
        new_ride_id = cursor.fetchone()[0]
        cursor.execute("""
                       INSERT INTO accounts_riderequest
                       (status, date, time, start_location, start_lat, start_lng, end_location, end_lat, end_lng,
                        estimated_fare, requested_vehicle_type, requested_capacity, payment_method, passenger_id,
                        ride_id, coupon_id)
                       VALUES (%s, CURRENT_DATE, CURRENT_TIME, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                               %s) RETURNING ride_request_id
                       """, [
                           'Pending', start_location, start_lat, start_lng, end_location, end_lat, end_lng,
                           estimated_fare, option['type'], option['capacity'], payment_method, user_id, new_ride_id,
                           coupon_code
                       ])
        new_request_id = cursor.fetchone()[0]

        cursor.execute("SELECT name, email, phone FROM accounts_passenger WHERE user_id = %s", [user_id])
        pass_row = cursor.fetchone()

    name = pass_row[0] if pass_row else 'Passenger'
    email = pass_row[1] if pass_row else 'passenger@example.com'
    phone = pass_row[2] if pass_row else '01700000000'

    if payment_method == 'online':
        try:
            fare_val = float(estimated_fare)
        except (TypeError, ValueError):
            fare_val = 0.0

        if fare_val > 0:
            tran_id = f"PASS-RIDE-{new_request_id}-{int(time.time())}"
            domain = request.build_absolute_uri('/')[:-1]
            success_url = f"{domain}/payment/ssl-success/"
            fail_url = f"{domain}/payment/ssl-fail/"
            cancel_url = f"{domain}/payment/ssl-cancel/"

            customer_data = {'name': name, 'email': email, 'phone': phone}
            success, result = initiate_sslcommerz_payment(
                tran_id=tran_id,
                amount=fare_val,
                success_url=success_url,
                fail_url=fail_url,
                cancel_url=cancel_url,
                cus_data=customer_data,
                product_name="Ride Fare Payment"
            )
            if success:
                messages.info(request, "Redirecting to SSLCommerz Payment Gateway...")
                return redirect(result)
            else:
                messages.error(request, f"SSLCommerz Session Error: {result}. Ride requested, please pay later.")

    messages.success(request,
                     f"Ride requested via {payment_method.capitalize()}! We'll notify you once a driver accepts.")
    return redirect('passenger_dashboard')


@csrf_exempt
def initiate_passenger_payment(request, request_id):
    """Passenger initiates online payment for an active or pending ride via SSLCommerz."""
    if request.session.get('role') != 'passenger':
        messages.error(request, 'Please log in as a passenger first')
        return redirect('home')

    user_id = request.session.get('user_id')

    with connection.cursor() as cursor:
        cursor.execute("""
                       SELECT rr.estimated_fare, rr.status, p.name, p.email, p.phone
                       FROM accounts_riderequest rr
                                JOIN accounts_passenger p ON rr.passenger_id = p.user_id
                       WHERE rr.ride_request_id = %s
                         AND rr.passenger_id = %s
                       """, [request_id, user_id])
        row = cursor.fetchone()

    if not row:
        messages.error(request, 'Ride request not found')
        return redirect('passenger_dashboard')

    estimated_fare, status, name, email, phone = row

    if status == 'Cancelled':
        messages.error(request, 'Cannot pay for a cancelled ride.')
        return redirect('passenger_dashboard')

    try:
        amount = float(estimated_fare)
    except (TypeError, ValueError):
        messages.error(request, 'Invalid fare amount.')
        return redirect('passenger_dashboard')

    tran_id = f"PASS-RIDE-{request_id}-{int(time.time())}"
    domain = request.build_absolute_uri('/')[:-1]
    success_url = f"{domain}/payment/ssl-success/"
    fail_url = f"{domain}/payment/ssl-fail/"
    cancel_url = f"{domain}/payment/ssl-cancel/"

    customer_data = {'name': name, 'email': email, 'phone': phone}
    success, result = initiate_sslcommerz_payment(
        tran_id=tran_id,
        amount=amount,
        success_url=success_url,
        fail_url=fail_url,
        cancel_url=cancel_url,
        cus_data=customer_data,
        product_name="Ride Fare Payment"
    )

    if success:
        return redirect(result)
    else:
        messages.error(request, f'SSLCommerz payment initialization failed: {result}')
        return redirect('passenger_dashboard')


# ==========================================
# DRIVER DASHBOARD
# ==========================================
def driver_dashboard(request):
    if request.session.get('role') != 'driver':
        messages.error(request, 'Please log in as a driver first')
        return redirect('home')

    driver_id = request.session.get('user_id')

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT name, phone, email, status FROM accounts_driver WHERE driver_id = %s",
            [driver_id]
        )
        driver_row = cursor.fetchone()

        # Most recently submitted vehicle, if any
        cursor.execute(
            "SELECT vehicle_id, vehicle_license, type, max_capacity, status "
            "FROM accounts_vehicle WHERE driver_id = %s ORDER BY vehicle_id DESC LIMIT 1",
            [driver_id]
        )
        vehicle_row = cursor.fetchone()

    if not driver_row:
        request.session.flush()
        return redirect('home')

    driver = {'name': driver_row[0], 'phone': driver_row[1], 'email': driver_row[2], 'status': driver_row[3]}

    vehicle = None
    if vehicle_row:
        vehicle = {
            'vehicle_id': vehicle_row[0],
            'vehicle_license': vehicle_row[1],
            'type': vehicle_row[2],
            'max_capacity': vehicle_row[3],
            'status': vehicle_row[4],
        }

    # Work out which stage of onboarding this driver is at
    if driver['status'] == 'Pending':
        stage = 'driver_pending'
    elif driver['status'] == 'Rejected':
        stage = 'driver_rejected'
    elif not vehicle:
        stage = 'vehicle_needed'
    elif vehicle['status'] == 'Pending':
        stage = 'vehicle_pending'
    elif vehicle['status'] == 'Rejected':
        stage = 'vehicle_rejected'
    else:
        stage = 'ready'

    context = {'driver': driver, 'vehicle': vehicle, 'stage': stage}
    return render(request, 'driver/driver-dashboard.html', context)


def register_vehicle(request):
    if request.session.get('role') != 'driver':
        messages.error(request, 'Please log in as a driver first')
        return redirect('home')

    driver_id = request.session.get('user_id')

    with connection.cursor() as cursor:
        cursor.execute("SELECT status FROM accounts_driver WHERE driver_id = %s", [driver_id])
        driver_row = cursor.fetchone()

        cursor.execute(
            "SELECT status FROM accounts_vehicle WHERE driver_id = %s ORDER BY vehicle_id DESC LIMIT 1",
            [driver_id]
        )
        existing_vehicle = cursor.fetchone()

    # Accept 'Approved' regardless of capitalization or surrounding whitespace
    if not driver_row or (driver_row[0] or '').strip().lower() != 'approved':
        messages.error(request, 'Your account needs to be approved before you can register a vehicle')
        return redirect('driver_dashboard')

    # Only block if there's already a Pending/Verified vehicle — a Rejected one can be resubmitted
    # Do a case-insensitive check to tolerate different capitalization in DB/admin
    if existing_vehicle and (existing_vehicle[0] or '').strip().lower() != 'rejected':
        messages.info(request, 'You already have a vehicle registered')
        return redirect('driver_dashboard')

    if request.method == 'POST':
        vehicle_license = request.POST.get('vehicle_license')
        vehicle_type = request.POST.get('type')
        max_capacity = request.POST.get('max_capacity')
        veh_license_image = request.FILES.get('veh_license_image')

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM accounts_vehicle WHERE vehicle_license = %s", [vehicle_license])
            if cursor.fetchone():
                messages.error(request, 'This vehicle license is already registered')
                return redirect('register_vehicle')

            image_path = None
            if veh_license_image:
                fs = FileSystemStorage()
                filename = fs.save(veh_license_image.name, veh_license_image)
                image_path = fs.url(filename)

            cursor.execute("""
                           INSERT INTO accounts_vehicle
                           (vehicle_license, veh_license_image, type, max_capacity, status, driver_id)
                           VALUES (%s, %s, %s, %s, %s, %s)
                           """, [vehicle_license, image_path, vehicle_type, max_capacity, 'Pending', driver_id])

        messages.success(request, 'Vehicle submitted for verification')
        return redirect('driver_dashboard')

    return render(request, 'driver/vehicle-register.html')


def driver_rides(request):
    if request.session.get('role') != 'driver':
        messages.error(request, 'Please log in as a driver first')
        return redirect('home')

    driver_id = request.session.get('user_id')

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT type, max_capacity FROM accounts_vehicle "
            "WHERE driver_id = %s AND status = 'approved' ORDER BY vehicle_id DESC LIMIT 1",
            [driver_id]
        )
        vehicle_row = cursor.fetchone()

    if not vehicle_row:
        messages.error(request, 'You need a verified vehicle before viewing ride requests')
        return redirect('driver_dashboard')

    context = {'vehicle_type': vehicle_row[0], 'vehicle_capacity': vehicle_row[1]}
    return render(request, 'driver/driver-rides.html', context)


def haversine_km(lat1, lng1, lat2, lng2):
    """Straight-line distance between two points in km — plenty accurate for
    'what's nearby', and doesn't need a network call per ride request."""
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def nearby_rides(request):
    """AJAX endpoint: pending ride requests within `radius` km of the driver's
    current lat/lng, matching their verified vehicle's type/capacity, nearest first."""
    if request.session.get('role') != 'driver':
        return JsonResponse({'error': 'Please log in as a driver first'}, status=403)

    try:
        driver_lat = float(request.GET.get('lat'))
        driver_lng = float(request.GET.get('lng'))
        print(driver_lat, driver_lng)
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Missing driver location'}, status=400)

    try:
        radius_km = float(request.GET.get('radius', 3))
    except ValueError:
        radius_km = 3.0

    driver_id = request.session.get('user_id')

    with connection.cursor() as cursor:
        cursor.execute("SELECT wallet_balance FROM accounts_driver WHERE driver_id = %s", [driver_id])
        w_row = cursor.fetchone()
        wallet_balance = float(w_row[0]) if w_row and w_row[0] is not None else 0.0

        if wallet_balance < -500.00:
            return JsonResponse({
                'rides': [],
                'is_blocked': True,
                'wallet_balance': round(wallet_balance, 2),
                'error': f'Your wallet balance (৳{wallet_balance:.2f}) is below the -৳500.00 BDT limit. Please settle your dues via SSLCommerz to resume accepting rides.'
            })

        cursor.execute(
            "SELECT type, max_capacity FROM accounts_vehicle "
            "WHERE driver_id = %s AND status = 'approved' ORDER BY vehicle_id DESC LIMIT 1",
            [driver_id]
        )
        vehicle_row = cursor.fetchone()

        if not vehicle_row:
            return JsonResponse({'error': 'No verified vehicle on file'}, status=403)

        vehicle_type, vehicle_capacity = vehicle_row

        # Check if driver currently has an active accepted ride
        cursor.execute(
            "SELECT r.ride_id, r.start_location, r.end_location "
            "FROM accounts_ride r "
            "WHERE r.driver_id = %s AND r.status = 'Accepted' ORDER BY r.ride_id DESC LIMIT 1",
            [driver_id]
        )
        active_ride_row = cursor.fetchone()
        active_ride_info = None
        if active_ride_row:
            a_id, a_start, a_end = active_ride_row
            cursor.execute(
                "SELECT COALESCE(SUM(estimated_fare), 0) FROM accounts_riderequest WHERE ride_id = %s",
                [a_id]
            )
            a_fare = cursor.fetchone()[0]
            active_ride_info = {
                'ride_id': a_id,
                'start_location': a_start,
                'end_location': a_end,
                'total_fare': float(a_fare) if a_fare else 0.0,
            }

        cursor.execute("""
                       SELECT ride_request_id,
                              start_location,
                              start_lat,
                              start_lng,
                              end_location,
                              estimated_fare,
                              requested_vehicle_type,
                              requested_capacity, time
                       FROM accounts_riderequest
                       WHERE status = 'Pending' AND start_lat IS NOT NULL AND start_lng IS NOT NULL
                       """)
        rows = cursor.fetchall()

    nearby = []
    for row in rows:
        (req_id, start_location, req_lat, req_lng, end_location,
         fare, req_type, req_capacity, req_time) = row

        # Only show requests this driver can actually fulfil
        if req_type != vehicle_type:
            continue
        if req_type == 'Car' and vehicle_capacity and req_capacity and req_capacity > vehicle_capacity:
            continue

        distance = haversine_km(driver_lat, driver_lng, req_lat, req_lng)
        if distance > radius_km:
            continue

        nearby.append({
            'request_id': req_id,
            'start_location': start_location,
            'end_location': end_location,
            'estimated_fare': float(fare) if fare is not None else None,
            'vehicle_type': req_type,
            'capacity': req_capacity,
            'time': req_time.strftime('%I:%M %p') if req_time else '',
            'distance_km': round(distance, 1),
        })

    nearby.sort(key=lambda r: r['distance_km'])
    return JsonResponse({
        'rides': nearby,
        'has_active_ride': active_ride_info is not None,
        'active_ride': active_ride_info
    })


def driver_active_ride(request):
    """AJAX endpoint: returns current active ride details for the logged-in driver."""
    if request.session.get('role') != 'driver':
        return JsonResponse({'error': 'Please log in as a driver first'}, status=403)

    driver_id = request.session.get('user_id')

    with connection.cursor() as cursor:
        cursor.execute("""
                       SELECT r.ride_id, r.status, r.start_location, r.end_location, r.date, r.time
                       FROM accounts_ride r
                       WHERE r.driver_id = %s
                         AND r.status = 'Accepted'
                       ORDER BY r.ride_id DESC LIMIT 1
                       """, [driver_id])
        ride_row = cursor.fetchone()

        if not ride_row:
            return JsonResponse({'active': False, 'ride': None})

        ride_id, status, start_loc, end_loc, date, time = ride_row

        cursor.execute("""
                       SELECT rr.ride_request_id, rr.start_location, rr.end_location, rr.estimated_fare, p.name, p.phone
                       FROM accounts_riderequest rr
                                JOIN accounts_passenger p ON rr.passenger_id = p.user_id
                       WHERE rr.ride_id = %s
                       """, [ride_id])
        req_rows = cursor.fetchall()

    total_fare = sum(float(row[3]) for row in req_rows if row[3] is not None)
    passengers = [
        {
            'name': row[4],
            'phone': row[5],
            'pickup': row[1],
            'dropoff': row[2],
            'fare': float(row[3]) if row[3] else 0.0
        }
        for row in req_rows
    ]

    return JsonResponse({
        'active': True,
        'ride': {
            'ride_id': ride_id,
            'status': status,
            'start_location': start_loc,
            'end_location': end_loc,
            'total_fare': round(total_fare, 2),
            'passengers': passengers,
            'passenger_count': len(passengers),
        }
    })


def accept_ride(request, request_id):
    if request.session.get('role') != 'driver':
        return JsonResponse({'error': 'Please log in as a driver first'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    driver_id = request.session.get('user_id')

    with connection.cursor() as cursor:
        cursor.execute("SELECT wallet_balance FROM accounts_driver WHERE driver_id = %s", [driver_id])
        w_row = cursor.fetchone()
        wallet_balance = float(w_row[0]) if w_row and w_row[0] is not None else 0.0
        if wallet_balance < -500.00:
            return JsonResponse({
                'error': f'Your wallet balance (৳{wallet_balance:.2f}) is below the -৳500.00 BDT limit. Please settle your dues via SSLCommerz before accepting new rides.'
            }, status=403)

        # Guard: Check if driver already has an active accepted ride
        cursor.execute(
            "SELECT ride_id FROM accounts_ride WHERE driver_id = %s AND status = 'Accepted' LIMIT 1",
            [driver_id]
        )
        if cursor.fetchone():
            return JsonResponse({
                'error': 'You already have an active ride in progress. You cannot accept another ride until you finish or cancel your current ride!'
            }, status=400)

        cursor.execute(
            "SELECT vehicle_id FROM accounts_vehicle "
            "WHERE driver_id = %s AND status = 'approved' ORDER BY vehicle_id DESC LIMIT 1",
            [driver_id]
        )
        vehicle_row = cursor.fetchone()
        if not vehicle_row:
            return JsonResponse({'error': 'No verified vehicle on file'}, status=403)
        vehicle_id = vehicle_row[0]

        cursor.execute(
            "SELECT ride_id FROM accounts_riderequest WHERE ride_request_id = %s", [request_id]
        )
        row = cursor.fetchone()
        if not row:
            return JsonResponse({'error': 'Ride request not found'}, status=404)
        ride_id = row[0]

    with connection.cursor() as cursor:
        # Atomically claim the request first — the WHERE guard means only one
        # driver can ever flip a given request from Pending to Accepted.
        cursor.execute(
            "UPDATE accounts_ride SET status = 'Accepted', driver_id = %s, vehicle_id = %s "
            "WHERE ride_id = %s AND status = 'Pending'",
            [driver_id, vehicle_id, ride_id]
        )
        if cursor.rowcount == 0:
            return JsonResponse({'error': 'This ride is no longer available'}, status=409)

        cursor.execute(
            "UPDATE accounts_riderequest SET status = 'Accepted' WHERE ride_id = %s AND status = 'Pending'",
            [ride_id]
        )

    return JsonResponse({'success': True, 'ride_id': ride_id})


def complete_ride(request, ride_id):
    """Endpoint for a driver to mark their active ride as completed, increasing driver earnings and applying platform commission."""
    if request.session.get('role') != 'driver':
        return JsonResponse({'error': 'Please log in as a driver first'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    driver_id = request.session.get('user_id')

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ride_id FROM accounts_ride WHERE ride_id = %s AND driver_id = %s AND status = 'Accepted'",
            [ride_id, driver_id]
        )
        if not cursor.fetchone():
            return JsonResponse({'error': 'Active ride not found or already completed'}, status=404)

        # Query passenger requests for this ride
        cursor.execute(
            "SELECT passenger_id, estimated_fare, payment_method FROM accounts_riderequest WHERE ride_id = %s",
            [ride_id]
        )
        req_rows = cursor.fetchall()

        total_fare = sum(float(r[1]) for r in req_rows if r[1] is not None)
        commission = total_fare * 0.15
        net_driver_amount = total_fare * 0.85

        payment_methods = [r[2] for r in req_rows if r[2]]
        ride_payment_method = payment_methods[0] if payment_methods else 'cash'

        # Mark ride as Completed
        cursor.execute(
            "UPDATE accounts_ride SET status = 'Completed' WHERE ride_id = %s",
            [ride_id]
        )

        # Mark ride requests as Completed
        cursor.execute(
            "UPDATE accounts_riderequest SET status = 'Completed' WHERE ride_id = %s",
            [ride_id]
        )

        # Credit driver cumulative gross earnings
        cursor.execute(
            "UPDATE accounts_driver SET earnings = COALESCE(earnings, 0) + %s WHERE driver_id = %s",
            [total_fare, driver_id]
        )

        if ride_payment_method == 'cash':
            # Driver took cash in hand from passenger.
            # System deducts 15% platform commission from Driver's wallet.
            cursor.execute(
                "UPDATE accounts_driver SET wallet_balance = COALESCE(wallet_balance, 0) - %s WHERE driver_id = %s",
                [commission, driver_id]
            )

            cursor.execute("""
                           INSERT INTO accounts_driverwallettransaction (driver_id, ride_id, amount, transaction_type, description, created_at)
                           VALUES (%s, %s, %s, 'cash_commission', %s, NOW())
                           """, [driver_id, ride_id, -commission,
                                 f'15% commission deducted for Cash Ride #{ride_id} (Fare: ৳{total_fare:.2f})'])

            for p_id, p_fare, p_method in req_rows:
                if p_fare is not None:
                    p_comm = float(p_fare) * 0.15
                    p_driver = float(p_fare) * 0.85
                    cursor.execute("""
                                   INSERT INTO accounts_payment (amount, status, payment_method, payment_type,
                                                                 commission_amount, driver_amount, passenger_id,
                                                                 ride_id)
                                   VALUES (%s, 'Paid', 'cash', 'ride_fare', %s, %s, %s, %s)
                                   """, [p_fare, p_comm, p_driver, p_id, ride_id])
        else:
            # Online payment: Passenger paid online via SSLCommerz. Platform holds money.
            # Platform retains 15% commission and credits 85% net fare to Driver's wallet.
            cursor.execute(
                "UPDATE accounts_driver SET wallet_balance = COALESCE(wallet_balance, 0) + %s WHERE driver_id = %s",
                [net_driver_amount, driver_id]
            )

            cursor.execute("""
                           INSERT INTO accounts_driverwallettransaction (driver_id, ride_id, amount, transaction_type, description, created_at)
                           VALUES (%s, %s, %s, 'online_ride_credit', %s, NOW())
                           """, [driver_id, ride_id, net_driver_amount,
                                 f'85% net fare credited for Online Ride #{ride_id} (Fare: ৳{total_fare:.2f})'])

            for p_id, p_fare, p_method in req_rows:
                if p_fare is not None:
                    p_comm = float(p_fare) * 0.15
                    p_driver = float(p_fare) * 0.85
                    cursor.execute("""
                                   INSERT INTO accounts_payment (amount, status, payment_method, payment_type,
                                                                 commission_amount, driver_amount, passenger_id,
                                                                 ride_id)
                                   VALUES (%s, 'Paid', 'online', 'ride_fare', %s, %s, %s, %s)
                                   """, [p_fare, p_comm, p_driver, p_id, ride_id])

    return JsonResponse({
        'success': True,
        'earned_amount': round(total_fare, 2),
        'commission': round(commission, 2),
        'net_driver_amount': round(net_driver_amount, 2),
        'payment_method': ride_payment_method,
        'message': f'Ride completed! Total Fare: ৳{total_fare:.2f} ({ride_payment_method.capitalize()}).'
    })


def cancel_ride(request, ride_id):
    """Endpoint for a driver to cancel an active accepted ride."""
    if request.session.get('role') != 'driver':
        return JsonResponse({'error': 'Please log in as a driver first'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    driver_id = request.session.get('user_id')

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ride_id FROM accounts_ride WHERE ride_id = %s AND driver_id = %s AND status = 'Accepted'",
            [ride_id, driver_id]
        )
        if not cursor.fetchone():
            return JsonResponse({'error': 'Active ride not found or cannot be cancelled'}, status=404)

        # Revert ride to Pending, unassign driver & vehicle
        cursor.execute(
            "UPDATE accounts_ride SET status = 'Pending', driver_id = NULL, vehicle_id = NULL WHERE ride_id = %s",
            [ride_id]
        )

        # Revert ride requests to Pending
        cursor.execute(
            "UPDATE accounts_riderequest SET status = 'Pending' WHERE ride_id = %s",
            [ride_id]
        )

    return JsonResponse(
        {'success': True, 'message': 'Ride cancelled successfully. It is now back in the pending requests queue.'})


@csrf_exempt
def cancel_passenger_ride(request, request_id):
    """Endpoint for a passenger to cancel their pending or accepted ride request."""
    if request.session.get('role') != 'passenger':
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get(
                'accept', ''):
            return JsonResponse({'error': 'Please log in as a passenger first'}, status=403)
        messages.error(request, 'Please log in as a passenger first')
        return redirect('home')

    if request.method != 'POST':
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get(
                'accept', ''):
            return JsonResponse({'error': 'POST required'}, status=405)
        return redirect('passenger_dashboard')

    user_id = request.session.get('user_id')

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ride_id, status FROM accounts_riderequest WHERE ride_request_id = %s AND passenger_id = %s",
            [request_id, user_id]
        )
        row = cursor.fetchone()

        if not row:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get(
                    'accept', ''):
                return JsonResponse({'error': 'Ride request not found'}, status=404)
            messages.error(request, 'Ride request not found.')
            return redirect('passenger_dashboard')

        ride_id, current_status = row

        if current_status not in ['Pending', 'Accepted']:
            msg = f'Cannot cancel ride request with status "{current_status}".'
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get(
                    'accept', ''):
                return JsonResponse({'error': msg}, status=400)
            messages.error(request, msg)
            return redirect('passenger_dashboard')

        # Mark this ride request as Cancelled
        cursor.execute(
            "UPDATE accounts_riderequest SET status = 'Cancelled' WHERE ride_request_id = %s",
            [request_id]
        )

        # Check if there are any remaining active requests for this ride
        if ride_id:
            cursor.execute(
                "SELECT COUNT(*) FROM accounts_riderequest WHERE ride_id = %s AND status IN ('Pending', 'Accepted')",
                [ride_id]
            )
            remaining_count = cursor.fetchone()[0]

            if remaining_count == 0:
                # If no active passengers left on this ride, cancel the parent ride as well
                cursor.execute(
                    "UPDATE accounts_ride SET status = 'Cancelled' WHERE ride_id = %s",
                    [ride_id]
                )

    msg = 'Your ride request has been cancelled successfully.'
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get(
            'accept', ''):
        return JsonResponse({'success': True, 'message': msg})

    messages.success(request, msg)
    return redirect('passenger_dashboard')


def driver_earnings(request):
    """View: Driver Earnings & Wallet Dashboard."""
    if request.session.get('role') != 'driver':
        messages.error(request, 'Please log in as a driver first')
        return redirect('home')

    driver_id = request.session.get('user_id')

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT name, email, phone, earnings, wallet_balance FROM accounts_driver WHERE driver_id = %s",
            [driver_id]
        )
        driver_row = cursor.fetchone()

        if not driver_row:
            request.session.flush()
            return redirect('home')

        driver_name, driver_email, driver_phone, stored_earnings, stored_wallet = driver_row
        stored_earnings = float(stored_earnings) if stored_earnings is not None else 0.0
        wallet_balance = float(stored_wallet) if stored_wallet is not None else 0.0
        is_blocked = wallet_balance < -500.00

        # Query completed rides history
        cursor.execute("""
                       SELECT r.ride_id,
                              r.start_location,
                              r.end_location,
                              r.date,
                              r.time,
                              COALESCE(SUM(rr.estimated_fare), 0) AS total_fare,
                              COUNT(rr.ride_request_id)           AS passenger_count
                       FROM accounts_ride r
                                LEFT JOIN accounts_riderequest rr ON r.ride_id = rr.ride_id
                       WHERE r.driver_id = %s
                         AND r.status = 'Completed'
                       GROUP BY r.ride_id, r.start_location, r.end_location, r.date, r.time
                       ORDER BY r.date DESC, r.time DESC
                       """, [driver_id])
        completed_rows = cursor.fetchall()

        # Query driver wallet transactions history
        cursor.execute("""
                       SELECT transaction_id, amount, transaction_type, description, created_at
                       FROM accounts_driverwallettransaction
                       WHERE driver_id = %s
                       ORDER BY created_at DESC
                       """, [driver_id])
        wallet_tx_rows = cursor.fetchall()

    completed_rides = [
        {
            'ride_id': row[0],
            'start_location': row[1],
            'end_location': row[2],
            'date': row[3],
            'time': row[4],
            'fare': float(row[5]),
            'passenger_count': row[6],
        }
        for row in completed_rows
    ]

    wallet_transactions = [
        {
            'transaction_id': row[0],
            'amount': float(row[1]),
            'abs_amount': abs(float(row[1])),
            'transaction_type': row[2],
            'description': row[3],
            'created_at': row[4],
        }
        for row in wallet_tx_rows
    ]

    total_completed = len(completed_rides)
    sum_fare = sum(r['fare'] for r in completed_rides)
    total_earnings = max(stored_earnings, sum_fare)
    avg_fare = (total_earnings / total_completed) if total_completed > 0 else 0.0

    context = {
        'driver': {
            'name': driver_name,
            'email': driver_email,
            'phone': driver_phone,
        },
        'wallet_balance': round(wallet_balance, 2),
        'is_blocked': is_blocked,
        'wallet_transactions': wallet_transactions,
        'total_earnings': round(total_earnings, 2),
        'total_completed': total_completed,
        'avg_fare': round(avg_fare, 2),
        'completed_rides': completed_rides,
    }
    return render(request, 'driver/driver-earnings.html', context)


@csrf_exempt
def initiate_driver_settlement(request):
    """Driver initiates wallet top-up / debt settlement via SSLCommerz Sandbox."""
    if request.session.get('role') != 'driver':
        return JsonResponse({'error': 'Please log in as a driver first'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    driver_id = request.session.get('user_id')

    amount_str = request.POST.get('amount')
    if not amount_str and request.body:
        try:
            body_json = json.loads(request.body)
            amount_str = body_json.get('amount')
        except Exception:
            pass

    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Please enter a valid positive settlement amount.'}, status=400)

    with connection.cursor() as cursor:
        cursor.execute("SELECT name, email, phone FROM accounts_driver WHERE driver_id = %s", [driver_id])
        driver_row = cursor.fetchone()

    if not driver_row:
        return JsonResponse({'error': 'Driver not found'}, status=404)

    name, email, phone = driver_row
    tran_id = f"DRV-SETTLE-{driver_id}-{int(time.time())}"

    domain = request.build_absolute_uri('/')[:-1]
    success_url = f"{domain}/payment/ssl-success/"
    fail_url = f"{domain}/payment/ssl-fail/"
    cancel_url = f"{domain}/payment/ssl-cancel/"

    customer_data = {'name': name, 'email': email, 'phone': phone}
    success, result = initiate_sslcommerz_payment(
        tran_id=tran_id,
        amount=amount,
        success_url=success_url,
        fail_url=fail_url,
        cancel_url=cancel_url,
        cus_data=customer_data,
        product_name="Driver Wallet Settlement"
    )

    if success:
        return JsonResponse({'success': True, 'gateway_url': result})
    else:
        return JsonResponse({'error': f'Payment initialization failed: {result}'}, status=400)


@csrf_exempt
def request_driver_withdraw(request):
    """Driver requests cash out / withdrawal of positive wallet balance to bKash / Nagad / Bank account."""
    if request.session.get('role') != 'driver':
        return JsonResponse({'error': 'Please log in as a driver first'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    driver_id = request.session.get('user_id')

    amount_str = request.POST.get('amount')
    method = request.POST.get('payment_method', 'bKash')
    account_no = request.POST.get('account_number', '').strip()

    if not amount_str and request.body:
        try:
            body_json = json.loads(request.body)
            amount_str = body_json.get('amount')
            method = body_json.get('payment_method', method)
            account_no = body_json.get('account_number', account_no)
        except Exception:
            pass

    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Please enter a valid positive withdrawal amount.'}, status=400)

    if not account_no:
        return JsonResponse({'error': 'Please provide a valid account or mobile number for payout.'}, status=400)

    with connection.cursor() as cursor:
        cursor.execute("SELECT wallet_balance FROM accounts_driver WHERE driver_id = %s", [driver_id])
        w_row = cursor.fetchone()
        current_balance = float(w_row[0]) if w_row and w_row[0] is not None else 0.0

        if amount > current_balance:
            return JsonResponse({
                'error': f'Insufficient balance! Available wallet balance: ৳{current_balance:.2f} BDT.'
            }, status=400)

        # Deduct requested amount from driver wallet balance
        cursor.execute(
            "UPDATE accounts_driver SET wallet_balance = wallet_balance - %s WHERE driver_id = %s",
            [amount, driver_id]
        )

        # Log driver wallet transaction for cash out
        desc = f'Cash Out via {method} ({account_no})'
        cursor.execute("""
                       INSERT INTO accounts_driverwallettransaction (driver_id, amount, transaction_type, description, created_at)
                       VALUES (%s, %s, 'wallet_withdraw', %s, NOW())
                       """, [driver_id, -amount, desc])

    return JsonResponse({
        'success': True,
        'message': f'Withdrawal request for ৳{amount:.2f} BDT via {method} ({account_no}) submitted successfully!'
    })


@csrf_exempt
def sslcommerz_success(request):
    """SSLCommerz Success Callback (POST/GET)."""
    post_data = request.POST if request.method == 'POST' else request.GET
    tran_id = post_data.get('tran_id')
    val_id = post_data.get('val_id')
    amount_str = post_data.get('amount')

    if not (tran_id and val_id):
        messages.error(request, 'Invalid callback payload from SSLCommerz.')
        return redirect('driver_earnings')

    is_valid, validation_resp = validate_sslcommerz_payment(val_id)

    if not is_valid:
        messages.error(request, 'SSLCommerz payment validation failed.')
        return redirect('driver_earnings')

    amount = float(amount_str or validation_resp.get('amount', 0))

    if tran_id.startswith('DRV-SETTLE-'):
        parts = tran_id.split('-')
        driver_id = int(parts[2])

        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE accounts_driver SET wallet_balance = COALESCE(wallet_balance, 0) + %s WHERE driver_id = %s",
                [amount, driver_id]
            )

            cursor.execute("""
                           INSERT INTO accounts_payment (amount, status, payment_method, payment_type, tran_id, val_id,
                                                         commission_amount, driver_amount)
                           VALUES (%s, 'Paid', 'online', 'driver_settlement', %s, %s, 0.00, %s)
                           """, [amount, tran_id, val_id, amount])

            cursor.execute("""
                           INSERT INTO accounts_driverwallettransaction (driver_id, amount, transaction_type, description, created_at)
                           VALUES (%s, %s, 'wallet_topup', %s, NOW())
                           """,
                           [driver_id, amount, f'Wallet Settlement / Recharge via SSLCommerz (Tran ID: {tran_id})'])

        messages.success(request, f'Successfully recharged ৳{amount:.2f} BDT to your driver wallet!')
        return redirect('driver_earnings')

    elif tran_id.startswith('PASS-RIDE-'):
        parts = tran_id.split('-')
        request_id = int(parts[2])

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT passenger_id, ride_id FROM accounts_riderequest WHERE ride_request_id = %s",
                [request_id]
            )
            row = cursor.fetchone()
            passenger_id = row[0] if row else None
            ride_id = row[1] if row else None

            cursor.execute(
                "UPDATE accounts_riderequest SET payment_method = 'online' WHERE ride_request_id = %s",
                [request_id]
            )

            comm_amount = round(amount * 0.15, 2)
            drv_amount = round(amount * 0.85, 2)

            cursor.execute("""
                           INSERT INTO accounts_payment (amount, status, payment_method, payment_type, tran_id, val_id,
                                                         passenger_id, ride_id, commission_amount, driver_amount)
                           VALUES (%s, 'Paid', 'online', 'ride_fare', %s, %s, %s, %s, %s, %s)
                           """, [amount, tran_id, val_id, passenger_id, ride_id, comm_amount, drv_amount])

        messages.success(request, f'Payment of ৳{amount:.2f} BDT completed successfully via SSLCommerz!')
        return redirect('passenger_dashboard')

    messages.success(request, 'Payment completed successfully.')
    return redirect('passenger_dashboard')


@csrf_exempt
def sslcommerz_fail(request):
    messages.error(request, 'Payment failed or was declined by SSLCommerz.')
    role = request.session.get('role')
    if role == 'driver':
        return redirect('driver_earnings')
    return redirect('passenger_dashboard')


@csrf_exempt
def sslcommerz_cancel(request):
    messages.info(request, 'Payment process was cancelled.')
    role = request.session.get('role')
    if role == 'driver':
        return redirect('driver_earnings')
    return redirect('passenger_dashboard')

    # functions added for multi ride calculations


def get_road_dist(lat1, lng1, lat2, lng2):
    """Real road distance in km via OSRM. Returns None on failure."""
    try:
        osrm_url = f"http://router.project-osrm.org/route/v1/driving/{lng1},{lat1};{lng2},{lat2}?overview=false"
        response = requests.get(osrm_url, headers={'User-Agent': 'MamaJabenRideShare/1.0'}, timeout=10)
        result = response.json()
        if result.get('code') != 'Ok':
            print("OSRM returned:", result)
            return None
        return result['routes'][0]['distance'] / 1000
    except Exception as e:
        print("OSRM ERROR:", e)
        return None


def check_feasibility(data, ride_start_loc, ride_id):
    """
    Tries to find the cheapest valid insertion slot for the new passenger's dropoff.

    data: dict with 'end_lat', 'end_lng', 'end_location', 'passenger_id', 'estimated_fare'
    ride_start_loc: (lat, lng) tuple — the shared pickup point
    ride_id: the ride we're trying to join

    Returns (insertion_index, best_new_dist) if feasible, or None if not.
    """
    with connection.cursor() as cursor:
        cursor.execute("""
                       SELECT end_lat, end_lng, passenger_id
                       FROM accounts_riderequest
                       WHERE ride_id = %s
                         AND status IN ('Pending', 'Accepted')
                       ORDER BY dropoff ASC
                       """, [ride_id])
        rows = cursor.fetchall()
    print("CHECKING RIDE:", ride_id)
    print("ROWS:", rows)
    if not rows:
        return None

    # Build the full sequence: [start, stop0, stop1, stop2, ...]
    # start is at index 0, existing dropoffs follow in order
    sequence = [ride_start_loc] + [(row[0], row[1]) for row in rows]
    passenger_ids = [row[2] for row in rows]
    n = len(sequence)  # includes the start point

    # Step 1: compute total distance of the CURRENT route (start → stop0 → stop1 → ...)
    current_dist = 0
    for i in range(n - 1):
        d = get_road_dist(sequence[i][0], sequence[i][1], sequence[i + 1][0], sequence[i + 1][1])
        if d is None:
            return None
        current_dist += d

    # Step 2: new passenger's direct distance from start (their baseline)
    new_e = (data['end_lat'], data['end_lng'])
    new_baseline = get_road_dist(ride_start_loc[0], ride_start_loc[1], new_e[0], new_e[1])
    if new_baseline is None:
        return None

    # Step 3: try inserting E at each possible slot
    # slot i means: insert between sequence[i] and sequence[i+1]
    # valid slots: 0 to n-1 (n slots total for n points in sequence)
    best_slot = None
    best_new_dist = None
    best_detour = float('inf')

    for i in range(n):
        if i < n - 1:
            # inserting between sequence[i] and sequence[i+1]
            dist_to_e = get_road_dist(sequence[i][0], sequence[i][1], new_e[0], new_e[1])
            dist_from_e = get_road_dist(new_e[0], new_e[1], sequence[i + 1][0], sequence[i + 1][1])
            dist_skipped = get_road_dist(sequence[i][0], sequence[i][1], sequence[i + 1][0], sequence[i + 1][1])

            if None in (dist_to_e, dist_from_e, dist_skipped):
                continue

            new_total = current_dist + dist_to_e + dist_from_e - dist_skipped

        else:
            # inserting at the very end (after the last existing stop)
            dist_to_e = get_road_dist(sequence[-1][0], sequence[-1][1], new_e[0], new_e[1])
            if dist_to_e is None:
                continue
            new_total = current_dist + dist_to_e

        detour_added = new_total - current_dist  # how much longer does the route get?

        # Check 1: does the route grow by more than 1km? (protects existing passengers)
        if detour_added > 1.0:
            print("Rejected: existing route detour =", detour_added)
            continue

        # Check 2: is the new passenger's actual distance from pickup to their stop
        # within 1km of their direct baseline? (protects the new passenger too)
        # Their distance = everything up to insertion point + dist_to_e
        dist_to_insertion_point = 0.0
        if i > 0:
            for j in range(i):
                dist = get_road_dist(
                    sequence[j][0], sequence[j][1], sequence[j + 1][0], sequence[j + 1][1]
                )
                if dist is not None:
                    dist_to_insertion_point += dist
        new_passenger_travel = dist_to_insertion_point + dist_to_e
        if new_passenger_travel - new_baseline > 1.0:
            print(
                "Rejected: new passenger detour =",
                new_passenger_travel - new_baseline
            )
            continue

        # This slot works — is it the cheapest so far?
        if detour_added < best_detour:
            best_detour = detour_added
            best_slot = i
            best_new_dist = new_total

    return (best_slot, best_new_dist, passenger_ids) if best_slot is not None else None


def apply_join(data, ride_id, ride_start_location, ride_start_loc, feasibility_result, new_status):
    """
    Actually writes the join to the database:
    - Updates dropoff for existing passengers shifted by the insertion
    - Inserts the new passenger's RideRequest row
    """
    insertion_idx, new_total_dist, passenger_ids = feasibility_result
    user_id = data['passenger_id']

    # Fare split: proportional to distance each passenger travels
    # Simple approximation: new passenger pays (their_dist / new_total_dist) * total_fare
    # For now use the same base fare formula
    option = VEHICLE_OPTIONS['car4']
    total_fare = option['base'] + option['per_km'] * new_total_dist
    new_passenger_fare = round(total_fare * 0.5)  # simplified: refine with real split later

    with connection.cursor() as cursor:
        # Shift dropoff of everyone AT or AFTER the insertion point up by 1
        # Passengers before insertion_idx are completely untouched
        for idx in range(len(passenger_ids) - 1, insertion_idx - 1, -1):
            cursor.execute(
                "UPDATE accounts_riderequest SET dropoff = %s "
                "WHERE ride_id = %s AND passenger_id = %s",
                [idx + 1, ride_id, passenger_ids[idx]]
            )

        # Insert the new passenger at the insertion slot
        cursor.execute("""
                       INSERT INTO accounts_riderequest
                       (status, date, time, start_location, start_lat, start_lng,
                        end_location, end_lat, end_lng, estimated_fare,
                        requested_vehicle_type, requested_capacity,
                        passenger_id, ride_id, coupon_id, dropoff)
                       VALUES (%s, CURRENT_DATE, CURRENT_TIME, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL,
                               %s) RETURNING ride_request_id
                       """, [
                           new_status, ride_start_location,
                           ride_start_loc[0], ride_start_loc[1],
                           data['end_location'], data['end_lat'], data['end_lng'],
                           new_passenger_fare, 'Car', 4,
                           user_id, ride_id, insertion_idx
                       ])
        new_request_id = cursor.fetchone()[0]

    return new_passenger_fare, new_request_id


def check_joinable_rides(request):
    if request.session.get('role') != 'passenger':
        messages.error(request, 'Please log in as a passenger first')
        return redirect('home')
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
        start_lat = float(data['start_lat'])
        start_lng = float(data['start_lng'])
        dest_lat = float(data['end_lat'])
        dest_lng = float(data['end_lng'])
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'error': 'Missing route information'}, status=400)

    with connection.cursor() as cursor:
        cursor.execute("SELECT ride_id FROM accounts_ride WHERE status IN ('Pending', 'Accepted')")
        current_ride_ids = [row[0] for row in cursor.fetchall()]
    # debugging
    print("ALL RIDES:", current_ride_ids)

    possible_rides = {}  # ride_id -> ride_start_loc tuple
    for ride_id in current_ride_ids:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT start_lat, start_lng FROM accounts_riderequest WHERE ride_id = %s LIMIT 1",
                [ride_id]
            )
            ride_start = cursor.fetchone()
            cursor.execute(
                "select count(*) from accounts_riderequest WHERE ride_id = %s",
                [ride_id]
            )
            num_passengers = cursor.fetchone()
            cursor.execute(
                "select requested_capacity from accounts_riderequest WHERE ride_id = %s LIMIT 1",
                [ride_id]
            )
            capacity = cursor.fetchone()
        print("RIDE:", ride_id, "START:", ride_start)
        print("current passenger start:", start_lat, start_lng)
        print("current passenger destinations:", dest_lat, dest_lng)
        if not ride_start:
            continue

        distance = get_road_dist(
            ride_start[0], ride_start[1],
            start_lat, start_lng
        )

        if distance is not None and distance <= 0.1 and capacity > num_passengers:
            possible_rides[ride_id] = ride_start

        print("DISTANCE:", distance, "km")

    # debugging
    print("POSSIBLE RIDES:", possible_rides)

    feasible_rides = []
    for ride_id, ride_start_loc in possible_rides.items():
        result = check_feasibility(
            {'end_lat': dest_lat, 'end_lng': dest_lng},
            ride_start_loc,
            ride_id
        )
        if result is not None:
            feasible_rides.append({
                'ride_id': ride_id,
                'insertion_index': result[0],
                'detour_km': round(result[1], 2),
            })

    return JsonResponse({'rides': feasible_rides})


def request_join_ride(request, ride_id):
    if request.session.get('role') != 'passenger':
        return JsonResponse({'error': 'Please log in as a passenger first'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    user_id = request.session.get('user_id')

    # Guard: passenger already has an active ride
    with connection.cursor() as cursor:
        """cursor.execute(
            "SELECT 1 FROM accounts_riderequest WHERE passenger_id = %s AND status IN ('Pending', 'Accepted')",
            [user_id]
        )
        if cursor.fetchone():
            return JsonResponse({'error': 'You already have an active ride request'}, status=409)"""

    try:
        data = json.loads(request.body)
        dest_lat = float(data['dest_lat'])
        dest_lng = float(data['dest_lng'])
        dest_label = data['end_location']
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'error': 'Missing destination information'}, status=400)

    data['passenger_id'] = user_id
    data['end_lat'] = dest_lat
    data['end_lng'] = dest_lng
    data['end_location'] = dest_label

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT status, start_location FROM accounts_ride WHERE ride_id = %s",
            [ride_id]
        )
        ride_row = cursor.fetchone()

    if not ride_row:
        return JsonResponse({'error': 'Ride not found'}, status=404)

    ride_status, ride_start_location = ride_row

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT start_lat, start_lng FROM accounts_riderequest WHERE ride_id = %s LIMIT 1",
            [ride_id]
        )
        ride_start_loc = cursor.fetchone()

    if not ride_start_loc:
        return JsonResponse({'error': 'Ride has no passengers'}, status=404)

    # Re-run feasibility check (don't trust check_joinable_rides result —
    # someone else might have joined between the user seeing the list and clicking join)
    feasibility_result = check_feasibility(data, ride_start_loc, ride_id)
    if feasibility_result is None:
        return JsonResponse({'error': 'No viable route found — joining would detour existing passengers too far'},
                            status=409)

    new_status = 'Accepted' if ride_status == 'Accepted' else 'Pending'

    fare, new_request_id = apply_join(
        data, ride_id, ride_start_location, ride_start_loc, feasibility_result, new_status
    )

    return JsonResponse({'success': True, 'your_estimated_fare': fare, 'request_id': new_request_id})
