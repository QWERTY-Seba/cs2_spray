import os
import winreg

def crear_archivo_gsi( ):
    ruta_steam = None
    try:
        clave = r"SOFTWARE\Wow6432Node\Valve\cs2"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, clave) as key:
            ruta_steam, _ = winreg.QueryValueEx(key, "InstallPath")
            
    except Exception as e:
        raise "NO SE ENCONTRO LA RUTA A STEAM"
        
    sobreescribir=True
    mantener_si_igual=True
    ruta_cfg = os.path.join(ruta_steam, r"game\csgo\cfg")
    archivo = os.path.join(ruta_cfg, "gamestate_arma_en_uso.cfg")

    contenido = '''"ARMA_EN_USO"
                {
                "uri" "http://localhost:54555"
                "timeout" "5.0"
                "buffer"  "0"
                "throttle" "0"
                "heartbeat" "10.0"
                "data"
                    {
                    "Player_Weapons" "1"      
                    }
                }'''

    try:
        os.makedirs(ruta_cfg, exist_ok=True)

        if os.path.exists(archivo):
            with open(archivo, "r", encoding="utf-8") as f:
                contenido_existente = f.read()

            if contenido_existente == contenido and mantener_si_igual:
                print(f"El archivo ya existe y el contenido es idéntico: {archivo}")
                return

            if not sobreescribir:
                print(f"El archivo ya existe en: {archivo} (no sobrescrito)")
                return

        # Crear o sobrescribir el archivo
        with open(archivo, "w", encoding="utf-8") as f:
            f.write(contenido)
        print(f"Archivo creado/sobrescrito en: {archivo}")

    except Exception as e:
        print("Error al crear el archivo:", e)