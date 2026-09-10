/**
 * Bus Reservation System - Seat Selection Engine
 */

document.addEventListener('DOMContentLoaded', function() {
    const seatContainer = document.getElementById('busSeatGrid');
    if (!seatContainer) return;

    const baseFare = parseFloat(seatContainer.dataset.fare) || 0;
    const scheduleId = seatContainer.dataset.scheduleId;
    const maxSeats = 6;

    let selectedSeats = []; // Array of { id, seatNumber }

    const selectedCountEl = document.getElementById('selectedSeatCount');
    const totalFareEl = document.getElementById('totalFareDisplay');
    const selectedListEl = document.getElementById('selectedSeatsBadges');
    const proceedBtn = document.getElementById('proceedToBookingBtn');

    // Click handler for seats
    seatContainer.addEventListener('click', function(e) {
        const seatEl = e.target.closest('.seat');
        if (!seatEl) return;

        if (seatEl.classList.contains('booked')) {
            return; // Booked seats cannot be clicked
        }

        const seatId = parseInt(seatEl.dataset.seatId);
        const seatNumber = seatEl.dataset.seatNumber;

        const existingIdx = selectedSeats.findIndex(s => s.id === seatId);

        if (existingIdx >= 0) {
            // Deselect seat
            selectedSeats.splice(existingIdx, 1);
            seatEl.classList.remove('selected');
        } else {
            // Check max limit
            if (selectedSeats.length >= maxSeats) {
                const alertMsg = seatContainer.dataset.maxSeatsAlert || `You can select a maximum of ${maxSeats} seats in a single booking.`;
                alert(alertMsg);
                return;
            }
            // Select seat
            selectedSeats.push({ id: seatId, seatNumber: seatNumber });
            seatEl.classList.add('selected');
        }

        updateSummary();
    });

    function updateSummary() {
        const count = selectedSeats.length;
        const total = (count * baseFare).toFixed(2);

        if (selectedCountEl) selectedCountEl.textContent = count;
        if (totalFareEl) totalFareEl.textContent = `₹${parseFloat(total).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;

        // Render badges
        if (selectedListEl) {
            if (count === 0) {
                const noSeatsTxt = seatContainer.dataset.noSeatsText || 'No seats selected yet';
                selectedListEl.innerHTML = `<span class="text-muted small">${noSeatsTxt}</span>`;
            } else {
                selectedListEl.innerHTML = selectedSeats.map(s => 
                    `<span class="badge bg-primary px-2 py-1 me-1 mb-1 fs-6">${s.seatNumber}</span>`
                ).join('');
            }
        }

        // Enable or disable button
        if (proceedBtn) {
            if (count > 0) {
                proceedBtn.removeAttribute('disabled');
                const seatIdsParam = selectedSeats.map(s => s.id).join(',');
                proceedBtn.onclick = function() {
                    window.location.href = `/book/${scheduleId}?seats=${seatIdsParam}`;
                };
            } else {
                proceedBtn.setAttribute('disabled', 'true');
                proceedBtn.onclick = null;
            }
        }
    }

    // Initial update
    updateSummary();
});
