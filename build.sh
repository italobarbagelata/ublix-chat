#!/bin/bash

# Actualizar pip
pip install --upgrade pip

# Instalar dependencias
pip install -r requirements.txt

# Verificar que supabase esté instalado
pip install supabase==2.13.0

echo "Build script completed successfully" 