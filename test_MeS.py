import sys
import math
import serial
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QGridLayout
)
from PyQt5.QtCore import QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

GRID_SIZE = 8
FOV_DEG = 60.0

# ============================================================
# 3D 그래프 창
# ============================================================
class GraphWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("3D Distance Viewer")
        self.setGeometry(500, 200, 600, 540)

        self.fig = Figure(figsize=(6, 4))
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111, projection='3d')

        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)

        self.az_center = 0.0
        self.elevs = [30, 15, 0, -15, -30, -45, -60, -75]
        self.reset_axis()

    def reset_axis(self):
        self.ax.cla()
        self.ax.set_xlim(-10, 10)
        self.ax.set_ylim(-10, 10)
        self.ax.set_zlim(-10, 10)
        self.ax.set_xlabel("X")
        self.ax.set_ylabel("Y")
        self.ax.set_zlabel("Z")
        self.ax.view_init(elev=20, azim=-60)

    def update_plot(self, dist_list_cm):
        if len(dist_list_cm) != GRID_SIZE**2:
            return

        half_fov = FOV_DEG / 2.0
        azims = [self.az_center - half_fov + i * FOV_DEG / (GRID_SIZE-1) for i in range(GRID_SIZE)]
        pts = []

        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                dist = dist_list_cm[r*GRID_SIZE + c]
                if dist is None:
                    continue
                az = math.radians(azims[c])
                el = math.radians(self.elevs[r])
                x = dist * math.sin(az) * math.cos(el)
                y = dist * math.cos(az) * math.cos(el)
                z = dist * math.sin(el)
                pts.append((x, y, z))

        self.reset_axis()
        if pts:
            xs, ys, zs = zip(*pts)
            self.ax.scatter(xs, ys, zs, c='red', s=50)
        self.ax.scatter([0], [0], [0], c='blue', s=50)
        self.canvas.draw()


# ============================================================
# 8×8 거리 표
# ============================================================
class DistanceWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("8x8 Distance Array (cm)")
        self.setGeometry(200, 200, 400, 400)

        layout = QGridLayout()
        self.labels = [[QLabel("0.0") for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                layout.addWidget(self.labels[r][c], r, c)
        self.setLayout(layout)

    def update_distances(self, dist_list_cm):
        for i, val in enumerate(dist_list_cm):
            r = i // GRID_SIZE
            c = i % GRID_SIZE
            if val is None:
                self.labels[r][c].setText("∞")
            else:
                self.labels[r][c].setText(f"{val:.2f}")


# ============================================================
# UART 수신/송신
# ============================================================
class UARTReceiver:
    def __init__(self, port="/dev/ttyAMA3", baud=115200):
        self.ser = serial.Serial(port, baudrate=baud, timeout=0.1)

    def read_line(self):
        try:
            line = self.ser.readline().decode(errors='ignore').strip()
            if not line:
                return None
            return line
        except:
            return None

    def send(self, msg):
        try:
            self.ser.write(msg.encode())
        except:
            pass


# ============================================================
# 컨트롤러 + 버튼
# ============================================================
class MainController(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UART Controller")
        self.setGeometry(850, 200, 200, 120)

        layout = QVBoxLayout()
        self.btn_send = QPushButton("Send MeS")
        layout.addWidget(self.btn_send)
        self.setLayout(layout)

        self.btn_send.clicked.connect(self.send_mes_signal)

        # 하위 윈도우
        self.graph_win = GraphWindow()
        self.distance_win = DistanceWindow()

        # UART
        self.uart = UARTReceiver("/dev/ttyAMA3", 115200)

        # 주기적 수신
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_loop)
        self.timer.start(50)

    def send_mes_signal(self):
        self.uart.send("MeS\n")  # 반드시 개행 포함
        print("MeS sent")

    def update_loop(self):
        line = self.uart.read_line()
        if not line:
            return

        print(f"Received: {line}")

        if line == "MeF":
            print("Finish")
            return

        parts = line.split(",")
        if len(parts) != GRID_SIZE**2:
            print(f"Invalid data length: {len(parts)} (expected {GRID_SIZE**2})")
            return

        dist_list_cm = []
        for x in parts:
            try:
                dist_list_cm.append(float(x)/10.0)
            except:
                dist_list_cm.append(None)

        self.graph_win.update_plot(dist_list_cm)
        self.distance_win.update_distances(dist_list_cm)

    def start(self):
        self.show()
        self.graph_win.show()
        self.distance_win.show()


# ============================================================
# 실행
# ============================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    controller = MainController()
    controller.start()
    sys.exit(app.exec_())
