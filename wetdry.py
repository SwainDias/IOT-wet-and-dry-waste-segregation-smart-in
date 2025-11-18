import utime
import machine
import network
import urequests # Required for sending data
from machine import Pin, PWM, ADC

# --- 1. WI-FI & THINGSPEAK CONFIGURATION ---
# ENTER YOUR DETAILS HERE
WIFI_SSID = "YOUR_WIFI_NAME"        # e.g. "Home_WiFi"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD" # e.g. "12345678"
THINGSPEAK_API_KEY = "YOUR_WRITE_API_KEY" # Copy from ThingSpeak

# --- Pin Definitions ---
print("DEBUG: Initializing pins...")
# Servo Motor (SG90)
servo_pin = Pin(13)
servo = PWM(servo_pin, freq=50)

# Soil Moisture Sensor (FC-28)
moisture_pin = Pin(34)
moisture_sensor = ADC(moisture_pin)
moisture_sensor.atten(ADC.ATTN_11DB)  # Set 3.3V range

# Ultrasonic Sensor (HC-SR04)
trig_pin = Pin(14, Pin.OUT)
echo_pin = Pin(12, Pin.IN)
print("DEBUG: Pins initialized.")

# --- Tunable Settings ---
DETECTION_DISTANCE_CM = 15
WET_THRESHOLD = 3200        # Your calibrated value
IDLE_ANGLE = 90
WET_ANGLE = 160
DRY_ANGLE = 20

# --- Wi-Fi Connection Function ---
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print(f"DEBUG: Connecting to Wi-Fi: {WIFI_SSID}...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        timeout = 0
        while not wlan.isconnected():
            utime.sleep(1)
            timeout += 1
            print(".", end="")
            if timeout > 15:
                print("\nDEBUG: Wi-Fi Connection Failed!")
                return False
    print(f"\nDEBUG: Wi-Fi Connected! IP: {wlan.ifconfig()[0]}")
    return True

# --- ThingSpeak Upload Function ---
def send_to_thingspeak(waste_type, moisture_val):
    # waste_type: 1 for Wet, 0 for Dry
    # moisture_val: The raw ADC number
    
    url = f"http://api.thingspeak.com/update?api_key={THINGSPEAK_API_KEY}&field1={waste_type}&field2={moisture_val}"
    
    try:
        print("DEBUG: Uploading to ThingSpeak...")
        response = urequests.get(url)
        response.close()
        print("DEBUG: Data sent successfully!")
    except Exception as e:
        print(f"DEBUG: Upload Failed. Error: {e}")

# --- Helper Function: Get Ultrasonic Distance ---
def get_distance():
    trig_pin.off()
    utime.sleep_us(2)
    trig_pin.on()
    utime.sleep_us(10)
    trig_pin.off()

    try:
        duration = machine.time_pulse_us(echo_pin, 1, 30000)
        if duration > 0:
            distance = (duration * 0.0343) / 2
            return distance
        else:
            return -1
            
    except OSError as ex:
        print(f"DEBUG: Sensor read error! {ex}")
        return -1

# --- Helper Function: Move Servo ---
def set_servo_angle(angle):
    duty = int(25 + (angle / 180) * (128 - 25))
    servo.duty(duty)

# --- Main Program ---
print("--- Waste Segregator Initializing ---")
print(f"DEBUG: WET_THRESHOLD = {WET_THRESHOLD}")

# Connect to Wi-Fi at startup
wifi_status = connect_wifi()
if not wifi_status:
    print("WARNING: Running without Wi-Fi. Data will not be uploaded.")

print("DEBUG: Setting servo to IDLE position...")
set_servo_angle(IDLE_ANGLE)
utime.sleep(2)

print("DEBUG: --- Main loop starting ---")

while True:
    distance = get_distance()
    
    if distance > 0 and distance < DETECTION_DISTANCE_CM:
        print(f"--- EVENT: Object Detected! ---")
        print(f"DEBUG: Distance: {distance:.1f} cm")
        utime.sleep_ms(500)
        
        # Read moisture
        moisture_raw = moisture_sensor.read()
        print(f"DEBUG: Moisture reading: {moisture_raw}")
        
        current_waste_type = 0 # Default to Dry (0)
        
        if moisture_raw < WET_THRESHOLD:
            print("DEBUG: Logic -> WET")
            set_servo_angle(WET_ANGLE)
            current_waste_type = 1 # Set to Wet
        else:
            print("DEBUG: Logic -> DRY")
            set_servo_angle(DRY_ANGLE)
            current_waste_type = 0 # Set to Dry (Explicitly)
            
        # --- UPLOAD TO CLOUD ---
        # We upload AFTER moving the servo so the physical sorting happens instantly
        if wifi_status:
            send_to_thingspeak(current_waste_type, moisture_raw)
            
        utime.sleep(3) # Hold position
        print("DEBUG: Returning to IDLE")
        set_servo_angle(IDLE_ANGLE)
        
        print("DEBUG: Waiting for object to be cleared...")
        while distance > 0 and distance < DETECTION_DISTANCE_CM:
            distance = get_distance()
            utime.sleep_ms(200)
        print("DEBUG: Object cleared. Ready for next item.")

    utime.sleep_ms(200)
