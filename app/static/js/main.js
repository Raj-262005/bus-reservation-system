/**
 * Bus Reservation System - Main Client Scripts
 */

document.addEventListener('DOMContentLoaded', function() {
    // 1. Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            try {
                const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
                bsAlert.close();
            } catch (e) {}
        }, 5000);
    });

    // 2. Initialize Bootstrap Tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

/**
 * Quick fill credentials on Login page for instant demo testing
 */
function fillCredentials(email, password) {
    const emailField = document.getElementById('email');
    const pwdField = document.getElementById('password');
    if (emailField && pwdField) {
        emailField.value = email;
        pwdField.value = password;
        // Highlight briefly
        emailField.classList.add('is-valid');
        pwdField.classList.add('is-valid');
        setTimeout(() => {
            emailField.classList.remove('is-valid');
            pwdField.classList.remove('is-valid');
        }, 1500);
    }
}
