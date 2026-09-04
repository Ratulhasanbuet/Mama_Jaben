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
    earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)


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
    payment_method = models.CharField(max_length=20, default='cash')  # cash or online
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
    payment_method = models.CharField(max_length=20, default='cash')  # cash or online
    tran_id = models.CharField(max_length=100, null=True, blank=True)
    val_id = models.CharField(max_length=100, null=True, blank=True)
    payment_type = models.CharField(max_length=30, default='ride_fare')  # ride_fare or driver_settlement
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    driver_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # "Pays" Relationship -> Passenger (Optional if driver settlement)
    passenger = models.ForeignKey(Passenger, on_delete=models.CASCADE, related_name='payments', null=True, blank=True)

    # "Receives" Relationship -> Ride (Optional if driver settlement)
    ride = models.ForeignKey(Ride, on_delete=models.CASCADE, related_name='payments', null=True, blank=True)

    def __str__(self):
        return f"Payment #{self.payment_id} - ৳{self.amount} ({self.status})"


# ==========================================
# 9. DRIVER WALLET TRANSACTION TABLE
# ==========================================
class DriverWalletTransaction(models.Model):
    transaction_id = models.AutoField(primary_key=True)
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='wallet_transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=30)  # cash_commission, online_ride_credit, wallet_topup
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    ride = models.ForeignKey(Ride, on_delete=models.SET_NULL, null=True, blank=True, related_name='wallet_transactions')

    def __str__(self):
        return f"Wallet Tx #{self.transaction_id} - Driver #{self.driver.driver_id}: ৳{self.amount} ({self.transaction_type})"
