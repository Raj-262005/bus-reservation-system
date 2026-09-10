-- ==========================================================
-- Bus Reservation System - Database Schema (MySQL 8.0)
-- Academic Software Engineering Project
-- ==========================================================

CREATE DATABASE IF NOT EXISTS bus_reservation_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE bus_reservation_db;

-- ----------------------------------------------------------
-- 1. Table: users
-- Roles: 'passenger', 'admin', 'operator'
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    phone VARCHAR(20) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('passenger', 'admin', 'operator') NOT NULL DEFAULT 'passenger',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_email (email),
    INDEX idx_user_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------
-- 2. Table: routes
-- Source, destination, distance, estimated duration
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS routes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_city VARCHAR(100) NOT NULL,
    destination_city VARCHAR(100) NOT NULL,
    distance_km DECIMAL(6, 2) NOT NULL DEFAULT 0.00,
    estimated_duration VARCHAR(50) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_route_cities (source_city, destination_city)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------
-- 3. Table: buses
-- Bus details, type, total seats, assigned operator
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS buses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    bus_number VARCHAR(30) NOT NULL UNIQUE,
    bus_name VARCHAR(100) NOT NULL,
    bus_type ENUM('AC Sleeper', 'AC Seater', 'Non-AC Sleeper', 'Non-AC Seater', 'Luxury Multi-Axle') NOT NULL DEFAULT 'AC Seater',
    total_seats INT NOT NULL DEFAULT 40,
    operator_id INT NULL,
    amenities VARCHAR(255) DEFAULT 'Air Conditioning, Charging Point, Reading Light, Water Bottle',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (operator_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_bus_number (bus_number),
    INDEX idx_bus_operator (operator_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------
-- 4. Table: seats
-- Physical seats belonging to each bus
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS seats (
    id INT AUTO_INCREMENT PRIMARY KEY,
    bus_id INT NOT NULL,
    seat_number VARCHAR(10) NOT NULL,
    seat_type ENUM('SEATER', 'SLEEPER', 'WINDOW', 'AISLE') NOT NULL DEFAULT 'SEATER',
    deck ENUM('LOWER', 'UPPER') NOT NULL DEFAULT 'LOWER',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    FOREIGN KEY (bus_id) REFERENCES buses(id) ON DELETE CASCADE,
    UNIQUE KEY uq_bus_seat (bus_id, seat_number),
    INDEX idx_seat_bus (bus_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------
-- 5. Table: schedules
-- Operational runs connecting bus, route, date and time
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS schedules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    bus_id INT NOT NULL,
    route_id INT NOT NULL,
    journey_date DATE NOT NULL,
    departure_time TIME NOT NULL,
    arrival_time TIME NOT NULL,
    fare DECIMAL(8, 2) NOT NULL,
    status ENUM('SCHEDULED', 'COMPLETED', 'CANCELLED') NOT NULL DEFAULT 'SCHEDULED',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bus_id) REFERENCES buses(id) ON DELETE CASCADE,
    FOREIGN KEY (route_id) REFERENCES routes(id) ON DELETE RESTRICT,
    INDEX idx_schedule_search (route_id, journey_date, status),
    INDEX idx_schedule_bus (bus_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------
-- 6. Table: bookings
-- Master booking record
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS bookings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id VARCHAR(30) NOT NULL UNIQUE,
    user_id INT NOT NULL,
    schedule_id INT NOT NULL,
    total_passengers INT NOT NULL DEFAULT 1,
    total_amount DECIMAL(10, 2) NOT NULL,
    booking_status ENUM('CONFIRMED', 'CANCELLED', 'PENDING') NOT NULL DEFAULT 'CONFIRMED',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    cancellation_reason VARCHAR(255) NULL,
    cancelled_at DATETIME NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY (schedule_id) REFERENCES schedules(id) ON DELETE RESTRICT,
    INDEX idx_booking_user (user_id),
    INDEX idx_booking_schedule (schedule_id),
    INDEX idx_booking_status (booking_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------
-- 7. Table: booking_passengers
-- Individual passenger per booked seat
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS booking_passengers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL,
    seat_id INT NOT NULL,
    passenger_name VARCHAR(100) NOT NULL,
    age INT NOT NULL,
    gender ENUM('Male', 'Female', 'Other') NOT NULL,
    seat_number VARCHAR(10) NOT NULL,
    FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
    FOREIGN KEY (seat_id) REFERENCES seats(id) ON DELETE RESTRICT,
    INDEX idx_passenger_booking (booking_id),
    INDEX idx_passenger_seat (seat_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------
-- 8. Table: payments
-- Payment transactions associated with bookings
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL,
    transaction_id VARCHAR(60) NOT NULL UNIQUE,
    payment_method ENUM('UPI', 'CARD', 'NETBANKING', 'RAZORPAY_TEST', 'RAZORPAY_LIVE') NOT NULL DEFAULT 'UPI',
    amount DECIMAL(10, 2) NOT NULL,
    payment_status ENUM('PENDING', 'SUCCESS', 'FAILED', 'REFUNDED') NOT NULL DEFAULT 'PENDING',
    gateway_payment_id VARCHAR(100) NULL,
    gateway_order_id VARCHAR(100) NULL,
    paid_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
    INDEX idx_payment_booking (booking_id),
    INDEX idx_payment_status (payment_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------
-- 9. Table: cancellations
-- Cancellation and refund tracking
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS cancellations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL UNIQUE,
    cancelled_by_id INT NOT NULL,
    refund_amount DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    refund_status ENUM('PENDING', 'PROCESSED', 'FAILED', 'NO_REFUND') NOT NULL DEFAULT 'PROCESSED',
    reason VARCHAR(255) NULL,
    cancellation_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
    FOREIGN KEY (cancelled_by_id) REFERENCES users(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------
-- 10. Table: tickets
-- Official issued E-Tickets for confirmed bookings
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS tickets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticket_number VARCHAR(40) NOT NULL UNIQUE,
    booking_id INT NOT NULL UNIQUE,
    passenger_name VARCHAR(100) NOT NULL,
    seat_numbers VARCHAR(100) NOT NULL,
    journey_date DATE NOT NULL,
    departure_time TIME NOT NULL,
    source_city VARCHAR(100) NOT NULL,
    destination_city VARCHAR(100) NOT NULL,
    bus_name VARCHAR(100) NOT NULL,
    total_fare DECIMAL(10, 2) NOT NULL,
    ticket_status ENUM('ISSUED', 'CANCELLED') NOT NULL DEFAULT 'ISSUED',
    issued_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
    INDEX idx_ticket_number (ticket_number),
    INDEX idx_ticket_booking (booking_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------
-- 11. Table: activity_logs
-- System audit & action logs
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS activity_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    action VARCHAR(100) NOT NULL,
    details TEXT NULL,
    ip_address VARCHAR(50) NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_log_user (user_id),
    INDEX idx_log_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

