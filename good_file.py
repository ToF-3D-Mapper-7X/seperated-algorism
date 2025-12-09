import sys
import math
import serial
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QGridLayout
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
        self.all_points = []  # 누적 포인트
        self.reset_axis()

    def reset_axis(self):
        self.ax.cla()
        self.ax.set_xlim(-20, 20)
        self.ax.set_ylim(-20, 20)
        self.ax.set_zlim(-20, 20)
        self.ax.set_xlabel("X (cm)")
        self.ax.set_ylabel("Y (cm)")
        self.ax.set_zlabel("Z (cm)")
        self.ax.view_init(elev=20, azim=-60)
        try:
            self.ax.set_box_aspect((1, 1, 1))
        except:
            pass

    def update_plot(self, dist_list_cm):
        if len(dist_list_cm) != GRID_SIZE**2:
            return

        half_fov = FOV_DEG / 2.0
        azims = [self.az_center - half_fov + i * FOV_DEG / (GRID_SIZE - 1)
                 for i in range(GRID_SIZE)]

        new_pts = []
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                dist = dist_list_cm[r * GRID_SIZE + c]
                if dist is None or dist <= 0:
                    continue
                az = math.radians(azims[c])
                el = math.radians(self.elevs[r])
                x = dist * math.sin(az) * math.cos(el)
                y = dist * math.cos(az) * math.cos(el)
                z = dist * math.sin(el)
                new_pts.append((x, y, z))

        if not new_pts:
            return

        self.all_points.extend(new_pts)
        self.reset_axis()

        xs, ys, zs = zip(*self.all_points)
        self.ax.scatter(xs, ys, zs, c='red', s=2)  # 점 색상/크기 변경
        self.ax.scatter([0], [0], [0], c='blue', s=30)  # 센서 위치

        # 시야축(FOV 중앙 방향) 표시
        fov_length = 60
        az = math.radians(self.az_center)
        el = math.radians(0)
        x = fov_length * math.sin(az) * math.cos(el)
        y = fov_length * math.cos(az) * math.cos(el)
        z = fov_length * math.sin(el)
        self.ax.plot([0, x], [0, y], [0, z], c='red', linewidth=2)

        self.canvas.draw()


# ============================================================
# 8×8 거리 표
# ============================================================
class DistanceWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("8x8 Distance Array (cm)")
        self.setGeometry(0, 0, 400, 400)
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
    def __init__(self, port, baud=115200):
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
# 메인 컨트롤러
# ============================================================
class MainController(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UART Controller")
        self.setGeometry(850, 200, 400, 200)

        main_layout = QVBoxLayout()
        input_layout = QHBoxLayout()

        # S 입력
        self.s_input = QLineEdit()
        self.s_input.setPlaceholderText("Enter number of samples S")
        input_layout.addWidget(self.s_input)

        # 좌표 표시용 QLabel
        self.coord_label = QLabel("Current angle: 0°")
        input_layout.addWidget(self.coord_label)

        # 8x8 배열창 추가
        self.distance_win = DistanceWindow()
        input_layout.addWidget(self.distance_win)

        main_layout.addLayout(input_layout)

        # START 버튼
        self.start_btn = QPushButton("START")
        self.start_btn.clicked.connect(self.start_process)
        main_layout.addWidget(self.start_btn)

        # 정보/수신 데이터 표시
        self.info_label = QLabel("")
        main_layout.addWidget(self.info_label)
        self.received_label = QLabel("Received data:")
        main_layout.addWidget(self.received_label)

        self.setLayout(main_layout)

        # 3D 그래프
        self.graph_win = GraphWindow()

        # UART
        self.uart_alg = UARTReceiver("/dev/ttyAMA2")  # UART2
        self.uart_mes = UARTReceiver("/dev/ttyAMA3")

        # 상태 변수
        self.S = 0
        self.SC = 0.0
        self.C = 0
        self.transmission_active = False
        self.wait_for_rf = False

        # 타이머
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_loop)
        self.timer.start(50)

    # --------------------------------------------------------
    def start_process(self):
        try:
            self.S = int(self.s_input.text())
        except:
            self.info_label.setText("Invalid input for S")
            return

        self.SC = 360 / self.S
        self.C = 0
        self.transmission_active = True
        self.wait_for_rf = False

        print(f"=== START ===")
        print(f"S = {self.S}, SC = {self.SC:.3f}°")
        self.info_label.setText(f"Transmission started: SC={self.SC:.2f}°")

        # 첫 SC 전송
        self.send_SC()
        self.graph_win.show()

    # SC 전송
    def send_SC(self):
        if not self.transmission_active:
            return
        msg = f"{self.SC:.3f}\n"
        self.uart_alg.send(msg)
        print(f"TX(SC): {msg.strip()}")

    # MeS 전송
    def send_MeS(self):
        self.uart_mes.send("MeS\n")
        print("MeS sent")

    # UART 수신 처리
    def update_loop(self):
        if self.wait_for_rf:
            line_alg = self.uart_alg.read_line()
            if line_alg:
                print(f"RX Alg: {line_alg}")
                if line_alg == "RF":
                    print("=== RF received, transmission ended ===")
                    self.wait_for_rf = False
            return

        line_alg = self.uart_alg.read_line()
        if line_alg:
            print(f"RX Alg: {line_alg}")
            if line_alg == "RF":
                self.transmission_active = False
                print("=== RF received, transmission ended ===")
                return
            if line_alg == "MF":
                print("MF received, triggering MeS in 2s")
                QTimer.singleShot(2000, self.send_MeS)

        line_mes = self.uart_mes.read_line()
        if line_mes:
            print(f"RX MeS: {line_mes}")
            self.received_label.setText(f"Received data: {line_mes}")

            parts = line_mes.split(",")
            if len(parts) == GRID_SIZE**2:
                dist_list_cm = []
                for x in parts:
                    try:
                        dist_list_cm.append(float(x) / 10.0)
                    except:
                        dist_list_cm.append(None)

                current_angle = self.C * self.SC
                self.graph_win.az_center = current_angle
                self.coord_label.setText(f"Current angle: {current_angle:.2f}°")

                self.graph_win.update_plot(dist_list_cm)
                self.distance_win.update_distances(dist_list_cm)

                self.C += 1
                print(f"COUNT = {self.C}/{self.S}")

                if self.C < self.S:
                    QTimer.singleShot(100, self.send_SC)
                elif self.C == self.S:
                    # RM 신호를 UART2로 전송
                    self.uart_alg.send("RM")
                    print("== RM sent to UART2, waiting for RF ==")
                    self.transmission_active = False
                    self.wait_for_rf = True

    # --------------------------------------------------------
    def start(self):
        self.show()


# ============================================================
# 실행
# ============================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    controller = MainController()
    controller.start()
    sys.exit(app.exec_())
