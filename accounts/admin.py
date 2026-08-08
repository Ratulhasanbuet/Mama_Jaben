from django.contrib import admin
from django.utils.html import format_html
from .models import Driver, Passenger, Vehicle, Coupon, Ride, RideRequest, Review, Payment


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ('driver_id', 'name', 'phone', 'license_no', 'license_thumb', 'status', 'joining_date')
    list_filter = ('status',)
    list_editable = ('status',)
    search_fields = ('name', 'phone', 'email', 'license_no')

    fields = ('name', 'phone', 'email', 'password', 'status',
              'license_no', 'license_image', 'license_preview', 'joining_date')
    readonly_fields = ('license_preview', 'joining_date')

    def license_thumb(self, obj):
        if obj.license_image:
            return format_html(
                '<img src="{}" style="height:42px;width:auto;border-radius:4px;object-fit:cover;" />',
                obj.license_image.url
            )
        return "—"
    license_thumb.short_description = 'Photo'

    def license_preview(self, obj):
        if obj.license_image:
            return format_html(
                '<a href="{0}" target="_blank" rel="noopener">'
                '<img src="{0}" style="max-width:420px;max-height:420px;border-radius:8px;border:1px solid #ddd;" />'
                '</a><p style="color:#666;margin-top:6px;">Click the photo to open it full-size in a new tab — '
                'compare the license number and expiry date shown on it against the fields above.</p>',
                obj.license_image.url
            )
        return "No license photo uploaded yet"
    license_preview.short_description = 'License Photo'


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('vehicle_id', 'vehicle_license', 'type', 'max_capacity', 'vehicle_thumb', 'status', 'driver')
    list_filter = ('status', 'type')
    list_editable = ('status',)
    search_fields = ('vehicle_license', 'driver__name')

    fields = ('driver', 'vehicle_license', 'type', 'max_capacity', 'status',
              'veh_license_image', 'vehicle_preview')
    readonly_fields = ('vehicle_preview',)

    def vehicle_thumb(self, obj):
        if obj.veh_license_image:
            return format_html(
                '<img src="{}" style="height:42px;width:auto;border-radius:4px;object-fit:cover;" />',
                obj.veh_license_image.url
            )
        return "—"
    vehicle_thumb.short_description = 'Photo'

    def vehicle_preview(self, obj):
        if obj.veh_license_image:
            return format_html(
                '<a href="{0}" target="_blank" rel="noopener">'
                '<img src="{0}" style="max-width:420px;max-height:420px;border-radius:8px;border:1px solid #ddd;" />'
                '</a><p style="color:#666;margin-top:6px;">Click the photo to open it full-size in a new tab.</p>',
                obj.veh_license_image.url
            )
        return "No license photo uploaded yet"
    vehicle_preview.short_description = 'Vehicle License Photo'


admin.site.register(Passenger)
admin.site.register(Coupon)
admin.site.register(Ride)
admin.site.register(RideRequest)
admin.site.register(Review)
admin.site.register(Payment)