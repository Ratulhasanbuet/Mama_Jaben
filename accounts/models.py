from django.db import models


# ==========================================
# 1. DRIVER TABLE
# ==========================================
class Driver(models.Model):
    driver_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    license_no = models.CharField(max_length=50, unique=True)
    license_image = models.ImageField(upload_to='driver_licenses/', null=True, blank=True)
    joining_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, default='Pending')  # Pending, Approved, Rejected


    def __str__(self):
        return f"{self.name} (Driver ID: {self.driver_id})"


# ==========================================
# 2. PASSENGER TABLE (With Self Relationship "Share Ride")
# ==========================================
class Passenger(models.Model):
    user_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)

    # ERD "Share Ride" Recursive Relationship (Passenger-to-Passenger)
    shared_passengers = models.ManyToManyField('self', blank=True, symmetrical=False, related_name='shared_with')

    def __str__(self):
        return f"{self.name} (Passenger ID: {self.user_id})"


# ==========================================
# 3. VEHICLE TABLE (Relationship: "Owns" with Driver)
# ==========================================
class Vehicle(models.Model):
    vehicle_id = models.AutoField(primary_key=True)
    vehicle_license = models.CharField(max_length=50, unique=True)
    veh_license_image = models.ImageField(upload_to='vehicle_licenses/', null=True, blank=True)
    type = models.CharField(max_length=30)  # Bike, Car, CNG
    max_capacity = models.IntegerField()
    status = models.CharField(max_length=20, default='Pending')  # Pending, Verified, Rejected

    # "Owns" Relationship -> Driver
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='vehicles')

    def __str__(self):
        return f"{self.type} - {self.vehicle_license}"


# ==========================================
# 4. COUPON TABLE (Relationship: "Gets" with Passenger)
# ==========================================
class Coupon(models.Model):
    code = models.CharField(max_length=30, primary_key=True)  # Primary Key 'code'
    expire_date = models.DateField()
    discount = models.DecimalField(max_digits=5, decimal_places=2)  # Discount percentage/amount

    # "Gets" Relationship -> Passenger
    passenger = models.ForeignKey(Passenger, on_delete=models.SET_NULL, null=True, blank=True, related_name='coupons')

    def __str__(self):
        return f"Coupon: {self.code} ({self.discount}% OFF)"


# ==========================================
# 5. RIDE TABLE (Relationships: "Serves" Driver, "Used" Vehicle)
# ==========================================
class Ride(models.Model):
    ride_id = models.AutoField(primary_key=True)
    start_location = models.CharField(max_length=255)
    end_location = models.CharField(max_length=255)
    date = models.DateField()
    time = models.TimeField()
    # slight modification
    status = models.CharField(max_length=20, default='Pending')
    # "Serves" Relationship -> Driver
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='rides',null=True, blank=True)

    # "Used" Relationship -> Vehicle
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='rides',null=True, blank=True)

    def __str__(self):
        return f"Ride #{self.ride_id}: {self.start_location} to {self.end_location}"


# ==========================================
# 6. RIDE REQUEST TABLE (Relationship: "Requests" Passenger & Ride)
# ==========================================
class RideRequest(models.Model):
    ride_request_id = models.AutoField(primary_key=True)
    status = models.CharField(max_length=20, default='Pending')  # Pending, Accepted, Rejected
    date = models.DateField()
    time = models.TimeField()

    # Trip details captured at request time, before any driver/vehicle is assigned
    start_location = models.CharField(max_length=255, default='')
    start_lat = models.FloatField(null=True, blank=True)
    start_lng = models.FloatField(null=True, blank=True)
    end_location = models.CharField(max_length=255, default='')
    end_lat = models.FloatField(null=True, blank=True)
    end_lng = models.FloatField(null=True, blank=True)
    estimated_fare = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    requested_vehicle_type = models.CharField(max_length=30, default='')  # Bike, Car
    requested_capacity = models.IntegerField(null=True, blank=True)  # 4 or 8, only when type is Car
    # dropoff keeps track of route sequence
    dropoff = models.IntegerField(null=True, blank=True)
    # Connected with Passenger & Ride
    passenger = models.ForeignKey(Passenger, on_delete=models.CASCADE, related_name='ride_requests')
    ride = models.ForeignKey(Ride, on_delete=models.CASCADE, related_name='requests', null=True, blank=True)

    # Coupon applied at request time, if any
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True, related_name='ride_requests')

    def __str__(self):
        return f"Req #{self.ride_request_id} - Status: {self.status}"


# ==========================================
# 7. REVIEW TABLE (Relationships: "Gives" Passenger, "Gets" Ride)
# ==========================================
class Review(models.Model):
    review_id = models.AutoField(primary_key=True)
    rating = models.IntegerField()  # e.g., 1 to 5
    comment = models.TextField(blank=True, null=True)

    # "Gives" Relationship -> Passenger
    passenger = models.ForeignKey(Passenger, on_delete=models.CASCADE, related_name='reviews')

    # "Gets" Relationship -> Ride
    ride = models.ForeignKey(Ride, on_delete=models.CASCADE, related_name='reviews')

    def __str__(self):
        return f"Review #{self.review_id} - Rating: {self.rating}/5"


# ==========================================
# 8. PAYMENT TABLE (Relationships: "Pays" Passenger, "Receives" Ride)
# ==========================================
class Payment(models.Model):
    payment_id = models.AutoField(primary_key=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, default='Pending')  # Paid, Pending, Failed

    # "Pays" Relationship -> Passenger
    passenger = models.ForeignKey(Passenger, on_delete=models.CASCADE, related_name='payments')

    # "Receives" Relationship -> Ride
    ride = models.ForeignKey(Ride, on_delete=models.CASCADE, related_name='payments')

    def __str__(self):
        return f"Payment #{self.payment_id} - ৳{self.amount} ({self.status})"