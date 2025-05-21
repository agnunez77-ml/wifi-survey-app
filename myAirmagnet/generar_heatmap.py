import json
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import griddata

# Cargar mediciones exportadas
with open("mediciones.json", "r") as f:
    datos = json.load(f)

# Preparar coordenadas y señales promedio
x, y, señal_prom = [], [], []

for punto in datos:
    señales = [r.get("Señal", 0) for r in punto["redes"] if "Señal" in r]
    if señales:
        x.append(punto["x_m"])
        y.append(punto["y_m"])
        señal_prom.append(sum(señales) / len(señales))

# Interpolación para generar heatmap
xi = np.linspace(min(x), max(x), 100)
yi = np.linspace(min(y), max(y), 100)
xi, yi = np.meshgrid(xi, yi)
zi = griddata((x, y), señal_prom, (xi, yi), method='cubic')

# Graficar
plt.figure(figsize=(8, 6))
plt.contourf(xi, yi, zi, levels=100, cmap="jet")
plt.colorbar(label="Señal WiFi promedio (dBm)")
plt.scatter(x, y, c="white", edgecolors="black", label="Mediciones")
plt.title("Mapa de calor WiFi")
plt.xlabel("X (m)")
plt.ylabel("Y (m)")
plt.legend()
plt.tight_layout()
plt.show()
