import sys
import math
import serial
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QGridLayout
)
from PyQt5.QtCore import QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


# ===============================================================
# 기본 설정
# ===============================================================
GRID_SIZE = 8
FOV_DEG = 60.0

PORT_MOTOR = "/dev/ttyAMA2"   # Atmega128
PORT_STM32 = "/dev/ttyAMA3"   # STM32

BAUD = 115200


# ===============================================================
# 3D Viewer
# ===============================================================
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
        azims = [self.az_center - half_fov + i * FOV_DEG / (GRID_SIZE-1)
                 for i in range(GRID_SIZE)]

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


# ===============================================================
# 8×8 Distance GUI
# ===============================================================
class DistanceWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("8 × 8 Distance Array (cm)")
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


# ===============================================================
# UART Wrapper
# ===============================================================
class UARTDevice:
    def __init__(self, port, baud=115200):
        self.ser = serial.Serial(port, baudrate=baud, timeout=0.01)

    def read_line(self):
        try:
            line = self.ser.readline().decode(errors="ignore").strip()
            if line == "":
                return None
            return line
        except:
            return None

    def send(self, msg):
        print(f"TX({self.ser.port}): {msg.strip()}")
        try:
            self.ser.write(msg.encode())
        except:
            pass


# ===============================================================
# Main Controller
# ===============================================================
class MainController(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Raspberry Pi 3-Sensor Controller")
        self.setGeometry(850, 200, 260, 200)

        # UI 구성
        layout = QVBoxLayout()

        self.s_edit = QLineEdit()
        self.s_edit.setPlaceholderText("Enter sample count S")
        layout.addWidget(self.s_edit)

        self.start_btn = QPushButton("START ALL PROCESS")
        layout.addWidget(self.start_btn)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self.setLayout(layout)

        # 버튼 클릭 연결
        self.start_btn.clicked.connect(self.start_all_process)

        # UART
        self.uart_motor = UARTDevice(PORT_MOTOR, BAUD)
        self.uart_stm32 = UARTDevice(PORT_STM32, BAUD)

        # 하위 윈도우
        self.graph_win = GraphWindow()
        self.distance_win = DistanceWindow()

        # 내부 상태 변수
        self.S = 0
        self.C = 0
        self.SC = 0.0
        self.motor_active = False

        self.measure_active = False
        self.measure_buffer = []

        # 주기적 수신
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_loop)
        self.timer.start(20)

    # -----------------------------------------------------------
    # START 버튼 클릭
    # -----------------------------------------------------------
    def start_all_process(self):
        try:
            self.S = int(self.s_edit.text())
        except:
            self.status_label.setText("Invalid S")
            return

        self.C = 0
        self.SC = 360 / self.S
        self.motor_active = True
        self.measure_active = False

        self.status_label.setText("Motor rotation started")

        # 첫 step 전달
        self.send_SC()

    # -----------------------------------------------------------
    # SC 전송
    # -----------------------------------------------------------
    def send_SC(self):
        msg = f"{self.SC:.3f}\n"
        self.uart_motor.send(msg)
        print(f"[SC] Sent: {msg.strip()}")

    # -----------------------------------------------------------
    # 주기업데이트 (UART 수신)
    # -----------------------------------------------------------
    def update_loop(self):
        # ------------------ MOTOR UART ------------------
        msg = self.uart_motor.read_line()
        if msg:
            print(f"[Motor RX] {msg}")

            if msg == "MF" and self.motor_active:
                self.C += 1
                print(f"COUNT = {self.C}/{self.S}")

                # 더 step 남아 있으면 3초 뒤 다음 step
                if self.C < self.S:
                    QTimer.singleShot(3000, self.send_SC)
                else:
                    print("Motor 360° completed!")
                    self.motor_active = False

                    # 스텝 완료 → STM32 측정 시작
                    self.uart_stm32.send("start measure\n")
                    self.measure_buffer = []
                    self.measure_active = True

            elif msg == "RF":
                print("Motor RF received")
                self.motor_active = False

        # ------------------ STM32 UART ------------------
        data = self.uart_stm32.read_line()
        if data:
            print(f"[STM32 RX] {data}")

            if data == "measure done":
                print("Measurement Finished!")

                # 버퍼에 저장된 마지막측정값 플로팅
                if len(self.measure_buffer) == 64:
                    self.graph_win.update_plot(self.measure_buffer)
                    self.distance_win.update_distances(self.measure_buffer)

                # 측정 완료 → Atmega128 에 reset angle
                self.uart_motor.send("reset angle\n")

                self.measure_active = False

            else:
                # CSV 데이터 처리
                parts = data.split(",")
                if len(parts) == 64:
                    tmp = []
                    for x in parts:
                        try:
                            tmp.append(float(x) / 10.0)
                        except:
                            tmp.append(None)

                    self.measure_buffer = tmp
                    self.graph_win.update_plot(tmp)
                    self.distance_win.update_distances(tmp)

        # ------------------ reset done  ------------------
        msg2 = self.uart_motor.read_line()
        if msg2 == "reset done":
            print("All process finished")
            self.status_label.setText("All process finished")

    # -----------------------------------------------------------
    def start(self):
        self.show()
        self.graph_win.show()
        self.distance_win.show()


# ===============================================================
# 실행
# ===============================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    controller = MainController()
    controller.start()
    sys.exit(app.exec_())
