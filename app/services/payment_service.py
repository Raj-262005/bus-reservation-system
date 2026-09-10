import os
from flask import current_app


class PaymentService:

    @staticmethod
    def is_razorpay_configured():
        key_id = current_app.config.get('RAZORPAY_KEY_ID')
        key_secret = current_app.config.get('RAZORPAY_KEY_SECRET')
        return bool(key_id and key_secret)

    @staticmethod
    def create_razorpay_order(amount, currency='INR', receipt=None):
        """Creates an order in Razorpay sandbox."""
        if not PaymentService.is_razorpay_configured():
            return None

        try:
            import razorpay
            client = razorpay.Client(
                auth=(current_app.config['RAZORPAY_KEY_ID'], current_app.config['RAZORPAY_KEY_SECRET'])
            )
            # Razorpay expects amount in paise (1 INR = 100 paise)
            data = {
                'amount': int(round(amount * 100)),
                'currency': currency,
                'receipt': receipt or 'rcpt_brs',
                'payment_capture': '1'
            }
            order = client.order.create(data=data)
            return order
        except Exception as e:
            current_app.logger.error(f"Razorpay order creation failed: {e}")
            return None

    @staticmethod
    def verify_razorpay_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
        """Verifies HMAC signature from Razorpay checkout."""
        if not PaymentService.is_razorpay_configured():
            return False

        try:
            import razorpay
            client = razorpay.Client(
                auth=(current_app.config['RAZORPAY_KEY_ID'], current_app.config['RAZORPAY_KEY_SECRET'])
            )
            params_dict = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            }
            client.utility.verify_payment_signature(params_dict)
            return True
        except Exception as e:
            current_app.logger.error(f"Signature verification error: {e}")
            return False

    @staticmethod
    def process_demo_payment(method, card_or_upi_info=None, simulate_failure=False):
        """
        Simulates demo payment processing without external APIs.
        Supports UPI, Card, Net Banking.
        Returns (success: bool, transaction_id: str, message: str)
        """
        import uuid
        from datetime import datetime

        if simulate_failure:
            return False, None, "Payment was declined by the simulated bank (Simulated failure test)."

        txn_id = f"DEMO-{method.upper()}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
        return True, txn_id, "Demo payment processed successfully."
