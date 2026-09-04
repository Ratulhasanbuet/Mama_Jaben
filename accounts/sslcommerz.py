import requests
from django.conf import settings


def initiate_sslcommerz_payment(tran_id, amount, success_url, fail_url, cancel_url, cus_data=None,
                                product_name="RideShare Service"):
    """
    Initiates a session with SSLCommerz Gateway (Sandbox or Live).
    Returns (success: bool, redirect_url_or_error: str)
    """
    store_id = settings.SSLCOMMERZ_STORE_ID
    store_passwd = settings.SSLCOMMERZ_STORE_PASS
    is_sandbox = getattr(settings, 'SSLCOMMERZ_IS_SANDBOX', True)

    if is_sandbox:
        api_url = "https://sandbox.sslcommerz.com/gwprocess/v4/api.php"
    else:
        api_url = "https://securepay.sslcommerz.com/gwprocess/v4/api.php"

    cus_data = cus_data or {}
    cus_name = cus_data.get('name', 'Valued Customer')
    cus_email = cus_data.get('email', 'customer@example.com')
    cus_phone = cus_data.get('phone', '01700000000')

    post_body = {
        'store_id': store_id,
        'store_passwd': store_passwd,
        'total_amount': f"{amount:.2f}",
        'currency': 'BDT',
        'tran_id': tran_id,
        'success_url': success_url,
        'fail_url': fail_url,
        'cancel_url': cancel_url,
        'emi_option': 0,
        'cus_name': cus_name,
        'cus_email': cus_email,
        'cus_add1': 'Dhaka, Bangladesh',
        'cus_city': 'Dhaka',
        'cus_country': 'Bangladesh',
        'cus_phone': cus_phone,
        'shipping_method': 'NO',
        'num_of_item': 1,
        'product_name': product_name,
        'product_category': 'Transport',
        'product_profile': 'general',
    }

    try:
        response = requests.post(api_url, data=post_body, timeout=15)
        response_data = response.json()
        if response_data.get('status') == 'SUCCESS' and response_data.get('GatewayPageURL'):
            return True, response_data['GatewayPageURL']
        else:
            failed_reason = response_data.get('failedreason', 'SSLCommerz session initialization failed.')
            return False, failed_reason
    except Exception as e:
        return False, str(e)


def validate_sslcommerz_payment(val_id):
    """
    Validates transaction using SSLCommerz Validation API.
    Returns (is_valid: bool, data_dict)
    """
    store_id = settings.SSLCOMMERZ_STORE_ID
    store_passwd = settings.SSLCOMMERZ_STORE_PASS
    is_sandbox = getattr(settings, 'SSLCOMMERZ_IS_SANDBOX', True)

    if is_sandbox:
        validation_url = "https://sandbox.sslcommerz.com/validator/api/validationserverAPI.php"
    else:
        validation_url = "https://securepay.sslcommerz.com/validator/api/validationserverAPI.php"

    params = {
        'val_id': val_id,
        'store_id': store_id,
        'store_passwd': store_passwd,
        'format': 'json'
    }

    try:
        response = requests.get(validation_url, params=params, timeout=15)
        data = response.json()
        if data.get('status') in ['VALID', 'VALIDATED']:
            return True, data
        return False, data
    except Exception:
        return False, {}
