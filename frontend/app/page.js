"use client";

import { useEffect, useState } from "react";

export default function Home() {
  const [slots, setSlots] = useState([]);
  const [selectedDate, setSelectedDate] = useState("2026-05-15");
  const [selectedSlot, setSelectedSlot] = useState("");
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [message, setMessage] = useState("");

  const barberId = "c36fbd7b-c3a7-46ce-aa01-6d3952de4b5d";
  const serviceId = "59be4262-cd6d-4440-afcf-107e327b1a69";

  function loadSlots(dateToLoad = selectedDate) {
    setMessage("");
    setSelectedSlot("");

    fetch(
      `https://chairtime-production-94da.up.railway.app/api/availability?barber_id=${barberId}&service_id=${serviceId}&target_date=${dateToLoad}`
    )
      .then((res) => res.json())
      .then((data) => setSlots(data.slots || []));
  }

  useEffect(() => {
    loadSlots(selectedDate);
  }, []);

  function handleDateChange(e) {
    const newDate = e.target.value;
    setSelectedDate(newDate);
    loadSlots(newDate);
  }

  async function bookAppointment() {
    setMessage("");

    if (!selectedSlot || !customerName || !customerPhone) {
      setMessage("Please choose a time and enter your name and phone number.");
      return;
    }

    const response = await fetch("https://chairtime-production-94da.up.railway.app/api/appointments", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        barber_id: barberId,
        service_id: serviceId,
        customer_name: customerName,
        customer_phone: customerPhone,
        start_datetime: selectedSlot,
      }),
    });

    if (response.ok) {
      setMessage("Appointment booked successfully!");
      setSelectedSlot("");
      setCustomerName("");
      setCustomerPhone("");
      loadSlots(selectedDate);
    } else if (response.status === 409) {
      setMessage("That time was just booked. Please choose another time.");
      loadSlots(selectedDate);
    } else {
      setMessage("Booking failed. Please try again.");
    }
  }

  return (
    <main className="min-h-screen bg-gray-100 p-10">
      <div className="max-w-2xl mx-auto bg-white rounded-2xl shadow p-8">
        <h1 className="text-4xl font-bold mb-2">ChairTime</h1>

        <p className="text-gray-600 mb-8">Book your appointment</p>

        <label className="block font-semibold mb-2">
          Choose a date
        </label>

        <input
          type="date"
          value={selectedDate}
          onChange={handleDateChange}
          className="w-full border rounded-xl p-3 mb-8"
        />

        <div className="grid grid-cols-2 gap-3 mb-8">
          {slots.length === 0 && (
            <p className="text-gray-500 col-span-2">
              No available times for this date.
            </p>
          )}

          {slots.map((slot) => (
            <button
              key={slot}
              onClick={() => setSelectedSlot(slot)}
              className={`p-4 border rounded-xl text-left ${
                selectedSlot === slot ? "bg-black text-white" : "bg-white"
              }`}
            >
              {new Date(slot).toLocaleTimeString([], {
                hour: "numeric",
                minute: "2-digit",
              })}
            </button>
          ))}
        </div>

        <div className="space-y-4">
          <input
            className="w-full border rounded-xl p-3"
            placeholder="Your name"
            value={customerName}
            onChange={(e) => setCustomerName(e.target.value)}
          />

          <input
            className="w-full border rounded-xl p-3"
            placeholder="Phone number"
            value={customerPhone}
            onChange={(e) => setCustomerPhone(e.target.value)}
          />

          <button
            onClick={bookAppointment}
            className="w-full bg-black text-white rounded-xl p-4 font-semibold"
          >
            Book Appointment
          </button>
        </div>

        {message && <p className="mt-6 font-medium">{message}</p>}
      </div>
    </main>
  );
}