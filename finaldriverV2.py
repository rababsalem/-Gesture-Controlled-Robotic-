import cv2
import mediapipe as mp
import numpy as np
import time
import queue
import socket
import threading
import requests
import concurrent.futures
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from threading import Thread

class ESP32CamGestureController:
    def __init__(self, root):
        self.root = root
        self.root.title("ESP32-CAM Gesture Controller")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Create variables
        self.esp_cam_ip = None
        self.esp8266_ip = tk.StringVar(value="192.168.4.1")  # Default ESP8266 IP
        self.esp8266_port = tk.IntVar(value=80)
        self.esp8266_socket = None
        self.connected = False
        self.attempting_reconnection = False
        self.camera_source = tk.IntVar(value=0)  # 0 for webcam, 1 for ESP32-CAM
        
        # Image queues
        self.webcam_queue = queue.Queue(maxsize=2)
        self.esp32cam_queue = queue.Queue(maxsize=2)
        
        # Thread control flags
        self.running = True
        self.active_threads = []
        
        # Build UI
        self.create_ui()
        
        # MediaPipe setup
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        self.hands = self.mp_hands.Hands(
            model_complexity=0,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7,
            max_num_hands=1
        )
        
        # Start processing
        self.process_thread = Thread(target=self.process_frames, daemon=True)
        self.process_thread.start()
        self.active_threads.append(self.process_thread)
        
    def create_ui(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left side - Controls and logs
        control_frame = ttk.LabelFrame(main_frame, text="Controls", padding=10)
        control_frame.pack(side=tk.LEFT, fill=tk.BOTH)
        
        # Camera selection
        camera_frame = ttk.Frame(control_frame)
        camera_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(camera_frame, text="Camera Source:").pack(side=tk.LEFT)
        ttk.Radiobutton(camera_frame, text="Webcam", variable=self.camera_source, 
                        value=0, command=self.toggle_camera_source).pack(side=tk.LEFT)
        ttk.Radiobutton(camera_frame, text="ESP32-CAM", variable=self.camera_source, 
                        value=1, command=self.toggle_camera_source).pack(side=tk.LEFT)
        
        # ESP32-CAM scanning
        esp32cam_frame = ttk.LabelFrame(control_frame, text="ESP32-CAM", padding=5)
        esp32cam_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(esp32cam_frame, text="Scan for ESP32-CAM", 
                   command=self.start_scan_thread).pack(fill=tk.X)
        
        self.esp32cam_status = ttk.Label(esp32cam_frame, text="Status: Not Connected")
        self.esp32cam_status.pack(fill=tk.X, pady=5)
        
        # ESP8266 connection
        esp8266_frame = ttk.LabelFrame(control_frame, text="ESP8266 Control", padding=5)
        esp8266_frame.pack(fill=tk.X, pady=5)
        
        ip_frame = ttk.Frame(esp8266_frame)
        ip_frame.pack(fill=tk.X, pady=2)
        ttk.Label(ip_frame, text="IP:").pack(side=tk.LEFT)
        ttk.Entry(ip_frame, textvariable=self.esp8266_ip).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        port_frame = ttk.Frame(esp8266_frame)
        port_frame.pack(fill=tk.X, pady=2)
        ttk.Label(port_frame, text="Port:").pack(side=tk.LEFT)
        ttk.Entry(port_frame, textvariable=self.esp8266_port, width=7).pack(side=tk.LEFT)
        
        self.connect_btn = ttk.Button(esp8266_frame, text="Connect", command=self.connect_to_esp8266)
        self.connect_btn.pack(fill=tk.X, pady=2)
        
        # Command frame
        cmd_frame = ttk.Frame(esp8266_frame)
        cmd_frame.pack(fill=tk.X, pady=5)
        
        self.command_entry = ttk.Entry(cmd_frame)
        self.command_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        send_btn = ttk.Button(cmd_frame, text="Send", command=self.send_command)
        send_btn.pack(side=tk.RIGHT)
        
        # Log area
        log_frame = ttk.LabelFrame(control_frame, text="Log", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Gesture control section
        gesture_frame = ttk.LabelFrame(control_frame, text="Guide", padding=5)
        gesture_frame.pack(fill=tk.X, pady=5)
        
        self.gesture_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(gesture_frame, text="Enable Gesture Control", 
                        variable=self.gesture_enabled).pack(anchor="w")
        
        gesture_info = ttk.Label(gesture_frame, 
                                text="Choose camera :\n"
                                     "Connect to car\n"
                                     "Steer with thumb :\n"
                                     "Drive with other fingers"
        )
        gesture_info.pack(fill=tk.X, pady=5)
        
        # Right side - Video display
        video_frame = ttk.LabelFrame(main_frame, text="Video Feed", padding=10)
        video_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(video_frame, background="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
    def log(self, message):
        """Add message to log with timestamp"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        
    def start_scan_thread(self):
        """Start ESP32-CAM scanning in a separate thread"""
        self.log("Starting network scan for ESP32-CAM...")
        scan_thread = Thread(target=self.scan_for_esp32cam, daemon=True)
        scan_thread.start()
        self.active_threads.append(scan_thread)
        
    def scan_for_esp32cam(self):
        """Scan the network for ESP32-CAM devices"""
        local_ip = self.get_local_ip()
        if not local_ip:
            self.log("Could not determine local IP address.")
            return
        
        subnet = self.get_subnet(local_ip)
        self.log(f"Local IP: {local_ip}")
        self.log(f"Scanning subnet: {subnet}.0/24")
        
        # Find first ESP32-CAM device
        esp32_ip = self.find_esp32_cam(subnet)
        
        if esp32_ip:
            self.log(f"Found ESP32-CAM at: {esp32_ip}")
            self.esp_cam_ip = esp32_ip
            self.esp32cam_status.config(text=f"Status: Found at {esp32_ip}")
            
            # Start ESP32-CAM capture thread if currently using ESP32 as source
            if self.camera_source.get() == 1:
                self.start_esp32cam_capture()
        else:
            self.log("No ESP32-CAM device found on the network.")
            self.esp32cam_status.config(text="Status: Not Found")
    
    def get_local_ip(self):
        """Get the local IP address of the computer"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception as e:
            self.log(f"Error getting local IP: {e}")
            return None

    def get_subnet(self, ip):
        """Get the subnet address from an IP address"""
        try:
            parts = ip.split('.')
            return f"{parts[0]}.{parts[1]}.{parts[2]}"
        except Exception as e:
            self.log(f"Error getting subnet: {e}")
            return None

    def check_esp32_cam(self, ip):
        """Check if an IP address responds as an ESP32-CAM"""
        url = f"http://{ip}/capture"
        try:
            response = requests.get(url, timeout=0.5)
            if response.status_code == 200 and 'image' in response.headers.get('Content-Type', ''):
                return ip
            return None
        except requests.exceptions.RequestException:
            return None

    def find_esp32_cam(self, subnet):
        """Scan the network for first ESP32-CAM device"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            ip_list = [f"{subnet}.{i}" for i in range(1, 255)]
            futures = [executor.submit(self.check_esp32_cam, ip) for ip in ip_list]
            
            scan_count = 0
            for future in concurrent.futures.as_completed(futures):
                scan_count += 1
                if scan_count % 25 == 0:
                    self.log(f"Scanned {scan_count} addresses...")
                
                result = future.result()
                if result:
                    # Cancel all pending futures and return the first found
                    for f in futures:
                        f.cancel()
                    return result
        
        return None
    
    def toggle_camera_source(self):
        """Handle camera source toggle"""
        source = self.camera_source.get()
        if source == 0:  # Webcam
            self.log("Switching to webcam")
            self.start_webcam_capture()
        else:  # ESP32-CAM
            if self.esp_cam_ip:
                self.log(f"Switching to ESP32-CAM at {self.esp_cam_ip}")
                self.start_esp32cam_capture()
            else:
                self.log("ESP32-CAM not found. Please scan for it first.")
                self.camera_source.set(0)  # Switch back to webcam
    
    def start_webcam_capture(self):
        """Start capturing from webcam"""
        # Clear the queue
        while not self.webcam_queue.empty():
            try:
                self.webcam_queue.get_nowait()
            except queue.Empty:
                break
        
        # Start capture thread
        capture_thread = Thread(target=self.capture_webcam_images, daemon=True)
        capture_thread.start()
        self.active_threads.append(capture_thread)
        self.log("Started webcam capture")
    
    def capture_webcam_images(self):
        """Capture images from laptop camera and put them in the queue"""
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            self.log("Error: Could not open webcam")
            return

        # Set camera resolution
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        while self.running:
            try:
                ret, frame = cap.read()
                if not ret:
                    self.log("Failed to get frame from webcam")
                    time.sleep(0.1)
                    continue
                    
                frame = cv2.flip(frame, 1)  # Mirror image
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                
                if self.webcam_queue.full():
                    try:
                        self.webcam_queue.get_nowait()
                    except queue.Empty:
                        pass
                self.webcam_queue.put(rgb_frame)
                time.sleep(0.01)  # Small delay to prevent thread hogging
            except Exception as e:
                self.log(f"Error capturing webcam image: {e}")
                time.sleep(0.1)
        
        cap.release()
    
    def start_esp32cam_capture(self):
        """Start capturing from ESP32-CAM"""
        if not self.esp_cam_ip:
            self.log("ESP32-CAM IP not set")
            return
            
        # Clear the queue
        while not self.esp32cam_queue.empty():
            try:
                self.esp32cam_queue.get_nowait()
            except queue.Empty:
                break
                
        # Start capture thread
        capture_thread = Thread(target=self.capture_esp32cam_images, daemon=True)
        capture_thread.start()
        self.active_threads.append(capture_thread)
        self.log(f"Started ESP32-CAM capture from {self.esp_cam_ip}")
    
    def capture_esp32cam_images(self):
        """Thread function to continuously capture images from the ESP32-CAM"""
        url = f"http://{self.esp_cam_ip}/capture"
        
        while self.running and self.camera_source.get() == 1:
            try:
                response = requests.get(url, timeout=2)
                if response.status_code == 200:
                    image_array = np.frombuffer(response.content, dtype=np.uint8)
                    frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
                    frame = cv2.flip(frame, 1)  # Mirror image
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                    
                    if self.esp32cam_queue.full():
                        try:
                            self.esp32cam_queue.get_nowait()
                        except queue.Empty:
                            pass
                    self.esp32cam_queue.put(rgb_frame)
                else:
                    self.log(f"Failed to get image: {response.status_code}")
            except requests.exceptions.RequestException as e:
                self.log(f"ESP32-CAM request error: {e}")
                time.sleep(1)
            except Exception as e:
                self.log(f"ESP32-CAM error: {e}")
                time.sleep(1)
    
    def connect_to_esp8266(self):
        """Connect to ESP8266 device"""
        if self.connected or self.attempting_reconnection:
            # Disconnect
            try:
                if self.esp8266_socket:
                    self.esp8266_socket.close()
                self.connected = False
                self.attempting_reconnection = False
                self.connect_btn.config(text="Connect")
                self.log("Disconnected from ESP8266")
            except Exception as e:
                self.log(f"Error disconnecting: {e}")
            return
            
        try:
            self.start_connection()
        except Exception as e:
            self.log(f"Connection error: {e}")
    
    def start_connection(self):
        """Start connection to ESP8266"""
        esp_ip = self.esp8266_ip.get()
        esp_port = self.esp8266_port.get()
        
        self.log(f"Connecting to ESP8266 at {esp_ip}:{esp_port}...")
        self.connect_btn.config(text="Disconnect")
        
        # Create socket and connect
        try:
            self.esp8266_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.esp8266_socket.settimeout(5)  # 5 second timeout
            self.esp8266_socket.connect((esp_ip, esp_port))
            
            self.connected = True
            self.attempting_reconnection = False
            self.log(f"Connected to ESP8266 at {esp_ip}:{esp_port}")
            
            # Start receive thread
            rx_thread = Thread(target=self.receive_esp8266_messages, daemon=True)
            rx_thread.start()
            self.active_threads.append(rx_thread)
            
        except Exception as e:
            self.log(f"Connection error: {e}")
            # Start reconnection thread if not already attempting
            if not self.attempting_reconnection:
                self.attempting_reconnection = True
                recon_thread = Thread(target=self.reconnection_loop, daemon=True)
                recon_thread.start()
                self.active_threads.append(recon_thread)
    
    def reconnection_loop(self):
        """Loop to attempt reconnection every second"""
        while self.running and self.attempting_reconnection:
            try:
                # Close any existing socket
                if self.esp8266_socket:
                    try:
                        self.esp8266_socket.close()
                    except:
                        pass
                
                esp_ip = self.esp8266_ip.get()
                esp_port = self.esp8266_port.get()
                
                # self.log(f"Attempting to reconnect to ESP8266 at {esp_ip}:{esp_port}...")
                
                # Create new socket and connect
                self.esp8266_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.esp8266_socket.settimeout(5)
                self.esp8266_socket.connect((esp_ip, esp_port))
                
                self.connected = True
                self.attempting_reconnection = False
                # self.log(f"Successfully reconnected to ESP8266 at {esp_ip}:{esp_port}")
                
                # Start receive thread
                rx_thread = Thread(target=self.receive_esp8266_messages, daemon=True)
                rx_thread.start()
                self.active_threads.append(rx_thread)
                
                # Exit reconnection loop
                break
                
            except Exception as e:
                self.log(f"Reconnection attempt failed: {e}")
                time.sleep(1)
    
    def receive_esp8266_messages(self):
        """Thread function to receive messages from ESP8266"""
        while self.running and self.connected:
            try:
                data = self.esp8266_socket.recv(1024).decode().strip()
                if data:
                    self.log(f"ESP8266: {data}")
                elif data == '':  # Connection closed by remote host
                    # self.log("Connection closed by ESP8266")
                    self.connected = False
                    
                    # Start reconnection attempts
                    if not self.attempting_reconnection:
                        self.attempting_reconnection = True
                        recon_thread = Thread(target=self.reconnection_loop, daemon=True)
                        recon_thread.start()
                        self.active_threads.append(recon_thread)
                    break
            except socket.timeout:
                continue
            except Exception as e:
                self.log(f"Receive error: {e}")
                self.connected = False
                
                # Start reconnection attempts
                if not self.attempting_reconnection:
                    self.attempting_reconnection = True
                    recon_thread = Thread(target=self.reconnection_loop, daemon=True)
                    recon_thread.start()
                    self.active_threads.append(recon_thread)
                break
    
    def send_command(self):
        """Send command to ESP8266"""
        if not self.connected:
            self.log("Not connected to ESP8266")
            return
            
        msg = self.command_entry.get()
        if msg.strip():
            try:
                self.esp8266_socket.sendall((msg + "\n").encode())
                self.log(f"Sent: {msg}")
                self.command_entry.delete(0, tk.END)
            except Exception as e:
                self.log(f"Send error: {e}")
                self.connected = False
                
                # Start reconnection if not already attempting
                if not self.attempting_reconnection:
                    self.attempting_reconnection = True
                    recon_thread = Thread(target=self.reconnection_loop, daemon=True)
                    recon_thread.start()
                    self.active_threads.append(recon_thread)
    
    def send_gesture_command(self, command):
        """Send command based on gesture"""
        if not self.connected or not self.gesture_enabled.get():
            return
            
        try:
            self.esp8266_socket.sendall((command + "\n").encode())
            self.log(f"Gesture command: {command}")
        except Exception as e:
            self.log(f"Gesture command error: {e}")
            self.connected = False
            
            # Start reconnection if not already attempting
            if not self.attempting_reconnection:
                self.attempting_reconnection = True
                recon_thread = Thread(target=self.reconnection_loop, daemon=True)
                recon_thread.start()
                self.active_threads.append(recon_thread)
    
    def detect_hands(self, image):
        """Detect hands in the image using MediaPipe"""
        results = self.hands.process(image)
        return results
    
    def detect_finger_status(self, hand_landmarks, handedness_info):
        """Detect which fingers are raised, thumb direction, and palm orientation"""
        landmarks = np.array([[l.x, l.y, l.z] for l in hand_landmarks.landmark])
        
        # Get wrist position
        wrist = landmarks[0]
        
        # Determine handedness (left or right hand)
        is_right_hand = handedness_info[0].classification[0].label == "Right"
        
        # Calculate palm orientation
        # We'll use the normal vector to determine if palm is facing the camera
        # Points on the palm: wrist (0), index MCP (5), pinky MCP (17)
        wrist_pos = landmarks[0]
        index_pos = landmarks[5]
        pinky_pos = landmarks[17]
        
        # Vectors to form a plane
        v1 = index_pos - wrist_pos
        v2 = pinky_pos - wrist_pos
        
        # Cross product gives normal vector to palm
        normal = np.cross(v1[:2], v2[:2])  # Only use x,y coordinates
        
        # The z value of the normal tells us if palm is facing camera or away
        # For MediaPipe, +z is toward the camera
        # The sign depends on whether it's the right or left hand due to cross product direction
        palm_facing_camera = normal > 0 if is_right_hand else normal < 0
        
        # Dictionary to hold finger status
        finger_status = {
            "Thumb": False,
            "Index": False,
            "Middle": False,
            "Ring": False,
            "Pinky": False
        }
        
        # List of finger names for easier referencing
        fingers = ["Thumb", "Index", "Middle", "Ring", "Pinky"]
        
        # Finger tips and base joints
        finger_tips = [4, 8, 12, 16, 20]
        finger_bases = [2, 5, 9, 13, 17]
        
        # Check which fingers are raised
        for i, (name, tip_idx, base_idx) in enumerate(zip(fingers, finger_tips, finger_bases)):
            fingertip = landmarks[tip_idx]
            base = landmarks[base_idx]
            
            # Special logic for thumb
            if i == 0:
                # For thumb, check if the tip is extended away from palm
                thumb_mcp = landmarks[2]  # Thumb MCP joint
                thumb_tip = landmarks[4]  # Thumb tip
                
                # Vector from MCP to tip
                mcp_to_tip = thumb_tip - thumb_mcp
                
                # Length of thumb when extended
                thumb_length = np.linalg.norm(mcp_to_tip)
                
                # Consider thumb raised if extended enough
                finger_status["Thumb"] = thumb_length > 0.08
            else:
                # For other fingers, check if they're extended
                # Get PIP joint (middle joint of finger)
                pip = landmarks[tip_idx - 2]
                
                # Check if fingertip is higher than PIP joint (y-coordinate is lower in image space)
                finger_status[name] = fingertip[1] < pip[1]
        
        # Determine thumb direction (only if thumb is raised)
        thumb_direction = "none"
        if finger_status["Thumb"]:
            thumb_tip = landmarks[4]
            thumb_base = landmarks[2]  # Using MCP as base
            thumb_vector = thumb_tip - thumb_base
            
            # Determine dominant direction
            x, y, z = thumb_vector
            x, y, z = thumb_vector
            if palm_facing_camera: 
                 if abs(x) > abs(y) and abs(x) > abs(z):
                    thumb_direction = "down" if x > 0 else "left"
                 elif abs(y) > abs(x) and abs(y) > abs(z):
                    thumb_direction = "down" if y > 0 else "up"
                 else:
                    thumb_direction = "none"
            else :
                if abs(x) > abs(y) and abs(x) > abs(z):
                    thumb_direction = "right" if x > 0 else "left"
                elif abs(y) > abs(x) and abs(y) > abs(z):
                    thumb_direction = "down" if y > 0 else "up"
                else:
                    thumb_direction = "none" 
        # Get list of raised fingers
        raised_fingers = [name for name, is_raised in finger_status.items() if is_raised]
        
        return {
            "raised_fingers": raised_fingers,
            "raised_count": len(raised_fingers),
            "thumb_direction": thumb_direction,
            "palm_facing_camera": palm_facing_camera,
            "is_right_hand": is_right_hand
        }
    
    def process_gesture(self, finger_info):
        """Process gesture to determine command based on thumb direction, palm orientation, and raised finger count"""
        if not self.gesture_enabled.get():
            return

        # Get thumb direction and palm orientation
        thumb_direction = finger_info['thumb_direction']
        palm_facing_camera = finger_info['palm_facing_camera']

        # Count raised fingers excluding thumb
        non_thumb_fingers = [f for f in finger_info['raised_fingers'] if f != "Thumb"]
        non_thumb_count = len(non_thumb_fingers)
        word_command = f"{thumb_direction}_{non_thumb_count}"

        # Mapping logic
        
        if non_thumb_count == 0 :
            command="0" #stop
        elif thumb_direction == "up":
            command = str(non_thumb_count)
        elif thumb_direction == "down":
            command = str(non_thumb_count + 4)
        elif thumb_direction == "right":  # When palm faces away, right means actual right
            command = format(non_thumb_count + 8, 'x')  # 9, a, b, c
        elif thumb_direction == "left":
            command = format(non_thumb_count + 12, 'x')  # d, e, f, 
            if command == '10' :
                command = 'g'
        else:
            command = "0"  # Default stop

        # Send the command to ESP8266
        self.send_gesture_command(command)

        # Only log if this is a new word_command
        if getattr(self, 'last_word_command', None) != word_command:
            self.last_word_command = word_command
            if thumb_direction == "none":
                self.log(f"Last command sent: Stop")
            else:
                self.log(f"Last command sent: {word_command}")

    def process_frames(self):
        """Process frames from active queue"""
        last_time = time.time()
        last_gesture_time = 0
        gesture_cooldown = 0.5  # 0.5 second cooldown between gestures
        
        while self.running:
            try:
                # Get frame from appropriate queue
                frame = None
                if self.camera_source.get() == 0 and not self.webcam_queue.empty():
                    frame = self.webcam_queue.get()
                elif self.camera_source.get() == 1 and not self.esp32cam_queue.empty():
                    frame = self.esp32cam_queue.get()
                
                if frame is not None:
                    # Calculate FPS
                    current_time = time.time()
                    fps = 1 / (current_time - last_time) if (current_time - last_time) > 0 else 0
                    last_time = current_time
                    
                    # Process the frame
                    display_frame = frame.copy()                    
                    
                    # Hand detection
                    results = self.detect_hands(frame)
                    
                    # If hands are detected
                    if results.multi_hand_landmarks and results.multi_handedness:
                        for i, (hand_landmarks, handedness) in enumerate(zip(results.multi_hand_landmarks, results.multi_handedness)):
                            # Draw hand landmarks
                            self.mp_drawing.draw_landmarks(
                                display_frame,
                                hand_landmarks,
                                self.mp_hands.HAND_CONNECTIONS,
                                self.mp_drawing_styles.get_default_hand_landmarks_style(),
                                self.mp_drawing_styles.get_default_hand_connections_style()
                            )
                            
                            # Get finger status with palm orientation
                            finger_info = self.detect_finger_status(hand_landmarks, results.multi_handedness)
                            
                            # Display finger information
                            y_pos = 60
                            
                            # Show raised fingers
                            raised = ", ".join(finger_info['raised_fingers']) if finger_info['raised_fingers'] else "None"
                            cv2.putText(display_frame, f"Raised fingers: {raised}", 
                                        (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
                            y_pos += 30
                            
                            # Show number of raised fingers
                            cv2.putText(display_frame, f"Raised count: {finger_info['raised_count']}", 
                                        (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
                            y_pos += 30
                            
                            # Show palm orientation
                            orientation = "Facing camera" if finger_info['palm_facing_camera'] else "Facing away"
                            cv2.putText(display_frame, f"Palm: {orientation}", 
                                        (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
                            y_pos += 30
                            
                            # Show hand type
                            hand_type = "Right hand" if finger_info['is_right_hand'] else "Left hand"
                            cv2.putText(display_frame, f"Hand: {hand_type}", 
                                        (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
                            y_pos += 30
                            
                            # Show thumb direction if thumb is raised
                            if "Thumb" in finger_info['raised_fingers']:
                                thumb_text = f"Thumb direction: {finger_info['thumb_direction']}"
                                cv2.putText(display_frame, thumb_text, 
                                            (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
                            
                            # Process gesture with cooldown
                            if current_time - last_gesture_time > gesture_cooldown:
                                self.process_gesture(finger_info)
                                last_gesture_time = current_time
                    else:
                        # No hands detected
                        cv2.putText(display_frame, "No hand detected", (10, 60), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
                    
                    # Add connection status
                    status_text = "Connected" if self.connected else "Disconnected"
                    if self.attempting_reconnection:
                        status_text = "Reconnecting..."
                    
                    cv2.putText(display_frame, f"ESP8266: {status_text}", 
                                (10, display_frame.shape[0] - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, 
                                (0, 255, 0) if self.connected else (0, 0, 255), 2)
                    
                    # Show FPS
                    cv2.putText(display_frame, f"FPS: {fps:.1f}", 
                                (display_frame.shape[1] - 120, display_frame.shape[0] - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    
                    # Convert to RGB for tkinter
                    rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                    img = tk.PhotoImage(data=cv2.imencode('.ppm', rgb_frame)[1].tobytes())
                    
                    # Update canvas
                    self.canvas.config(width=rgb_frame.shape[1], height=rgb_frame.shape[0])
                    self.canvas.create_image(0, 0, image=img, anchor=tk.NW)
                    self.canvas.image = img  # Keep reference
                
                # Brief delay to reduce CPU usage
                time.sleep(0.01)
                
            except Exception as e:
                print(f"Process error: {e}")
                time.sleep(0.1)
    
    def on_close(self):
        """Handle window close event"""
        self.running = False
        
        # Stop reconnection attempts
        self.attempting_reconnection = False
        
        # Close sockets
        if self.esp8266_socket:
            try:
                self.esp8266_socket.close()
            except:
                pass
        
        # Wait for threads to finish
        for thread in self.active_threads:
            if thread.is_alive():
                thread.join(timeout=1.0)
        
        self.root.destroy()

def main():
    root = tk.Tk()
    app = ESP32CamGestureController(root)
    root.mainloop()

if __name__ == "__main__":
    main()