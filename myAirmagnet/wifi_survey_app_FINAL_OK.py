import sys
import math
import json
import os
import platform
import tempfile
import subprocess
import io
from fpdf import FPDF
from PyQt5 import QtWidgets, QtGui, QtCore
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import griddata

class WifiSurveyApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WiFi Survey - Con ubicación de AP")
        self.setGeometry(100, 100, 1000, 700)

        self.image_label = QtWidgets.QLabel(self)
        self.image_label.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        self.setCentralWidget(self.image_label)
        self.image_label.mousePressEvent = self.get_click_position

        # Menú de planificación
        plan_menu = self.menuBar().addMenu("🔷 Planificación")
        plan_menu.addAction("📂 Cargar plano", self.load_image)
        plan_menu.addAction("📐 Calibrar escala", self.recalibrar_escala)
        plan_menu.addAction("📡 Ubicar Access Point", self.activar_modo_ap)
        plan_menu.addAction("📡 Ver cobertura estimada desde APs", self.ver_cobertura_estimada)

        # Menú de site survey
        survey_menu = self.menuBar().addMenu("🔶 Site Survey")
        survey_menu.addAction("📍 Tomar mediciones (clic en plano)", self.activar_modo_medicion)
        survey_menu.addAction("📊 Ver Heatmap por SSID", self.ver_heatmap_por_ssid)
        survey_menu.addAction("💾 Exportar informe", self.exportar_informe)
        survey_menu.addAction("🖨️ Exportar informe PDF", self.exportar_informe_pdf)

        # Acción global de limpieza
        clear_action = QtWidgets.QAction("🧹 Clear", self)
        clear_action.triggered.connect(self.reset_clicks)
        self.menuBar().addAction(clear_action)


        self.statusBar().showMessage("Cargá un plano, calibrá, ubicá el AP y empezá a medir.")

        self.image = None
        self.original_image = None
        self.clicks = []
        self.escala_pts = []
        self.escala = None
        self.mediciones = []
        self.modo_ap = False
        self.modo_medicion = False  # Inicializado correctamente
        self.aps_manual = []  # Lista de APs manuales con nombre y posición
        self.temp_files = []  # Lista para rastrear archivos temporales

    def load_image(self):
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Abrir imagen", "", "Imágenes (*.png *.jpg *.bmp)")
        if file_name:
            self.image = QtGui.QPixmap(file_name)
            self.original_image = QtGui.QPixmap(file_name)

            # Crear una copia del plano con elementos agregados
            painter = QtGui.QPainter(self.image)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)

            # Agregar escala visual (10 metros)
            if self.escala:
                escala_metros = 10
                largo_px = int(self.escala * escala_metros)
                painter.setPen(QtGui.QPen(QtGui.QColor("black"), 3))
                painter.drawLine(30, self.image.height() - 40, 30 + largo_px, self.image.height() - 40)
                painter.drawText(30 + largo_px + 10, self.image.height() - 35, f"{escala_metros} m")

            # Agregar flecha norte
            painter.setPen(QtGui.QPen(QtGui.QColor("black"), 2))
            painter.drawLine(60, 60, 60, 20)
            painter.drawLine(60, 20, 55, 30)
            painter.drawLine(60, 20, 65, 30)
            painter.drawText(50, 15, "N")

            painter.end()
            self.image_label.setPixmap(self.image)
            self.resize(self.image.width(), self.image.height() + 30)
            self.reset_clicks()


    def recalibrar_escala(self):
        self.escala = None
        self.escala_pts.clear()
        self.statusBar().showMessage("Hacé dos clics sobre una distancia conocida para calibrar.")

    def activar_modo_ap(self):
        self.modo_ap = True
        self.modo_medicion = False  # Desactivar otros modos
        self.statusBar().showMessage("Modo AP activado: hacé clic en el plano para ubicar el Access Point.")
        
    def activar_modo_medicion(self):
        self.modo_medicion = True
        self.modo_ap = False  # Desactivar otros modos
        self.statusBar().showMessage("Modo medición activado: hacé clic en el plano para registrar puntos.")


    def reset_clicks(self):
        if self.original_image:
            self.image = QtGui.QPixmap(self.original_image)
            self.image_label.setPixmap(self.image)
        self.clicks.clear()
        self.escala_pts.clear()
        self.escala = None
        self.mediciones.clear()
        self.modo_medicion = False
        self.modo_ap = False
        self.statusBar().showMessage("Todo reseteado. Cargá plano y calibrá escala.")

    def get_click_position(self, event):
        if not self.image:
            return

        x, y = event.pos().x(), event.pos().y()
        painter = QtGui.QPainter(self.image)

        # Modo ubicación de AP (soporte múltiple)
        if self.modo_ap:
            nombre_ap, ok = QtWidgets.QInputDialog.getText(self, "Nombre del AP", "Identificador del AP:")
            if not ok or not nombre_ap.strip():
                self.statusBar().showMessage("Ubicación de AP cancelada.")
                self.modo_ap = False
                return
            self.aps_manual.append({"nombre": nombre_ap.strip(), "x_px": x, "y_px": y})
            painter.setBrush(QtGui.QBrush(QtGui.QColor("blue")))
            painter.setPen(QtGui.QPen(QtGui.QColor("black")))
            painter.drawEllipse(QtCore.QPoint(x, y), 8, 8)
            painter.drawText(x + 10, y, nombre_ap.strip())
            self.statusBar().showMessage(f"AP '{nombre_ap}' ubicado en ({x}, {y})")
            self.modo_ap = False
            painter.end()
            self.image_label.setPixmap(self.image)
            return


        # Calibración de escala
        if self.escala is None:
            self.escala_pts.append((x, y))
            if len(self.escala_pts) == 2:
                x1, y1 = self.escala_pts[0]
                x2, y2 = self.escala_pts[1]
                d_pixels = math.hypot(x2 - x1, y2 - y1)
                metros, ok = QtWidgets.QInputDialog.getDouble(self, "Distancia real", "¿Cuántos metros hay entre los puntos?", min=0.1)
                if ok and metros > 0:
                    self.escala = d_pixels / metros
                    pen_escala = QtGui.QPen(QtGui.QColor("green"))
                    pen_escala.setWidth(2)
                    painter.setPen(pen_escala)
                    painter.drawLine(x1, y1, x2, y2)
                    painter.drawText(int((x1 + x2) / 2), int((y1 + y2) / 2), f"{metros:.1f} m")
                    self.statusBar().showMessage(f"Escala definida: {self.escala:.2f} px/m")
                    self.escala_pts.clear()
        elif self.modo_medicion:   
            painter.setPen(QtGui.QPen(QtGui.QColor("red"), 5))
            painter.drawPoint(x, y)
            painter.drawText(x + 5, y - 5, str(len(self.mediciones)))

            x_real = x / self.escala
            y_real = y / self.escala
            redes = self.escanear_wifi()
            if redes:
                coords = (round(x_real, 2), round(y_real, 2))
                if not any(m["x_m"] == coords[0] and m["y_m"] == coords[1] for m in self.mediciones):
                    self.mediciones.append({
                        "x_m": coords[0],
                        "y_m": coords[1],
                        "redes": redes
                    })
                    self.statusBar().showMessage(f"Medición registrada en ({coords[0]:.2f} m, {coords[1]:.2f} m) con {len(redes)} redes.")
                else:
                    self.statusBar().showMessage("Punto duplicado, ignorado.")
            else:
                self.statusBar().showMessage("No se detectaron redes en este punto.")
        painter.end()
        self.image_label.setPixmap(self.image)

    def escanear_wifi(self):
        try:
            sistema = platform.system()
            redes = []

            if sistema == "Linux":
                resultado = subprocess.check_output(
                    ['nmcli', '-f', 'SSID,SIGNAL,BSSID', 'device', 'wifi', 'list'],
                    encoding='utf-8'
                )
                lineas = resultado.strip().split('\n')[1:]
                for linea in lineas:
                    partes = [x.strip() for x in linea.split() if x.strip()]
                    if len(partes) >= 3:
                        ssid = ' '.join(partes[:-2])
                        signal = partes[-2]
                        bssid = partes[-1]
                        redes.append({'SSID': ssid, 'BSSID': bssid, 'Señal': int(signal), 'Canal': 'N/A'})

            elif sistema == "Windows":
                resultado = subprocess.check_output(
                    ['netsh', 'wlan', 'show', 'networks', 'mode=bssid'],
                    encoding='utf-8',
                )
                lineas = resultado.splitlines()
                ssid = None
                for i, linea in enumerate(lineas):
                    linea = linea.strip()
                    if linea.startswith("SSID") and " : " in linea:
                        nueva_ssid = linea.split(":", 1)[1].strip()
                        if nueva_ssid:
                            ssid = nueva_ssid
                    elif linea.startswith("BSSID"):
                        bssid = linea.split(":", 1)[1].strip()
                        canal = "N/A"
                        signal = None
                        for offset in range(1, 10):
                            if i + offset < len(lineas):
                                l = lineas[i + offset].strip()
                                if l.startswith("Canal"):
                                    canal = l.split(":", 1)[1].strip()
                                if l.startswith("Señal"):
                                    try:
                                        signal = int(l.split(":", 1)[1].strip().replace("%", ""))
                                    except:
                                        signal = None
                                    break
                        if signal is not None:
                            redes.append({
                                'SSID': ssid or "Desconocido",
                                'BSSID': bssid,
                                'Señal': signal,
                                'Canal': canal
                            })
            else:
                redes.append({"error": "Sistema operativo no soportado", "SSID": "Error", "BSSID": "N/A", "Señal": 0, "Canal": "N/A"})

            return redes

        except Exception as e:
            return [{"error": str(e), "SSID": "Error", "BSSID": "N/A", "Señal": 0, "Canal": "N/A"}]


    def exportar_informe(self):
        if not self.mediciones:
            QtWidgets.QMessageBox.warning(self, "Sin datos", "No hay mediciones para exportar.")
            return
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Guardar informe", "mediciones.json", "JSON (*.json)")
        if file_name:
            with open(file_name, 'w') as f:
                json.dump(self.mediciones, f, indent=2)
            self.statusBar().showMessage(f"Informe exportado: {file_name}")

    def ver_heatmap_por_ssid(self):
        if not self.mediciones:
            QtWidgets.QMessageBox.warning(self, "Sin datos", "No hay mediciones para graficar.")
            return

        ssids = set()
        for punto in self.mediciones:
            for r in punto["redes"]:
                if "SSID" in r and r["SSID"].strip():
                    ssids.add(r["SSID"])
        ssids = sorted(ssids)

        if not ssids:
            QtWidgets.QMessageBox.warning(self, "Sin SSIDs", "No se encontraron SSIDs.")
            return
        tipo_mapa, ok = QtWidgets.QInputDialog.getItem(
            self, "Tipo de visualización",
            "¿Cómo querés ver el mapa?",
            ["Por celdas (real por punto)", "Interpolado (suavizado)"],
            0, False
        )
        if not ok:
            return

        ssid, ok = QtWidgets.QInputDialog.getItem(self, "Seleccionar SSID", "SSID:", ssids, editable=False)
        if not ok or not ssid:
            return
            
        modo, ok = QtWidgets.QInputDialog.getItem(
            self, "Modo de análisis",
            "¿Qué querés visualizar?",
            ["Señal (dBm)", "Señal/Ruido (SNR)", "Interferencia estimada"],
            0, False
        )
        if not ok:
            return

        # Recolectar BSSIDs asociados a ese SSID
        bssids = set()
        for punto in self.mediciones:
            for r in punto["redes"]:
                if r.get("SSID") == ssid and r.get("BSSID"):
                    bssids.add(r["BSSID"])
        bssids = sorted(bssids)

        # Preguntar si se quiere analizar todos o uno solo
        todos_o_uno, ok = QtWidgets.QInputDialog.getItem(
            self, "Filtrado por AP",
            "¿Querés ver todos los APs o uno específico?",
            ["Todos los APs", "Elegir un AP (BSSID)"],
            0, False
        )
        if not ok:
            return

        bssid_seleccionado = None
        if todos_o_uno == "Elegir un AP (BSSID)":
            bssid_seleccionado, ok = QtWidgets.QInputDialog.getItem(
                self, "Seleccionar BSSID", "BSSID:", bssids, editable=False
            )
            if not ok or not bssid_seleccionado:
                return

        x, y, señal = [], [], []
        for punto in self.mediciones:
            señales = []
            if modo == "Interferencia estimada":
                # Contar redes distintas al SSID seleccionado
                valor = len([r for r in punto["redes"] if r.get("SSID") != ssid])
                señales = [valor]
            else:
                for r in punto["redes"]:
                    if r.get("SSID") == ssid and (
                        not bssid_seleccionado or r.get("BSSID") == bssid_seleccionado
                    ):

                        valor = (r["Señal"] / 2) - 100  # dBm
                        if modo == "Señal/Ruido (SNR)":
                            ruido_estimado = -95
                            valor = valor - ruido_estimado
                        señales.append(valor)

            if señales:
                x.append(punto["x_m"])
                y.append(punto["y_m"])
                señal.append(sum(señales) / len(señales))


        if len(x) < 3:
            QtWidgets.QMessageBox.warning(self, "Datos insuficientes", f"No hay suficientes puntos para {ssid}.")
            return

        xi = np.linspace(0, self.image.width() / self.escala, 200)
        yi = np.linspace(0, self.image.height() / self.escala, 200)
        xi, yi = np.meshgrid(xi, yi)
        
        # Convertir QPixmap a QImage y luego a array numpy
        qimage = self.original_image.toImage().convertToFormat(QtGui.QImage.Format_RGBA8888)
        width = qimage.width()
        height = qimage.height()
        ptr = qimage.bits()
        ptr.setsize(qimage.byteCount())
        arr = np.array(ptr).reshape((height, width, 4))
        arr = np.flipud(arr)  # Invertir eje Y
        img = arr / 255.0  # Normalizar a [0, 1]

        plt.figure(figsize=(8, 6))

        # Mostrar cobertura según tipo seleccionado
        if tipo_mapa == "Interpolado (suavizado)":
            try:
                # Interpolación primero
                zi = griddata((x, y), señal, (xi, yi), method='cubic')
                # Verificar si la interpolación funcionó correctamente
                if zi is None or np.all(np.isnan(zi)):
                    raise ValueError("No se pudo interpolar correctamente.")
                
                zi = np.nan_to_num(zi, nan=-100)

                # Mostrar fondo del plano
                plt.imshow(
                    img[:, :, :3],
                    extent=[0, self.image.width() / self.escala, 0, self.image.height() / self.escala],
                    interpolation='bilinear',
                    origin='lower',
                    zorder=0,
                    alpha=0.5
                )

                # Mostrar interpolación sobre fondo
                plt.contourf(xi, yi, zi, levels=np.linspace(-90, -30, 100), cmap="jet", alpha=0.6)

                # Barra de colores
                sm = plt.cm.ScalarMappable(cmap="jet", norm=plt.Normalize(vmin=-90, vmax=-30))
                sm.set_array([])
                cbar = plt.colorbar(sm, ax=plt.gca())
                cbar.set_label("Señal estimada (dBm)")

                # Guardado automático
                nombre_archivo = f"heatmap_{ssid.replace(' ', '_')}_interpolado.png"
                ruta_guardado = QtWidgets.QFileDialog.getSaveFileName(self, "Guardar heatmap interpolado", nombre_archivo, "Imágenes (*.png)")[0]
                if ruta_guardado:
                    plt.savefig(ruta_guardado)
                    self.statusBar().showMessage(f"Imagen guardada: {ruta_guardado}")

            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Error", f"No se pudo crear el mapa interpolado: {str(e)}")
                return

        else:
            # Visualización por celdas reales estilo FSPL con fondo
            plt.imshow(
                img,
                extent=[0, self.image.width() / self.escala, 0, self.image.height() / self.escala],
                interpolation='bilinear',
                origin='lower',
                alpha=0.5,
                zorder=0
            )

            # Generar grilla
            grid_x = np.linspace(min(x), max(x), 100)
            grid_y = np.linspace(min(y), max(y), 100)
            grid_x, grid_y = np.meshgrid(grid_x, grid_y)

            try:
                # Interpolación estilo "nearest" para mapa tipo celdas
                grid_z = griddata((x, y), señal, (grid_x, grid_y), method='linear')
                if grid_z is None or np.all(np.isnan(grid_z)):
                    raise ValueError("No se pudo interpolar correctamente.")
                
                grid_z = np.nan_to_num(grid_z, nan=-100)

                # Mostrar mapa
                plt.contourf(grid_x, grid_y, grid_z, levels=np.linspace(-90, -30, 100), cmap="jet", alpha=0.6, zorder=1)

                sm = plt.cm.ScalarMappable(cmap="jet", norm=plt.Normalize(vmin=-90, vmax=-30))
                sm.set_array([])
                cbar = plt.colorbar(sm, ax=plt.gca())
                cbar.set_label("Señal estimada por punto (dBm)")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Error", f"No se pudo crear el mapa por celdas: {str(e)}")
                return

        # Dibujar APs si los hay
        if self.aps_manual and self.escala:
            for ap in self.aps_manual:
                ap_x = ap["x_px"] / self.escala
                ap_y = ap["y_px"] / self.escala
                plt.plot(ap_x, ap_y, marker='o', color='blue', markersize=10)
                plt.text(ap_x + 0.2, ap_y, ap["nombre"], color='blue', fontsize=9)

        plt.tight_layout()
        plt.show()


    def ver_cobertura_estimada(self):
        if not self.aps_manual:
            QtWidgets.QMessageBox.warning(self, "Sin APs", "No hay APs definidos para proyectar cobertura.")
            return
        if not self.escala:
            QtWidgets.QMessageBox.warning(self, "Sin escala", "Primero calibrá la escala para poder calcular distancias.")
            return

        ancho_px = self.image.width()
        alto_px = self.image.height()

        # Generar grilla en píxeles
        paso = 10  # resolución del mapa
        x_px = np.arange(0, ancho_px, paso)
        y_px = np.arange(0, alto_px, paso)
        x_px_grid, y_px_grid = np.meshgrid(x_px, y_px)

        # Calcular RSSI estimado por celda (en base a distancia a AP más cercano)
        RSSI = np.full_like(x_px_grid, -100.0, dtype=float)
        TX_POWER = -30  # dBm asumido cerca del AP

        for ap in self.aps_manual:
            ap_x = ap["x_px"]
            ap_y = ap["y_px"]
            dx = (x_px_grid - ap_x) / self.escala  # en metros
            dy = (y_px_grid - ap_y) / self.escala  # en metros
            dist = np.sqrt(dx**2 + dy**2)
            dist[dist < 1] = 1  # evitar log(0)

            rssi_ap = TX_POWER - 20 * np.log10(dist)
            RSSI = np.maximum(RSSI, rssi_ap)  # tomamos el mejor (mayor dBm)

        # Graficar
        plt.figure(figsize=(8, 6))
        
        # Mostrar plano de fondo
        qimage = self.original_image.toImage().convertToFormat(QtGui.QImage.Format_RGBA8888)
        width = qimage.width()
        height = qimage.height()
        ptr = qimage.bits()
        ptr.setsize(qimage.byteCount())
        arr = np.array(ptr).reshape((height, width, 4))
        arr = np.flipud(arr)  # Invertir eje Y
        img = arr / 255.0
        plt.imshow(
            img,
            extent=[0, self.image.width() / self.escala, 0, self.image.height() / self.escala],
            interpolation='bilinear',
            origin='lower',
            zorder=0,
            alpha=0.5
        )

        # Superponer el heatmap
        plt.contourf(x_px_grid / self.escala, y_px_grid / self.escala, RSSI, levels=100, cmap="jet", alpha=0.6)

        plt.colorbar(label="Señal estimada (dBm)")

        # Marcar APs
        for ap in self.aps_manual:
            ap_x_m = ap["x_px"] / self.escala
            ap_y_m = ap["y_px"] / self.escala
            plt.plot(ap_x_m, ap_y_m, marker='o', color='blue', markersize=10)
            plt.text(ap_x_m + 0.2, ap_y_m, ap["nombre"], color='blue', fontsize=9)

        plt.title("Cobertura estimada desde los APs (modelo FSPL)")
        plt.xlabel("X (m)")
        plt.ylabel("Y (m)")
        plt.tight_layout()
        guardar, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Guardar cobertura estimada", "cobertura_estimada.png", "Imágenes (*.png)")

        if guardar:
            plt.savefig(guardar)
            self.statusBar().showMessage(f"Imagen guardada: {guardar}")

        plt.show()

    def estimar_velocidad_dbm(self, señal):
        if señal >= -50:
            return 400, "Excelente", "802.11ac/n 5GHz"
        elif señal >= -65:
            return 100, "Buena", "802.11n/g"
        elif señal >= -75:
            return 35, "Regular", "802.11g/b"
        elif señal >= -85:
            return 8, "Mala", "802.11b"
        else:
            return 0.5, "Crítica", "Sin conexión"

    
    def generar_graficos_analisis(self):
        if not self.mediciones:
            return {}

        # Limpiar archivos temporales anteriores
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except:
                pass
        self.temp_files = []

        datos_por_ssid = {}
        for punto in self.mediciones:
            for red in punto['redes']:
                ssid = red.get("SSID", "Desconocido")
                señal = red.get("Señal", 0)
                señal_dbm = (señal / 2) - 100
                velocidad, _, _ = self.estimar_velocidad_dbm(señal_dbm)

                if ssid not in datos_por_ssid:
                    datos_por_ssid[ssid] = {"dbm": [], "vel": []}

                datos_por_ssid[ssid]["dbm"].append(señal_dbm)
                datos_por_ssid[ssid]["vel"].append(velocidad)

        imagenes = {}
        for ssid, datos in datos_por_ssid.items():
            try:
                fig, ax = plt.subplots(figsize=(6, 4))
                ax.plot(datos['dbm'], label="Señal (dBm)", marker='o')
                ax.plot(datos['vel'], label="Velocidad (Mbps)", marker='x')
                ax.set_title(f"Análisis por SSID: {ssid}")
                ax.set_xlabel("Punto de Medición")
                ax.set_ylabel("Valor")
                ax.legend()
                ax.grid(True)
                fig.tight_layout()

                # Crear archivo temporal y recordarlo para eliminar después
                temp_path = tempfile.NamedTemporaryFile(delete=False, suffix='.png').name
                self.temp_files.append(temp_path)
                
                fig.savefig(temp_path)
                plt.close(fig)

                imagenes[ssid] = temp_path
            except Exception as e:
                print(f"Error al generar gráfico para {ssid}: {str(e)}")

        return imagenes


    def clasificar_banda(self, canal):
        try:
            canal = int(canal)
            if 1 <= canal <= 14:
                return "2.4 GHz"
            elif 36 <= canal <= 165:
                return "5 GHz"
        except:
            pass
        return "Desconocido"

    # Método de exportación PDF con imagen y tabla
    def exportar_informe_pdf(self):
        if not self.mediciones:
            QtWidgets.QMessageBox.warning(self, "Sin datos", "No hay mediciones para exportar.")
            return

        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Guardar informe PDF", "informe_wifi.pdf", "PDF (*.pdf)")
        if not file_name:
            return

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, "Informe de Site Survey WiFi", ln=True, align="C")
        pdf.ln(10)
        pdf.set_font("Arial", size=12)

        # Insertar heatmap si existe - ya no usamos un nombre fijo, sino que generamos uno temporal
        heatmap_path = None
        try:
            # Generar un heatmap temporal para el informe si hay datos
            if len(self.mediciones) >= 3:
                # Código para generar un heatmap simplificado para el informe
                plt.figure(figsize=(8, 4))
                # Usar el primer SSID con datos suficientes
                ssids_disponibles = []
                for punto in self.mediciones:
                    for red in punto["redes"]:
                        if "SSID" in red and red["SSID"].strip():
                            ssids_disponibles.append(red["SSID"])
                
                if ssids_disponibles:
                    ssid_comun = max(set(ssids_disponibles), key=ssids_disponibles.count)
                    
                    # Recolectar datos para este SSID
                    x, y, señal = [], [], []
                    for punto in self.mediciones:
                        for r in punto["redes"]:
                            if r.get("SSID") == ssid_comun:
                                x.append(punto["x_m"])
                                y.append(punto["y_m"])
                                señal.append((r["Señal"] / 2) - 100)  # dBm
                                break
                    
                    if len(x) >= 3:
                        # Crear un heatmap simple para el informe
                        heatmap_path = tempfile.NamedTemporaryFile(delete=False, suffix='.png').name
                        self.temp_files.append(heatmap_path)
                        
                        # Generar grilla e interpolar
                        grid_x = np.linspace(min(x), max(x), 50)
                        grid_y = np.linspace(min(y), max(y), 50)
                        grid_x, grid_y = np.meshgrid(grid_x, grid_y)
                        
                        try:
                            grid_z = griddata((x, y), señal, (grid_x, grid_y), method='cubic')
                            grid_z = np.nan_to_num(grid_z, nan=-100)
                            
                            plt.contourf(grid_x, grid_y, grid_z, levels=np.linspace(-90, -30, 20), cmap="jet")
                            plt.colorbar(label="dBm")
                            plt.title(f"Mapa de calor de señal - {ssid_comun}")
                            plt.savefig(heatmap_path)
                            plt.close()
                        except:
                            # Si falla la interpolación, ignoramos
                            if os.path.exists(heatmap_path):
                                os.unlink(heatmap_path)
                            heatmap_path = None
        except:
            heatmap_path = None

        # Si tenemos un heatmap, lo añadimos al PDF
        if heatmap_path and os.path.exists(heatmap_path):
            pdf.image(heatmap_path, x=10, y=None, w=180)
            pdf.ln(5)

        total_velocidad = 0
        total_puntos = 0
        clasificacion_contador = {"Excelente": 0, "Buena": 0, "Regular": 0, "Mala": 0, "Crítica": 0}

        for i, punto in enumerate(self.mediciones, 1):
            x, y = punto['x_m'], punto['y_m']
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, f"Punto #{i} - Coordenadas: ({x} m, {y} m)", ln=True)

            for red in punto['redes']:
                ssid = red.get("SSID", "N/A")
                bssid = red.get("BSSID", "N/A")
                señal = red.get("Señal", 0)
                canal = red.get("Canal", "N/A")
                banda = self.clasificar_banda(canal)

                señal_dbm = (señal / 2) - 100
                velocidad, clasificacion, tecnologia = self.estimar_velocidad_dbm(señal_dbm)
                pdf.set_font("Arial", size=11)
                pdf.cell(0, 8,
                    f"SSID: {ssid} | BSSID: {bssid} | Señal: {señal_dbm:.1f} dBm | "
                    f"Velocidad: {velocidad} Mbps | {clasificacion} ({tecnologia}) | "
                    f"Canal: {canal} | Banda: {banda}",
                    ln=True
                )

                total_velocidad += velocidad
                total_puntos += 1
                clasificacion_contador[clasificacion] += 1
            pdf.ln(4)

        if total_puntos:
            velocidad_prom = total_velocidad / total_puntos
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, f"Velocidad promedio estimada: {velocidad_prom:.2f} Mbps", ln=True)
            for clas, count in clasificacion_contador.items():
                porcentaje = (count / total_puntos) * 100
                pdf.cell(0, 8, f"{clas}: {count} puntos ({porcentaje:.1f}%)", ln=True)

        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "Tabla de referencia de velocidad estimada", ln=True)
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 8, "Señal (dBm) | Estimación | Tecnología | Velocidad estimada", ln=True)
        pdf.cell(0, 8, "-30 a -50    | Excelente  | 802.11ac/n 5GHz | 200-600 Mbps", ln=True)
        pdf.cell(0, 8, "-51 a -65    | Buena      | 802.11n/g       | 50-150 Mbps", ln=True)
        pdf.cell(0, 8, "-66 a -75    | Regular    | 802.11g/b       | 20-50 Mbps", ln=True)
        pdf.cell(0, 8, "-76 a -85    | Mala       | 802.11b         | 1-11 Mbps", ln=True)
        pdf.cell(0, 8, "< -85        | Crítica    | Sin conexión    | 0-1 Mbps", ln=True)

        try:
            # Insertar gráficos por SSID
            imagenes = self.generar_graficos_analisis()
            for ssid, img_path in imagenes.items():
                if os.path.exists(img_path):
                    pdf.add_page()
                    pdf.set_font("Arial", 'B', 14)
                    pdf.cell(0, 10, f"Gráfico de Análisis - SSID: {ssid}", ln=True)
                    pdf.image(img_path, x=10, y=None, w=180)
            
            # Guardar el PDF
            pdf.output(file_name)
            self.statusBar().showMessage(f"Informe PDF guardado: {file_name}")
            
            # Limpiar archivos temporales después de guardar
            for temp_file in self.temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except:
                    pass
            self.temp_files = []
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error al guardar PDF", str(e))
    
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = WifiSurveyApp()
    window.showMaximized()
    sys.exit(app.exec_())