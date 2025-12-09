import sys
import math
import serial
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QGridLayout
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

        self.az_center = 0.0                      # 센서 중앙 방위각(터릿 회전 각도)
        self.elevs = [30, 15, 0, -15, -30, -45, -60, -75]

        # ★ 누적 포인트 저장용 리스트
        self.all_points = []

        self.reset_axis()

    def reset_axis(self):
        self.ax.cla()
        # 거리 단위가 cm라서 대충 -200~200 정도로 잡음 (원하면 조절 가능)
        self.ax.set_xlim(-200, 200)
        self.ax.set_ylim(-200, 200)
        self.ax.set_zlim(-200, 200)
        self.ax.set_xlabel("X (cm)")
        self.ax.set_ylabel("Y (cm)")
        self.ax.set_zlabel("Z (cm)")
        self.ax.view_init(elev=20, azim=-60)
        # 3D 비율 맞추기 (정육면체 비율)
        try:
            self.ax.set_box_aspect((1, 1, 1))
        except:
            pass  # 오래된 matplotlib이면 없어도 동작하게

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

                # 전방(y축), 오른쪽(x축), 위(z축) 기준 좌표
                x = dist * math.sin(az) * math.cos(el)
                y = dist * math.cos(az) * math.cos(el)
                z = dist * math.sin(el)

                new_pts.append((x, y, z))

        if not new_pts:
            return

        # ★ 이번 프레임에서 계산된 포인트들을 누적 리스트에 추가
        self.all_points.extend(new_pts)

        # ★ 축 초기화 후, 누적된 모든 포인트를 다시 그림
        self.reset_axis()

        xs, ys, zs = zip(*self.all_points)
        self.ax.scatter(xs, ys, zs, c='red', s=5)      # 누적 거리 포인트
        self.ax.scatter([0], [0], [0], c='blue', s=30) # 센서 위치

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
        self.setWindowTitle("UART Controller with S Input")
        self.setGeometry(850, 200, 250, 180)

        layout = QVBoxLayout()

        # S 입력 UI
        self.s_input = QLineEdit()
        self.s_input.setPlaceholderText("Enter number of samples S")
        layout.addWidget(self.s_input)

        self.start_btn = QPushButton("START")
        self.start_btn.clicked.connect(self.start_process)
        layout.addWidget(self.start_btn)

        self.info_label = QLabel("")
        layout.addWidget(self.info_label)

        self.received_label = QLabel("Received data:")
        layout.addWidget(self.received_label)

        self.setLayout(layout)

        # 하위 윈도우
        self.graph_win = GraphWindow()
        self.distance_win = DistanceWindow()

        # UART
        self.uart_alg = UARTReceiver("/dev/ttyAMA2")  # SC 전송용
        self.uart_mes = UARTReceiver("/dev/ttyAMA3")  # MeS 전송/수신

        # 상태 변수
        self.S = 0
        self.SC = 0.0
        self.C = 0
        self.transmission_active = False

        # 타이머
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_loop)
        self.timer.start(50)

    def start_process(self):
        try:
            self.S = int(self.s_input.text())
        except:
            self.info_label.setText("Invalid input for S")
            return

        self.SC = 360 / self.S
        self.C = 0
        self.transmission_active = True

        print(f"=== START ===")
        print(f"S = {self.S}, SC = {self.SC:.3f}°")
        self.info_label.setText(f"Transmission started: SC={self.SC:.2f}°")

        # 첫 SC 전송
        self.send_SC()
        self.graph_win.show()
        self.distance_win.show()

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
        # Algorism UART
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

        # MeS UART
        line_mes = self.uart_mes.read_line()
        if line_mes:
            print(f"RX MeS: {line_mes}")
            self.received_label.setText(f"Received data: {line_mes}")

            # 64배열 수신 완료 시 C 증가 + 화면 갱신
            parts = line_mes.split(",")
            if len(parts) == GRID_SIZE**2:
                dist_list_cm = []
                for x in parts:
                    try:
                        dist_list_cm.append(float(x)/10.0)
                    except:
                        dist_list_cm.append(None)

                self.graph_win.update_plot(dist_list_cm)
                self.distance_win.update_distances(dist_list_cm)

                self.C += 1
                print(f"COUNT = {self.C}/{self.S}")

                if self.C < self.S:
                    QTimer.singleShot(100, self.send_SC)
                else:
                    print("=== All SC transmissions completed ===")
                    self.transmission_active = False

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
