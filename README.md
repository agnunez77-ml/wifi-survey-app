# WiFi Survey App

Aplicación visual para realizar site surveys de redes WiFi con planos reales. Permite:

- Cargar plano de una oficina o casa
- Calibrar escala en metros
- Ubicar Access Points (APs)
- Tomar mediciones de señal WiFi
- Visualizar heatmaps interpolados o por celdas
- Exportar informes en JSON o PNG

## Capturas
📷 Ver carpeta `/screenshots` para ejemplos.

## Requisitos
```bash
pip install -r requirements.txt

# WiFi Survey App

Aplicación visual para realizar site surveys de redes WiFi sobre planos reales. Diseñada para profesionales de redes que necesiten analizar la cobertura inalámbrica en hogares, oficinas y edificios.

## Funcionalidades

- 📂 Cargar un plano de fondo (imagen)
- 📐 Calibrar la escala en metros
- 📡 Ubicar Access Points (APs)
- 📍 Tomar mediciones de señal WiFi
- 🔥 Visualizar heatmaps por SSID:
  - Modo interpolado (suavizado)
  - Modo por celdas (real por punto)
  - Estimación de interferencia
- 📊 Visualizar cobertura proyectada desde APs (modelo FSPL)
- 💾 Exportar informes en JSON y gráficos en PNG
- 🧼 Función de limpieza de datos

## Requisitos

- Python 3.7+
- PyQt5
- matplotlib
- numpy
- scipy

## Instalación

```bash
pip install -r requirements.txt
```

## Ejecución

```bash
python3 wifi_survey_app.py
```


