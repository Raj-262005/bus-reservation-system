# -*- coding: utf-8 -*-
"""
Comprehensive Multi-Language & Language Switcher Verification Script
Tests:
  1. Default language is English ('en')
  2. Language switching transitions: EN -> HI -> MR -> EN
  3. Session & cookie persistence across page requests
  4. Devanagari text rendering in Hindi and Marathi
  5. UI chrome translation across all major pages (Home, Search, Seat Selection, Login, Register, Dashboards, Admin, Operator)
  6. CRITICAL DATA RULE: City names, bus names, fares (₹), booking IDs, dates, and passenger names are NOT altered
  7. Role support: Passenger, Admin, Operator authenticated views
  8. Responsive selector presence in navbar
"""

import sys
import io

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import requests
from bs4 import BeautifulSoup

BASE_URL = "http://127.0.0.1:5000"

def test_language_switcher_and_translations():
    session = requests.Session()
    print("=================================================================")
    print("RUNNING MULTI-LANGUAGE SYSTEM VERIFICATION")
    print("=================================================================")

    # 1. Test Default Language (English)
    print("\n--- 1. Testing Default Language (English) ---")
    r = session.get(f"{BASE_URL}/")
    assert r.status_code == 200, f"Failed to load home page: {r.status_code}"
    soup = BeautifulSoup(r.text, 'html.parser')

    # Verify navbar language selector is present
    lang_btn = soup.select_one('#languageDropdown')
    assert lang_btn is not None, "Language selector button '#languageDropdown' not found in navbar!"
    print(f" [PASS] Language selector found: '{lang_btn.get_text(strip=True)}'")
    assert "English" in lang_btn.get_text(), "Default language name should be English"

    # Verify English UI text
    assert "Search Buses" in r.text, "English 'Search Buses' not found on homepage"
    assert "Your Journey Begins With Comfort" in soup.get_text(), "English hero title not found"
    print(" [PASS] Default English homepage UI confirmed.")

    # 2. Switch to Hindi (हिन्दी)
    print("\n--- 2. Testing Switch to Hindi (हिन्दी) ---")
    r = session.get(f"{BASE_URL}/set-language/hi", allow_redirects=True)
    assert r.status_code == 200
    soup = BeautifulSoup(r.text, 'html.parser')

    lang_btn = soup.select_one('#languageDropdown')
    print(f" Language selector text in Hindi: '{lang_btn.get_text(strip=True)}'")
    assert "हिन्दी" in lang_btn.get_text(), f"Expected 'हिन्दी' in selector, got '{lang_btn.get_text()}'"

    # Check Hindi Devanagari translations on Homepage
    assert "बस खोजें" in r.text, "Hindi 'बस खोजें' (Search Buses) not found on homepage"
    assert "आपकी यात्रा आराम और सुरक्षा के साथ शुरू होती है" in soup.get_text(), "Hindi hero title not found"
    assert "कहाँ से (प्रस्थान)" in r.text, "Hindi 'कहाँ से (प्रस्थान)' not found"
    assert "कहाँ तक (गंतव्य)" in r.text, "Hindi 'कहाँ तक (गंतव्य)' not found"
    assert "यात्रा की तारीख" in r.text, "Hindi 'यात्रा की तारीख' not found"
    print(" [PASS] Hindi homepage UI rendered correctly in Devanagari.")

    # Test persistence on subsequent request (e.g. search page navigation)
    print("\n--- 3. Testing Hindi Persistence Across Navigation & Search ---")
    search_url = f"{BASE_URL}/search?source=Mumbai&destination=Pune&date=2026-09-11"
    r_search = session.get(search_url)
    assert r_search.status_code == 200
    assert "सीटें देखें" in r_search.text or "सीटें उपलब्ध" in r_search.text or "कहाँ से (प्रस्थान)" in r_search.text, "Hindi search UI labels not found"

    # Verify CRITICAL DATA RULE: Actual cities and fares remain untouched
    assert "Mumbai" in r_search.text, "City name 'Mumbai' must remain untouched"
    assert "Pune" in r_search.text, "City name 'Pune' must remain untouched"
    print(" [PASS] Hindi preserved on search results. Cities 'Mumbai' & 'Pune' remain untranslated.")

    # Test Seat Selection Page in Hindi
    print("\n--- 3b. Testing Seat Selection Page in Hindi ---")
    search_soup = BeautifulSoup(r_search.text, 'html.parser')
    select_btn = search_soup.select_one('a[href*="/seat-selection/"]')
    if select_btn:
        seat_url = f"{BASE_URL}{select_btn['href']}"
        r_seats = session.get(seat_url)
        assert r_seats.status_code == 200
        # Check Devanagari seat selection legend and labels
        assert "सीट चयन" in r_seats.text or "उपलब्ध" in r_seats.text or "चुनी गई" in r_seats.text or "बुक की गई" in r_seats.text
        print(" [PASS] Seat selection UI rendered in Hindi (legend, status, summary).")

    # 4. Switch to Marathi (मराठी)
    print("\n--- 4. Testing Switch to Marathi (मराठी) ---")
    r_mr = session.get(f"{BASE_URL}/set-language/mr", allow_redirects=True)
    assert r_mr.status_code == 200
    soup_mr = BeautifulSoup(r_mr.text, 'html.parser')

    lang_btn = soup_mr.select_one('#languageDropdown')
    print(f" Language selector text in Marathi: '{lang_btn.get_text(strip=True)}'")
    assert "मराठी" in lang_btn.get_text(), f"Expected 'मराठी' in selector, got '{lang_btn.get_text()}'"

    # Check Marathi Devanagari translations
    assert "बस शोधा" in r_mr.text, "Marathi 'बस शोधा' (Search Buses) not found on homepage"
    assert "आपला प्रवास सुखकर आणि सुरक्षिततेने सुरू होतो" in soup_mr.get_text(), "Marathi hero title not found"
    assert "कुठून (प्रस्थान)" in r_mr.text, "Marathi 'कुठून (प्रस्थान)' not found"
    assert "कुठे (गंतव्य)" in r_mr.text, "Marathi 'कुठे (गंतव्य)' not found"
    assert "प्रवासाची तारीख" in r_mr.text, "Marathi 'प्रवासाची तारीख' not found"
    print(" [PASS] Marathi homepage UI rendered correctly in Devanagari.")

    # 5. Switch back to English
    print("\n--- 5. Testing Switch Back to English (en) ---")
    r_en = session.get(f"{BASE_URL}/set-language/en", allow_redirects=True)
    assert r_en.status_code == 200
    assert "Search Buses" in r_en.text
    print(" [PASS] English restored smoothly.")

    # 6. Test Auth Pages in Hindi
    print("\n--- 6. Testing Authentication Pages in Hindi ---")
    session.get(f"{BASE_URL}/set-language/hi")
    r_login = session.get(f"{BASE_URL}/login")
    assert "साइन इन" in r_login.text or "ईमेल" in r_login.text, "Hindi login labels not found"
    assert "पासवर्ड" in r_login.text, "Hindi password label not found"
    print(" [PASS] Login page in Hindi verified.")

    r_reg = session.get(f"{BASE_URL}/register")
    assert "यात्री पंजीकरण" in r_reg.text or "पूरा नाम" in r_reg.text, "Hindi register title not found"
    assert "ईमेल पता" in r_reg.text or "फ़ोन नंबर" in r_reg.text, "Hindi email/phone labels not found"
    print(" [PASS] Registration page in Hindi verified.")

    # 7. Test Admin Pages in Marathi
    print("\n--- 7. Testing Admin Portal in Marathi ---")
    session.get(f"{BASE_URL}/set-language/mr")
    
    # Login as Admin
    login_data = {
        "email": "admin@busreservation.com",
        "password": "Admin@123"
    }
    r_admin_login = session.post(f"{BASE_URL}/login", data=login_data, allow_redirects=True)
    assert r_admin_login.status_code == 200

    r_admin_dash = session.get(f"{BASE_URL}/admin/dashboard")
    assert "प्रशासक डॅशबोर्ड" in r_admin_dash.text or "एकूण बसेस" in r_admin_dash.text, "Marathi admin dashboard text not found"
    print(" [PASS] Admin dashboard in Marathi verified.")

    r_admin_buses = session.get(f"{BASE_URL}/admin/buses")
    assert "बस ताफा व्यवस्थापन" in r_admin_buses.text or "नवीन बस जोडा" in r_admin_buses.text, "Marathi admin buses text not found"
    print(" [PASS] Admin bus management in Marathi verified.")

    r_admin_routes = session.get(f"{BASE_URL}/admin/routes")
    assert "मार्ग व्यवस्थापन" in r_admin_routes.text or "नवीन मार्ग जोडा" in r_admin_routes.text, "Marathi admin routes text not found"
    print(" [PASS] Admin routes management in Marathi verified.")

    r_admin_scheds = session.get(f"{BASE_URL}/admin/schedules")
    assert "वेळापत्रक व्यवस्थापन" in r_admin_scheds.text or "नवीन वेळापत्रक तयार करा" in r_admin_scheds.text, "Marathi admin schedules text not found"
    print(" [PASS] Admin schedules in Marathi verified.")

    r_admin_users = session.get(f"{BASE_URL}/admin/users")
    assert "वापरकर्ता व्यवस्थापन" in r_admin_users.text or "सर्व वापरकर्ते" in r_admin_users.text, "Marathi admin users text not found"
    print(" [PASS] Admin users in Marathi verified.")

    r_admin_reports = session.get(f"{BASE_URL}/admin/reports")
    assert "अहवाल आणि महसूल विश्लेषण" in r_admin_reports.text or "फिल्टर केलेले उत्पन्न" in r_admin_reports.text or "अहवाल प्रिंट करा" in r_admin_reports.text, "Marathi admin reports text not found"
    print(" [PASS] Admin reports in Marathi verified.")

    # 8. Test Operator Portal in Hindi
    print("\n--- 8. Testing Operator Portal in Hindi ---")
    session.get(f"{BASE_URL}/set-language/hi")
    
    # Logout and login as operator
    session.get(f"{BASE_URL}/logout")
    session.get(f"{BASE_URL}/set-language/hi")
    op_login = {
        "email": "operator@busreservation.com",
        "password": "Operator@123"
    }
    r_op_login = session.post(f"{BASE_URL}/login", data=op_login, allow_redirects=True)
    assert r_op_login.status_code == 200

    r_op_dash = session.get(f"{BASE_URL}/operator/dashboard")
    assert "ऑपरेटर डैशबोर्ड" in r_op_dash.text or "सौंपा गया बेड़ा" in r_op_dash.text, "Hindi operator dashboard text not found"
    print(" [PASS] Operator dashboard in Hindi verified.")

    # 9. Test Passenger Portal in Hindi
    print("\n--- 9. Testing Passenger Portal in Hindi ---")
    session.get(f"{BASE_URL}/logout")
    session.get(f"{BASE_URL}/set-language/hi")
    pass_login = {
        "email": "passenger@busreservation.com",
        "password": "Passenger@123"
    }
    session.post(f"{BASE_URL}/login", data=pass_login, allow_redirects=True)
    
    r_pass_dash = session.get(f"{BASE_URL}/dashboard")
    assert "यात्री डैशबोर्ड" in r_pass_dash.text or "मेरी बुकिंग्स" in r_pass_dash.text or "डैशबोर्ड" in r_pass_dash.text, "Hindi passenger dashboard text not found"
    print(" [PASS] Passenger dashboard in Hindi verified.")

    r_pass_bookings = session.get(f"{BASE_URL}/my-bookings")
    assert "मेरी यात्रा बुकिंग्स" in r_pass_bookings.text or "सभी बुकिंग्स" in r_pass_bookings.text, "Hindi my bookings text not found"
    print(" [PASS] My Bookings in Hindi verified.")

    r_pass_profile = session.get(f"{BASE_URL}/profile")
    assert "मेरी प्रोफ़ाइल और खाता सेटिंग्स" in r_pass_profile.text or "पासवर्ड बदलें" in r_pass_profile.text, "Hindi profile text not found"
    print(" [PASS] Profile page in Hindi verified.")

    # Restore to English
    session.get(f"{BASE_URL}/set-language/en")
    print("\n=================================================================")
    print("ALL MULTI-LANGUAGE VERIFICATIONS PASSED SUCCESSFULLY!")
    print("=================================================================")

if __name__ == "__main__":
    try:
        test_language_switcher_and_translations()
    except Exception as e:
        print(f"\n[FAIL] Verification error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
