import sys
import serial
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton
from PyQt5.QtCore import QTimer

PORT = "/dev/ttyAMA2"   # UART port
BAUD = 115200

class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UART SC Sender with MF Delay")
        self.setGeometry(400, 200, 300, 150)

        self.ser = serial.Serial(PORT, BAUD, timeout=0.01)

        self.S = 0                 # number of samples
        self.C = 0                 # current count
        self.SC = 0.0              # angle increment to send
        self.transmission_active = False  # stop flag on RF

        layout = QVBoxLayout()

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

        # UART receive timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_uart)
        self.timer.start(10)

    # --------------------------------------------------------
    def start_process(self):
        try:
            self.S = int(self.s_input.text())
        except:
            self.info_label.setText("Invalid input for S")
            return

        self.C = 0
        self.SC = 360 / self.S
        self.transmission_active = True

        print(f"=== START ===")
        print(f"S = {self.S}, SC = {self.SC:.3f}°")

        # Send first SC
        self.send_SC()
        self.info_label.setText(f"Transmission started: SC={self.SC:.2f}°")

    # --------------------------------------------------------
    def send_SC(self):
        if not self.transmission_active:
            return
        msg = f"{self.SC:.3f}\n"
        self.ser.write(msg.encode('utf-8'))
        print(f"TX(SC): {msg.strip()}")

    # --------------------------------------------------------
    def check_uart(self):
        if self.ser.in_waiting > 0:
            data = self.ser.readline().decode(errors="ignore").strip()
            if data == "":
                return

            print(f"RX: {data}")
            self.received_label.setText(f"Received data: {data}")

            # RF has priority: stop all transmission immediately
            if data == "RF":
                self.transmission_active = False
                print("=== FINISH (RF received, transmission stopped) ===")
                return

            # Only process MF if transmission is active
            if self.transmission_active and data == "MF":
                self.C += 1
                print(f"COUNT = {self.C}/{self.S}")

                if self.C < self.S:
                    # Delay 3 seconds before sending next SC
                    QTimer.singleShot(3000, self.send_SC)
                else:
                    print("=== All SC transmissions completed ===")
                    self.transmission_active = False

# --------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Window()
    w.show()
    sys.exit(app.exec_())
