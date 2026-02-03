import cv2
import mediapipe as mp
import numpy as np
import time
import pygame
import socket
import base64
import threading

# --- CONNECTION SETTINGS ---
HOST = '127.0.0.1'
PORT = 65432

def calculate_EAR(eye_points, landmarks, frame_width, frame_height):
    def get_point(idx):
        x = int(landmarks[idx].x * frame_width)
        y = int(landmarks[idx].y * frame_height)
        return np.array([x, y])

    p1 = get_point(eye_points[0])
    p2 = get_point(eye_points[1])
    p3 = get_point(eye_points[2])
    p4 = get_point(eye_points[3])
    p5 = get_point(eye_points[4])
    p6 = get_point(eye_points[5])

    vertical1 = np.linalg.norm(p2 - p6)
    vertical2 = np.linalg.norm(p3 - p5)
    horizontal = np.linalg.norm(p1 - p4)
    return (vertical1 + vertical2) / (2.0 * horizontal)

# --- NEW: Run Audio in Background to prevent Freezing ---
def play_sound(file_path):
    def _play():
        try:
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
        except Exception:
            pass # Ignore if file missing
    threading.Thread(target=_play, daemon=True).start()

def start_backend():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # ---------
    try:
        server.bind((HOST, PORT))
    except OSError:
        print(f"Error: Port {PORT} is busy. Close other Python windows.")
        return
    server.listen(1)
    
    mp_face_mesh = mp.solutions.face_mesh
    pygame.mixer.init()

    print(f"Backend listening on {HOST}:{PORT}...")

    while True: # Main Reconnection Loop
        print("Waiting for UI to connect...")
        conn, addr = server.accept()
        print(f"UI Connected: {addr}")

        cap = cv2.VideoCapture(0)
        
        # Variables
        blink_counter_C1 = 0 
        blink_counter_C2 = 0 
        frame_counter = 0 
        blink_detected_C1 = False 
        blink_detected_C2 = False 
        time_start_C1 = time.time()
        time_start_C2 = time.time()
        session_start_time = time.time()
        total_blinks_session = 0

        with mp_face_mesh.FaceMesh(max_num_faces=1, refine_landmarks=True, min_detection_confidence=0.5) as face_mesh:
            while True:
                try:
                    ret, frame = cap.read()
                    if not ret: break
                    
                    frame = cv2.flip(frame, 1)
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    results = face_mesh.process(rgb_frame)
                    
                    avg_EAR = 0.0
                    eye_status_text = "Open"
                    status_text = "Relaxed"
                    timer_display = 0

                    if results.multi_face_landmarks:
                        for face_landmarks in results.multi_face_landmarks:
                            h, w, _ = frame.shape
                            left_idx = [362, 385, 387, 263, 373, 380]
                            right_idx = [33, 160, 158, 133, 153, 144]

                            # Visuals
                            left_pts = np.array([[int(face_landmarks.landmark[i].x * w), int(face_landmarks.landmark[i].y * h)] for i in left_idx], np.int32)
                            right_pts = np.array([[int(face_landmarks.landmark[i].x * w), int(face_landmarks.landmark[i].y * h)] for i in right_idx], np.int32)
                            cv2.polylines(frame, [left_pts], True, (0, 255, 0), 1)
                            cv2.polylines(frame, [right_pts], True, (0, 255, 0), 1)

                            # EAR
                            left_ear = calculate_EAR(left_idx, face_landmarks.landmark, w, h)
                            right_ear = calculate_EAR(right_idx, face_landmarks.landmark, w, h)
                            avg_EAR = (left_ear + right_ear) / 2.0

                            # Logic
                            EAR_OPEN = 0.25
                            EAR_PARTIAL = 0.20

                            if avg_EAR < EAR_PARTIAL:
                                eye_status_text = "Closed (Blink)"
                            elif avg_EAR < EAR_OPEN:
                                eye_status_text = "Partially Closed"
                            else:
                                eye_status_text = "Open"

                            if avg_EAR < EAR_PARTIAL:
                                frame_counter += 1
                                if frame_counter >= 3:
                                    if not blink_detected_C1: 
                                        blink_counter_C1 += 1
                                        total_blinks_session += 1
                                        blink_detected_C1 = True
                                    if not blink_detected_C2:
                                        blink_counter_C2 += 1
                                        blink_detected_C2 = True
                            else:
                                frame_counter = 0
                                blink_detected_C1 = False
                                blink_detected_C2 = False

                            now = time.time()
                            timeperiod_C1 = now - time_start_C1
                            timeperiod_C2 = now - time_start_C2
                            
                            timer_display = int(timeperiod_C1)

                            # ALERTS (Using play_sound helper)
                            if blink_counter_C1 <= 1 and timeperiod_C1 >= 10:
                                status_text = "[ALERT] Staring! Blink Now"
                                play_sound("audios/no_blink.mp3")
                                blink_counter_C1 = 0
                                time_start_C1 = now
                            elif blink_counter_C1 >= 2 and timeperiod_C1 >= 10:
                                blink_counter_C1 = 0
                                time_start_C1 = now

                            if blink_counter_C2 > 6 and timeperiod_C2 <= 10:
                                status_text = "[ALERT] High Strain! Break!"
                                play_sound("audios/high_blink_rate.mp3")
                                blink_counter_C2 = 0
                                time_start_C2 = now
                            elif blink_counter_C2 >= 7 and timeperiod_C2 >= 10:
                                blink_counter_C2 = 0
                                time_start_C2 = now

                    # PREPARE PACKET
                    sess_seconds = int(time.time() - session_start_time)
                    h = sess_seconds // 3600
                    m = (sess_seconds % 3600) // 60
                    s = sess_seconds % 60
                    session_str = f"{h:02}:{m:02}:{s:02}"

                    small_frame = cv2.resize(frame, (340, 220))
                    _, buffer = cv2.imencode('.jpg', small_frame)
                    img_str = base64.b64encode(buffer).decode('utf-8')

                    # Send Data (No Emojis to prevent crashes)
                    packet = f"{avg_EAR:.2f}|{session_str}|{eye_status_text}|{total_blinks_session}|{int(timeperiod_C1)}|{int(timeperiod_C2)}|{status_text}|{img_str}\n"

                    conn.sendall(packet.encode('utf-8'))
                    time.sleep(0.03)

                except ConnectionResetError:
                    print("UI Disconnected. Waiting for reconnection...")
                    break # Break inner loop to go back to server.accept()
                except Exception as e:
                    print(f"Error in loop: {e}")
                    break

        cap.release()
        conn.close()

if __name__ == "__main__":
    start_backend()