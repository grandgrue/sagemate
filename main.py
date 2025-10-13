import warnings
warnings.filterwarnings('ignore', category=UserWarning, module='pydantic')

import os
import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv
import anthropic
from atproto import Client

# .env laden
load_dotenv()

# Proxy aus .env setzen (nur lokal nötig, nicht auf Railway)
http_proxy = os.getenv('HTTP_PROXY')
if http_proxy:
    os.environ['HTTP_PROXY'] = http_proxy
    os.environ['HTTPS_PROXY'] = os.getenv('HTTPS_PROXY', http_proxy)
    print(f"🌐 Proxy aktiviert: {http_proxy}\n")


def debug_env_vars():
    """Prüft ob alle benötigten Umgebungsvariablen vorhanden sind"""
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
        return "Du bist ein hilfreicher Assistent auf Bluesky. Antworte kurz und prägnant."


def test_bluesky_connection():
    """Testet die Verbindung zu Bluesky"""
    print("🔄 Verbinde mit Bluesky...")
    
    client = Client()
    handle = os.getenv('BLUESKY_HANDLE')
    password = os.getenv('BLUESKY_PASSWORD')
    
    try:
        client.login(handle, password)
        print(f"✅ Erfolgreich eingeloggt als: {handle}")
        
        profile = client.get_profile(handle)
        print(f"📊 Display Name: {profile.display_name}")
        print(f"👥 Followers: {profile.followers_count}\n")
        
        return client
    except Exception as e:
        print(f"❌ Fehler beim Login: {e}")
        return None


def test_claude_api():
    """Testet die Claude API mit Sonnet 4.5"""
    print("🔄 Teste Claude API...")
    
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("❌ ANTHROPIC_API_KEY fehlt in .env")
        return False
    
    try:
        client = anthropic.Anthropic(api_key=api_key)
        
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=50,
            messages=[{
                "role": "user",
                "content": "Antworte mit einem Wort: OK"
            }]
        )
        
        response = message.content[0].text
        print(f"✅ Claude antwortet: {response}\n")
        return True
        
    except Exception as e:
        print(f"❌ Fehler bei Claude: {e}")
        return False


def extract_urls(text):
    """Extrahiert URLs aus einem Text"""
    url_pattern = r'https?://[^\s]+'
    return re.findall(url_pattern, text)


def fetch_url_content(url):
    """Holt den Inhalt einer Webseite"""
    print(f"🔗 Lade Webseite: {url}")
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; SagemateBot/1.0)'}
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Entferne Scripts, Styles, Navigation, etc.
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()
        
        # Hole und bereinige Text
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        text = '\n'.join(line for line in lines if line)
        
        # Begrenze auf 3000 Zeichen (Kosten sparen!)
        content = text[:3000]
        print(f"✅ Webseite geladen: {len(content)} Zeichen")
        return content
        
    except Exception as e:
        print(f"⚠️ Fehler beim Laden der URL: {e}")
        return None


def generate_response_with_claude(post_text, url_content=None):
    """Generiert Antwort mit Claude Sonnet 4.5"""
    print("🤖 Generiere Antwort mit Claude Sonnet 4.5...")
    
    api_key = os.getenv('ANTHROPIC_API_KEY')
    client = anthropic.Anthropic(api_key=api_key)
    
    # System-Prompt laden
    system_prompt = load_system_prompt()
    
    # User-Prompt zusammenstellen
    if url_content:
        user_prompt = f"""Ein Nutzer hat folgenden Post geschrieben und dabei auf eine Webseite verlinkt:

Post: {post_text}

Webseiten-Inhalt (gekürzt): {url_content}

WICHTIG: Deine Antwort darf maximal 280 Zeichen lang sein! Sei prägnant aber informativ.
Schreibe eine hilfreiche Antwort."""
    else:
        user_prompt = f"""Ein Nutzer hat folgenden Post geschrieben:

{post_text}

WICHTIG: Deine Antwort darf maximal 280 Zeichen lang sein! Sei prägnant aber informativ.
Schreibe eine hilfreiche Antwort."""
    
    try:
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=200,
            system=system_prompt,
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


def truncate_for_bluesky(text, max_length=280):
    """Kürzt Text auf Bluesky-sichere Länge (280 Zeichen)"""
    if len(text) <= max_length:
        return text
    
    # Kürze beim letzten Wort und füge "..." hinzu
    truncated = text[:max_length - 3].rsplit(' ', 1)[0]
    return truncated + "..."


def get_recent_mentions(client):
    """Holt alle ungelesenen Mentions"""
    print("📬 Prüfe auf neue Mentions...")
    
    try:
        notifications = client.app.bsky.notification.list_notifications()
        
        mentions = []
        for notif in notifications.notifications:
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


def reply_to_mention(client, mention, reply_text):
    """Antwortet auf eine Mention"""
    # Sicherheit: Kürze auf Bluesky-Limit
    safe_text = truncate_for_bluesky(reply_text, max_length=280)
    
    if len(reply_text) > len(safe_text):
        print(f"⚠️ Antwort war zu lang ({len(reply_text)} Zeichen) - gekürzt auf {len(safe_text)}")
    
    print(f"💬 Poste Antwort ({len(safe_text)} Zeichen): {safe_text[:60]}...")
    
    try:
        client.send_post(
            text=safe_text,
            reply_to={
                'root': {'uri': mention['uri'], 'cid': mention['cid']},
                'parent': {'uri': mention['uri'], 'cid': mention['cid']}
            }
        )
        
        print("✅ Antwort erfolgreich gepostet!")
        return True
        
    except Exception as e:
        print(f"❌ Fehler beim Posten: {e}")
        return False


def mark_notification_as_read(client):
    """Markiert alle Notifications als gelesen"""
    try:
        client.app.bsky.notification.update_seen({
            'seen_at': datetime.now().isoformat() + 'Z'
        })
        print("✅ Notifications als gelesen markiert")
    except Exception as e:
        print(f"⚠️ Konnte Notifications nicht als gelesen markieren: {e}")


def process_mention(client, mention):
    """Verarbeitet eine einzelne Mention: URL laden → LLM → Antworten"""
    print(f"\n{'='*60}")
    print(f"📬 Neue Mention von @{mention['author']}")
    print(f"📝 Text: {mention['text']}")
    print(f"{'='*60}")
    
    # 1. Prüfe auf URLs im Post
    urls = extract_urls(mention['text'])
    url_content = None
    
    if urls:
        print(f"\n🔗 {len(urls)} URL(s) gefunden")
        url_content = fetch_url_content(urls[0])
    
    # 2. Generiere Antwort mit Claude Sonnet
    print("\n🤖 Frage Claude Sonnet nach Antwort...")
    response = generate_response_with_claude(mention['text'], url_content)
    
    if not response:
        print("❌ Keine Antwort generiert - überspringe")
        return False
    
    # 3. Poste Antwort auf Bluesky
    success = reply_to_mention(client, mention, response)
    
    if success:
        print(f"\n✅ Mention erfolgreich verarbeitet!")
    
    return success


def process_all_mentions(client):
    """Verarbeitet alle neuen Mentions"""
    print("\n" + "="*60)
    print("🔍 SUCHE NACH NEUEN MENTIONS")
    print("="*60)
    
    # Hole Mentions
    mentions = get_recent_mentions(client)
    
    if not mentions:
        print("📭 Keine neuen Mentions gefunden")
        return 0
    
    # Verarbeite jede Mention
    successful = 0
    for i, mention in enumerate(mentions, 1):
        print(f"\n[{i}/{len(mentions)}]")
        if process_mention(client, mention):
            successful += 1
    
    # Markiere als gelesen
    mark_notification_as_read(client)
    
    print(f"\n{'='*60}")
    print(f"✅ {successful}/{len(mentions)} Mentions erfolgreich verarbeitet")
    print(f"{'='*60}\n")
    
    return successful


def run_bot_continuously(client, check_interval=60):
    """Lässt den Bot dauerhaft laufen und prüft regelmäßig auf Mentions"""
    print("\n" + "="*60)
    print(f"🤖 BOT LÄUFT DAUERHAFT")
    print(f"⏰ Prüft alle {check_interval} Sekunden auf neue Mentions")
    print("="*60)
    print("💡 Drücke Ctrl+C um zu stoppen\n")
    
    iteration = 0
    
    try:
        while True:
            iteration += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            print(f"\n⏰ [{timestamp}] Check #{iteration}")
            
            # Verarbeite alle neuen Mentions
            count = process_all_mentions(client)
            
            if count > 0:
                print(f"✅ {count} Mention(s) bearbeitet")
            
            # Warte bis zum nächsten Check
            print(f"😴 Schlafe {check_interval} Sekunden...")
            time.sleep(check_interval)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Bot wurde manuell gestoppt (Ctrl+C)")
    except Exception as e:
        print(f"\n❌ Unerwarteter Fehler: {e}")
        print("⏳ Warte 60 Sekunden und versuche es erneut...")
        time.sleep(60)
        # Rekursiver Aufruf um Bot am Laufen zu halten
        run_bot_continuously(client, check_interval)


def main():
    """Hauptfunktion"""
    import sys
    
    print("=== Sagemate Bot ===\n")
    
    # Umgebungsvariablen prüfen
    if not debug_env_vars():
        print("⚠️ Bitte .env Datei prüfen!")
        exit(1)
    
    # Bluesky Login
    client = test_bluesky_connection()
    if not client:
        print("❌ Konnte nicht bei Bluesky einloggen")
        exit(1)
    
    # Claude API Test
    if not test_claude_api():
        print("❌ Claude API funktioniert nicht")
        exit(1)
    
    print("✅ Alle Verbindungen erfolgreich!\n")
    
    # Entscheide: Einmal oder Dauerbetrieb?
    if "--continuous" in sys.argv or os.getenv('BOT_MODE') == 'continuous':
        # Dauerbetrieb (für Railway)
        check_interval = int(os.getenv('CHECK_INTERVAL', '60'))
        run_bot_continuously(client, check_interval=check_interval)
    else:
        # Einmal durchlaufen (Test-Modus)
        print("📋 TEST-MODUS (einmalig)")
        print("💡 Für Dauerbetrieb: python main.py --continuous\n")
        process_all_mentions(client)
        print("\n✅ Test abgeschlossen!")


if __name__ == "__main__":
    main()