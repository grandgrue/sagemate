import os
from dotenv import load_dotenv

# .env laden
load_dotenv()

# Proxy aus .env setzen
http_proxy = os.getenv('HTTP_PROXY')
if http_proxy:
    os.environ['HTTP_PROXY'] = http_proxy
    os.environ['HTTPS_PROXY'] = os.getenv('HTTPS_PROXY', http_proxy)
    print(f"🌐 Proxy aktiviert\n")

from atproto import Client

# Umgebungsvariablen laden
load_dotenv()

def debug_env_vars():
    """Prüft ob Umgebungsvariablen geladen sind"""
    print("🔍 Prüfe Umgebungsvariablen...\n")
    
    handle = os.getenv('BLUESKY_HANDLE')
    password = os.getenv('BLUESKY_PASSWORD')
    api_key = os.getenv('ANTHROPIC_API_KEY')
    
    print(f"BLUESKY_HANDLE: {'✅ gefunden' if handle else '❌ FEHLT'}")
    if handle:
        print(f"  Wert: {handle}")
    
    print(f"BLUESKY_PASSWORD: {'✅ gefunden' if password else '❌ FEHLT'}")
    if password:
        print(f"  Länge: {len(password)} Zeichen")
    
    print(f"ANTHROPIC_API_KEY: {'✅ gefunden' if api_key else '❌ FEHLT'}")
    if api_key:
        print(f"  Beginnt mit: {api_key[:10]}...")
    
    print()
    return handle and password and api_key

def test_bluesky_connection():
    """Testet die Verbindung zu Bluesky"""
    print("🔄 Verbinde mit Bluesky...")
    
    # Bluesky Client erstellen
    client = Client()
    
    # Login
    handle = os.getenv('BLUESKY_HANDLE')
    password = os.getenv('BLUESKY_PASSWORD')
    
    try:
        client.login(handle, password)
        print(f"✅ Erfolgreich eingeloggt als: {handle}")
        
        # Hole eigenes Profil
        profile = client.get_profile(handle)
        print(f"📊 Display Name: {profile.display_name}")
        print(f"👥 Followers: {profile.followers_count}")
        
        return client
    except Exception as e:
        print(f"❌ Fehler beim Login: {e}")
        return None

if __name__ == "__main__":
    print("=== Sagemate Bot - Debug & Test ===\n")
    
    # Erst debuggen
    if debug_env_vars():
        # Dann Verbindung testen
        client = test_bluesky_connection()
    else:
        print("⚠️ Bitte .env Datei prüfen und Keys eintragen!")