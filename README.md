# F1 Telemetry Dashboard

An interactive Formula 1 telemetry analysis dashboard built using **FastF1**, **Dash**, and **Plotly**.

This project explores driver performance comparison, lap consistency, and telemetry-based delta analysis using real F1 session data.

The app supports both race weekends and testing events with dynamic event/session handling.

---

## Features

- Dynamic Year → Event → Session dropdown flow (includes testing events)
- Driver vs Driver fastest-lap comparison
- Comparative KPI cards:
  - Fastest lap gap
  - Top speed delta
  - Average speed delta
  - Largest sector swing
- Cumulative delta vs distance graph
- Sector delta bar chart
- Speed distribution (lap-distance share by speed band)
- Multi-channel telemetry overlay:
  - Speed
  - Throttle
  - RPM
  - Brake
  - Gear
- Track mini-map with synced cursor position
- Track segment advantage map (binary faster-driver coloring)
- Fastest lap benchmark table
- Session Analysis tab:
  - Lap drilldown (single driver)
  - Selected lap vs fastest lap telemetry overlay
  - Delta to fastest lap graph
  - Lap time evolution (supports up to 2 drivers)
  - New lap controls: **Prev / input / Next**

---

## Tech Stack

- Python
- FastF1
- Pandas
- Plotly
- Dash
- NumPy

---

## Installation

Clone the repository:

```
git clone git@github.com:Raxxy-m/f1-telemetry-dashboard.git
cd f1-telemetry-dashboard
```

Create virtual Environment:

```
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:
```
pip3 install -r requirements.txt
```

Run the app:
```
python3 app.py
```

---

## Notes

- Lap drilldown telemetry views are intentionally single-driver.
- Lap time evolution supports one or two drivers for direct pace comparison.
- For testing events, sessions are loaded using FastF1 testing-session flow.

---
## License
This project is for educational and portfolio purposes.

---
