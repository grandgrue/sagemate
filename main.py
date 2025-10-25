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
import trafilatura

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


def fetch_url_content_trafilatura(url):
    """Holt den Inhalt einer Webseite mit Trafilatura (bessere Extraktion)"""
    print(f"🔗 Lade Webseite mit Trafilatura: {url}")
    
    try:
        # Download der Webseite
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; SagemateBot/1.0)'}
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
        
        # Trafilatura extrahiert den Hauptinhalt (Artikel, Blog-Posts, etc.)
        # Entfernt automatisch Menüs, Werbung, Footer, etc.
        content = trafilatura.extract(
            response.content,
            include_comments=False,  # Keine Kommentare
            include_tables=True,     # Tabellen beibehalten
            no_fallback=False,       # Fallback-Methoden nutzen
            favor_precision=True,    # Höhere Qualität, weniger Rauschen
            with_metadata=False      # Keine Meta-Infos (Autor, Datum, etc.)
        )
        
        if content:
            # Begrenze auf 4000 Zeichen (Kosten sparen!)
            content = content[:4000]
            print(f"✅ Webseite geladen: {len(content)} Zeichen")
            return content
        else:
            print(f"⚠️ Kein Inhalt extrahiert von {url}")
            return None
        
    except Exception as e:
        print(f"⚠️ Fehler beim Laden der URL: {e}")
        return None


def fetch_url_content(url):
    """Wrapper-Funktion für URL-Abruf (Fallback auf BeautifulSoup falls Trafilatura fehlschlägt)"""
    # Versuche zuerst Trafilatura (bessere Artikel-Extraktion)
    content = fetch_url_content_trafilatura(url)
    
    if content:
        return content
    
    # Fallback auf alte BeautifulSoup-Methode wenn Trafilatura fehlschlägt
    print(f"🔄 Fallback: Verwende BeautifulSoup für {url}")
    
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
        print(f"✅ Webseite geladen (Fallback): {len(content)} Zeichen")
        return content
        
    except Exception as e:
        print(f"⚠️ Auch Fallback fehlgeschlagen: {e}")
        return None


def get_thread_context(client, post_uri):
    """Holt den kompletten Thread-Context eines Posts (alle vorherigen Antworten)"""
    print(f"📜 Lade Thread-Context...")
    
    try:
        # Hole Thread über AT Protocol API
        thread = client.get_post_thread(uri=post_uri)
        
        # Sammle alle Posts im Thread
        context_posts = []
        
        # Funktion zum rekursiven Durchlaufen des Threads
        def collect_posts(post_obj, depth=0):
            if not post_obj or depth > 10:  # Max 10 Ebenen tief (Schutz vor Endlosschleifen)
                return
            
            # Aktueller Post
            if hasattr(post_obj, 'post'):
                post = post_obj.post
                context_posts.append({
                    'author': post.author.handle if hasattr(post.author, 'handle') else 'unknown',
                    'text': post.record.text if hasattr(post.record, 'text') else '',
                    'created_at': post.record.created_at if hasattr(post.record, 'created_at') else ''
                })
            
            # Parent-Posts rekursiv sammeln (gehe die Kette nach oben)
            if hasattr(post_obj, 'parent'):
                collect_posts(post_obj.parent, depth + 1)
        
        # Starte Sammlung beim aktuellen Post
        collect_posts(thread.thread)
        
        # Sortiere chronologisch (älteste zuerst = Thread-Reihenfolge)
        context_posts.reverse()
        
        print(f"✅ {len(context_posts)} Post(s) im Thread gefunden")
        return context_posts
        
    except Exception as e:
        print(f"⚠️ Fehler beim Laden des Thread-Contexts: {e}")
        return []


def generate_response_with_claude(mention_text, thread_context=None, url_contents=None):
    """
    Generiert Antwort mit Claude Sonnet 4.5 unter Berücksichtigung des Thread-Contexts
    
    Args:
        mention_text: Der Text der aktuellen Mention
        thread_context: Liste von Posts im Thread (chronologisch)
        url_contents: Dict mit URL -> Inhalt Mapping
    """
    print("🤖 Generiere Antwort mit Claude Sonnet 4.5...")
    
    api_key = os.getenv('ANTHROPIC_API_KEY')
    client = anthropic.Anthropic(api_key=api_key)
    
    # System-Prompt laden
    system_prompt = load_system_prompt()
    
    # User-Prompt zusammenstellen
    user_prompt_parts = []
    
    # 1. Thread-Context hinzufügen (falls vorhanden)
    if thread_context and len(thread_context) > 0:
        user_prompt_parts.append("KONVERSATIONS-VERLAUF (chronologisch):")
        for i, post in enumerate(thread_context, 1):
            user_prompt_parts.append(f"{i}. @{post['author']}: {post['text']}")
        user_prompt_parts.append("\n---\n")
    
    # 2. Aktuelle Mention
    user_prompt_parts.append(f"AKTUELLE MENTION (an dich gerichtet):\n{mention_text}")
    
    # 3. URL-Inhalte hinzufügen (falls vorhanden)
    if url_contents:
        user_prompt_parts.append("\n---\n")
        user_prompt_parts.append("VERLINKTE WEBSEITEN-INHALTE:")
        for i, (url, content) in enumerate(url_contents.items(), 1):
            # Max 2000 Zeichen pro URL (Kosten sparen)
            user_prompt_parts.append(f"\nURL {i}: {url}\n{content[:2000]}")
    
    # 4. Anweisungen für Claude
    user_prompt_parts.append("\n---\n")
    user_prompt_parts.append("WICHTIG: Deine Antwort darf maximal 280 Zeichen lang sein!")
    user_prompt_parts.append("Berücksichtige den Konversationsverlauf und die Webseiten-Inhalte.")
    user_prompt_parts.append("Schreibe eine hilfreiche, kontextbezogene Antwort.")
    
    user_prompt = "\n".join(user_prompt_parts)
    
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
    """
    Verarbeitet eine einzelne Mention mit vollem Kontext
    
    Workflow:
    1. Thread-Context laden (alle vorherigen Posts)
    2. URLs aus Mention UND Thread extrahieren
    3. Webseiten-Inhalte laden
    4. Claude um Antwort bitten (mit Kontext + URLs)
    5. Antwort auf Bluesky posten
    """
    print(f"\n{'='*60}")
    print(f"📬 Neue Mention von @{mention['author']}")
    print(f"📝 Text: {mention['text']}")
    print(f"{'='*60}")
    
    # 1. Hole Thread-Context (alle Posts die zu dieser Konversation gehören)
    thread_context = get_thread_context(client, mention['uri'])
    
    # 2. Sammle alle URLs aus der Mention UND aus dem gesamten Thread
    all_text = mention['text']
    if thread_context:
        # Füge alle Thread-Posts zusammen um URLs zu finden
        all_text += " " + " ".join([post['text'] for post in thread_context])
    
    urls = extract_urls(all_text)
    url_contents = {}
    
    if urls:
        print(f"\n🔗 {len(urls)} URL(s) im Thread gefunden")
        # Lade max. 3 URLs um Kosten/Zeit zu sparen
        for url in urls[:3]:
            content = fetch_url_content(url)
            if content:
                url_contents[url] = content
    
    # 3. Generiere Antwort mit Claude (mit vollem Kontext)
    print("\n🤖 Frage Claude Sonnet nach Antwort (mit Kontext)...")
    response = generate_response_with_claude(
        mention['text'], 
        thread_context=thread_context,
        url_contents=url_contents if url_contents else None
    )
    
    if not response:
        print("❌ Keine Antwort generiert - überspringe")
        return False
    
    # 4. Poste Antwort auf Bluesky
    success = reply_to_mention(client, mention, response)
    
    if success:
        print(f"\n✅ Mention erfolgreich verarbeitet!")
    
    return success


def process_all_mentions(client):
    """Verarbeitet alle neuen Mentions"""
    print("\n" + "="*60)
    print("🔍 SUCHE NACH NEUEN MENTIONS")
    print("="*60)
    
    mentions = get_recent_mentions(client)
    
    if not mentions:
        print("📭 Keine neuen Mentions gefunden")
        return 0
    
    successful = 0
    for i, mention in enumerate(mentions, 1):
        print(f"\n[{i}/{len(mentions)}]")
        if process_mention(client, mention):
            successful += 1
    
    mark_notification_as_read(client)
    
    print(f"\n{'='*60}")
    print(f"✅ {successful}/{len(mentions)} Mentions erfolgreich verarbeitet")
    print(f"{'='*60}\n")
    
    return successful


def run_bot_continuously(client, check_interval=60):
    """
    Lässt den Bot dauerhaft laufen und prüft regelmäßig auf Mentions
    
    Der Bot läuft in einer Endlosschleife und:
    - Prüft alle X Sekunden auf neue Mentions
    - Verarbeitet alle gefundenen Mentions
    - Behandelt Fehler gracefully und startet neu
    - Kann mit Ctrl+C gestoppt werden
    """
    print("\n" + "="*60)
    print(f"🤖 BOT LÄUFT DAUERHAFT")
    print(f"⏰ Prüft alle {check_interval} Sekunden auf neue Mentions")
    print("="*60)
    print("💡 Drücke Ctrl+C um zu stoppen\n")
    
    iteration = 0
    
    try:
        while True:  # Endlosschleife für 24/7 Betrieb
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
        # Manuelles Stoppen mit Ctrl+C
        print("\n\n🛑 Bot wurde manuell gestoppt (Ctrl+C)")
    except Exception as e:
        # Bei unerwartetem Fehler: Warte und versuche neu zu starten
        print(f"\n❌ Unerwarteter Fehler: {e}")
        print("⏳ Warte 60 Sekunden und versuche es erneut...")
        time.sleep(60)
        # Rekursiver Aufruf um Bot am Laufen zu halten
        run_bot_continuously(client, check_interval)


def main():
    """Hauptfunktion"""
    import sys
    
    print("=== Sagemate Bot (Extended) ===\n")
    
    if not debug_env_vars():
        print("⚠️ Bitte .env Datei prüfen!")
        exit(1)
    
    client = test_bluesky_connection()
    if not client:
        print("❌ Konnte nicht bei Bluesky einloggen")
        exit(1)
    
    if not test_claude_api():
        print("❌ Claude API funktioniert nicht")
        exit(1)
    
    print("✅ Alle Verbindungen erfolgreich!\n")
    
    if "--continuous" in sys.argv or os.getenv('BOT_MODE') == 'continuous':
        check_interval = int(os.getenv('CHECK_INTERVAL', '60'))
        run_bot_continuously(client, check_interval=check_interval)
    else:
        print("📋 TEST-MODUS (einmalig)")
        print("💡 Für Dauerbetrieb: python main.py --continuous\n")
        process_all_mentions(client)
        print("\n✅ Test abgeschlossen!")


if __name__ == "__main__":
    main()