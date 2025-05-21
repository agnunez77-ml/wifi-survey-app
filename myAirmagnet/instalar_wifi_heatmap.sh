#!/bin/bash

echo "Instalando dependencias necesarias para wifi-heatmap..."
sudo apt update
sudo apt install -y python3 python3-pip python3-tk git

echo "Clonando el repositorio de wifi-heatmap..."
git clone https://github.com/ewen-lbh/wifi-heatmap.git ~/wifi-heatmap

echo "Instalando dependencias de Python..."
pip3 install matplotlib numpy

echo "Instalación completa."
echo "Para usarlo:"
echo "1. Ir a la carpeta: cd ~/wifi-heatmap"
echo "2. Ejecutar: python3 wifi_heatmap.py"
echo "3. Cargar un plano de fondo (imagen) y comenzar a registrar puntos de señal WiFi."
