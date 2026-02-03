import sys
import socket
import threading
import base64
import cv2
import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, 
                             QPushButton, QVBoxLayout, QHBoxLayout, QFrame, 
                             QGraphicsDropShadowEffect, QMessageBox)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QImage, QPixmap, QColor, QFont

HOST = '127.0.0.1'
PORT = 65432

# --- WORKER THREAD ---
class BackendListener(QObject):
    # Signal: EAR, SessionTime, EyeStatus, Blinks, TimerSec, StatusText, Image
    data_received = pyqtSignal(str, str, str, str, str, str,str, QImage)
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.running = True
        self.client = None

    def run(self):
        while self.running:
            try:
                self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client.connect((HOST, PORT))
                file_obj = self.client.makefile('r')

                for line in file_obj:
                    if not self.running: break
                    try:
                        parts = line.strip().split('|')
                        if len(parts) < 8: continue

                        ear = parts[0]
                        sess_time = parts[1]
                        eye_stat = parts[2]
                        blinks = parts[3]
                        timer_c1 = parts[4]
                        timer_c2 = parts[5]
                        main_stat = parts[6]
                        img_b64 = parts[7]

                        # Decode Image
                        img_bytes = base64.b64decode(img_b64)
                        nparr = np.frombuffer(img_bytes, np.uint8)
                        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        h, w, ch = frame.shape
                        bytes_per_line = ch * w
                        qt_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)

                        self.data_received.emit(ear, sess_time, eye_stat, blinks, timer_c1,timer_c2, main_stat, qt_img)
                    except Exception as e:
                        print("Parse Error:", e)
            except Exception as e:
                # Only retry if we are supposed to be running
                if self.running:
                    QTimer.singleShot(1000, self.run)
                break
        self.finished.emit()

    def stop(self):
        self.running = False
        # FORCE CLOSE THE CONNECTION
        if self.client:
            try:
                self.client.close()
            except:
                pass

# --- CUSTOM UI COMPONENTS ---
class ModernToggle(QPushButton):
    def __init__(self):
        super().__init__()
        self.setCheckable(True)
        self.setFixedSize(80, 34)
        self.setChecked(True) # Default ON
        self.setText("ON")
        self.setStyleSheet("""
            QPushButton {
                background-color: #333333; 
                color: #888;
                border-radius: 17px;
                font-weight: bold;
                font-family: 'Segoe UI';
            }
            QPushButton:checked {
                background-color: #2F80ED;
                color: white;
            }
        """)

class EyraUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EYRA")
        self.setFixedSize(400, 650) # Matches screenshot ratio
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Main Background
        self.central_widget = QWidget()
        self.central_widget.setStyleSheet("""
            QWidget#MainFrame {
                background-color: #0b0e14; 
                border-radius: 20px; 
                border: 1px solid #1c2333;
            }
            QLabel {
                font-family: 'Segoe UI';
                color: #b0b3b8;
                font-size: 14px;
            }
        """)
        self.central_widget.setObjectName("MainFrame")
        self.setCentralWidget(self.central_widget)
        
        layout = QVBoxLayout(self.central_widget)
        layout.setContentsMargins(20, 20, 20, 20)

        # 1. TITLE BAR
        header = QHBoxLayout()
        logo_label = QLabel()
        # Make sure "logo.png" is in your folder, or provide full path
        logo_pixmap = QPixmap("logoimages/logo2.png") 
        
        # Scale it to fit nicely (e.g., 25x25 pixels)
        if not logo_pixmap.isNull():
            logo_label.setPixmap(logo_pixmap.scaled(25, 25, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            logo_label.setText("👁️") # Fallback emoji if image fails
            
        header.addWidget(logo_label) # Add the logo FIRST

        title = QLabel("EYRA")
        title.setStyleSheet("color: #6c8ebf; font-size: 18px; font-weight: 600; letter-spacing: 1px;")
        
        btns = QHBoxLayout()
        btn_min = QPushButton("—")
        btn_close = QPushButton("✕")
        for b in [btn_min, btn_close]:
            b.setFixedSize(30, 30)
            b.setStyleSheet("background:none; border:none; color: #888; font-size:14px;")
        btn_close.clicked.connect(self.close)
        btn_min.clicked.connect(self.showMinimized)

        btns.addWidget(btn_min)    # <--- DID YOU MISS THIS?
        btns.addWidget(btn_close)  # <--- DID YOU MISS THIS?
        
        header.addWidget(title)
        header.addStretch()
        header.addLayout(btns)
        layout.addLayout(header)

        # 2. CAMERA CONTAINER (The Blue Glow Box)
        self.cam_frame = QLabel("Camera Screen")
        self.cam_frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cam_frame.setFixedSize(360, 220)
        self.cam_frame.setStyleSheet("""
            background-color: #090b10;
            border-radius: 15px;
            border: 2px solid #1a253a;
            color: #444;
        """)
        # Outer Glow Effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(47, 128, 237, 60)) # Blue Glow
        self.cam_frame.setGraphicsEffect(shadow)
        
        cam_container = QVBoxLayout()
        cam_container.setContentsMargins(0, 10, 0, 10)
        cam_container.addWidget(self.cam_frame)
        layout.addLayout(cam_container)

        # 3. TOGGLE ROW
        toggle_row = QHBoxLayout()
        toggle_label = QLabel("Background Access & Camera")
        toggle_label.setStyleSheet("color: #888; font-size: 13px;")
        
        self.toggle = ModernToggle()

        self.toggle.toggled.connect(self.toggle_camera)
        
        toggle_row.addWidget(toggle_label)
        toggle_row.addStretch()
        toggle_row.addWidget(self.toggle)
        layout.addLayout(toggle_row)
        
        layout.addSpacing(10)

        # 4. STATS CONTAINER
        self.stats_box = QFrame()
        self.stats_box.setStyleSheet("""
            QFrame {
                background-color: #11161f;
                border-radius: 15px;
                border: 1px solid #1f293a;
            }
        """)
        stats_layout = QVBoxLayout(self.stats_box)
        stats_layout.setSpacing(12)
        stats_layout.setContentsMargins(20, 20, 20, 20)

        # Helper to create rows
        def create_row(icon, text, value_id):
            row = QHBoxLayout()
            lbl_icon = QLabel(icon)
            lbl_icon.setFixedWidth(25)
            lbl_icon.setStyleSheet("color: #888; font-size: 16px;")
            
            lbl_text = QLabel(text)
            lbl_val = QLabel("Waiting...")
            lbl_val.setObjectName(value_id)
            lbl_val.setStyleSheet("color: #E0E0E0; font-weight: 500;")
            
            row.addWidget(lbl_icon)
            row.addWidget(lbl_text)
            row.addStretch()
            row.addWidget(lbl_val)
            return row, lbl_val

        # Row 1: Session Time
        r1, self.lbl_session = create_row("🕒", "Time Since Screen On:", "session")
        stats_layout.addLayout(r1)

        # Row 2: EAR
        r2, self.lbl_ear = create_row("📉", "EAR:", "ear")
        stats_layout.addLayout(r2)

        # Row 3: Eye Status
        r3, self.lbl_eye = create_row("👁️", "Eye Status:", "eye")
        stats_layout.addLayout(r3)

        # Row 4: Blink Count
        r4, self.lbl_blinks = create_row("⚡", "Blink Count:", "blinks")
        stats_layout.addLayout(r4)

        # Row 5a: Timer C1 (Staring)
        r5a, self.lbl_timer_c1 = create_row("⏱️", "Timer (Staring):", "timer_c1")
        stats_layout.addLayout(r5a)

        # Row 5b: Timer C2 (Strain)
        r5b, self.lbl_timer_c2 = create_row("⏳", "Timer (Strain):", "timer_c2")
        stats_layout.addLayout(r5b)
        
        # Row 6: Main Status
        r6, self.lbl_main_stat = create_row("🧠", "Eyes Status:", "main")
        self.lbl_main_stat.setStyleSheet("color: #2F80ED; font-weight: bold;") # Blue default
        stats_layout.addLayout(r6)

        layout.addWidget(self.stats_box)
        layout.addStretch()

        # Logo/Footer
        footer = QLabel("") # Placeholder logo
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("font-family: 'Times New Roman'; font-style: italic; font-size: 24px; color: #2F80ED;")
        layout.addWidget(footer)

        # --- PART 2: START 20-MINUTE TIMER ---
        self.break_timer = QTimer(self)
        self.break_timer.timeout.connect(self.show_break_popup)
        # 20 minutes = 1,200,000 milliseconds
        self.break_timer.start(1200000)

        # Drag Logic
        self.oldPos = None

        # Start Thread

        # --- PART 3: THE CHAINED POPUP LOGIC ---
    def show_break_popup(self):
        # 1. Pause the timer
        self.break_timer.stop()
        
        # --- POPUP 1: TIME ALERT ---
        msg1 = QMessageBox(self)
        # msg1.setWindowTitle("Time Alert")
        msg1.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        msg1.setText("You have been using the screen for 20 minutes!")
        msg1.setIcon(QMessageBox.Icon.Warning)
        msg1.setStyleSheet("background-color: #1a1d24; color: #FF4B4B; font-size: 14px;")
        msg1.exec() # Pauses here until user clicks OK
        
        # --- POPUP 2: EXERCISE INSTRUCTION ---
        msg2 = QMessageBox(self)
        # msg2.setWindowTitle("20-20-20 Rule")
        msg2.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        msg2.setText("Exercise Time!")
        msg2.setInformativeText("Look at something 20 feet away for 20 seconds.\n\nRelax your eyes.")
        msg2.setIcon(QMessageBox.Icon.Information)
        
        # Custom Button logic
        btn_done = msg2.addButton("I did it!", QMessageBox.ButtonRole.AcceptRole)
        msg2.setDefaultButton(btn_done)
        
        msg2.setStyleSheet("background-color: #1a1d24; color: #E0E0E0; font-size: 14px;")
        msg2.exec() # Pauses here until user clicks "I did it!"
        
        # 3. Restart timer for the next 20 minutes
        self.break_timer.start(1200000)

    def toggle_camera(self, checked):
        if checked:
            # Turning ON
            self.toggle.setText("ON")
            # CHANGED: 'thread' -> 'worker_thread'
            if not hasattr(self, 'worker_thread') or not self.worker_thread.is_alive():
                self.start_worker()
        else:
            # Turning OFF
            self.toggle.setText("OFF")
            if hasattr(self, 'listener'):
                self.listener.stop() # Kill connection
            
            # Clear UI
            self.cam_frame.setText("Camera Paused")
            self.cam_frame.setPixmap(QPixmap())
            self.lbl_main_stat.setText("Monitoring Paused")
            self.lbl_main_stat.setStyleSheet("color: #888; font-weight: normal;")


    def start_worker(self):
        # CHANGED ALL 3 LINES: 'thread' -> 'worker_thread'
        self.worker_thread = threading.Thread(target=self.run_listener)
        self.worker_thread.daemon = True
        self.worker_thread.start()

    def run_listener(self):
        self.listener = BackendListener()
        self.listener.data_received.connect(self.update_data)
        self.listener.run()

    def update_data(self, ear, sess, eye_stat, blinks, timer_c1, timer_c2, main_stat, qt_img):
        # Update Image
        self.cam_frame.setPixmap(QPixmap.fromImage(qt_img).scaled(360, 220, Qt.AspectRatioMode.KeepAspectRatioByExpanding))
        
        # Update Labels
        self.lbl_session.setText(sess)
        self.lbl_ear.setText(ear)
        self.lbl_eye.setText(eye_stat)
        self.lbl_blinks.setText(blinks)
        self.lbl_timer_c1.setText(f"{timer_c1}s (Resets > 10s)")
        self.lbl_timer_c2.setText(f"{timer_c2}s (Resets > 10s)")
        self.lbl_main_stat.setText(main_stat)
        
        # Color Logic (Updated for new text format)
        # Check for [ALERT] tag or "Strain" keyword
        if "[ALERT]" in main_stat or "Strain" in main_stat:
            self.lbl_main_stat.setStyleSheet("color: #FF4B4B; font-weight: bold;") # Red
        else:
            self.lbl_main_stat.setStyleSheet("color: #2F80ED; font-weight: bold;") # Blue

    # Drag Window Code
    def mousePressEvent(self, event):
        self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.oldPos:
            delta = event.globalPosition().toPoint() - self.oldPos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPosition().toPoint()

# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#     window = EyraUI()
#     window.show()
#     sys.exit(app.exec())

# --- WRAP THE MAIN EXECUTION IN A FUNCTION ---
def start_frontend():
    app = QApplication(sys.argv)
    window = EyraUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    start_frontend()