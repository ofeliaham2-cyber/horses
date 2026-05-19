import os
import subprocess
import sys
from pathlib import Path

def check_poetry():
    """Verifica si Poetry está instalado en el sistema."""
    print("🔍 Verificando instalación de Poetry...")
    try:
        result = subprocess.run(["poetry", "--version"], capture_output=True, text=True, check=True)
        print(f"✅ Poetry detectado: {result.stdout.strip()}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Error: Poetry no está instalado o no está en el PATH.")
        print("\nPara instalar Poetry en Windows, abre PowerShell como administrador y ejecuta:")
        print("(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -")
        print("Asegúrate de agregar la ruta de Poetry a tus variables de entorno.")
        return False

def configure_env():
    """Pide credenciales al usuario y las guarda en un archivo .env."""
    env_path = Path(".env")
    print("\n🔐 Configuración de Credenciales (Supabase)")
    
    # Si ya existe, preguntar si se quiere sobrescribir
    if env_path.exists():
        resp = input("El archivo .env ya existe. ¿Deseas reconfigurarlo? (s/N): ")
        if resp.lower() != 's':
            print("Saltando configuración de .env...")
            return

    supabase_url = input("Ingresa tu SUPABASE_URL: ").strip()
    supabase_key = input("Ingresa tu SUPABASE_ANON_KEY o SERVICE_ROLE_KEY: ").strip()

    with open(env_path, "w", encoding="utf-8") as f:
        f.write(f"SUPABASE_URL={supabase_url}\n")
        f.write(f"SUPABASE_KEY={supabase_key}\n")
    
    print("✅ Archivo .env generado exitosamente.")

def install_dependencies():
    """Instala las dependencias usando Poetry."""
    print("\n📦 Instalando dependencias del proyecto mediante Poetry...")
    try:
        subprocess.run(["poetry", "install"], check=True)
        print("✅ Dependencias de Python instaladas.")
        
        print("\n🌐 Instalando navegadores de Playwright para web scraping...")
        subprocess.run(["poetry", "run", "playwright", "install"], check=True)
        print("✅ Playwright configurado exitosamente.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error instalando dependencias. Revisa los logs. Detalle: {e}")
        sys.exit(1)

def test_supabase_connection():
    """Prueba la conexión a la base de datos Supabase."""
    print("\n📡 Testeando conexión a la Base de Datos (Supabase)...")
    
    try:
        # Importamos dentro de la función para asegurar que el entorno ya las tiene instaladas
        from dotenv import load_dotenv
        from supabase import create_client, Client

        load_dotenv()
        url: str = os.environ.get("SUPABASE_URL")
        key: str = os.environ.get("SUPABASE_KEY")

        if not url or not key:
            print("❌ Error: Faltan credenciales en .env")
            return

        supabase: Client = create_client(url, key)
        
        # Prueba simple: Consultar hipódromos
        response = supabase.table("hipodromos").select("*").limit(1).execute()
        print("✅ Conexión a Supabase exitosa.")
        print(f"Respuesta de la DB (Tabla hipodromos): {response.data}")

    except Exception as e:
        print(f"❌ Falló la conexión a Supabase: {e}")

def main():
    print("=" * 60)
    print("🚀 SIPH-ANTIGRAVITY: SCRIPT DE AUTO-CONFIGURACIÓN (ETL)")
    print("=" * 60)
    
    if not check_poetry():
        sys.exit(1)
        
    configure_env()
    install_dependencies()
    
    # Para probar Supabase, usamos el script usando poetry run python (o lo intentamos importar directo si es el mismo entorno)
    # Como el script puede no estar corriendo en el entorno virtual de poetry, le avisaremos al usuario:
    print("\n=======================================================")
    print("¡Entorno configurado correctamente! 🎉")
    print("Para probar la conexión a Supabase, ejecuta:")
    print("poetry run python -c \"from dotenv import load_dotenv; import os; from supabase import create_client; load_dotenv(); supabase=create_client(os.environ.get('SUPABASE_URL'), os.environ.get('SUPABASE_KEY')); print('✅ Conexión:', supabase.table('hipodromos').select('*').limit(1).execute().data)\"")
    print("=======================================================")

if __name__ == "__main__":
    main()
