import json
import requests

import math
from django.shortcuts import render, redirect
from django.db import connection
from django.contrib.auth.hashers import make_password, check_password
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.http import JsonResponse


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


# ==========================================
# PASSENGER DASHBOARD
# ==========================================
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
                              d.name
                       FROM accounts_riderequest rr
                                LEFT JOIN accounts_ride r ON rr.ride_id = r.ride_id
                                LEFT JOIN accounts_driver d ON r.driver_id = d.driver_id
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


# ==========================================
# RIDE BOOKING
# ==========================================

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

    # Resolve coordinates server-side via OpenStreetMap Nominatim
    start_lat, start_lng = geocode_location(start_location)
    end_lat, end_lng = geocode_location(end_location)

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

        cursor.execute("""
                       INSERT INTO accounts_riderequest
                       (status, date, time, start_location, start_lat, start_lng, end_location, end_lat, end_lng,
                        estimated_fare, requested_vehicle_type, requested_capacity, passenger_id, ride_id, coupon_id)
                       VALUES (%s, CURRENT_DATE, CURRENT_TIME, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, %s)
                       """, [
                           'Pending', start_location, start_lat, start_lng, end_location, end_lat, end_lng,
                           estimated_fare, option['type'], option['capacity'], user_id, coupon_code,
                       ])

    messages.success(request, "Ride requested! We'll notify you once a driver accepts.")
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
        cursor.execute(
            "SELECT type, max_capacity FROM accounts_vehicle "
            "WHERE driver_id = %s AND status = 'approved' ORDER BY vehicle_id DESC LIMIT 1",
            [driver_id]
        )
        vehicle_row = cursor.fetchone()

        if not vehicle_row:
            return JsonResponse({'error': 'No verified vehicle on file'}, status=403)

        vehicle_type, vehicle_capacity = vehicle_row

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
    return JsonResponse({'rides': nearby})


def accept_ride(request, request_id):
    if request.session.get('role') != 'driver':
        return JsonResponse({'error': 'Please log in as a driver first'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    driver_id = request.session.get('user_id')

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT vehicle_id FROM accounts_vehicle "
            "WHERE driver_id = %s AND status = 'approved' ORDER BY vehicle_id DESC LIMIT 1",
            [driver_id]
        )
        vehicle_row = cursor.fetchone()
        if not vehicle_row:
            return JsonResponse({'error': 'No verified vehicle on file'}, status=403)
        vehicle_id = vehicle_row[0]

        # Atomically claim the request first — the WHERE guard means only one
        # driver can ever flip a given request from Pending to Accepted.
        cursor.execute(
            "UPDATE accounts_riderequest SET status = 'Accepted' WHERE ride_request_id = %s AND status = 'Pending'",
            [request_id]
        )
        if cursor.rowcount == 0:
            return JsonResponse({'error': 'This ride is no longer available'}, status=409)

        cursor.execute(
            "SELECT start_location, end_location, date, time FROM accounts_riderequest WHERE ride_request_id = %s",
            [request_id]
        )
        start_location, end_location, req_date, req_time = cursor.fetchone()

        cursor.execute(
            "INSERT INTO accounts_ride (start_location, end_location, date, time, driver_id, vehicle_id) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            [start_location, end_location, req_date, req_time, driver_id, vehicle_id]
        )
        new_ride_id = cursor.lastrowid

        cursor.execute(
            "UPDATE accounts_riderequest SET ride_id = %s WHERE ride_request_id = %s",
            [new_ride_id, request_id]
        )

    return JsonResponse({'success': True, 'ride_id': new_ride_id})
