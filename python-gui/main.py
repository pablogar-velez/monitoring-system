import sys
import os
import csv
import subprocess
import serial
import serial.tools.list_ports
import threading
import pyqtgraph as pg
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QTextEdit, QLabel, QComboBox, QMessageBox, QFrame, QSizePolicy,
    QTabWidget, QStyle, QLineEdit, QFileDialog
)
from PyQt5.QtCore import pyqtSignal, QObject, Qt, QRectF
from PyQt5.QtGui import QPainter, QColor, QFont, QLinearGradient, QPen, QPainterPath

# Color palette
COLORS = {
    'background': '#f8f9fa',
    'primary': '#2c3e50',
    'secondary': '#34495e',
    'accent': '#3498db',
    'text': '#2c3e50',
    'success': '#2ecc71',
    'warning': '#f39c12',
    'danger': '#e74c3c',
    'card_bg': '#ffffff',
    'border': '#dfe6e9'
}

## Custom widget for temperature (vertical bar thermometer - centered)
class ThermometerWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.temperature = 20  # Default temperature
        self.setMinimumSize(200, 200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_temperature(self, temperature):
        # Clamp temperature between -25°C and 55°C
        self.temperature = max(-25, min(55, temperature))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        size = min(width, height) - 20  # Padding of 10 on each side
        rect = QRectF((width - size) / 2, (height - size) / 2, size, size)

        # Draw the background circle
        painter.setPen(QPen(Qt.lightGray, 14))
        painter.drawArc(rect, 0, 360 * 16)

        # Map temperature to angle (from -25°C to 55°C → 0° to 180°)
        angle_range = 180
        temp_min = -25
        temp_max = 55
        sweep_angle = ((self.temperature - temp_min) / (temp_max - temp_min)) * angle_range

        # Determine color based on temperature
        if self.temperature < 10:
            color = QColor('#3498db')  # Cool blue
        elif self.temperature > 30:
            color = QColor('#e67e22')  # Warm orange
        else:
            color = QColor('#2ecc71')  # Comfortable green

        # Draw the temperature arc
        painter.setPen(QPen(color, 14, Qt.SolidLine, Qt.RoundCap))
        start_angle = 180  # Start at 9 o'clock position
        painter.drawArc(rect, (360 - start_angle) * 16, -sweep_angle * 16)

        # Draw the temperature text in the center
        painter.setPen(Qt.black)
        font = QFont("Arial", 12, QFont.Bold)  # Set custom font
        painter.setFont(font)
        text = f"{self.temperature:.1f} °C"
        painter.drawText(self.rect(), Qt.AlignCenter, text)


# Custom widget for humidity (centered inverted drop)
class HumidityWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.humidity = 50
        self.setMinimumSize(120, 180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
    def set_humidity(self, humidity):
        self.humidity = max(0, min(100, humidity))
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        width = self.width()
        height = self.height()
        
        # Drop dimensions (fully centered)
        drop_width = min(width, height) * 0.7
        drop_height = drop_width * 1.1
        center_x = width / 2
        drop_top = (height - drop_height) / 2  
        
        # Create inverted drop path
        drop_path = QPainterPath()
        drop_path.moveTo(center_x, drop_top + drop_height)  # Bottom center
        
        # Right curve
        drop_path.cubicTo(
            center_x + drop_width/2, drop_top + drop_height,
            center_x + drop_width/2, drop_top + drop_height/2,
            center_x, drop_top
        )
        
        # Left curve
        drop_path.cubicTo(
            center_x - drop_width/2, drop_top + drop_height/2,
            center_x - drop_width/2, drop_top + drop_height,
            center_x, drop_top + drop_height
        )
        
        # Draw drop outline
        painter.setPen(QPen(QColor('#3498db'), 2))
        painter.setBrush(QColor('#f8f9fa'))  
        painter.drawPath(drop_path)
        
        # Draw water level (from bottom)
        water_level = drop_height * (self.humidity / 100)
        water_path = QPainterPath()
        water_path.addRect(
            center_x - drop_width/2,
            drop_top + drop_height - water_level,
            drop_width,
            water_level
        )
        
        # Water gradient 
        water_gradient = QLinearGradient(0, drop_top + drop_height - water_level, 0, drop_top + drop_height)
        water_gradient.setColorAt(0, QColor('#74b9ff'))  
        water_gradient.setColorAt(1, QColor('#0984e3'))  
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(water_gradient)
        painter.drawPath(drop_path.intersected(water_path))
        
        # Draw percentage (centered)
        
        painter.setPen(Qt.black)
        font = QFont('Arial', 12, QFont.Bold)
        painter.setFont(font)
        percentage = f"{self.humidity:.0f}%"
        text_width = painter.fontMetrics().width(percentage)
        painter.setPen(QColor('#2c3e50'))  
        painter.drawText(center_x - text_width/2, center_x + 5, percentage)
        
        # Draw label (centered below)
        painter.setPen(Qt.black)
        font = QFont('Arial', 12)
        painter.setFont(font)
        label = "Humidity"
        text_width = painter.fontMetrics().width(label)
        painter.drawText(center_x - text_width/2, drop_top + drop_height + 20, label)

# Custom widget for CO2 (modern indicator)
class CO2Widget(QWidget):
    def __init__(self):
        super().__init__()
        self.co2 = 800
        self.setMinimumSize(200, 100)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
    def set_co2(self, co2):
        self.co2 = co2
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        width = self.width()
        height = self.height()
        
        # Determine color and status based on CO2 level
        if self.co2 < 800:
            color = QColor('#00b894')
            status = "Excellent"
        elif self.co2 < 1200:
            color = QColor('#fdcb6e')
            status = "Good"
        else:
            color = QColor('#e17055')
            status = "Poor"
        
        # Draw background
        painter.setBrush(QColor(COLORS['card_bg']))
        painter.setPen(QPen(QColor(COLORS['border']), 1))
        
        # Draw indicator circle
        circle_size = min(width, height) * 0.9
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(width//2 - circle_size//2, height//2 - circle_size//2, 
                          circle_size, circle_size)
        
        # Draw CO2 value
        painter.setPen(Qt.black)
        font = QFont('Arial', 12, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor(COLORS['text']))
        painter.drawText(width//2 - 30, height//2 + 5, f"{self.co2:.0f} ppm")
        
        # Draw status text
        painter.setPen(Qt.black)
        font = QFont('Arial', 12)
        painter.setFont(font)
        painter.drawText(width//2 - 30, height//2 + 30, status)

class DataReceiver(QObject):
    data_received = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.running = False
        self.thread = None
        self.process = None
        self.serial_port = None

    def start_simulator(self):
        self.running = True
        self.thread = threading.Thread(target=self.read_from_simulator)
        self.thread.start()

    def start_serial(self, port, baudrate=9600):
        self.running = True
        self.thread = threading.Thread(target=self.read_from_serial, args=(port, baudrate))
        self.thread.start()

    def stop(self):
            self.running = False
            if self.process:
                self.process.terminate()
                self.process.wait()
                self.process = None
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
                self.serial_port = None
            if self.thread:
                self.thread.join(timeout=1.0)
                self.thread = None

    def read_from_simulator(self):
        simulator_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'simulator', 'simulator.exe'))

        try:
            self.process = subprocess.Popen(
                [simulator_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            while self.running:
                line = self.process.stdout.readline()
                if line:
                    self.data_received.emit(line.strip())
        except Exception as e:
            self.data_received.emit(f"Error running simulator: {e}")

    def read_from_serial(self, port, baudrate):
        try:
            self.serial_port = serial.Serial(port, baudrate, timeout=1)
            while self.running:
                line = self.serial_port.readline().decode('utf-8').strip()
                if line:
                    self.data_received.emit(line)
        except serial.SerialException as e:
            self.data_received.emit(f"Serial port error: {e}")

class MonitoringApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Environmental Monitoring System")
        self.setWindowIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        self.receiver = DataReceiver()
        self.receiver.data_received.connect(self.update_display)
        self.receiver.data_received.connect(self.update_graphs)
        self.receiver.data_received.connect(self.update_widgets)
        self.data = []
        self.init_ui()
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
            }}
            QPushButton {{
                background-color: {COLORS['primary']};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {COLORS['accent']};
            }}
            QPushButton:disabled {{
                background-color: {COLORS['secondary']};
                color: #95a5a6;
            }}
            QTextEdit, QComboBox {{
                background-color: {COLORS['card_bg']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 4px;
            }}
            QLabel {{
                font-weight: bold;
                color: {COLORS['primary']};
            }}
            QFrame {{
                background-color: {COLORS['card_bg']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Control panel
        control_frame = QFrame()
        control_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        control_layout = QVBoxLayout(control_frame)
        control_layout.setContentsMargins(15, 15, 15, 15)
        control_layout.setSpacing(10)

        # Source selection
        source_layout = QHBoxLayout()
        source_layout.addWidget(QLabel("Data Source:"))
        self.source_selector = QComboBox()
        self.source_selector.addItems(["Simulator", "Microcontroller"])
        self.source_selector.currentTextChanged.connect(self.toggle_com_selector)
        source_layout.addWidget(self.source_selector)
        control_layout.addLayout(source_layout)

        # COM port selection
        self.com_layout = QHBoxLayout()
        self.com_selector = QComboBox()
        self.refresh_button = QPushButton("Refresh Ports")
        self.refresh_button.clicked.connect(self.update_com_ports)
        self.com_layout.addWidget(QLabel("COM Port:"))
        self.com_layout.addWidget(self.com_selector)
        self.com_layout.addWidget(self.refresh_button)
        self.com_widget = QWidget()
        self.com_widget.setLayout(self.com_layout)
        self.com_widget.setVisible(False)
        control_layout.addWidget(self.com_widget)

        #Baudrate Selection
        self.baud_layout = QHBoxLayout()
        self.baud_label = QLabel("Baud Rate:")
        self.baud_selector = QComboBox()
        self.baud_selector.addItems(["9600", "19200", "38400", "57600", "115200", "Custom"])
        self.baud_selector.currentTextChanged.connect(self.update_baud_rate)
        self.custom_baud = QLineEdit()
        self.custom_baud.setPlaceholderText("Enter custom baud rate")
        self.custom_baud.setVisible(False)
        
        self.baud_layout.addWidget(self.baud_label)
        self.baud_layout.addWidget(self.baud_selector)
        self.baud_layout.addWidget(self.custom_baud)
        control_layout.addLayout(self.baud_layout)
        
        self.current_baudrate = 9600  # Valor por defecto


        # Button row
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Monitoring")
        self.start_button.clicked.connect(self.start_data_acquisition)
        self.stop_button = QPushButton("Stop Monitoring")
        self.stop_button.clicked.connect(self.stop_data_acquisition)
        self.stop_button.setEnabled(False)
        self.save_button = QPushButton("Save Data")
        self.save_button.clicked.connect(self.save_data)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.save_button)
        control_layout.addLayout(button_layout)

        main_layout.addWidget(control_frame)

        # Sensor widgets row
        sensor_frame = QFrame()
        sensor_layout = QHBoxLayout(sensor_frame)
        sensor_layout.setContentsMargins(10, 10, 10, 10)
        sensor_layout.setSpacing(20)

        # Temperature widget
        temp_group = QFrame()
        temp_layout = QVBoxLayout(temp_group)
        temp_layout.addWidget(QLabel("Temperature"))
        self.temperature_widget = ThermometerWidget()
        temp_layout.addWidget(self.temperature_widget)
        sensor_layout.addWidget(temp_group)

        # Humidity widget
        hum_group = QFrame()
        hum_layout = QVBoxLayout(hum_group)
        hum_layout.addWidget(QLabel("Humidity"))
        self.humidity_widget = HumidityWidget()
        hum_layout.addWidget(self.humidity_widget)
        sensor_layout.addWidget(hum_group)

        # CO2 widget
        co2_group = QFrame()
        co2_layout = QVBoxLayout(co2_group)
        co2_layout.addWidget(QLabel("CO2 Level"))
        self.co2_widget = CO2Widget()
        co2_layout.addWidget(self.co2_widget)
        sensor_layout.addWidget(co2_group)

        main_layout.addWidget(sensor_frame)

        # Data display and graphs
        data_frame = QFrame()
        data_layout = QVBoxLayout(data_frame)
        data_layout.setContentsMargins(10, 10, 10, 10)
        data_layout.setSpacing(10)

        # Console output
        self.display = QTextEdit()
        self.display.setReadOnly(True)
        self.display.setMinimumHeight(100)
        data_layout.addWidget(QLabel("Console Output:"))
        data_layout.addWidget(self.display)

        # Graphs for real-time data
        graph_tab = QTabWidget()
        
        # Temperature graph
        self.temperature_graph = pg.PlotWidget()
        self.temperature_graph.setBackground(COLORS['card_bg'])
        self.temperature_graph.setTitle("Temperature (°C)", color=COLORS['text'], size="12pt")
        self.temperature_graph.setLabel('left', "Temperature", units='°C')
        self.temperature_graph.setLabel('bottom', "Time")
        self.temperature_graph.addLegend()
        self.temperature_curve = self.temperature_graph.plot(pen=pg.mkPen(color='#e74c3c', width=2), name="Temperature")
        graph_tab.addTab(self.temperature_graph, "Temperature")
        
        # Humidity graph
        self.humidity_graph = pg.PlotWidget()
        self.humidity_graph.setBackground(COLORS['card_bg'])
        self.humidity_graph.setTitle("Humidity (%)", color=COLORS['text'], size="12pt")
        self.humidity_graph.setLabel('left', "Humidity", units='%')
        self.humidity_graph.setLabel('bottom', "Time")
        self.humidity_graph.addLegend()
        self.humidity_curve = self.humidity_graph.plot(pen=pg.mkPen(color='#3498db', width=2), name="Humidity")
        graph_tab.addTab(self.humidity_graph, "Humidity")
        
        # CO2 graph
        self.co2_graph = pg.PlotWidget()
        self.co2_graph.setBackground(COLORS['card_bg'])
        self.co2_graph.setTitle("CO2 Level (ppm)", color=COLORS['text'], size="12pt")
        self.co2_graph.setLabel('left', "CO2", units='ppm')
        self.co2_graph.setLabel('bottom', "Time")
        self.co2_graph.addLegend()
        self.co2_curve = self.co2_graph.plot(pen=pg.mkPen(color='#2ecc71', width=2), name="CO2")
        graph_tab.addTab(self.co2_graph, "CO2 Level")

        data_layout.addWidget(graph_tab)
        main_layout.addWidget(data_frame)

        # Initialize data storage
        self.temperature_data = []
        self.humidity_data = []
        self.co2_data = []
        self.time_data = []
        self.time_counter = 0

        self.setLayout(main_layout)
        self.update_com_ports()

    def update_baud_rate(self, text):
            if text == "Custom":
                self.custom_baud.setVisible(True)
            else:
                self.custom_baud.setVisible(False)
                try:
                    self.current_baudrate = int(text)
                except ValueError:
                    self.current_baudrate = 9600

    def toggle_com_selector(self, source):
        if source == "Microcontroller":
            self.com_widget.setVisible(True)
            self.baud_layout.parentWidget().setVisible(True)  # Show baud rate
            self.update_com_ports()
        else:
            self.com_widget.setVisible(False)
            self.baud_layout.parentWidget().setVisible(False)  # Hide baud rate

    def update_com_ports(self):
        self.com_selector.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.com_selector.addItem(port.device)

    def start_data_acquisition(self):
        self.stop_data_acquisition()
        
        source = self.source_selector.currentText()
        if source == "Simulator":
            self.receiver.start_simulator()
        else:
            selected_port = self.com_selector.currentText()
            if selected_port:
                if self.baud_selector.currentText() == "Custom":
                    try:
                        baud = int(self.custom_baud.text())
                    except ValueError:
                        baud = 9600
                        self.display.append("Invalid baud rate, using 9600")
                else:
                    baud = int(self.baud_selector.currentText())
                    
                self.receiver.start_serial(port=selected_port, baudrate=baud)
    
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.display.append(f"Monitoring started ({source})")

    def stop_data_acquisition(self):
        self.receiver.stop()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.display.append("Monitoring stopped.")

    def update_display(self, data):
        try:
            # Ensure it's a string
            data_str = data.strip() if isinstance(data, str) else str(data)
            
            # Verify correct format
            if not all(x in data_str for x in ['T:', 'H:', 'CO2:']):
                print(f"Incorrect format, data ignored: {data_str}")
                return
                
            # Display in QTextEdit
            self.display.append(data_str)
            
            # Ensure self.data exists
            if not hasattr(self, 'data'):
                self.data = []
                
            # Store raw data (exactly as received)
            self.data.append(data_str)
            
            # Debug: show current state of self.data
            print(f"Data added. Total records: {len(self.data)}")
            
        except Exception as e:
            print(f"Error in update_display: {str(e)}")

    def update_graphs(self, data):
        try:
            # Extract values from format "T:25,H:60,CO2:400"
            temp_str = data.split('T:')[1].split(',')[0]
            hum_str = data.split('H:')[1].split(',')[0]
            co2_str = data.split('CO2:')[1]

            temp = float(temp_str)
            hum = float(hum_str)
            co2 = float(co2_str)
            
            self.temperature_data.append(temp)
            self.humidity_data.append(hum)
            self.co2_data.append(co2)
            self.time_data.append(self.time_counter)
            self.time_counter += 1

            # Update graphs with smooth curves
            self.temperature_curve.setData(self.time_data, self.temperature_data, pen=pg.mkPen('#e74c3c', width=2))
            self.humidity_curve.setData(self.time_data, self.humidity_data, pen=pg.mkPen('#3498db', width=2))
            self.co2_curve.setData(self.time_data, self.co2_data, pen=pg.mkPen('#2ecc71', width=2))
            
            # Auto-scale the graphs
            self.temperature_graph.enableAutoRange('xy', True)
            self.humidity_graph.enableAutoRange('xy', True)
            self.co2_graph.enableAutoRange('xy', True)
        except (ValueError, IndexError) as e:
            print(f"Error parsing data: {e}")

    def update_widgets(self, data):
        try:
            # Extract values from format "T:25,H:60,CO2:400"
            temp_str = data.split('T:')[1].split(',')[0]
            hum_str = data.split('H:')[1].split(',')[0]
            co2_str = data.split('CO2:')[1]
            
            temp = float(temp_str)
            hum = float(hum_str)
            co2 = float(co2_str)
            
            self.temperature_widget.set_temperature(temp)
            self.humidity_widget.set_humidity(hum)
            self.co2_widget.set_co2(co2)
        except (ValueError, IndexError) as e:
            print(f"Error parsing data: {e}")

    def save_data(self):
        try:
            # Comprehensive self.data verification
            if not hasattr(self, 'data') or not self.data:
                QMessageBox.warning(self, "Error", "No data in memory to save")
                print("Error: self.data doesn't exist or is empty")
                return
                
            print(f"Attempting to save {len(self.data)} records...")
            
            filename = "sensor_data.csv"
            saved_records = 0
            
            with open(filename, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(["Temperature", "Humidity", "CO2"])
                
                for record in self.data:
                    try:
                        # Safe value extraction
                        temp = record.split('T:')[1].split(',H:')[0]
                        hum = record.split(',H:')[1].split(',CO2:')[0]
                        co2 = record.split(',CO2:')[1].strip()
                        
                        # Additional validation
                        if not (temp.replace('.', '').isdigit() and 
                                hum.replace('.', '').isdigit() and 
                                co2.isdigit()):
                            raise ValueError("Non-numeric values")
                        
                        # Write to CSV
                        writer.writerow([temp, hum, co2])
                        saved_records += 1
                        
                        # Debug per record
                        print(f"Saved: T={temp}, H={hum}, CO2={co2}")
                        
                    except Exception as e:
                        print(f"Error processing record {record}: {str(e)}")
                        continue

            # Final result
            msg = f"File saved: {filename}\nRecords: {saved_records}/{len(self.data)}"
            print(msg)
            QMessageBox.information(self, "Result", msg)
            
            # Additional verification: read the newly created file
            try:
                with open(filename, 'r') as f:
                    print("File content:")
                    print(f.read())
            except Exception as e:
                print(f"Couldn't verify file: {str(e)}")
                
        except Exception as e:
            error_msg = f"Save error: {str(e)}"
            print(error_msg)
            QMessageBox.critical(self, "Critical Error", error_msg)

    def closeEvent(self, event):
        self.save_data()
        self.receiver.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Set application font
    font = QFont()
    font.setFamily("Segoe UI")
    font.setPointSize(10)
    app.setFont(font)
    
    window = MonitoringApp()
    window.resize(1000, 800)
    window.show()
    sys.exit(app.exec_())