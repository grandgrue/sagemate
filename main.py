import warnings
warnings.filterwarnings('ignore', category=UserWarning, module='pydantic')

import os
from dotenv import load_dotenv

import anthropic

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

def load_system_prompt():
    """Lädt den System-Prompt aus Datei"""
    try:
        with open('system_prompt.txt', 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        print("⚠️ system_prompt.txt nicht gefunden, nutze Standard-Prompt")
        # Fallback-Prompt
        return "Du bist ein hilfreicher Assistent auf Bluesky. Antworte kurz und prägnant."

def generate_response_with_claude(post_text, url_content=None):
    """Generiert Antwort mit Claude unter Verwendung des System-Prompts"""
    print("🤖 Generiere Antwort mit Claude...")
    
    api_key = os.getenv('ANTHROPIC_API_KEY')
    client = anthropic.Anthropic(api_key=api_key)
    
    # System-Prompt laden
    system_prompt = load_system_prompt()
    
    # User-Prompt zusammenstellen
    if url_content:
        user_prompt = f"""Ein Nutzer hat folgenden Post geschrieben und dabei auf eine Webseite verlinkt:

Post: {post_text}

Webseiten-Inhalt (gekürzt): {url_content}

Schreibe eine hilfreiche Antwort."""
    else:
        user_prompt = f"""Ein Nutzer hat folgenden Post geschrieben:

{post_text}

Schreibe eine hilfreiche Antwort."""
    
    try:
        message = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=300,
            system=system_prompt,  # ← Hier wird der System-Prompt übergeben!
            messages=[{
                "role": "user",
                "content": user_prompt
            }]
        )
        
        response = message.content[0].text
        print(f"✅ Antwort generiert: {response[:80]}...")
        return response
        
    except Exception as e:
        print(f"❌ Fehler bei Claude: {e}")
        return None

def test_response_generation():
    """Testet die Antwort-Generierung"""
    print("\n🧪 Teste Antwort-Generierung...\n")
    
    # Test 1: Einfacher Post
    test_post = "Hey @sagemate, kannst du mir Python erklären?"
    response = generate_response_with_claude(test_post)
    
    if response:
        print(f"\n📝 Test-Post: {test_post}")
        print(f"💬 Bot-Antwort: {response}\n")
    
    return response is not None

def get_recent_mentions(client):
    """Holt die neuesten Mentions"""
    print("\n📬 Prüfe auf neue Mentions...")
    
    try:
        # Hole Notifications
        notifications = client.app.bsky.notification.list_notifications()
        
        mentions = []
        for notif in notifications.notifications:
            # Nur Mentions, die noch nicht gelesen sind
            if notif.reason == 'mention' and not notif.is_read:
                mentions.append({
                    'author': notif.author.handle,
                    'text': notif.record.text if hasattr(notif.record, 'text') else "",
                    'uri': notif.uri,
                    'cid': notif.cid
                })
        
        if mentions:
            print(f"✅ {len(mentions)} neue Mention(s) gefunden!")
        else:
            print("📭 Keine neuen Mentions")
        
        return mentions
        
    except Exception as e:
        print(f"❌ Fehler beim Abrufen von Mentions: {e}")
        return []

def test_mentions():
    """Testet das Abrufen von Mentions"""
    print("\n🧪 Teste Mentions abrufen...\n")
    
    # Bluesky Login
    client = test_bluesky_connection()
    if not client:
        return False
    
    # Mentions holen
    mentions = get_recent_mentions(client)
    
    if mentions:
        print("\n📋 Gefundene Mentions:")
        for m in mentions:
            print(f"  👤 @{m['author']}: {m['text'][:60]}...")
    
    return True

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
    
def test_claude_api():
    """Testet die Claude API"""
    print("\n🔄 Teste Claude API...")
    
    api_key = os.getenv('ANTHROPIC_API_KEY')
    
    if not api_key:
        print("❌ ANTHROPIC_API_KEY fehlt in .env")
        return False
    
    try:
        client = anthropic.Anthropic(api_key=api_key)
        
        message = client.messages.create(
            model="claude-3-haiku-20240307",  # ← KORRIGIERT!
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": "Antworte mit genau einem Satz: Funktioniert die API?"
            }]
        )
        
        response = message.content[0].text
        print(f"✅ Claude antwortet: {response}")
        return True
        
    except Exception as e:
        print(f"❌ Fehler bei Claude: {e}")
        return False
    

if __name__ == "__main__":
    print("=== Sagemate Bot - Tests ===\n")
    
    # Test 1: Umgebungsvariablen
    if not debug_env_vars():
        print("⚠️ Bitte .env Datei prüfen!")
        exit(1)
    
    # Test 2: Bluesky-Verbindung
    client = test_bluesky_connection()
    if not client:
        exit(1)
    
    # Test 3: Claude API
    if not test_claude_api():
        exit(1)
    
    # Test 4: Antwort-Generierung mit System-Prompt
    if not test_response_generation():
        exit(1)
    
    # Test 5: Mentions abrufen
    test_mentions()
    
    print("\n✅ Alle Tests erfolgreich!")