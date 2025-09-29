/*
 * ARAS Smart Home Control System - Arduino Side
 * Controls 2 lights using 4-channel relay module
 * Uses Classic Bluetooth Serial for communication with PyQt6 home viewer app
 * 
 * Device Layout:
 * - Light 1: Pin 4 (digital output)
 * - Light 2: Pin 5 (digital output)
 * - Bluetooth: SoftwareSerial (RX=2, TX=3)
 * - Status LED: Pin 13 (built-in LED)
 */

#include <SoftwareSerial.h>

// Pin definitions
const int LIGHT_PINS[2] = {4, 5};
const int STATUS_LED = 13; // Built-in LED

// Bluetooth setup
SoftwareSerial BT(2, 3); // RX, TX pins for Bluetooth (avoiding pins 0,1 for Serial)

// Device states
bool deviceStates[2] = {false}; // 2 lights

// Status tracking
unsigned long lastHeartbeat = 0;
const unsigned long HEARTBEAT_INTERVAL = 5000; // 5 seconds
bool bluetoothConnected = false;

void setup() {
  // Initialize serial communication
  Serial.begin(9600);
  
  // Initialize all output pins
  initializePins();
  
  // Initialize device states
  initializeDeviceStates();
  
  // Status indicator
  pinMode(STATUS_LED, OUTPUT);
  
  // Initial status
  digitalWrite(STATUS_LED, HIGH);
  
  // Initialize Bluetooth at 9600 baud
  initializeBluetooth();
  
  Serial.println("ARAS Ready - Smart Home Controller");
  Serial.println("Waiting for Bluetooth commands...");
  Serial.println("Send 'z' for ping, 'A' for light 1 ON, 'a' for light 1 OFF");
  Serial.println("Send 'B' for light 2 ON, 'b' for light 2 OFF");
}

void loop() {
  // Handle Bluetooth communication
  handleBluetoothCommunication();
  
  // Send periodic heartbeat
  sendHeartbeat();
  
  // Small delay to prevent overwhelming the system
  delay(10);
}

void initializePins() {
  // Initialize light pins (L1-L2) - Active LOW relays
  for (int i = 0; i < 2; i++) {
    pinMode(LIGHT_PINS[i], OUTPUT);
    digitalWrite(LIGHT_PINS[i], HIGH); // HIGH = OFF for active LOW relays
  }
}

void initializeDeviceStates() {
  // All devices start in OFF state
  for (int i = 0; i < 2; i++) {
    deviceStates[i] = false;
  }
}

void initializeBluetooth() {
  BT.begin(9600); // Default HC-05 baud rate
  delay(1000);
  
  // Test communication by sending a ping
  BT.print("z"); // Send single character ping
  delay(500);
  
  // Check for response
  if (BT.available()) {
    String response = BT.readString();
    if (response.indexOf("PONG") >= 0 || response.indexOf("OK") >= 0) {
      bluetoothConnected = true;
      Serial.println("Bluetooth connected!");
      return;
    }
  }
  
  bluetoothConnected = false;
  Serial.println("Bluetooth not connected");
}

void handleBluetoothCommunication() {
  if (BT.available()) {
    // Read all available characters
    String command = "";
    while (BT.available()) {
      char c = BT.read();
      command += c;
      delay(10); // Small delay to ensure all data is received
    }
    
    Serial.print("Received: ");
    Serial.println(command);

    // Process each character in the command
    for (int i = 0; i < command.length(); i++) {
      char cmd = command.charAt(i);
      if (cmd != '\n' && cmd != '\r') { // Skip newline characters
        processCommand(cmd);
      }
    }
  }
}

void processCommand(char cmd) {
  // Process single character commands for 2 lights
  switch (cmd) {
    // Lights L1-L2 (A-B for ON, a-b for OFF)
    case 'A': toggleDevice(0); break;   // L1 ON
    case 'a': toggleDevice(0); break;   // L1 OFF
    case 'B': toggleDevice(1); break;   // L2 ON
    case 'b': toggleDevice(1); break;   // L2 OFF
    
    // Special commands
    case 'Y': handleAllOn(); break;     // All devices ON
    case 'y': handleAllOff(); break;    // All devices OFF
    case 'Z': handleGetStatus(); break; // Get status
    case 'z': handlePing(); break;      // Ping
    
    default: 
      Serial.println("Unknown command: " + String(cmd));
      break;
  }
}

void toggleDevice(int deviceIndex) {
  if (deviceIndex < 0 || deviceIndex >= 2) {
    return;
  }
  
  deviceStates[deviceIndex] = !deviceStates[deviceIndex];
  updateDeviceOutput(deviceIndex);
  
  String deviceName = getDeviceName(deviceIndex);
  String state = deviceStates[deviceIndex] ? "ON" : "OFF";
  Serial.println(deviceName + " " + state);
}



void handleAllOn() {
  for (int i = 0; i < 2; i++) {
    deviceStates[i] = true;
    updateDeviceOutput(i);
  }
  
  sendResponse("ALL_DEVICES_ON", "All devices turned ON");
}

void handleAllOff() {
  for (int i = 0; i < 2; i++) {
    deviceStates[i] = false;
    updateDeviceOutput(i);
  }
  
  sendResponse("ALL_DEVICES_OFF", "All devices turned OFF");
}

void handleGetStatus() {
  if (bluetoothConnected) {
    String status = "STATUS:";
    
    // Device states
    for (int i = 0; i < 2; i++) {
      status += String(deviceStates[i] ? "1" : "0");
      if (i < 1) status += ",";
    }
    
    BT.println(status);
  }
  
  sendResponse("STATUS", "Device states sent");
}

void handlePing() {
  Serial.println("Ping received - sending PONG");
  sendResponse("PONG", "Arduino controller online");
  BT.println("PONG"); // Also send via BT for debugging
}

void updateDeviceOutput(int deviceIndex) {
  if (deviceIndex < 2) {
    // Light (L1-L2) - Active LOW relays
    digitalWrite(LIGHT_PINS[deviceIndex], deviceStates[deviceIndex] ? LOW : HIGH);
  }
}

String getDeviceName(int deviceIndex) {
  if (deviceIndex < 2) {
    return "L" + String(deviceIndex + 1);
  }
  return "UNKNOWN";
}

void sendResponse(String command, String message) {
  if (bluetoothConnected) {
    String response = command + ":" + message;
    BT.println(response);
  }
}

void sendError(String errorCode, String message) {
  if (bluetoothConnected) {
    String error = "ERROR:" + errorCode + ":" + message;
    BT.println(error);
  }
  
  // Flash status LED for error indication
  digitalWrite(STATUS_LED, LOW);
  delay(100);
  digitalWrite(STATUS_LED, HIGH);
}

void sendHeartbeat() {
  unsigned long currentTime = millis();
  if (currentTime - lastHeartbeat >= HEARTBEAT_INTERVAL) {
    sendResponse("HEARTBEAT", "Arduino online");
    lastHeartbeat = currentTime;
    
    // Toggle status LED to show activity
    digitalWrite(STATUS_LED, !digitalRead(STATUS_LED));
  }
}

