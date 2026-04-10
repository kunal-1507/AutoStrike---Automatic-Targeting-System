# 🔌 AutoStrike Wiring Details

This document explains the complete hardware wiring for the **AutoStrike: Intelligent Object Tracking System** using Raspberry Pi, Camera Module, and Servo Motors.

---

## 🧰 Components Used

* Raspberry Pi
* Pi Camera Module
* 2x Servo Motors (MG996R)
* LM2596 Buck Converter
* 7.4V Li-Ion Battery
* Connecting Wires

---

## ⚡ Power Distribution

* **Battery (7.4V Li-Ion)** → Input to LM2596 Buck Converter
* **LM2596 Output (5V)** → Powers Servo Motors
* **Raspberry Pi** → Powered separately (recommended via USB/adapter)

> ⚠️ Do NOT power servos directly from Raspberry Pi (can damage Pi)

---

## 🎥 Camera Module Connection

| Camera Pin | Raspberry Pi    |
| ---------- | --------------- |
| CSI Cable  | CSI Camera Port |

* Connect the ribbon cable to the **CSI slot** on Raspberry Pi
* Ensure correct orientation (metal contacts aligned properly)

---

## 🔄 Servo Motor Connections

### 🟢 Pan Servo (Horizontal Movement)

| Servo Wire             | Connection         |
| ---------------------- | ------------------ |
| Red (VCC)              | 5V (LM2596 Output) |
| Brown/Black (GND)      | GND (LM2596)       |
| Orange/Yellow (Signal) | GPIO 18            |

---

### 🔵 Tilt Servo (Vertical Movement)

| Servo Wire             | Connection         |
| ---------------------- | ------------------ |
| Red (VCC)              | 5V (LM2596 Output) |
| Brown/Black (GND)      | GND (LM2596)       |
| Orange/Yellow (Signal) | GPIO 13            |

---

## 🔗 Common Ground (IMPORTANT)

* Connect **LM2596 GND** and **Raspberry Pi GND together**

> ⚠️ Without common ground, servos may behave unpredictably

---

## 🧠 GPIO Pin Mapping

| Function   | GPIO Pin |
| ---------- | -------- |
| Pan Servo  | GPIO 18  |
| Tilt Servo | GPIO 13  |

---

## ⚙️ Buck Converter (LM2596)

* Input: 7.4V from battery
* Output: Adjust to **5V (using onboard potentiometer)**
* Use multimeter to verify output before connecting

---

## ⚠️ Safety Precautions

* Double-check polarity before powering ON
* Ensure stable 5V supply for servos
* Avoid loose connections
* Do not exceed servo voltage ratings

---

## 📌 Notes

* Servos may draw high current → use good quality battery
* If jitter occurs → add capacitor across VCC & GND
* Use proper mounting for stable tracking

---

## 🖼️ Reference

Refer to the circuit diagram in:
`hardware/circuit_diagram.png`

---

## ✅ Summary

* Camera → CSI port
* Servos → GPIO + external 5V supply
* Common Ground → Required
* Buck Converter → Regulates voltage

---
