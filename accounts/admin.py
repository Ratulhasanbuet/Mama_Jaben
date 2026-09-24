from datetime import date
from django.contrib import admin
from django.db import connection
from django.utils.html import format_html
from .models import (
    Coupon,
    Driver,
    Passenger,
    Payment,
    Review,
    Ride,
    RideRequest,
    Vehicle,
)


def _get_image_url(image_field):
    if not image_field:
        return None
    val = str(image_field).strip()
    if not val:
        return None
    if val.startswith('/media/') or val.startswith('http://') or val.startswith('https://'):
        return val
    try:
        return image_field.url
    except Exception:
        return f"/media/{val}"


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = (
        'driver_id',
        'name',
        'phone',
        'license_no',
        'license_thumb',
        'status',
        'joining_date',
    )
    list_filter = ('status',)
    list_editable = ('status',)
    search_fields = ('name', 'phone', 'email', 'license_no')

    fields = (
        'name',
        'phone',
        'email',
        'password',
        'status',
        'license_no',
        'license_image',
        'license_preview',
        'joining_date',
    )
    readonly_fields = ('license_preview', 'joining_date')

    def license_thumb(self, obj):
        url = _get_image_url(obj.license_image)
        if url:
            return format_html(
                '<img src="{}" style="height:42px;width:auto;border-radius:4px;object-fit:cover;" />',
                url,
            )
        return '—'

    license_thumb.short_description = 'Photo'

    def license_preview(self, obj):
        url = _get_image_url(obj.license_image)
        if url:
            return format_html(
                '<a href="{0}" target="_blank" rel="noopener">'
                '<img src="{0}" style="max-width:420px;max-height:420px;border-radius:8px;border:1px solid #ddd;" />'
                '</a><p style="color:#666;margin-top:6px;">Click the photo to open it full-size in a new tab — compare the license number and expiry date shown on it against the fields above.</p>',
                url,
            )
        return 'No license photo uploaded yet'

    license_preview.short_description = 'License Photo'


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = (
        'vehicle_id',
        'vehicle_license',
        'type',
        'max_capacity',
        'vehicle_thumb',
        'status',
        'driver',
    )
    list_filter = ('status', 'type')
    list_editable = ('status',)
    search_fields = ('vehicle_license', 'driver__name')

    fields = (
        'driver',
        'vehicle_license',
        'type',
        'max_capacity',
        'status',
        'veh_license_image',
        'vehicle_preview',
    )
    readonly_fields = ('vehicle_preview',)

    def vehicle_thumb(self, obj):
        url = _get_image_url(obj.veh_license_image)
        if url:
            return format_html(
                '<img src="{}" style="height:42px;width:auto;border-radius:4px;object-fit:cover;" />',
                url,
            )
        return '—'

    vehicle_thumb.short_description = 'Photo'

    def vehicle_preview(self, obj):
        url = _get_image_url(obj.veh_license_image)
        if url:
            return format_html(
                '<a href="{0}" target="_blank" rel="noopener">'
                '<img src="{0}" style="max-width:420px;max-height:420px;border-radius:8px;border:1px solid #ddd;" />'
                '</a><p style="color:#666;margin-top:6px;">Click the photo to open it full-size in a new tab.</p>',
                url,
            )
        return 'No license photo uploaded yet'

    vehicle_preview.short_description = 'Vehicle License Photo'


@admin.register(Passenger)
class PassengerAdmin(admin.ModelAdmin):
    list_display = (
        'user_id',
        'name',
        'phone',
        'email',
        'passenger_category',
    )
    search_fields = ('name', 'phone', 'email')

    def passenger_category(self, obj):
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT fn_get_passenger_category(%s)', [obj.user_id]
                )
                cat = cursor.fetchone()[0]
        except Exception:
            cat = 'NEWBIE'

        colors = {
            'VIP': ('#842029', '#f8d7da', '🌟 VIP'),
            'REGULAR': ('#055160', '#cff4fc', '🚗 Regular'),
            'NEWBIE': ('#0f5132', '#d1e7dd', '🚴 Newbie'),
        }
        fg, bg, label = colors.get(cat, ('#333', '#eee', cat))
        return format_html(
            '<span style="color: {}; background: {}; padding: 4px 10px;'
            ' border-radius: 12px; font-weight: bold; font-size:'
            ' 12px;">{}</span>',
            fg,
            bg,
            label,
        )

    passenger_category.short_description = 'Category (PL/pgSQL)'


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'passenger',
        'category_target',
        'discount_display',
        'max_discount_display',
        'is_used',
        'expire_date',
        'created_at',
        'status_badge',
    )
    list_filter = ('is_used', 'category_target', 'expire_date')
    search_fields = (
        'code',
        'passenger__name',
        'passenger__email',
        'category_target',
    )
    ordering = ('-created_at', 'expire_date')
    actions = [
        'distribute_vip_coupons',
        'distribute_regular_coupons',
        'distribute_newbie_coupons',
        'distribute_all_coupons',
    ]

    def discount_display(self, obj):
        return f'{obj.discount}%'

    discount_display.short_description = 'Discount (%)'

    def max_discount_display(self, obj):
        if obj.max_discount > 0:
            return f'৳{obj.max_discount}'
        return 'No Cap'

    max_discount_display.short_description = 'Max Cap'

    def status_badge(self, obj):
        if obj.is_used:
            color, bg, text = '#6c757d', '#e9ecef', 'Used'
        elif obj.expire_date < date.today():
            color, bg, text = '#dc3545', '#f8d7da', 'Expired'
        else:
            color, bg, text = '#198754', '#d1e7dd', 'Active'

        return format_html(
            '<span style="color: {}; background: {}; padding: 3px 8px;'
            ' border-radius: 12px; font-weight: bold;">{}</span>',
            color,
            bg,
            text,
        )

    status_badge.short_description = 'Status'

    @admin.action(
        description=(
            '⚡ Auto-distribute 25%% OFF (Max 100 Tk) to VIP Passengers (via'
            ' PL/pgSQL)'
        )
    )
    def distribute_vip_coupons(self, request, queryset):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT sp_assign_coupons_by_category('VIP', 25.00, 100.00, 30,"
                " 'VIP')"
            )
            count = cursor.fetchone()[0]
        self.message_user(
            request,
            f'PL/pgSQL procedure executed! {count} VIP coupons successfully'
            ' created & assigned.',
        )

    @admin.action(
        description=(
            '⚡ Auto-distribute 15%% OFF (Max 60 Tk) to REGULAR Passengers'
            ' (via PL/pgSQL)'
        )
    )
    def distribute_regular_coupons(self, request, queryset):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT sp_assign_coupons_by_category('REG', 15.00, 60.00, 30,"
                " 'REGULAR')"
            )
            count = cursor.fetchone()[0]
        self.message_user(
            request,
            f'PL/pgSQL procedure executed! {count} Regular coupons successfully'
            ' created & assigned.',
        )

    @admin.action(
        description=(
            '⚡ Auto-distribute 10%% OFF (Max 40 Tk) to NEWBIE Passengers (via'
            ' PL/pgSQL)'
        )
    )
    def distribute_newbie_coupons(self, request, queryset):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT sp_assign_coupons_by_category('NEW', 10.00, 40.00, 30,"
                " 'NEWBIE')"
            )
            count = cursor.fetchone()[0]
        self.message_user(
            request,
            f'PL/pgSQL procedure executed! {count} Newbie coupons successfully'
            ' created & assigned.',
        )

    @admin.action(
        description=(
            '⚡ Auto-distribute 20%% OFF (Max 80 Tk) to ALL Passengers (via'
            ' PL/pgSQL)'
        )
    )
    def distribute_all_coupons(self, request, queryset):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT sp_assign_coupons_by_category('OFFER', 20.00, 80.00,"
                " 30, 'ALL')"
            )
            count = cursor.fetchone()[0]
        self.message_user(
            request,
            f'PL/pgSQL procedure executed! {count} Coupons successfully'
            ' created & assigned to all eligible passengers.',
        )


admin.site.register(Ride)
admin.site.register(RideRequest)
admin.site.register(Review)
admin.site.register(Payment)