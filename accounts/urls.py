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
    path('passenger/cancel-ride/<int:request_id>/', views.cancel_passenger_ride, name='cancel_passenger_ride'),
    path('payment/passenger-ssl/<int:request_id>/', views.initiate_passenger_payment, name='initiate_passenger_payment'),

    path('driver/dashboard/', views.driver_dashboard, name='driver_dashboard'),
    path('driver/register-vehicle/', views.register_vehicle, name='register_vehicle'),
    path('driver/rides/', views.driver_rides, name='driver_rides'),

    path('geocode-search/', views.geocode_search, name='geocode_search'),
    path('geocode-reverse/', views.geocode_reverse, name='geocode_reverse'),
    path('driver/nearby-rides/', views.nearby_rides, name='nearby_rides'),
    path('driver/accept-ride/<int:request_id>/', views.accept_ride, name='accept_ride'),
    path('driver/active-ride/', views.driver_active_ride, name='driver_active_ride'),
    path('driver/complete-ride/<int:ride_id>/', views.complete_ride, name='complete_ride'),
    path('driver/cancel-ride/<int:ride_id>/', views.cancel_ride, name='cancel_ride'),
    path('driver/earnings/', views.driver_earnings, name='driver_earnings'),
    path('driver/settle-dues/', views.initiate_driver_settlement, name='initiate_driver_settlement'),
    path('driver/withdraw/', views.request_driver_withdraw, name='request_driver_withdraw'),

    path('payment/ssl-success/', views.sslcommerz_success, name='sslcommerz_success'),
    path('payment/ssl-fail/', views.sslcommerz_fail, name='sslcommerz_fail'),
    path('payment/ssl-cancel/', views.sslcommerz_cancel, name='sslcommerz_cancel'),

    path('check-joinable-rides/', views.check_joinable_rides, name='check_joinable_rides'),
    path('request-join-ride/<int:ride_id>/', views.request_join_ride, name='request_join_ride'),
]

