"""
Tello Drone BCI Controller – PyQt6 Dashboard
Flow: BCI Setup -> Test Controls -> Drone Setup -> Flight Dashboard
"""

import sys
import os
import time
import threading
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox, QGroupBox, QComboBox,
    QProgressBar, QScrollArea, QPlainTextEdit, QSlider, QStackedWidget,
    QSizePolicy, QGridLayout, QTabWidget, QDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QObject, QRectF
from PyQt6.QtGui import QImage, QPixmap, QColor, QPalette, QPainter, QPen, QBrush
import math
from config_manager import ConfigManager
from app_paths import resource_path
import i18n
from i18n import t, bind

class EmittingStream(QObject):
    textWritten = pyqtSignal(str)
    def write(self, text):
        if text.strip():
            self.textWritten.emit(str(text))
    def flush(self):
        pass

STYLESHEET = """
QMainWindow { background-color: #0d1117; }
QWidget { color: #e6edf3; font-family: 'Inter', sans-serif; }
QGroupBox {
    border: 1px solid #30363d; border-radius: 8px;
    margin-top: 12px; padding: 14px 10px 10px 10px;
    background-color: #161b22; font-weight: bold; font-size: 13px;
}
QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 6px; color: #58a6ff; }
QLineEdit, QComboBox {
    background-color: #0d1117; border: 1px solid #30363d; border-radius: 6px;
    padding: 8px 12px; color: #e6edf3; font-size: 14px;
}
QLineEdit:focus, QComboBox:focus { border-color: #58a6ff; }
QPushButton {
    border: none; border-radius: 6px; padding: 10px 20px;
    font-weight: bold; font-size: 14px; color: white; background-color: #21262d; border: 1px solid #30363d;
}
QPushButton:hover { background-color: #30363d; }
QPushButton:disabled { background-color: #161b22; color: #8b949e; border-color: #21262d; }
QPushButton#primaryBtn { background-color: #238636; border: none; }
QPushButton#primaryBtn:hover { background-color: #2ea043; }
QPushButton#primaryBtn:disabled { background-color: #1a4220; color: #8b949e; }
QPushButton#dangerBtn { background-color: #da3633; border: none; }
QPushButton#dangerBtn:hover { background-color: #f85149; }
QPushButton#blueBtn { background-color: #1f6feb; border: none; }
QPushButton#blueBtn:hover { background-color: #388bfd; }
QCheckBox { spacing: 8px; font-size: 14px; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border: 1px solid #30363d; background: #0d1117; }
QCheckBox::indicator:checked { background-color: #58a6ff; border-color: #58a6ff; }
QSlider::groove:horizontal { height: 6px; background: #30363d; border-radius: 3px; }
QSlider::handle:horizontal { width: 16px; height: 16px; margin: -5px 0; background: #58a6ff; border-radius: 8px; }
QPlainTextEdit {
    background-color: #010409; color: #3fb950; border: 1px solid #30363d;
    border-radius: 6px; font-family: monospace; font-size: 12px;
}
QLabel#titleLabel { font-size: 24px; font-weight: bold; color: #ffffff; }
QLabel#subtitleLabel { font-size: 14px; color: #8b949e; }
QLabel#statusBadge {
    background-color: #1a1e24; border: 1px solid #30363d; border-radius: 12px;
    padding: 6px 16px; font-size: 14px; font-weight: bold;
}
QProgressBar { border: 1px solid #30363d; border-radius: 4px; background-color: #0d1117; text-align: center; color: white; }
QProgressBar::chunk { background-color: #58a6ff; border-radius: 3px; }
"""

class VideoThread(QThread):
    frame_ready = pyqtSignal(QImage)
    status_update = pyqtSignal(str)

    def __init__(self, tello=None):
        super().__init__()
        self.tello = tello
        self._running = False
        self._av_container = None  # Direct PyAV container for color-correct decoding

    def run(self):
        self._running = True
        if self.tello:
            try:
                self.tello.streamon()
                self.status_update.emit(t("log.camera_started"))
            except Exception as e:
                self.status_update.emit(t("log.camera_error", detail=e))
                return

            # Open a direct PyAV container so we control the YUV→RGB conversion
            # instead of relying on djitellopy's to_image() which ignores VUI metadata.
            try:
                import av as _av
                udp_addr = self.tello.get_udp_video_address()
                # Use low-delay flags to prevent FFmpeg from buffering frames
                opts = {"fflags": "nobuffer", "flags": "low_delay"}
                self._av_container = _av.open(udp_addr, timeout=(10, None), options=opts)
                self.status_update.emit(t("log.pyav_active"))
            except Exception as e:
                self._av_container = None
                self.status_update.emit(t("log.pyav_failed", detail=e))

        if self._av_container:
            self._run_pyav_decode()
        else:
            self._run_fallback_decode()

    def _run_pyav_decode(self):
        """Decode via PyAV with explicit BT.709 / limited-range color conversion."""
        import av as _av

        try:
            for frame in self._av_container.decode(video=0):
                if not self._running:
                    break

                # Use to_ndarray with explicit format to force correct colorspace.
                # The Tello H.264 stream uses YUV420p; we convert to RGB24 here.
                # PyAV's reformatter applies the correct color matrix when we
                # set src_color_range and dst_color_range on the frame.
                frame.colorspace = _av.video.reformatter.Colorspace.ITU709
                rgb_frame = frame.to_ndarray(format='rgb24')

                h, w, ch = rgb_frame.shape
                # Apply limited-range (16-235) → full-range (0-255) stretch
                # to fix crushed blacks and washed-out highlights
                rgb_frame = self._stretch_limited_to_full(rgb_frame)
                img = QImage(rgb_frame.data, w, h, ch * w, QImage.Format.Format_RGB888)
                self.frame_ready.emit(img)
                
                # NOTE: No time.sleep() here! This is an iterator over a live stream.
                # Sleeping here causes the decode buffer to back up, creating massive lag.
                
        except Exception as e:
            print(f"[VideoThread] PyAV decode error, switching to fallback: {e}")
            self._av_container = None
            self._run_fallback_decode()

    def _run_fallback_decode(self):
        """Fallback: use djitellopy's built-in frame reader (to_image → RGB already)."""
        while self._running:
            if self.tello:
                try:
                    frame = self.tello.get_frame_read().frame
                    if frame is not None:
                        # djitellopy's to_image() already returns RGB via PIL,
                        # so do NOT apply cv2.cvtColor(BGR2RGB) — that swaps R↔B.
                        h, w, ch = frame.shape
                        img = QImage(frame.data, w, h, ch * w, QImage.Format.Format_RGB888)
                        self.frame_ready.emit(img)
                except Exception:
                    pass
            else:
                frame = self._generate_sim_frame()
                h, w, ch = frame.shape
                img = QImage(frame.data, w, h, ch * w, QImage.Format.Format_RGB888)
                self.frame_ready.emit(img)
            time.sleep(0.033)

    @staticmethod
    def _stretch_limited_to_full(frame: np.ndarray) -> np.ndarray:
        """Rescale pixel values from limited range (16-235) to full range (0-255).
        
        H.264 streams typically use 'tv' / limited range. If the decoder outputs
        values in limited range but the display expects full range, blacks look
        gray and colors appear washed out. This stretches the range correctly.
        """
        # (x - 16) * 255 / (235 - 16), clamped to [0, 255]
        f = frame.astype(np.float32)
        f = (f - 16.0) * (255.0 / 219.0)
        return np.clip(f, 0, 255).astype(np.uint8)

    def stop(self):
        self._running = False
        if self.tello:
            try:
                self.tello.streamoff()
            except Exception:
                pass

    def _generate_sim_frame(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:] = (13, 17, 23)
        for x in range(0, 640, 80): frame[:, x:x+1] = (48, 54, 61)
        for y in range(0, 480, 80): frame[y:y+1, :] = (48, 54, 61)
        cv2.line(frame, (300, 240), (340, 240), (88, 166, 255), 2)
        cv2.line(frame, (320, 220), (320, 260), (88, 166, 255), 2)
        cv2.circle(frame, (320, 240), 30, (88, 166, 255), 1)
        cv2.putText(frame, "SIMULATION MODE", (210, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (88, 166, 255), 2)
        return frame


class DroneSimulatorWidget(QWidget):
    def __init__(self, main_app=None, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        self.setMinimumSize(400, 300)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.drone_x = 0.0
        self.drone_y = 20.0
        self.drone_z = 0.0
        self.yaw = 0.0
        self.pitch = 0.0
        self.roll = 0.0
        
        self.score = 0
        self.coins = []
        self.coin_counter = 1
        self.spawn_coin()
        
        from PyQt6.QtGui import QPixmap
        self.bg_image = QPixmap(resource_path("bg.png"))

    def spawn_coin(self):
        import random
        rad = math.radians(self.yaw)
        dist = random.uniform(150, 400)
        offset = random.uniform(-120, 120)
        
        # Forward vector is (sin, -cos), Right vector is (cos, sin)
        cx = self.drone_x + math.sin(rad) * dist + math.cos(rad) * offset
        cz = self.drone_z - math.cos(rad) * dist + math.sin(rad) * offset
        cy = random.uniform(15, 80)
        
        self.coins.append([cx, cy, cz, random.uniform(0, 360), self.coin_counter])
        self.coin_counter += 1
        
    def update_rc(self, lr, fb, ud, yaw):
        speed_factor = 0.8
        rot_factor = 0.15
        
        self.yaw += yaw * rot_factor
        
        # Dynamic pitch and roll based on joystick inputs to make it look alive
        self.pitch = -fb * 0.3
        self.roll = -lr * 0.3
        
        rad = math.radians(self.yaw)
        # Tello fb forward is +Z in our local coords maybe? Let's say Z is backward, so -Z is forward
        dz = -fb * math.cos(rad) * speed_factor + lr * math.sin(rad) * speed_factor
        dx = fb * math.sin(rad) * speed_factor + lr * math.cos(rad) * speed_factor
        dy = ud * speed_factor
        
        self.drone_x += dx
        self.drone_y += dy
        self.drone_z += dz
        
        # Bounding box for altitude only (infinite X and Z!)
        self.drone_y = max(5, min(1000, self.drone_y))
        
        # Coin collection logic
        collected = []
        for coin in self.coins:
            cx, cy, cz, rot, num = coin
            dist = math.sqrt((self.drone_x - cx)**2 + (self.drone_y - cy)**2 + (self.drone_z - cz)**2)
            if dist < 100:  # Huge hitbox for easier collection
                collected.append(coin)
                self.score += 10
            else:
                coin[3] = (coin[3] + 4) % 360  # Spin animation
                
        for c in collected:
            self.coins.remove(c)
            self.spawn_coin()
        
        self.update()

    def rotate_3d(self, x, y, z, pitch, yaw, roll):
        p, yw, r = math.radians(pitch), math.radians(yaw), math.radians(roll)
        # Roll (Z axis)
        x1 = x * math.cos(r) - y * math.sin(r)
        y1 = x * math.sin(r) + y * math.cos(r)
        z1 = z
        # Pitch (X axis)
        x2 = x1
        y2 = y1 * math.cos(p) - z1 * math.sin(p)
        z2 = y1 * math.sin(p) + z1 * math.cos(p)
        # Yaw (Y axis)
        x3 = x2 * math.cos(yw) - z2 * math.sin(yw)
        y3 = y2
        z3 = x2 * math.sin(yw) + z2 * math.cos(yw)
        return x3, y3, z3

    def project(self, x, y, z):
        # Chase camera positioning
        cam_dist = 250
        cam_height = 80
        rad = math.radians(self.yaw)
        
        # Position camera behind the drone
        cx = self.drone_x - math.sin(rad) * cam_dist
        cy = self.drone_y + cam_height
        cz = self.drone_z + math.cos(rad) * cam_dist
        
        # Translate to camera space
        x -= cx; y -= cy; z -= cz
        
        # Apply camera yaw (counter-rotate to look exactly in the direction the drone is facing)
        cam_yaw = -rad
        x1 = x * math.cos(cam_yaw) - z * math.sin(cam_yaw)
        z1 = x * math.sin(cam_yaw) + z * math.cos(cam_yaw)
        
        # Camera pitch (look down by 5 degrees for a better horizon view)
        cam_pitch = math.radians(5)
        y_cam = y * math.cos(cam_pitch) - z1 * math.sin(cam_pitch)
        z_cam = y * math.sin(cam_pitch) + z1 * math.cos(cam_pitch)
        
        # Perspective projection
        f = 400
        z_depth = z_cam if z_cam < -1 else -1 # Prevent div by zero
        
        px = (x1 * f) / abs(z_depth) + self.width() / 2
        py = (-y_cam * f) / abs(z_depth) + self.height() / 2 # Invert Y for screen coords
        return px, py, abs(z_depth)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0d1117"))
        
        # Calculate true mathematical 3D horizon based on 5 degree camera pitch
        horizon_y = int(-math.tan(math.radians(5)) * 400 + self.height() / 2)
        
        # Draw infinite panning mountain skybox
        if not self.bg_image.isNull():
            target_h = self.height()
            scaled_bg = self.bg_image.scaledToHeight(target_h, Qt.TransformationMode.SmoothTransformation)
            sw = scaled_bg.width()
            
            # Mountains pan as you yaw (parallax effect)
            pan_speed = 2.0
            offset_x = int(((self.yaw % 360) / 360.0) * sw * pan_speed) % sw
            
            curr_x = -offset_x
            while curr_x < self.width():
                painter.drawPixmap(curr_x, 0, scaled_bg)
                curr_x += sw
                
        # Fill solid ground to hide the underground mountains
        painter.fillRect(0, horizon_y, self.width(), self.height() - horizon_y, QColor("#1e242c"))
        
        # Draw 3D Grid floor (Y = 0)
        painter.setPen(QPen(QColor("#2d333b"), 1))
        
        # Infinite sliding floor grid centered on the drone
        grid_size = 800
        step = 40
        start_x = int(self.drone_x // step) * step - grid_size // 2
        start_z = int(self.drone_z // step) * step - grid_size // 2
        
        for i in range(0, grid_size + 1, step):
            gx = start_x + i
            gz = start_z + i
            
            p1x, p1y, _ = self.project(gx, 0, start_z)
            p2x, p2y, _ = self.project(gx, 0, start_z + grid_size)
            painter.drawLine(int(p1x), int(p1y), int(p2x), int(p2y))
            
            p3x, p3y, _ = self.project(start_x, 0, gz)
            p4x, p4y, _ = self.project(start_x + grid_size, 0, gz)
            painter.drawLine(int(p3x), int(p3y), int(p4x), int(p4y))
            
        # Drone geometry in local space
        arms = [
            (25, 0, -25, "#e74c3c"),  # Front Right (Red)
            (-25, 0, -25, "#e74c3c"), # Front Left (Red)
            (25, 0, 25, "#3498db"),   # Back Right (Blue)
            (-25, 0, 25, "#3498db")   # Back Left (Blue)
        ]
        
        # Get center projection
        cx, cy, cz = self.rotate_3d(0, 0, 0, self.pitch, self.yaw, self.roll)
        c_px, c_py, c_depth = self.project(cx + self.drone_x, cy + self.drone_y, cz + self.drone_z)
        
        # Draw vertical line to ground to show altitude
        gx, gy, _ = self.project(self.drone_x, 0, self.drone_z)
        painter.setPen(QPen(QColor("#58a6ff"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(int(c_px), int(c_py), int(gx), int(gy))
        
        # Draw arms and props
        for ax, ay, az, color in arms:
            rx, ry, rz = self.rotate_3d(ax, ay, az, self.pitch, self.yaw, self.roll)
            wx = rx + self.drone_x
            wy = ry + self.drone_y
            wz = rz + self.drone_z
            px, py, depth = self.project(wx, wy, wz)
            
            # Arm line
            painter.setPen(QPen(QColor("#aaaaaa"), 3))
            painter.drawLine(int(c_px), int(c_py), int(px), int(py))
            
            # Propeller
            size = max(2, int(6000 / (depth + 100))) # Scale by depth
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color))
            painter.drawEllipse(int(px - size/2), int(py - size/2), size, size)
            
        # Draw central body box
        painter.setBrush(QColor("#ffffff"))
        b_size = max(5, int(10000 / (c_depth + 100)))
        painter.drawRect(int(c_px - b_size/2), int(c_py - b_size/2), b_size, b_size)
        
        # Draw collectible coins
        for cx, cy, cz, rot, num in self.coins:
            px, py, depth = self.project(cx, cy, cz)
            if depth <= 1.0: 
                continue # Hide coin if it's perfectly behind the camera
                
            size = max(10, int(12000 / (depth + 100))) # Make coins visually larger
            
            # Hover bounce effect
            bounce = math.sin(math.radians(rot)) * 10
            py += bounce * (400 / (depth + 100))
            
            # Tether line to ground
            gx, gy, g_depth = self.project(cx, 0, cz)
            if g_depth > 1.0:
                painter.setPen(QPen(QColor("#f39c12"), 1, Qt.PenStyle.DotLine))
                painter.drawLine(int(px), int(py), int(gx), int(gy))
            
            # Golden coin outer body
            painter.setPen(QPen(QColor("#d4af37"), max(1, size//10)))
            painter.setBrush(QColor("#f1c40f"))
            painter.drawEllipse(int(px - size/2), int(py - size/2), size, size)
            
            # Inner circle (Coin edge detail)
            painter.setPen(QPen(QColor("#d4af37"), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(int(px - size/3), int(py - size/3), size*2//3, size*2//3)
            
            # Number inside coin
            painter.setPen(QColor("#b8860b"))
            font = painter.font()
            font.setPointSize(max(6, size // 2))
            font.setBold(True)
            painter.setFont(font)
            text = str(num)
            metrics = painter.fontMetrics()
            tw = metrics.horizontalAdvance(text)
            th = metrics.capHeight()
            painter.drawText(int(px - tw/2), int(py + th/2), text)

        # Draw Score HUD
        painter.setPen(QColor("#f1c40f"))
        font = painter.font()
        font.setPointSize(16)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(15, 30, t("sim.score", score=self.score))

        # Draw ESC prompt if fullscreen
        if self.isFullScreen():
            painter.setPen(QColor("#ffffff"))
            font.setPointSize(12)
            painter.setFont(font)
            painter.drawText(15, 60, t("sim.esc_hint"))

        # Draw Mental Command Visual Feedback
        if self.main_app and self.main_app.drone_client and getattr(self.main_app.drone_client, 'drone', None):
            action = getattr(self.main_app.drone_client.drone, 'last_executed_action', None)
            action_time = getattr(self.main_app.drone_client.drone, 'last_action_time', 0.0)
            now = time.time()
            if action and (now - action_time) < 2.0:
                # Fade out over 2 seconds
                alpha = int(255 * (1.0 - (now - action_time) / 2.0))
                if alpha > 0:
                    text = t("sim.mental_command", action=action.upper())
                    font.setPointSize(24)
                    font.setBold(True)
                    painter.setFont(font)
                    metrics = painter.fontMetrics()
                    tw = metrics.horizontalAdvance(text)
                    th = metrics.capHeight()
                    
                    # Draw glowing background
                    bx = self.width() // 2 - tw // 2 - 20
                    by = 20
                    bw = tw + 40
                    bh = th + 20
                    
                    bg_color = QColor(88, 166, 255, alpha // 2)
                    painter.setBrush(bg_color)
                    painter.setPen(QPen(QColor(88, 166, 255, alpha), 2))
                    painter.drawRoundedRect(bx, by, bw, bh, 8, 8)
                    
                    # Draw text
                    painter.setPen(QColor(255, 255, 255, alpha))
                    painter.drawText(bx + 20, by + bh - 10, text)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            if self.main_app:
                self.main_app.toggle_fullscreen()


class FullscreenHUDWidget(QWidget):
    """Fullscreen Camera HUD with Flight Controller Overlays"""
    def __init__(self, main_app=None, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.latest_frame = QImage()

    def update_frame(self, img: QImage):
        self.latest_frame = img
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        cx = w // 2
        cy = h // 2

        # 1. Draw Camera Feed
        if not self.latest_frame.isNull():
            scaled = self.latest_frame.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            
            # Center the image
            draw_x = (w - scaled.width()) // 2
            draw_y = (h - scaled.height()) // 2
            painter.drawImage(draw_x, draw_y, scaled)
        else:
            painter.fillRect(self.rect(), QColor(0, 0, 0))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, t("hud.no_signal"))

        # 2. Draw HUD Elements
        painter.setPen(QPen(QColor(0, 255, 0, 200), 2))
        
        # Crosshair
        painter.drawLine(cx - 20, cy, cx - 5, cy)
        painter.drawLine(cx + 5, cy, cx + 20, cy)
        painter.drawLine(cx, cy - 20, cx, cy - 5)
        painter.drawLine(cx, cy + 5, cx, cy + 20)
        painter.drawPoint(cx, cy)

        # Get telemetry
        lr, fb, ud, yaw = 0, 0, 0, 0
        batt, alt, temp = 0, 0, 0
        action, action_time = None, 0.0
        now = time.time()

        if self.main_app:
            if self.main_app.drone_client and self.main_app.drone_client.drone:
                lr, fb, ud, yaw = self.main_app.drone_client.drone.get_rc_values()
                action = getattr(self.main_app.drone_client.drone, 'last_executed_action', None)
                action_time = getattr(self.main_app.drone_client.drone, 'last_action_time', 0.0)
            if self.main_app.tello:
                try:
                    batt = self.main_app.tello.get_battery()
                    alt = self.main_app.tello.get_height()
                    temp = self.main_app.tello.get_temperature()
                except:
                    pass

        # Font setup. Courier has no CJK glyphs, so only force it for Latin text —
        # otherwise the translated overlays would render as boxes.
        font = painter.font()
        if i18n.get_lang() == "en":
            font.setFamily("Courier")
        font.setPointSize(14)
        font.setBold(True)
        painter.setFont(font)

        # Telemetry Text
        painter.drawText(20, 40, f"PWR: {batt}%")
        painter.drawText(20, 65, f"ALT: {alt} cm")
        painter.drawText(20, 90, f"TMP: {temp} C")

        # RC Bars (Left side = UD/YAW, Right side = FB/LR)
        def draw_bar(x, y, val, label, is_horizontal=False):
            painter.setPen(QColor(0, 255, 0, 150))
            if is_horizontal:
                painter.drawLine(x - 50, y, x + 50, y)
                painter.drawLine(x, y - 5, x, y + 5)
                # Fill
                if val != 0:
                    bx = x if val > 0 else x + int(val / 2.0)
                    bw = abs(int(val / 2.0))
                    painter.fillRect(bx, y - 2, bw, 4, QColor(0, 255, 0, 200))
            else:
                painter.drawLine(x, y - 50, x, y + 50)
                painter.drawLine(x - 5, y, x + 5, y)
                if val != 0:
                    # Invert Y so positive is up
                    by = y - int(val / 2.0) if val > 0 else y
                    bh = abs(int(val / 2.0))
                    painter.fillRect(x - 2, by, 4, bh, QColor(0, 255, 0, 200))
            painter.drawText(x - 20, y + 70 if not is_horizontal else y + 25, label)

        draw_bar(50, cy, ud, "THR")
        draw_bar(w - 50, cy, fb, "PIT")
        draw_bar(cx - 150, h - 50, yaw, "YAW", True)
        draw_bar(cx + 150, h - 50, lr, "ROL", True)

        # Horizon Line (Pitch/Roll estimate from RC inputs)
        # Note: Tello doesn't provide live IMU roll/pitch via SDK, so we estimate it for the HUD
        sim_roll = math.radians(-lr * 0.3)
        sim_pitch = fb * 0.3
        
        hx1 = -150
        hx2 = 150
        hy1 = sim_pitch
        hy2 = sim_pitch
        
        # Rotate by roll
        rx1 = cx + hx1 * math.cos(sim_roll) - hy1 * math.sin(sim_roll)
        ry1 = cy + hx1 * math.sin(sim_roll) + hy1 * math.cos(sim_roll)
        rx2 = cx + hx2 * math.cos(sim_roll) - hy2 * math.sin(sim_roll)
        ry2 = cy + hx2 * math.sin(sim_roll) + hy2 * math.cos(sim_roll)
        
        painter.setPen(QPen(QColor(0, 255, 0, 200), 1, Qt.PenStyle.DashLine))
        painter.drawLine(int(rx1), int(ry1), int(rx2), int(ry2))

        # Mental Command Banner
        if action and (now - action_time) < 2.0:
            alpha = int(255 * (1.0 - (now - action_time) / 2.0))
            if alpha > 0:
                text = f"*** {action.upper()} ***"
                font.setPointSize(20)
                painter.setFont(font)
                metrics = painter.fontMetrics()
                tw = metrics.horizontalAdvance(text)
                
                painter.setPen(QColor(255, 0, 0, alpha))
                painter.drawText(cx - tw // 2, 60, text)
                
        # ESC prompt
        painter.setPen(QColor(255, 255, 255, 100))
        font.setPointSize(10)
        painter.setFont(font)
        painter.drawText(w - 150, 30, t("hud.esc"))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self.main_app:
                self.main_app.close_fullscreen_hud()
            self.close()


class TelloControllerApp(QMainWindow):
    log_signal = pyqtSignal(str)
    drone_connected_signal = pyqtSignal(bool, str)
    bci_status_signal = pyqtSignal(str)
    bci_telemetry_signal = pyqtSignal(int, int)
    profiles_signal = pyqtSignal(list)
    headsets_signal = pyqtSignal(list)
    training_signal = pyqtSignal(str)
    dev_data_signal = pyqtSignal(int, list)
    mc_config_signal = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.resize(1100, 820)
        self.config = ConfigManager.load_config()
        # Language has to be settled before any widget is built, so the first
        # bind() call already produces text in the right language.
        i18n.set_lang(self.config.get("language", "en"))
        bind(self, "app.title", "setWindowTitle")
        self.tello = None
        self.drone_client = None
        self.video_thread = None
        self.client_thread = None

        # --- Signals ---
        self.log_signal.connect(self._append_log)
        self.drone_connected_signal.connect(self._on_drone_connection_result)
        self.bci_status_signal.connect(self._do_update_bci_status)
        self.bci_telemetry_signal.connect(self._do_update_bci_telemetry)
        self.profiles_signal.connect(self._populate_profiles)
        self.headsets_signal.connect(self._populate_headsets)
        self.training_signal.connect(self._on_training_update)
        self.dev_data_signal.connect(self._on_dev_data_update)
        self.mc_config_signal.connect(self._on_mc_config_update)

        self.stdout_stream = EmittingStream()
        self.stdout_stream.textWritten.connect(self.log_signal.emit)
        self.original_stdout = sys.stdout
        sys.stdout = self.stdout_stream

        self.init_ui()
        self.load_settings()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        header = QHBoxLayout()
        header.addStretch()

        self.lang_lbl = QLabel()
        bind(self.lang_lbl, "header.language")
        header.addWidget(self.lang_lbl)

        self.lang_combo = QComboBox()
        self.lang_combo.setFixedWidth(120)
        for code, name in i18n.available_languages():
            self.lang_combo.addItem(name, userData=code)
        current = self.lang_combo.findData(i18n.get_lang())
        if current >= 0:
            self.lang_combo.setCurrentIndex(current)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        header.addWidget(self.lang_combo)

        self.settings_btn = QPushButton()
        bind(self.settings_btn, "btn.settings")
        self.settings_btn.setObjectName("blueBtn")
        self.settings_btn.clicked.connect(self.show_settings)
        header.addWidget(self.settings_btn)
        main_layout.addLayout(header)

        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)

        self.setup_page_auth()
        self.setup_page_headset()
        self.setup_page_profile()
        self.setup_page_eq_check()
        self.setup_page_train_neutral()
        self.setup_page_train_push()
        self.setup_page_1()
        self.setup_page_2()
        self.setup_page_3()

        self.telem_timer = QTimer()
        self.telem_timer.timeout.connect(self.update_telemetry)

    def _on_language_changed(self, index: int):
        code = self.lang_combo.itemData(index)
        if not code or code == i18n.get_lang():
            return
        i18n.set_lang(code)
        self.config["language"] = code
        ConfigManager.save_config(self.config)
        i18n.retranslate()
        self._retranslate_dynamic()

    def _retranslate_dynamic(self):
        """Redo the bits that bind() cannot reach: combo entries and repaints."""
        # A combo showing a placeholder holds no real data, so its single item
        # is safe to rewrite. _placeholder_key says which message is up.
        for combo in (self.headset_combo, self.profile_combo):
            key = getattr(combo, "_placeholder_key", None)
            if key and combo.count() == 1:
                combo.setItemText(0, t(key))
        for widget in (self.drone_sim, self.neutral_sim, self.push_sim):
            widget.update()
        if getattr(self, "hud_widget", None) is not None:
            self.hud_widget.update()

    def setup_page_auth(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        container = QWidget(); container.setFixedWidth(600)
        c_layout = QVBoxLayout(container); c_layout.setSpacing(15)

        title = QLabel(); title.setObjectName("titleLabel")
        bind(title, "auth.title")
        c_layout.addWidget(title)

        auth_group = QGroupBox()
        bind(auth_group, "auth.group", "setTitle")
        auth_layout = QVBoxLayout(auth_group)
        auth_layout.addWidget(bind(QLabel(), "auth.client_id"))
        self.client_id_input = QLineEdit()
        auth_layout.addWidget(self.client_id_input)
        auth_layout.addWidget(bind(QLabel(), "auth.client_secret"))
        self.client_secret_input = QLineEdit()
        self.client_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        auth_layout.addWidget(self.client_secret_input)

        self.simulate_cb = QCheckBox()
        bind(self.simulate_cb, "auth.simulate")
        auth_layout.addWidget(self.simulate_cb)

        self.connect_bci_btn = QPushButton(); self.connect_bci_btn.setObjectName("blueBtn")
        bind(self.connect_bci_btn, "auth.connect")
        self.connect_bci_btn.clicked.connect(self._start_bci)
        auth_layout.addWidget(self.connect_bci_btn)
        c_layout.addWidget(auth_group)

        c_layout.addWidget(bind(QLabel(), "auth.logs"))
        self.bci_log_terminal = QPlainTextEdit()
        self.bci_log_terminal.setReadOnly(True)
        self.bci_log_terminal.setMaximumBlockCount(200)
        self.bci_log_terminal.setFixedHeight(120)
        c_layout.addWidget(self.bci_log_terminal)

        layout.addWidget(container)
        self.stacked_widget.addWidget(page)

    def setup_page_headset(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        container = QWidget(); container.setFixedWidth(600)
        c_layout = QVBoxLayout(container); c_layout.setSpacing(15)

        title = QLabel(); title.setObjectName("titleLabel")
        bind(title, "headset.title")
        c_layout.addWidget(title)

        self.headset_group = QGroupBox()
        bind(self.headset_group, "headset.group", "setTitle")
        headset_layout = QVBoxLayout(self.headset_group)
        self.headset_combo = QComboBox()
        self.headset_combo._placeholder_key = "headset.awaiting_auth"
        self.headset_combo.addItem(t("headset.awaiting_auth"))
        self.headset_combo.setStyleSheet(
            "QComboBox { background-color: #0d1117; border: 1px solid #30363d; border-radius: 6px;"
            "padding: 8px 12px; color: #8b949e; font-size: 14px; }"
            "QComboBox:enabled { color: #e6edf3; }"
            "QComboBox QAbstractItemView { background-color: #161b22; color: #e6edf3;"
            "selection-background-color: #1f6feb; border: 1px solid #30363d; }"
        )
        headset_layout.addWidget(self.headset_combo)
        
        self.connect_headset_btn = QPushButton()
        bind(self.connect_headset_btn, "headset.connect")
        self.connect_headset_btn.setObjectName("blueBtn")
        self.connect_headset_btn.clicked.connect(self._connect_headset)
        headset_layout.addWidget(self.connect_headset_btn)

        self.bci_conn_status_lbl = QLabel()
        bind(self.bci_conn_status_lbl, "badge.not_connected")
        self.bci_conn_status_lbl.setObjectName("statusBadge")
        self.bci_conn_status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        headset_layout.addWidget(self.bci_conn_status_lbl)
        c_layout.addWidget(self.headset_group)

        # Back button
        back_btn = QPushButton()
        bind(back_btn, "headset.back")
        back_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        c_layout.addWidget(back_btn)

        layout.addWidget(container)
        self.stacked_widget.addWidget(page)

    def setup_page_profile(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        container = QWidget(); container.setFixedWidth(600)
        c_layout = QVBoxLayout(container); c_layout.setSpacing(15)

        title = QLabel(); title.setObjectName("titleLabel")
        bind(title, "profile.title")
        c_layout.addWidget(title)

        self.profile_group = QGroupBox()
        bind(self.profile_group, "profile.group", "setTitle")
        profile_layout = QVBoxLayout(self.profile_group)

        profile_hdr = QHBoxLayout()
        profile_hdr.addWidget(bind(QLabel(), "profile.label"))
        profile_hdr.addStretch()
        self.refresh_profiles_btn = QPushButton()
        bind(self.refresh_profiles_btn, "profile.refresh")
        bind(self.refresh_profiles_btn, "profile.refresh.tip", "setToolTip")
        self.refresh_profiles_btn.setFixedWidth(90)
        self.refresh_profiles_btn.clicked.connect(self._refresh_profiles)
        profile_hdr.addWidget(self.refresh_profiles_btn)
        profile_layout.addLayout(profile_hdr)

        self.profile_combo = QComboBox()
        self.profile_combo._placeholder_key = "profile.connect_first"
        self.profile_combo.addItem(t("profile.connect_first"))
        self.profile_combo.setStyleSheet(
            "QComboBox { background-color: #0d1117; border: 1px solid #30363d; border-radius: 6px;"
            "padding: 8px 12px; color: #8b949e; font-size: 14px; }"
            "QComboBox:enabled { color: #e6edf3; }"
            "QComboBox QAbstractItemView { background-color: #161b22; color: #e6edf3;"
            "selection-background-color: #1f6feb; border: 1px solid #30363d; }"
        )
        profile_layout.addWidget(self.profile_combo)

        self.load_profile_btn = QPushButton()
        bind(self.load_profile_btn, "profile.load")
        self.load_profile_btn.setObjectName("primaryBtn")
        self.load_profile_btn.clicked.connect(self._load_selected_profile)
        profile_layout.addWidget(self.load_profile_btn)

        self.profile_status_lbl = QLabel()
        bind(self.profile_status_lbl, "profile.hint")
        self.profile_status_lbl.setStyleSheet(
            "color: #8b949e; font-size: 13px; font-style: italic; margin-top: 8px;"
        )
        profile_layout.addWidget(self.profile_status_lbl)
        
        # New: Create & Train Profile Section
        train_layout = QHBoxLayout()
        self.new_profile_input = QLineEdit()
        bind(self.new_profile_input, "profile.new_placeholder", "setPlaceholderText")

        self.train_profile_btn = QPushButton()
        bind(self.train_profile_btn, "profile.create_train")
        self.train_profile_btn.setObjectName("primaryBtn")
        self.train_profile_btn.clicked.connect(self._create_and_train_profile)
        
        train_layout.addWidget(self.new_profile_input)
        train_layout.addWidget(self.train_profile_btn)
        profile_layout.addLayout(train_layout)

        self.profile_group.setEnabled(False)
        c_layout.addWidget(self.profile_group)

        # ── Next Button & Back Button ──
        btn_row = QHBoxLayout()
        back_btn = QPushButton()
        bind(back_btn, "profile.back")
        back_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))

        self.p0_next_btn = QPushButton()
        bind(self.p0_next_btn, "profile.next")
        self.p0_next_btn.setObjectName("primaryBtn")
        self.p0_next_btn.setEnabled(False)
        self.p0_next_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(6))
        
        btn_row.addWidget(back_btn)
        btn_row.addWidget(self.p0_next_btn)
        c_layout.addLayout(btn_row)

        layout.addWidget(container)
        self.stacked_widget.addWidget(page)

    def _get_artifact_image_path(self, filename: str) -> str:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".gemini", "antigravity-ide", "brain", "d3a45a7c-55b3-4531-b454-34ccaf34c9bd", filename)
        if not os.path.exists(path):
            path = f"/Users/giovaniflorek/.gemini/antigravity-ide/brain/d3a45a7c-55b3-4531-b454-34ccaf34c9bd/{filename}"
        return path

    def setup_page_eq_check(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        container = QWidget(); container.setFixedWidth(700)
        c_layout = QVBoxLayout(container); c_layout.setSpacing(15)

        title = QLabel()
        bind(title, "eq.title")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #58a6ff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(title)

        subtitle = QLabel()
        bind(subtitle, "eq.subtitle")
        subtitle.setStyleSheet("font-size: 14px; color: #8b949e;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(subtitle)

        self.eq_overall_lbl = QLabel()
        bind(self.eq_overall_lbl, "eq.overall_waiting")
        self.eq_overall_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.eq_overall_lbl.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #e6edf3;"
            "padding: 10px; background-color: #161b22; border: 1px solid #30363d; border-radius: 8px;"
        )
        c_layout.addWidget(self.eq_overall_lbl)

        sensor_group = QGroupBox()
        bind(sensor_group, "eq.group", "setTitle")
        self.eq_sensor_layout = QGridLayout(sensor_group)
        self.eq_sensor_layout.setSpacing(8)
        self.eq_sensor_labels = {}
        c_layout.addWidget(sensor_group)

        self.eq_status_lbl = QLabel()
        bind(self.eq_status_lbl, "eq.waiting_data")
        self.eq_status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.eq_status_lbl.setStyleSheet("font-size: 14px; color: #e3a01a; margin-top: 10px;")
        c_layout.addWidget(self.eq_status_lbl)

        btn_row = QHBoxLayout()
        back_btn = QPushButton()
        bind(back_btn, "eq.back")
        back_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(2))

        self.eq_next_btn = QPushButton()
        bind(self.eq_next_btn, "eq.next")
        self.eq_next_btn.setObjectName("primaryBtn")
        self.eq_next_btn.setEnabled(False)
        self.eq_next_btn.clicked.connect(self._start_training_from_eq)

        btn_row.addWidget(back_btn)
        btn_row.addWidget(self.eq_next_btn)
        c_layout.addLayout(btn_row)

        layout.addWidget(container)
        self.stacked_widget.addWidget(page)

    def _start_training_from_eq(self):
        self._begin_training_sequence("neutral")

    def _begin_training_sequence(self, action):
        self.current_training_action = action
        if action == "neutral":
            self.stacked_widget.setCurrentIndex(4)
        else:
            self.stacked_widget.setCurrentIndex(5)
            
        if not hasattr(self, "countdown_overlay"):
            self.countdown_overlay = QLabel(self.stacked_widget)
            self.countdown_overlay.setStyleSheet("font-size: 120px; font-weight: bold; color: rgba(255, 123, 114, 255); background-color: rgba(0, 0, 0, 150); border-radius: 20px;")
            self.countdown_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
        self.countdown_overlay.resize(200, 200)
        sw_rect = self.stacked_widget.rect()
        self.countdown_overlay.move(
            int((sw_rect.width() - 200) / 2),
            int((sw_rect.height() - 200) / 2)
        )
        
        self.countdown_val = 3
        self.countdown_overlay.setText(str(self.countdown_val))
        self.countdown_overlay.show()
        self.countdown_overlay.raise_()
        
        lbl = self.neutral_status_lbl if action == "neutral" else self.push_status_lbl
        bind(lbl, "train.get_ready")

        if hasattr(self, "countdown_timer") and self.countdown_timer.isActive():
            self.countdown_timer.stop()
            
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(lambda: self._on_countdown_tick(action))
        self.countdown_timer.start(1000)

    def _on_countdown_tick(self, action):
        self.countdown_val -= 1
        if self.countdown_val > 0:
            self.countdown_overlay.setText(str(self.countdown_val))
        else:
            self.countdown_timer.stop()
            self.countdown_overlay.hide()
            
            lbl = self.neutral_status_lbl if action == "neutral" else self.push_status_lbl
            self.recording_val = 8
            bind(lbl, "train.recording", seconds=self.recording_val)

            if hasattr(self, "recording_timer") and self.recording_timer.isActive():
                self.recording_timer.stop()
                
            self.recording_timer = QTimer(self)
            self.recording_timer.timeout.connect(lambda: self._on_recording_tick(action))
            self.recording_timer.start(1000)
            
            if action == "push":
                self.push_anim_timer.start(50)
                
            self.drone_client.start_training(action)

    def _on_recording_tick(self, action):
        self.recording_val -= 1
        lbl = self.neutral_status_lbl if action == "neutral" else self.push_status_lbl
        if self.recording_val > 0:
            bind(lbl, "train.recording", seconds=self.recording_val)
        else:
            self.recording_timer.stop()
            bind(lbl, "train.finishing")

    def setup_page_train_neutral(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        title = QLabel()
        bind(title, "train.neutral.title")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #58a6ff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel()
        bind(subtitle, "train.neutral.subtitle")
        subtitle.setStyleSheet("font-size: 14px; color: #8b949e;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        self.neutral_sim = DroneSimulatorWidget(self)
        self.neutral_sim.setMinimumSize(500, 350)
        layout.addWidget(self.neutral_sim, stretch=1)

        self.neutral_status_lbl = QLabel()
        bind(self.neutral_status_lbl, "train.waiting")
        self.neutral_status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.neutral_status_lbl.setStyleSheet("font-size: 16px; color: #e6edf3;")
        layout.addWidget(self.neutral_status_lbl)
        
        btn_layout = QHBoxLayout()
        self.neutral_accept_btn = QPushButton()
        bind(self.neutral_accept_btn, "train.accept")
        self.neutral_accept_btn.setObjectName("primaryBtn")
        self.neutral_accept_btn.clicked.connect(lambda: self._on_training_accept("neutral"))
        self.neutral_accept_btn.hide()

        self.neutral_reject_btn = QPushButton()
        bind(self.neutral_reject_btn, "train.reject")
        self.neutral_reject_btn.setObjectName("dangerBtn")
        self.neutral_reject_btn.clicked.connect(lambda: self._on_training_reject("neutral"))
        self.neutral_reject_btn.hide()
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.neutral_accept_btn)
        btn_layout.addWidget(self.neutral_reject_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.stacked_widget.addWidget(page)

    def setup_page_train_push(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        title = QLabel()
        bind(title, "train.push.title")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #58a6ff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel()
        bind(subtitle, "train.push.subtitle")
        subtitle.setStyleSheet("font-size: 14px; color: #8b949e;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        
        self.push_sim = DroneSimulatorWidget(self)
        self.push_sim.setMinimumSize(500, 350)
        layout.addWidget(self.push_sim, stretch=1)
        
        # Timer to animate the push sim forward
        self.push_anim_timer = QTimer()
        self.push_anim_timer.timeout.connect(lambda: self.push_sim.update_rc(0, 10, 0, 0))
        
        self.push_status_lbl = QLabel()
        bind(self.push_status_lbl, "train.waiting")
        self.push_status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.push_status_lbl.setStyleSheet("font-size: 16px; color: #e6edf3;")
        layout.addWidget(self.push_status_lbl)
        
        btn_layout = QHBoxLayout()
        self.push_accept_btn = QPushButton()
        bind(self.push_accept_btn, "train.accept")
        self.push_accept_btn.setObjectName("primaryBtn")
        self.push_accept_btn.clicked.connect(lambda: self._on_training_accept("push"))
        self.push_accept_btn.hide()

        self.push_reject_btn = QPushButton()
        bind(self.push_reject_btn, "train.reject")
        self.push_reject_btn.setObjectName("dangerBtn")
        self.push_reject_btn.clicked.connect(lambda: self._on_training_reject("push"))
        self.push_reject_btn.hide()

        self.push_next_btn = QPushButton()
        bind(self.push_next_btn, "train.finish")
        self.push_next_btn.setObjectName("primaryBtn")
        self.push_next_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(6))
        self.push_next_btn.hide()
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.push_accept_btn)
        btn_layout.addWidget(self.push_reject_btn)
        btn_layout.addWidget(self.push_next_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.stacked_widget.addWidget(page)

    def setup_page_1(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        container = QWidget(); container.setFixedWidth(700)
        c_layout = QVBoxLayout(container); c_layout.setSpacing(20)

        title = QLabel(); title.setObjectName("titleLabel")
        bind(title, "test.title")
        subtitle = QLabel()
        bind(subtitle, "test.subtitle")
        subtitle.setObjectName("subtitleLabel"); subtitle.setWordWrap(True)
        c_layout.addWidget(title); c_layout.addWidget(subtitle)

        top_split = QHBoxLayout()

        state_group = QGroupBox()
        bind(state_group, "test.state_group", "setTitle")
        self.state_layout = QVBoxLayout()
        self.virtual_flight_state_lbl = QLabel()
        bind(self.virtual_flight_state_lbl, "test.landed")
        self.virtual_flight_state_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #8b949e;")
        self.state_layout.addWidget(self.virtual_flight_state_lbl)

        self.last_action_lbl = QLabel()
        bind(self.last_action_lbl, "test.last_command_none")
        self.last_action_lbl.setStyleSheet("color: #58a6ff;")
        self.state_layout.addWidget(self.last_action_lbl)

        self.rc_lbl = QLabel("RC: lr=   0  fb=   0  ud=   0  yaw=   0")
        self.rc_lbl.setStyleSheet("font-family: monospace; font-size: 14px; background: #0d1117; padding: 10px; border-radius: 5px;")
        self.state_layout.addWidget(self.rc_lbl)
        
        self.drone_sim = DroneSimulatorWidget(self)
        self.state_layout.addWidget(self.drone_sim)
        state_group.setLayout(self.state_layout)
        top_split.addWidget(state_group)

        rc_group = QGroupBox()
        bind(rc_group, "test.rc_group", "setTitle")
        rc_grid = QGridLayout()
        def make_bar():
            b = QProgressBar()
            b.setRange(-100, 100); b.setValue(0); b.setTextVisible(True); b.setFormat("%v")
            return b
        self.test_yaw_bar = make_bar()
        self.test_fb_bar = make_bar()
        rc_grid.addWidget(bind(QLabel(), "test.yaw"), 0, 0)
        rc_grid.addWidget(self.test_yaw_bar, 0, 1)
        rc_grid.addWidget(bind(QLabel(), "test.pitch"), 1, 0)
        rc_grid.addWidget(self.test_fb_bar, 1, 1)
        rc_group.setLayout(rc_grid)
        top_split.addWidget(rc_group)
        c_layout.addLayout(top_split)

        raw_group = QGroupBox()
        bind(raw_group, "test.raw_group", "setTitle")
        raw_layout = QVBoxLayout()
        self.raw_mot_lbl = QLabel("MOT: None")
        self.raw_mot_lbl.setStyleSheet("color: #8b949e; font-family: monospace; font-size: 11px;")
        self.raw_com_lbl = QLabel("COM: None")
        self.raw_com_lbl.setStyleSheet("color: #8b949e; font-family: monospace; font-size: 11px;")
        raw_layout.addWidget(self.raw_mot_lbl)
        raw_layout.addWidget(self.raw_com_lbl)
        raw_group.setLayout(raw_layout)
        c_layout.addWidget(raw_group)

        btn_row = QHBoxLayout()
        back_btn = bind(QPushButton(), "test.back")
        back_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(2))

        fs_btn = bind(QPushButton(), "test.fullscreen")
        fs_btn.clicked.connect(self.toggle_fullscreen)

        self.recenter_btn_p1 = bind(QPushButton(), "test.recenter")
        self.recenter_btn_p1.setObjectName("blueBtn")
        self.recenter_btn_p1.clicked.connect(self.reset_headset)
        next_btn = bind(QPushButton(), "test.next"); next_btn.setObjectName("primaryBtn")
        next_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(7))
        btn_row.addWidget(back_btn); btn_row.addWidget(fs_btn); btn_row.addWidget(self.recenter_btn_p1); btn_row.addWidget(next_btn)
        c_layout.addLayout(btn_row)

        layout.addWidget(container)
        self.stacked_widget.addWidget(page)

    def setup_page_2(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        container = QWidget(); container.setFixedWidth(500)
        c_layout = QVBoxLayout(container); c_layout.setSpacing(20)

        title = bind(QLabel(), "drone.title"); title.setObjectName("titleLabel")
        subtitle = bind(QLabel(), "drone.subtitle")
        subtitle.setObjectName("subtitleLabel"); subtitle.setWordWrap(True)
        c_layout.addWidget(title); c_layout.addWidget(subtitle)

        self.drone_conn_status_lbl = bind(QLabel(), "drone.ready")
        self.drone_conn_status_lbl.setObjectName("subtitleLabel")
        c_layout.addWidget(self.drone_conn_status_lbl)

        self.connect_drone_btn = bind(QPushButton(), "drone.connect")
        self.connect_drone_btn.setObjectName("blueBtn")
        self.connect_drone_btn.clicked.connect(self.check_drone_connection)
        c_layout.addWidget(self.connect_drone_btn)

        self.p2_next_btn = bind(QPushButton(), "drone.launch"); self.p2_next_btn.setObjectName("primaryBtn")
        self.p2_next_btn.setEnabled(False)
        self.p2_next_btn.clicked.connect(self.go_to_dashboard)
        c_layout.addWidget(self.p2_next_btn)

        back_btn = bind(QPushButton(), "drone.back")
        back_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(6))
        c_layout.addWidget(back_btn)

        layout.addWidget(container)
        self.stacked_widget.addWidget(page)

    def setup_page_3(self):
        page = QWidget()
        root = QHBoxLayout(page)
        root.setContentsMargins(15, 15, 15, 15)

        left = QVBoxLayout()
        cam_group = bind(QGroupBox(), "dash.camera", "setTitle")
        cam_layout = QVBoxLayout()
        self.camera_label = QLabel()
        self.camera_label.setMinimumSize(640, 480)
        self.camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_label.setStyleSheet("background-color: #010409; border-radius: 8px; border: 1px solid #30363d;")
        self.camera_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        cam_layout.addWidget(self.camera_label)
        cam_group.setLayout(cam_layout)
        left.addWidget(cam_group, stretch=1)

        telem_group = bind(QGroupBox(), "dash.telemetry", "setTitle")
        telem_grid = QGridLayout()
        self.battery_lbl = bind(QLabel(), "dash.battery_empty")
        self.height_lbl = bind(QLabel(), "dash.height_empty")
        self.temp_lbl = bind(QLabel(), "dash.temp_empty")
        self.bci_telem_lbl = bind(QLabel(), "dash.headset_empty")
        for i, lbl in enumerate([self.battery_lbl, self.height_lbl, self.temp_lbl, self.bci_telem_lbl]):
            lbl.setStyleSheet("font-size: 13px; color: #8b949e;")
            telem_grid.addWidget(lbl, 0, i)
        
        self.rc_lbl = QLabel("RC: lr=0 fb=0 ud=0 yaw=0")
        self.rc_lbl.setStyleSheet("font-size: 13px; color: #58a6ff; font-family: monospace;")
        telem_grid.addWidget(self.rc_lbl, 1, 0, 1, 4)
        telem_group.setLayout(telem_grid)
        left.addWidget(telem_group)

        btn_group = bind(QGroupBox(), "dash.controls", "setTitle")
        btn_layout = QHBoxLayout()
        self.takeoff_btn = bind(QPushButton(), "dash.takeoff"); self.takeoff_btn.setObjectName("primaryBtn")
        self.takeoff_btn.clicked.connect(self.takeoff)
        self.land_btn = bind(QPushButton(), "dash.land"); self.land_btn.setObjectName("dangerBtn")
        self.land_btn.clicked.connect(self.land)
        self.emergency_btn = bind(QPushButton(), "dash.emergency"); self.emergency_btn.setObjectName("dangerBtn")
        self.emergency_btn.setStyleSheet("border: 2px solid #fff;")
        self.emergency_btn.clicked.connect(self.emergency_stop)
        self.recenter_btn_p3 = bind(QPushButton(), "dash.recenter"); self.recenter_btn_p3.setObjectName("blueBtn")
        self.recenter_btn_p3.clicked.connect(self.reset_headset)
        
        btn_layout.addWidget(self.takeoff_btn)
        btn_layout.addWidget(self.land_btn)
        btn_layout.addWidget(self.recenter_btn_p3)
        btn_layout.addWidget(self.emergency_btn)
        btn_group.setLayout(btn_layout)
        left.addWidget(btn_group)

        root.addLayout(left, stretch=3)

        right = QVBoxLayout()
        top_bar = QVBoxLayout()
        status_row = QHBoxLayout()
        self.dash_drone_lbl = bind(QLabel(), "dash.drone_connected"); self.dash_drone_lbl.setObjectName("statusBadge")
        self.dash_bci_lbl = bind(QLabel(), "badge.bci_active"); self.dash_bci_lbl.setObjectName("statusBadge")
        status_row.addWidget(self.dash_drone_lbl); status_row.addWidget(self.dash_bci_lbl)
        status_row.addStretch()
        top_bar.addLayout(status_row)
        
        # MC Indicator
        self.dash_mc_lbl = bind(QLabel(), "dash.mc_none")
        self.dash_mc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dash_mc_lbl.setStyleSheet(
            "background-color: #0d1117; border: 1px solid #30363d; border-radius: 6px;"
            "padding: 8px 12px; color: #8b949e; font-size: 14px; font-weight: bold;"
        )
        top_bar.addWidget(self.dash_mc_lbl)
        right.addLayout(top_bar)

        # Action Buttons
        act_group = bind(QGroupBox(), "dash.system", "setTitle")
        act_layout = QVBoxLayout()
        self.hud_btn = bind(QPushButton(), "dash.hud")
        self.hud_btn.setObjectName("blueBtn")
        self.hud_btn.clicked.connect(self.open_fullscreen_hud)
        act_layout.addWidget(self.hud_btn)

        self.disconnect_btn = bind(QPushButton(), "dash.disconnect")
        self.disconnect_btn.setObjectName("dangerBtn")
        self.disconnect_btn.clicked.connect(self._disconnect_and_quit)
        act_layout.addWidget(self.disconnect_btn)
        act_group.setLayout(act_layout)
        right.addWidget(act_group)

        term_group = bind(QGroupBox(), "dash.log", "setTitle")
        term_layout = QVBoxLayout()
        self.terminal = QPlainTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setMaximumBlockCount(500)
        term_layout.addWidget(self.terminal)
        term_group.setLayout(term_layout)
        right.addWidget(term_group, stretch=1)

        root.addLayout(right, stretch=1)
        self.stacked_widget.addWidget(page)

    def _start_bci(self):
        self.save_settings()
        from drone_controller import TelloDroneClient

        is_sim = self.simulate_cb.isChecked()
        cid = 'SIM' if is_sim else self.client_id_input.text()
        csec = 'SIM' if is_sim else self.client_secret_input.text()

        self.connect_bci_btn.setEnabled(False)
        bind(self.bci_conn_status_lbl, "badge.connecting")

        self.drone_client = TelloDroneClient(
            cid, csec, tello=None,
            fix_indices=self.config.get("fix_indices", False),
            debug=False, config=self.config,
            bci_status_callback=self.update_bci_status,
            bci_telemetry_callback=self.update_bci_telemetry,
            profiles_callback=self.update_profiles,
            headsets_callback=self.update_headsets,
            training_callback=self.training_signal.emit,
            dev_data_callback=self.dev_data_signal.emit,
            mc_config_callback=self.mc_config_signal.emit
        )

        self.client_thread = threading.Thread(
            target=lambda: self.drone_client.simulate() if is_sim else self.drone_client.start(
                headset_id="", # User will pick after auth
                profile_name="" # profile is auto-selected in on_query_profile_done
            ), daemon=True
        )
        self.client_thread.start()
        self.telem_timer.start(50)

    def update_bci_status(self, status: str):
        self.bci_status_signal.emit(status)

    def update_profiles(self, profiles: list):
        """Thread-safe: forward profile list to the Qt main thread."""
        self.profiles_signal.emit(profiles)

    def update_headsets(self, headsets: list):
        """Thread-safe: forward headset list to the Qt main thread."""
        self.headsets_signal.emit(headsets)
        
    def update_training(self, event: str):
        self.training_signal.emit(event)

    def update_dev_data(self, signal: int, cq_list: list):
        self.dev_data_signal.emit(signal, cq_list)

    # ──────────────────────────────────────────────
    # Signal Handlers (Main Thread)
    # ──────────────────────────────────────────────
    def _populate_headsets(self, headsets: list):
        """Populate the headset dropdown."""
        self.headset_combo.clear()
        
        if not headsets:
            self.headset_combo._placeholder_key = "headset.none_found"
            self.headset_combo.addItem(t("headset.none_found"))
            self.headset_combo.setEnabled(False)
            self.connect_headset_btn.setEnabled(False)
            self.log(t("log.no_headsets"))
            return

        self.headset_combo._placeholder_key = None
        for hs in headsets:
            hs_id = hs.get('id', 'Unknown')
            status = hs.get('status', 'Unknown')
            self.headset_combo.addItem(t("headset.item", id=hs_id, status=status), userData=hs_id)

        self.headset_combo.setEnabled(True)
        self.connect_headset_btn.setEnabled(True)
        self.headset_group.setEnabled(True)
        self.log(t("log.headsets_available", count=len(headsets)))
        # Auto-advance to headset selection screen on successful authentication & headset query
        self.stacked_widget.setCurrentIndex(1)

    def _connect_headset(self):
        """Connect to the selected headset."""
        idx = self.headset_combo.currentIndex()
        headset_id = self.headset_combo.itemData(idx)
        if not headset_id:
            self.log(t("log.no_headset_selected"))
            return

        self.connect_headset_btn.setEnabled(False)
        bind(self.connect_headset_btn, "headset.connecting_btn")
        
        # Load and apply device-specific config profile
        device_type = headset_id.split('-')[0]
        self.config = ConfigManager.get_device_config(self.config, device_type)
        self.config["device_id"] = headset_id
        
        self._apply_config_to_client()
        
        self.log(t("log.connecting_headset", headset=headset_id))

        if self.drone_client:
            threading.Thread(
                target=self.drone_client.connect_headset,
                args=(headset_id,),
                daemon=True
            ).start()
        else:
            self.log(t("log.client_not_init"))
            self.connect_headset_btn.setEnabled(True)
            bind(self.connect_headset_btn, "headset.connect")

    def _populate_profiles(self, profiles: list):
        """Populate the profile dropdown so the user can pick which one to load."""
        self.refresh_profiles_btn.setEnabled(True)
        self.profile_combo.clear()

        if not profiles:
            self.profile_combo._placeholder_key = "profile.none_found"
            self.profile_combo.addItem(t("profile.none_found"))
            self.profile_combo.setEnabled(False)
            self.load_profile_btn.setEnabled(False)
            bind(self.profile_status_lbl, "profile.none_hint")
            self.profile_status_lbl.setStyleSheet(
                "color: #f85149; font-size: 11px; font-style: italic; padding: 0 2px;"
            )
            return

        self.profile_combo._placeholder_key = None
        for p in profiles:
            self.profile_combo.addItem(f"🧠  {p}", userData=p)

        self.profile_combo.setEnabled(True)
        self.load_profile_btn.setEnabled(True)

        # Pre-select the profile from config if it exists in the list
        saved_profile = self.config.get("profile_name", "")
        if saved_profile:
            for i in range(self.profile_combo.count()):
                if self.profile_combo.itemData(i) == saved_profile:
                    self.profile_combo.setCurrentIndex(i)
                    break

        count = len(profiles)
        bind(self.profile_status_lbl, "profile.available", count=count)
        self.profile_status_lbl.setStyleSheet(
            "color: #8b949e; font-size: 11px; font-style: italic; padding: 0 2px;"
        )
        self.log(t("log.profiles_available", count=count))

    def _load_selected_profile(self):
        """Load the profile the user selected in the dropdown."""
        idx = self.profile_combo.currentIndex()
        profile_name = self.profile_combo.itemData(idx)
        if not profile_name:
            self.log(t("log.no_profile_selected"))
            return

        self.load_profile_btn.setEnabled(False)
        bind(self.load_profile_btn, "profile.loading_btn")
        self.config["profile_name"] = profile_name
        self.log(t("log.loading_profile", profile=profile_name))

        if self.drone_client:
            threading.Thread(
                target=self.drone_client.load_profile,
                args=(profile_name,),
                daemon=True
            ).start()
        else:
            self.log(t("log.bci_not_connected"))
            self.load_profile_btn.setEnabled(True)
            bind(self.load_profile_btn, "profile.load")

    def _refresh_profiles(self):
        """Re-send queryProfile to Cortex (available once authorized)."""
        if self.drone_client and hasattr(self.drone_client, 'c'):
            try:
                self.drone_client.c.query_profile()
                self.log(t("log.refreshing_profiles"))
            except Exception as e:
                self.log(t("log.refresh_failed", detail=e))

    def _do_update_bci_status(self, status: str):
        # The Cortex layer still speaks in finished English sentences; translate
        # them at this boundary so the badge and the log follow the UI language.
        self.log(t("log.bci_status", status=i18n.backend_status(status)))

        if status.startswith("PENDING_ACCESS:"):
            self._show_access_pending_ui(status[len("PENDING_ACCESS:"):])
            return

        if status.startswith("PROFILE_LOADED:"):
            msg = status[len("PROFILE_LOADED:"):]
            bind(self.bci_conn_status_lbl, "badge.profile_loaded",
                 profile=i18n.profile_name_from_loaded(msg))
            self.bci_conn_status_lbl.setStyleSheet("background-color: #1a4a2e; border: 1px solid #3fb950;")
            self._hide_access_pending_ui()
            self.p0_next_btn.setEnabled(True)
            self._override_action_for_test()
            # Re-enable the Load button so the user can switch profiles
            self.load_profile_btn.setEnabled(True)
            bind(self.load_profile_btn, "profile.load")
            bind(self.profile_status_lbl, "profile.selected",
                 profile=self.profile_combo.currentText())
            self.profile_status_lbl.setStyleSheet(
                "color: #3fb950; font-size: 11px; font-style: italic; padding: 0 2px;"
            )
            return

        bind(self.bci_conn_status_lbl, "badge.status", status=i18n.backend_status(status))
        if "Active" in status:
            bind(self.bci_conn_status_lbl, "badge.bci_active")
            self.bci_conn_status_lbl.setStyleSheet("background-color: #238636;")
            self._hide_access_pending_ui()
            self._override_action_for_test()
            # Session is active — user can now select and load a profile.
            self.profile_group.setEnabled(True)
            self.profile_combo.setEnabled(True)
            bind(self.profile_status_lbl, "profile.session_active")
            # Auto-advance to profile selection screen only if still on auth/headset screens
            if self.stacked_widget.currentIndex() <= 1:
                self.stacked_widget.setCurrentIndex(2)
            # Enable Next for simulation; otherwise wait for profile load.
            is_sim = self.simulate_cb.isChecked()
            if is_sim:
                self.p0_next_btn.setEnabled(True)
        elif "Error" in status or "error" in status.lower() or "finished" in status.lower() or "warning" in status.lower() or "failed" in status.lower():
            bind(self.bci_conn_status_lbl, "badge.scan_finished")
            bind(self.connect_bci_btn, "auth.retry")
            self.connect_bci_btn.setEnabled(True)
            # Re-enable load button in case of profile load error
            self.load_profile_btn.setEnabled(True)
            bind(self.load_profile_btn, "profile.load")

    def _show_access_pending_ui(self, message: str):
        """Show a prominent inline banner asking the user to approve via EMOTIV Launcher."""
        bind(self.bci_conn_status_lbl, "badge.waiting_approval")
        self.bci_conn_status_lbl.setStyleSheet("background-color: #7d4e00; border: 1px solid #e3a01a;")

        # Cortex sends its own English sentence here; swap in the translated one
        # when it is the stock message, otherwise show what Cortex said.
        default_en = i18n.I18N["en"]["access.default_msg"]
        message_key = "access.default_msg" if message.strip() == default_en else None

        # Build or reuse the banner widget
        if not hasattr(self, '_access_banner') or self._access_banner is None:
            from PyQt6.QtWidgets import QFrame
            banner = QFrame()
            banner.setStyleSheet(
                "QFrame { background-color: #1f1300; border: 1px solid #e3a01a; "
                "border-radius: 8px; padding: 6px; }"
            )
            b_layout = QVBoxLayout(banner)
            b_layout.setSpacing(8)

            icon_row = QHBoxLayout()
            warn_icon = QLabel("⚠️")
            warn_icon.setStyleSheet("font-size: 22px; background: transparent; border: none;")
            warn_title = bind(QLabel(), "access.title")
            warn_title.setStyleSheet(
                "font-weight: bold; font-size: 14px; color: #e3a01a; "
                "background: transparent; border: none;"
            )
            icon_row.addWidget(warn_icon)
            icon_row.addWidget(warn_title)
            icon_row.addStretch()
            b_layout.addLayout(icon_row)

            self._access_msg_lbl = QLabel(message)
            if message_key:
                bind(self._access_msg_lbl, message_key)
            self._access_msg_lbl.setWordWrap(True)
            self._access_msg_lbl.setStyleSheet(
                "color: #c9d1d9; font-size: 13px; background: transparent; border: none;"
            )
            b_layout.addWidget(self._access_msg_lbl)

            instructions = bind(QLabel(), "access.steps")
            instructions.setWordWrap(True)
            instructions.setStyleSheet(
                "color: #8b949e; font-size: 12px; background: transparent; border: none; "
                "line-height: 1.6;"
            )
            b_layout.addWidget(instructions)

            retry_btn = bind(QPushButton(), "access.retry")
            retry_btn.setObjectName("blueBtn")
            retry_btn.clicked.connect(self._retry_access_request)
            b_layout.addWidget(retry_btn)

            self._access_banner = banner
            # Insert banner right below the status badge in the page-0 container
            # The container's layout is c_layout (index 0 child of page 0)
            page0_container = self.stacked_widget.widget(0).findChild(QWidget)
            page0_c_layout = page0_container.layout() if page0_container else None
            if page0_c_layout:
                # Insert before the btn_row (second-to-last item) - just append for safety
                page0_c_layout.insertWidget(
                    page0_c_layout.indexOf(self.bci_conn_status_lbl) + 1,
                    banner
                )
        else:
            if message_key:
                bind(self._access_msg_lbl, message_key)
            else:
                i18n.unbind(self._access_msg_lbl)
                self._access_msg_lbl.setText(message)
            self._access_banner.setVisible(True)

    def _hide_access_pending_ui(self):
        if hasattr(self, '_access_banner') and self._access_banner is not None:
            self._access_banner.setVisible(False)

    def _retry_access_request(self):
        """Re-send requestAccess so Cortex re-checks or EMOTIV Launcher re-prompts."""
        if self.drone_client and hasattr(self.drone_client, 'c'):
            self.log(t("log.retry_access"))
            try:
                self.drone_client.c.request_access()
            except Exception as e:
                self.log(t("log.retry_failed", detail=e))

    def _create_and_train_profile(self):
        new_name = self.new_profile_input.text().strip()
        if not new_name:
            self.log(t("log.enter_profile_name"))
            return
            
        self.current_training_action = "neutral"
        self.stacked_widget.setCurrentIndex(3)
        self.drone_client.create_and_train_profile(new_name)
        
    def _on_training_accept(self, action: str):
        if action == "neutral":
            self.neutral_accept_btn.hide()
            self.neutral_reject_btn.hide()
            bind(self.neutral_status_lbl, "train.accepting")
        else:
            self.push_accept_btn.hide()
            self.push_reject_btn.hide()
            bind(self.push_status_lbl, "train.accepting")
        self.drone_client.accept_training(action)
        
    def _on_training_reject(self, action: str):
        if action == "neutral":
            self.neutral_accept_btn.hide()
            self.neutral_reject_btn.hide()
            bind(self.neutral_status_lbl, "train.retrying")
        else:
            self.push_accept_btn.hide()
            self.push_reject_btn.hide()
            bind(self.push_status_lbl, "train.retrying")
        self.drone_client.reject_training(action)
        
    def _on_training_update(self, event: str):
        idx = self.stacked_widget.currentIndex()
        if idx not in [4, 5]:
            return
            
        action = getattr(self, "current_training_action", "neutral")
        
        lbl = self.neutral_status_lbl if action == "neutral" else self.push_status_lbl
        btn_acc = self.neutral_accept_btn if action == "neutral" else self.push_accept_btn
        btn_rej = self.neutral_reject_btn if action == "neutral" else self.push_reject_btn
        
        if event.startswith("PROFILE_LOADED:"):
            self.stacked_widget.setCurrentIndex(3)
            return

        event_lower = event.lower()
        if "started" in event_lower:
            pass # Handled by local recording timer
        elif "succeeded" in event_lower:
            if hasattr(self, "recording_timer") and self.recording_timer.isActive():
                self.recording_timer.stop()
            bind(lbl, "train.succeeded")
            btn_acc.show()
            btn_rej.show()
            bind(btn_rej, "train.reject")
        elif "failed" in event_lower:
            if hasattr(self, "recording_timer") and self.recording_timer.isActive():
                self.recording_timer.stop()
            bind(lbl, "train.failed")
            btn_acc.hide()
            btn_rej.show()
            bind(btn_rej, "train.retry")
        elif "completed" in event_lower:
            if hasattr(self, "recording_timer") and self.recording_timer.isActive():
                self.recording_timer.stop()
            if action == "neutral":
                self._begin_training_sequence("push")
            else:
                self.push_anim_timer.stop()
                bind(lbl, "train.complete")
                self.drone_client.save_profile()
                self.push_next_btn.show()

    def _on_dev_data_update(self, signal: int, cq_list: list):
        """Update the EQ quality check screen with per-sensor contact quality."""
        # Only update when on the EQ check screen (index 3)
        if self.stacked_widget.currentIndex() != 3:
            return

        # Overall signal quality (0-4)
        signal_keys = {0: "quality.none", 1: "quality.very_bad", 2: "quality.poor",
                       3: "quality.fair", 4: "quality.good"}
        signal_colors = {0: "#da3633", 1: "#da3633", 2: "#e3a01a", 3: "#58a6ff", 4: "#3fb950"}
        key = signal_keys.get(signal)
        sig_text = t(key) if key else t("quality.unknown", value=signal)
        sig_color = signal_colors.get(signal, "#8b949e")
        bind(self.eq_overall_lbl, "eq.overall", quality=sig_text, value=signal)
        self.eq_overall_lbl.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {sig_color};"
            f"padding: 10px; background-color: #161b22; border: 1px solid {sig_color}; border-radius: 8px;"
        )

        # Per-sensor contact quality
        # CQ values: 0=No Signal, 1=Bad, 2=Poor, 3=Fair, 4=Good
        cq_colors = {0: "#da3633", 1: "#da3633", 2: "#e3a01a", 3: "#58a6ff", 4: "#3fb950"}
        cq_keys = {0: "quality.none", 1: "quality.bad", 2: "quality.poor",
                   3: "quality.fair", 4: "quality.good"}

        for i, cq_val in enumerate(cq_list):
            sensor_name = f"S{i}"
            cq_val_int = int(cq_val) if isinstance(cq_val, (int, float)) else 0
            color = cq_colors.get(cq_val_int, "#8b949e")
            cq_key = cq_keys.get(cq_val_int, "quality.short_unknown")

            if sensor_name not in self.eq_sensor_labels:
                name_lbl = QLabel(sensor_name)
                name_lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #e6edf3;")
                name_lbl.setFixedWidth(40)

                bar = QProgressBar()
                bar.setRange(0, 4)
                bar.setFixedHeight(20)
                bar.setTextVisible(False)

                status_lbl = bind(QLabel(), cq_key)
                status_lbl.setFixedWidth(80)

                row = len(self.eq_sensor_labels)
                self.eq_sensor_layout.addWidget(name_lbl, row, 0)
                self.eq_sensor_layout.addWidget(bar, row, 1)
                self.eq_sensor_layout.addWidget(status_lbl, row, 2)
                self.eq_sensor_labels[sensor_name] = (name_lbl, bar, status_lbl)

            _, bar, status_lbl = self.eq_sensor_labels[sensor_name]
            bar.setValue(cq_val_int)
            bar.setStyleSheet(
                f"QProgressBar {{ background-color: #21262d; border: 1px solid #30363d; border-radius: 4px; }}"
                f"QProgressBar::chunk {{ background-color: {color}; border-radius: 3px; }}"
            )
            bind(status_lbl, cq_key)
            status_lbl.setStyleSheet(f"color: {color}; font-size: 12px;")

        # Determine if quality is good enough to start training
        if cq_list:
            avg_cq = sum(int(v) if isinstance(v, (int, float)) else 0 for v in cq_list) / len(cq_list)
            good_enough = avg_cq >= 2.0 and signal >= 2
        else:
            good_enough = False

        if good_enough:
            bind(self.eq_status_lbl, "eq.ok")
            self.eq_status_lbl.setStyleSheet("font-size: 14px; color: #3fb950; margin-top: 10px;")
            self.eq_next_btn.setEnabled(True)
        else:
            bind(self.eq_status_lbl, "eq.bad")
            self.eq_status_lbl.setStyleSheet("font-size: 14px; color: #e3a01a; margin-top: 10px;")
            self.eq_next_btn.setEnabled(False)

    def _on_mc_config_update(self, data: dict):
        if hasattr(self, 'settings_dialog_ref') and self.settings_dialog_ref:
            self.settings_dialog_ref.handle_mc_config(data)

    def update_bci_telemetry(self, battery: int, signal: int):
        self.bci_telemetry_signal.emit(battery, signal)

    def _do_update_bci_telemetry(self, battery: int, signal: int):
        bind(self.bci_telem_lbl, "dash.headset", battery=battery, signal=signal)

    def _override_action_for_test(self):
        if not self.drone_client: return
        original_execute = self.drone_client.drone.execute_action
        
        def test_execute(action, auto_release_time=0.0):
            was_flying = self.drone_client.drone.is_flying
            original_execute(action, auto_release_time)
            is_flying = self.drone_client.drone.is_flying
            
            def _update_ui():
                ignored = (
                    (action == "TakeOff" and was_flying and is_flying)
                    or (action in ["Land", "EmergencyStop"] and not was_flying and not is_flying)
                    or (action.startswith("Flip") and not is_flying)
                )
                key = "test.last_command_ignored" if ignored else "test.last_command"
                bind(self.last_action_lbl, key, action=action)
                if is_flying and not was_flying:
                    bind(self.virtual_flight_state_lbl, "test.flying")
                    self.virtual_flight_state_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #3fb950;")
                elif not is_flying and was_flying:
                    bind(self.virtual_flight_state_lbl, "test.landed")
                    self.virtual_flight_state_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #8b949e;")
            QTimer.singleShot(0, _update_ui)
        self.drone_client.drone.execute_action = test_execute

    def reset_headset(self):
        if self.drone_client:
            self.drone_client.reset_center()
            self.log(t("log.recenter"))

    def toggle_fullscreen(self):
        if self.drone_sim.isFullScreen():
            self.drone_sim.setWindowFlags(Qt.WindowType.Widget)
            self.drone_sim.showNormal()
            self.state_layout.addWidget(self.drone_sim)
        else:
            self.drone_sim.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
            self.drone_sim.showFullScreen()
            self.drone_sim.setFocus()

    def check_drone_connection(self):
        self.connect_drone_btn.setEnabled(False)
        bind(self.drone_conn_status_lbl, "drone.connecting")

        is_sim = self.simulate_cb.isChecked()
        if is_sim:
            self.drone_connected_signal.emit(True, t("drone.sim_skip"))
            return

        def _connect():
            try:
                from djitellopy import Tello
                tello = Tello()
                tello.connect()
                batt = tello.get_battery()
                self.tello = tello
                self.drone_connected_signal.emit(True, t("drone.connected", battery=batt))
            except Exception as e:
                self.tello = None
                self.drone_connected_signal.emit(False, t("drone.failed", detail=e))

        threading.Thread(target=_connect, daemon=True).start()

    def _on_drone_connection_result(self, success, message):
        self.connect_drone_btn.setEnabled(True)
        # `message` is already-translated text, not a key.
        i18n.unbind(self.drone_conn_status_lbl)
        self.drone_conn_status_lbl.setText(message)
        
        if success:
            self.p2_next_btn.setEnabled(True)
            self.drone_conn_status_lbl.setStyleSheet("color: #3fb950; font-weight: bold;")
            if self.drone_client:
                self.drone_client.drone.tello = self.tello

    def go_to_dashboard(self):
        self.stacked_widget.setCurrentIndex(8)
        is_sim = self.simulate_cb.isChecked()
        bind(self.dash_drone_lbl, "dash.drone_sim" if is_sim else "dash.drone_connected")
        self.video_thread = VideoThread(tello=self.tello)
        self.video_thread.frame_ready.connect(self.update_camera)
        self.video_thread.status_update.connect(self.log)
        self.video_thread.start()

    def update_telemetry(self):
        if self.drone_client and self.stacked_widget.currentIndex() in [6, 8]:
            if self.drone_client and self.drone_client.drone:
                lr, fb, ud, yaw = self.drone_client.drone.get_rc_values()
                self.rc_lbl.setText(f"RC: lr={lr:+4d}  fb={fb:+4d}  ud={ud:+4d}  yaw={yaw:+4d}")
                if self.stacked_widget.currentIndex() == 6:
                    self.drone_sim.update_rc(lr, fb, ud, yaw)
                    self.test_yaw_bar.setValue(yaw)
                    self.test_fb_bar.setValue(fb)
                
                # Update MC Dashboard Indicator
                action = getattr(self.drone_client.drone, 'last_executed_action', None)
                action_time = getattr(self.drone_client.drone, 'last_action_time', 0.0)
                now = time.time()
                if action and (now - action_time) < 2.0:
                    bind(self.dash_mc_lbl, "dash.mc", action=action)
                    self.dash_mc_lbl.setStyleSheet(
                        "background-color: #1f6feb; border: 1px solid #58a6ff; border-radius: 6px;"
                        "padding: 8px 12px; color: #ffffff; font-size: 14px; font-weight: bold;"
                    )
                else:
                    bind(self.dash_mc_lbl, "dash.mc_none")
                    self.dash_mc_lbl.setStyleSheet(
                        "background-color: #0d1117; border: 1px solid #30363d; border-radius: 6px;"
                        "padding: 8px 12px; color: #8b949e; font-size: 14px; font-weight: bold;"
                    )
            
            mot_str = self.drone_client.latest_raw_mot[:120] + "..." if len(self.drone_client.latest_raw_mot) > 120 else self.drone_client.latest_raw_mot
            self.raw_mot_lbl.setText(f"MOT: {mot_str}")
            self.raw_com_lbl.setText(f"COM: {self.drone_client.latest_raw_com}")

        # Update Drone Dashboard Stats
        if self.tello and self.stacked_widget.currentIndex() == 3:
            try:
                bind(self.battery_lbl, "dash.battery", value=self.tello.get_battery())
                bind(self.height_lbl, "dash.height", value=self.tello.get_height())
                bind(self.temp_lbl, "dash.temp", value=self.tello.get_temperature())
            except Exception:
                pass

    def _disconnect_and_quit(self):
        """Clean up connection and return to setup page."""
        self.log(t("log.disconnecting"))
        if self.video_thread:
            self.video_thread.stop()
            self.video_thread.wait(1000)
            self.video_thread = None
        
        if self.drone_client:
            if getattr(self.drone_client, 'drone', None):
                self.drone_client.drone.stop_movement()
                self.drone_client.drone.is_flying = False
            self.drone_client.running = False
            if hasattr(self.drone_client, 'c'):
                try: self.drone_client.c.close()
                except: pass
            
        if self.tello:
            threading.Thread(target=self._safe_land_and_end, daemon=True).start()

        self.stacked_widget.setCurrentIndex(0)
        self.log(t("log.disconnected"))

    def _safe_land_and_end(self):
        try:
            self.tello.land()
        except:
            pass
        try:
            self.tello.end()
        except:
            pass
        self.tello = None

    def update_camera(self, img: QImage):
        scaled = img.scaled(self.camera_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.camera_label.setPixmap(QPixmap.fromImage(scaled))
        
        if hasattr(self, 'hud_widget') and self.hud_widget is not None:
            self.hud_widget.update_frame(img)

    def open_fullscreen_hud(self):
        if not hasattr(self, 'hud_widget') or self.hud_widget is None:
            self.hud_widget = FullscreenHUDWidget(main_app=self)
            # Setup an update timer for the HUD telemetry elements
            self.hud_timer = QTimer(self)
            self.hud_timer.timeout.connect(self.hud_widget.update)
            self.hud_timer.start(50)  # 20 FPS refresh for the HUD overlays

        self.hud_widget.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.hud_widget.showFullScreen()
        self.hud_widget.setFocus()
        self.log(t("log.hud_opened"))

    def close_fullscreen_hud(self):
        if hasattr(self, 'hud_widget') and self.hud_widget is not None:
            self.hud_timer.stop()
            self.hud_widget.close()
            self.hud_widget = None
        self.log(t("log.hud_closed"))

    # ─── Flight actions ───
    def takeoff(self):
        if self.tello:
            threading.Thread(target=self._safe_takeoff, daemon=True).start()
        elif self.drone_client:
            self.drone_client.drone.is_flying = True
            self.drone_client.drone.start_rc_loop()
            self.log(t("log.sim_takeoff"))

    def _safe_takeoff(self):
        try:
            self.tello.takeoff()
            # Default takeoff height is ~1.2m. The user wants ~1.6m.
            self.tello.move_up(40)
            if self.drone_client:
                self.drone_client.drone.is_flying = True
                self.drone_client.drone.start_rc_loop()
            self.log_signal.emit(t("log.airborne"))
        except Exception as e:
            self.log_signal.emit(t("log.takeoff_failed", detail=e))

    def land(self):
        if self.drone_client:
            self.drone_client.drone.stop_movement()
            self.drone_client.drone.is_flying = False
        if self.tello:
            threading.Thread(target=lambda: self._safe_cmd(self.tello.land, t("log.landed")), daemon=True).start()
        else:
            self.log(t("log.sim_landing"))

    def emergency_stop(self):
        if self.drone_client:
            self.drone_client.drone.stop_movement()
            self.drone_client.drone.is_flying = False
        if self.tello:
            threading.Thread(target=lambda: self._safe_cmd(self.tello.emergency, t("log.motors_stopped")), daemon=True).start()
        else:
            self.log(t("log.sim_emergency"))

    def _safe_cmd(self, func, ok_msg):
        try:
            func()
            self.log_signal.emit(ok_msg)
        except Exception as e:
            self.log_signal.emit(t("log.error", detail=e))

    def load_settings(self):
        c = self.config
        self.client_id_input.setText(c.get("client_id", ""))
        self.client_secret_input.setText(c.get("client_secret", ""))
        self.simulate_cb.setChecked(c.get("simulate", False))
        # Profile combo is populated dynamically; just remember the saved name
        # so _populate_profiles can re-select it once the list arrives.

    def save_settings(self):
        self.config["client_id"] = self.client_id_input.text()
        self.config["client_secret"] = self.client_secret_input.text()
        self.config["language"] = i18n.get_lang()
        # profile_name is set automatically by _populate_profiles when profiles arrive
        self.config["simulate"] = self.simulate_cb.isChecked()
        ConfigManager.save_config(self.config)

    def _apply_config_to_client(self):
        if self.drone_client and self.drone_client.program:
            qp = self.drone_client.program.quaternion_processor
            qp.invert_yaw = self.config.get("invert_yaw", False)
            qp.sens_left = self.config.get("sens_left", 70.0)
            qp.sens_right = self.config.get("sens_right", 70.0)
            qp.sens_fwd = self.config.get("sens_fwd", 50.0)
            qp.sens_back = self.config.get("sens_back", 50.0)
            qp.movement_deadzone = self.config.get("deadzone", 0.02)
            sw = self.config.get("smoothing_window", 4)
            qp.SmoothingWindow = sw
            qp._movement_buffer = __import__('collections').deque(maxlen=sw)
            
            # Update mental mappings
            mappings = self.config.get("mental_mappings", [])
            self.drone_client.program.mental_processor.mappings = mappings
            if hasattr(self.drone_client, 'drone'):
                mental_move_actions = {
                    m.get("action") for m in mappings
                    if m.get("action", "").startswith("Move")
                }
                self.drone_client.drone.set_mental_move_actions(mental_move_actions)

    def show_settings(self):
        dialog = SettingsDialog(self.config, self)
        self.settings_dialog_ref = dialog
        if dialog.exec():
            new_config = dialog.get_config()
            self.config.update(new_config)
            
            # Save the new configuration
            device_id = self.config.get("device_id", "")
            if device_id:
                device_type = device_id.split('-')[0]
                ConfigManager.update_device_profile(self.config, device_type, new_config)
            else:
                ConfigManager.save_config(self.config)
                
            # Apply to active client if running
            self._apply_config_to_client()

    def log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        formatted = f"[{ts}] {msg.strip()}"
        
        # Append to both terminals
        if hasattr(self, 'bci_log_terminal'):
            self.bci_log_terminal.appendPlainText(formatted)
            # scroll to bottom
            bar = self.bci_log_terminal.verticalScrollBar()
            bar.setValue(bar.maximum())

        if hasattr(self, 'terminal'):
            self.terminal.appendPlainText(formatted)
            bar = self.terminal.verticalScrollBar()
            bar.setValue(bar.maximum())

    def _append_log(self, msg: str):
        self.log(msg)

    def closeEvent(self, event):
        sys.stdout = self.original_stdout
        if self.drone_client:
            self.drone_client.running = False
            self.drone_client.drone.cleanup()
        if self.video_thread:
            self.video_thread.stop()
            self.video_thread.wait(2000)
        if self.tello:
            try: self.tello.end()
            except: pass
        event.accept()

class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("settings.title"))
        self.setMinimumWidth(400)
        self.config = config.copy()

        layout = QVBoxLayout(self)

        # Motion Settings. The dialog is modal and rebuilt on every open, so its
        # strings are resolved once here instead of going through bind().
        motion_group = QGroupBox(t("settings.motion"))
        motion_layout = QVBoxLayout()
        def add_slider(name, min_v, max_v, step, fmt_func, default_v, tooltip=""):
            row = QHBoxLayout()
            lbl = QLabel(f"{name} ⓘ" if tooltip else name)
            lbl.setFixedWidth(110)
            if tooltip:
                lbl.setToolTip(tooltip)
                lbl.setStyleSheet("QToolTip { font-size: 13px; color: #ffffff; background-color: #2b2b2b; border: 1px solid #58a6ff; padding: 4px; }")
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(min_v, max_v)
            slider.setSingleStep(step)
            slider.setValue(int(default_v))
            val_lbl = QLabel(fmt_func(default_v)); val_lbl.setFixedWidth(45)
            slider.valueChanged.connect(lambda v: val_lbl.setText(fmt_func(v)))
            row.addWidget(lbl); row.addWidget(slider); row.addWidget(val_lbl)
            slider.valueChanged.connect(self._live_update)
            motion_layout.addLayout(row)
            return slider

        self.invert_yaw_cb = QCheckBox(t("settings.invert_yaw"))
        self.invert_yaw_cb.setChecked(self.config.get("invert_yaw", False))
        self.invert_yaw_cb.stateChanged.connect(self._live_update)
        motion_layout.addWidget(self.invert_yaw_cb)

        self.sens_left_slider = add_slider(t("settings.sens_left"), 1, 300, 1, lambda x: f"{x:.0f}",
            self.config.get("sens_left", 70.0), t("settings.sens_left.tip"))
        self.sens_right_slider = add_slider(t("settings.sens_right"), 1, 300, 1, lambda x: f"{x:.0f}",
            self.config.get("sens_right", 70.0), t("settings.sens_right.tip"))
        self.sens_fwd_slider = add_slider(t("settings.sens_fwd"), 1, 300, 1, lambda x: f"{x:.0f}",
            self.config.get("sens_fwd", 50.0), t("settings.sens_fwd.tip"))
        self.sens_back_slider = add_slider(t("settings.sens_back"), 1, 300, 1, lambda x: f"{x:.0f}",
            self.config.get("sens_back", 50.0), t("settings.sens_back.tip"))

        self.dead_slider = add_slider(t("settings.deadzone"), 0, 500, 1, lambda x: f"{x/1000:.3f}",
            self.config.get("deadzone", 0.03) * 1000, t("settings.deadzone.tip"))
        self.smooth_slider = add_slider(t("settings.smoothing"), 1, 20, 1, str,
            self.config.get("smoothing_window", 6), t("settings.smoothing.tip"))
        self.speed_slider = add_slider(t("settings.max_speed"), 10, 100, 5, str,
            self.config.get("max_speed", 60), t("settings.max_speed.tip"))
        motion_group.setLayout(motion_layout)
        layout.addWidget(motion_group)

        # Emotiv API Settings
        emotiv_group = QGroupBox(t("settings.emotiv"))
        self.emotiv_layout = QVBoxLayout()
        self.emotiv_status_lbl = QLabel(t("settings.loading"))
        self.emotiv_status_lbl.setStyleSheet("color: #8b949e;")
        self.emotiv_layout.addWidget(self.emotiv_status_lbl)
        emotiv_group.setLayout(self.emotiv_layout)
        layout.addWidget(emotiv_group)
        
        self.mc_active_actions = []
        self.mc_sensitivities = []
        self.mc_sensitivity_sliders = []
        
        app = self.parent()
        if app and hasattr(app, 'drone_client') and app.drone_client:
            app.drone_client.get_mc_config()
        else:
            self.emotiv_status_lbl.setText(t("settings.not_connected"))

        # Mental Commands. The Cortex command names and drone action names are
        # protocol values, so they stay verbatim — only "None" is translated,
        # and the real value always travels in the item's userData.
        mental_group = QGroupBox(t("settings.mental"))
        self.mental_layout = QVBoxLayout()
        self.mapping_rows = []
        CMDS = ["None", "push", "pull", "lift", "drop", "click"]
        ACTIONS = [
            "None",
            "TakeOff", "Land", "EmergencyStop",
            "MoveForward", "MoveBack", "MoveLeft", "MoveRight", "MoveUp", "MoveDown",
            "FlipForward", "FlipBack", "FlipLeft", "FlipRight",
        ]

        def fill(combo, values):
            for value in values:
                combo.addItem(t("settings.none") if value == "None" else value, userData=value)

        mappings = self.config.get("mental_mappings", [])
        for i in range(4):
            row = QHBoxLayout()
            cmd_combo = QComboBox(); fill(cmd_combo, CMDS)
            action_combo = QComboBox(); fill(action_combo, ACTIONS)

            if i < len(mappings):
                idx = cmd_combo.findData(mappings[i].get("command", "None"))
                if idx >= 0: cmd_combo.setCurrentIndex(idx)
                idx = action_combo.findData(mappings[i].get("action", "None"))
                if idx >= 0: action_combo.setCurrentIndex(idx)

            cmd_combo.currentIndexChanged.connect(self._live_update)
            action_combo.currentIndexChanged.connect(self._live_update)
            
            row.addWidget(cmd_combo); row.addWidget(action_combo)
            self.mapping_rows.append({"command": cmd_combo, "action": action_combo})
            self.mental_layout.addLayout(row)
        mental_group.setLayout(self.mental_layout)
        layout.addWidget(mental_group)

        # Buttons
        btn_layout = QHBoxLayout()
        # "Save" button is now just "Close" since changes are live
        close_btn = QPushButton(t("settings.close")); close_btn.setObjectName("primaryBtn")
        close_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def handle_mc_config(self, event: dict):
        etype = event.get('type')
        data = event.get('data')
        
        if etype == 'active_actions':
            self.mc_active_actions = data
        elif etype == 'training_threshold':
            if hasattr(self, 'threshold_lbl'):
                self.threshold_lbl.deleteLater()
            self.threshold_lbl = QLabel(t(
                "settings.threshold",
                threshold=data.get('currentThreshold', 'N/A'),
                score=data.get('lastTrainingScore', 'N/A'),
            ))
            self.threshold_lbl.setStyleSheet("font-weight: bold; color: #58a6ff;")
            self.emotiv_layout.insertWidget(0, self.threshold_lbl)
        elif etype == 'action_sensitivity':
            self.mc_sensitivities = data
            self.emotiv_status_lbl.hide()
            self._build_sensitivity_sliders()
            
    def _build_sensitivity_sliders(self):
        for s in self.mc_sensitivity_sliders:
            s[0].deleteLater()
        self.mc_sensitivity_sliders.clear()
        
        if not self.mc_active_actions or not self.mc_sensitivities:
            return
            
        for i, action in enumerate(self.mc_active_actions):
            if i >= len(self.mc_sensitivities): break
            val = self.mc_sensitivities[i]
            
            row = QHBoxLayout()
            lbl = QLabel(t("settings.action_sens", action=action.capitalize()))
            lbl.setFixedWidth(110)
            
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(1, 10)
            slider.setSingleStep(1)
            slider.setValue(val)
            
            val_lbl = QLabel(str(val))
            val_lbl.setFixedWidth(20)
            slider.valueChanged.connect(lambda v, l=val_lbl: l.setText(str(v)))
            
            row.addWidget(lbl)
            row.addWidget(slider)
            row.addWidget(val_lbl)
            
            w = QWidget()
            w.setLayout(row)
            self.emotiv_layout.addWidget(w)
            
            self.mc_sensitivity_sliders.append((w, slider))

    def accept(self):
        # Save emotiv sensitivities
        if self.mc_active_actions and self.mc_sensitivity_sliders:
            new_sens = [s[1].value() for s in self.mc_sensitivity_sliders]
            if new_sens != self.mc_sensitivities:
                app = self.parent()
                if app and hasattr(app, 'drone_client') and app.drone_client:
                    app.drone_client.set_mc_sensitivity(new_sens)
        super().accept()

    def _live_update(self, *args):
        # Push current slider values to config instantly
        self.config["invert_yaw"] = self.invert_yaw_cb.isChecked()
        self.config["sens_left"] = float(self.sens_left_slider.value())
        self.config["sens_right"] = float(self.sens_right_slider.value())
        self.config["sens_fwd"] = float(self.sens_fwd_slider.value())
        self.config["sens_back"] = float(self.sens_back_slider.value())
        self.config["deadzone"] = self.dead_slider.value() / 1000.0
        self.config["smoothing_window"] = self.smooth_slider.value()
        self.config["max_speed"] = self.speed_slider.value()

        mappings = []
        for w in self.mapping_rows:
            cmd = w["command"].currentData()
            if cmd != "None":
                mappings.append({
                    "command": cmd,
                    "action": w["action"].currentData(),
                    "threshold": 0.5,
                    "auto_release": 0
                })
        self.config["mental_mappings"] = mappings
        
        ConfigManager.save_config(self.config)
        
        # Apply to active client immediately
        app = self.parent()
        if app and app.drone_client and app.drone_client.program:
            qp = app.drone_client.program.quaternion_processor
            qp.sens_left = self.config.get("sens_left", 70.0)
            qp.sens_right = self.config.get("sens_right", 70.0)
            qp.sens_fwd = self.config.get("sens_fwd", 50.0)
            qp.sens_back = self.config.get("sens_back", 50.0)
            qp.movement_deadzone = self.config.get("deadzone", 0.02)
            sw = self.config.get("smoothing_window", 6)
            qp.SmoothingWindow = sw
            # Don't reset deque here, too disruptive during live tweaking
            
            app.drone_client.program.mental_processor.mappings = mappings

    def get_config(self):
        # We still return the config just in case
        return self.config

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    window = TelloControllerApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
