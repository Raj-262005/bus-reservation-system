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
    def build_upi_uri(amount, note='BusReserve Booking', ref=None, upi_id=None, payee_name=None):
        """
        Builds standard NPCI UPI URI string with pre-filled amount.
        Format: upi://pay?pa={upi_id}&pn={payee_name}&am={amount:.2f}&cu=INR&tn={note}
        """
        from urllib.parse import quote
        if not upi_id:
            try:
                from flask import current_app
                upi_id = current_app.config.get('UPI_ID', 'rajthakare2005@oksbi')
            except Exception:
                upi_id = 'rajthakare2005@oksbi'

        if not payee_name:
            try:
                from flask import current_app
                payee_name = current_app.config.get('UPI_PAYEE_NAME', 'Raj Thakare')
            except Exception:
                payee_name = 'Raj Thakare'

        amount_val = float(amount)
        amount_str = f"{amount_val:.2f}"

        encoded_pa = quote(str(upi_id).strip(), safe='@')
        encoded_pn = quote(str(payee_name).strip())
        encoded_tn = quote(str(note or 'BusReserve Booking').strip())

        params = [
            f"pa={encoded_pa}",
            f"pn={encoded_pn}",
            f"am={amount_str}",
            "cu=INR",
            f"tn={encoded_tn}"
        ]
        if ref:
            params.append(f"tr={quote(str(ref).strip())}")

        return "upi://pay?" + "&".join(params)

    @staticmethod
    def generate_dynamic_upi_qr(amount, note=None, ref=None, upi_id=None, payee_name=None):
        """
        Generates a dynamic UPI QR Code containing the pre-filled authoritative amount.
        Returns a base64 encoded PNG data URI string: data:image/png;base64,...
        Falls back to None if generation fails.
        """
        import io
        import base64
        try:
            import qrcode
            uri = PaymentService.build_upi_uri(
                amount=amount,
                note=note or 'BusReserve Booking',
                ref=ref,
                upi_id=upi_id,
                payee_name=payee_name
            )
            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=3,
            )
            qr.add_data(uri)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            buf = io.BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            b64_str = base64.b64encode(buf.read()).decode('utf-8')
            return f"data:image/png;base64,{b64_str}"
        except Exception as e:
            try:
                from flask import current_app
                current_app.logger.error(f"Dynamic QR generation error: {e}")
            except Exception:
                pass
            return None

    @staticmethod
    def process_demo_payment(method='UPI_QR', card_or_upi_info=None, simulate_failure=False):
        """
        Records payment confirmation for external UPI QR / demo payments without simulated fake bank claims.
        Returns (success: bool, transaction_id: str, message: str)
        """
        import uuid
        from datetime import datetime

        if simulate_failure:
            return False, None, "Payment was not completed or confirmation was declined (Simulated test)."

        norm_method = (method or 'UPI_QR').upper().replace(' ', '_')
        if 'UPI' in norm_method:
            txn_id = f"UPI-CONFIRM-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
        else:
            txn_id = f"DEMO-{norm_method}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"

        return True, txn_id, "Payment confirmation recorded successfully."
