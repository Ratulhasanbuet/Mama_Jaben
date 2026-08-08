from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('user-login/', views.user_login, name='login'),
    path('signup_passenger/', views.passenger_register, name='signup_passenger'),

    path('signup_driver/', views.driver_register, name='signup_driver'),

    path('dashboard/', views.passenger_dashboard, name='passenger_dashboard'),
    path('logout/', views.user_logout, name='logout'),
    path('book-ride/', views.book_ride, name='book_ride'),
    path('calculate-fare/', views.calculate_fare, name='calculate_fare'),
    path('confirm-booking/', views.confirm_booking, name='confirm_booking'),

    path('driver/dashboard/', views.driver_dashboard, name='driver_dashboard'),
    path('driver/register-vehicle/', views.register_vehicle, name='register_vehicle'),
    path('driver/rides/', views.driver_rides, name='driver_rides'),

    path('geocode-search/', views.geocode_search, name='geocode_search'),
    path('geocode-reverse/', views.geocode_reverse, name='geocode_reverse'),
    path('driver/nearby-rides/', views.nearby_rides, name='nearby_rides'),
    path('driver/accept-ride/<int:request_id>/', views.accept_ride, name='accept_ride'),
]
