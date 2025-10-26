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


def extract_urls_from_post(post):
    """
    Extrahiert URLs aus einem Bluesky Post-Objekt
    
    Bluesky speichert URLs an mehreren Stellen:
    1. Im Text selbst
    2. In facets (strukturierte Link-Metadaten)
    3. In embeds (Link-Cards, externe Inhalte)
    """
    urls = []
    
    # 1. URLs aus dem Text extrahieren
    if hasattr(post, 'text'):
        text_urls = extract_urls(post.text)
        urls.extend(text_urls)
    
    # 2. URLs aus facets extrahieren (strukturierte Links)
    if hasattr(post, 'facets') and post.facets:
        for facet in post.facets:
            if hasattr(facet, 'features'):
                for feature in facet.features:
                    # Link-Feature
                    if hasattr(feature, 'uri'):
                        urls.append(feature.uri)
    
    # 3. URLs aus embeds extrahieren (Link-Cards)
    if hasattr(post, 'embed'):
        embed = post.embed
        
        # External embed (Link-Card)
        if hasattr(embed, 'external') and hasattr(embed.external, 'uri'):
            urls.append(embed.external.uri)
        
        # Record embed (Quote-Post mit möglicherweise URLs)
        if hasattr(embed, 'record'):
            record = embed.record
            if hasattr(record, 'uri'):
                # Rekursiv URLs aus eingebettetem Post extrahieren
                if hasattr(record, 'value'):
                    nested_urls = extract_urls_from_post(record.value)
                    urls.extend(nested_urls)
    
    # Duplikate entfernen und zurückgeben
    return list(set(urls))


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
    """
    Holt den kompletten Thread-Context eines Posts (alle vorherigen Antworten)
    Gibt Post-Objekte mit allen Metadaten zurück
    """
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
                    'created_at': post.record.created_at if hasattr(post.record, 'created_at') else '',
                    'record': post.record  # Speichere vollständiges record für URL-Extraktion
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
    
    # Kürze beim letzten Wort und füge "..." hinzu
    truncated = text[:max_length - 3].rsplit(' ', 1)[0]
    return truncated + "..."


def get_recent_mentions(client):
    """Holt alle ungelesenen Mentions mit vollständigen Post-Daten"""
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
                    'cid': notif.cid,
                    'record': notif.record  # Vollständiges record für URL-Extraktion
                })
        
        if mentions:
            print(f"✅ {len(mentions)} neue Mention(s) gefunden!")
        else:
            print("📭 Keine neuen Mentions")
        
        return mentions
        
    except Exception as e:
        print(f"❌ Fehler beim Abrufen von Mentions: {e}")
        return []


def get_direct_messages(client):
    """
    Holt alle ungelesenen Direktnachrichten
    
    NEU: Diese Funktion sucht nach Direktnachrichten die mit "Per Direktnachricht senden"
    gesendet wurden und auf einen Post verweisen
    
    WICHTIG: 
    - App-Passwort muss DM-Berechtigung haben!
    - Nutzt Chat-Proxy für DM-API-Zugriff
    - Filtert bereits verarbeitete Nachrichten
    """
    print("💌 Prüfe auf neue Direktnachrichten...")
    
    try:
        # Erstelle Chat-Proxy-Client für DM-API-Zugriff
        # Dies ist notwendig weil DM-API über einen separaten Service läuft
        dm_client = client.with_bsky_chat_proxy()
        
        # Shortcut zu Convo-Methoden
        dm = dm_client.chat.bsky.convo
        
        # Hole Chat-Liste
        convos = dm.list_convos()
        
        dms = []
        
        for convo in convos.convos:
            # Prüfe ob es ungelesene Nachrichten gibt
            if convo.unread_count > 0:
                # Hole Nachrichten dieser Konversation
                messages = dm.get_messages({
                    'convo_id': convo.id
                })
                
                for msg in messages.messages:
                    # Prüfe ob Nachricht von anderem Nutzer
                    if msg.sender.did != client.me.did:
                        # Prüfe ob es eine "Per Direktnachricht senden" Nachricht ist
                        # Diese haben normalerweise ein embed mit dem referenzierten Post
                        if hasattr(msg, 'embed') and msg.embed:
                            dms.append({
                                'convo_id': convo.id,
                                'message_id': msg.id,
                                'sender': msg.sender.handle if hasattr(msg.sender, 'handle') else 'unknown',
                                'text': msg.text if hasattr(msg, 'text') else "",
                                'embed': msg.embed,
                                'sent_at': msg.sent_at
                            })
        
        if dms:
            print(f"✅ {len(dms)} neue DM(s) mit Post-Referenz gefunden!")
        else:
            print("📭 Keine neuen DMs mit Post-Referenz")
        
        return dms
        
    except AttributeError as e:
        # with_bsky_chat_proxy() existiert nicht
        error_str = str(e)
        if 'with_bsky_chat_proxy' in error_str:
            print(f"⚠️  Deine atproto-Version unterstützt Chat-Proxy nicht")
            print(f"   Bitte aktualisiere: pip install --upgrade atproto")
        else:
            print(f"ℹ️  Chat-API nicht verfügbar: {e}")
        print("   DM-Support wird übersprungen (nur Mentions werden verarbeitet)")
        client._dm_not_available = True
        return []
    except Exception as e:
        # Prüfe auf spezifische API-Fehler
        error_str = str(e)
        if 'XRPCNotSupported' in error_str or '404' in error_str:
            print(f"ℹ️  Chat/DM-API nicht unterstützt oder App-Passwort hat keine DM-Berechtigung")
            print(f"   LÖSUNG: Erstelle neues App-Passwort mit DM-Zugriff in Bluesky-Einstellungen")
            print("   Der Bot arbeitet weiter im Mention-Modus")
            client._dm_not_available = True
        elif 'Bad token scope' in error_str or 'AuthScopeMismatch' in error_str:
            print(f"⚠️  App-Passwort hat keine DM-Berechtigung!")
            print(f"   LÖSUNG: Erstelle neues App-Passwort mit aktiviertem DM-Zugriff")
            print(f"   Gehe zu: Einstellungen → App-Passwörter → Neues erstellen")
            print(f"   ✓ Aktiviere 'Direct Messages' beim Erstellen")
            client._dm_not_available = True
        else:
            print(f"⚠️  Unerwarteter Fehler beim Abrufen von DMs: {e}")
            print(f"   Fehlertyp: {type(e).__name__}")
        return []


def get_post_from_dm_embed(client, dm):
    """
    Extrahiert den referenzierten Post aus einer DM
    
    Args:
        dm: DM-Objekt mit embed
    
    Returns:
        Post-Objekt oder None
    """
    try:
        embed = dm['embed']
        
        # Prüfe ob es ein Record-Embed ist (Post-Referenz)
        if hasattr(embed, 'record'):
            record = embed.record
            
            # Hole URI des referenzierten Posts
            if hasattr(record, 'uri'):
                post_uri = record.uri
                print(f"🔗 Post-Referenz in DM gefunden: {post_uri}")
                
                # Hole den vollständigen Post
                thread = client.get_post_thread(uri=post_uri)
                
                if hasattr(thread, 'thread') and hasattr(thread.thread, 'post'):
                    post = thread.thread.post
                    return {
                        'author': post.author.handle if hasattr(post.author, 'handle') else 'unknown',
                        'text': post.record.text if hasattr(post.record, 'text') else '',
                        'uri': post_uri,
                        'cid': post.cid if hasattr(post, 'cid') else None,
                        'record': post.record
                    }
        
        return None
        
    except Exception as e:
        print(f"⚠️ Fehler beim Extrahieren des Posts aus DM: {e}")
        return None


def send_dm_reply(client, convo_id, reply_text, dry_run=False):
    """
    Sendet eine Antwort per Direktnachricht
    
    Args:
        client: Bluesky Client
        convo_id: Konversations-ID
        reply_text: Text der Antwort
        dry_run: Wenn True, wird nicht wirklich gesendet
    """
    # Sicherheit: Kürze auf Bluesky-Limit (DMs haben oft höheres Limit, aber bleiben wir sicher)
    safe_text = truncate_for_bluesky(reply_text, max_length=1000)
    
    print(f"\n{'='*60}")
    print(f"💌 DM-ANTWORT ({len(safe_text)} Zeichen):")
    print(f"{'='*60}")
    print(safe_text)
    print(f"{'='*60}\n")
    
    # DRY RUN MODE
    if dry_run:
        print("🧪 DRY RUN MODUS: DM wird NICHT gesendet!")
        return True
    
    # Wirklich senden
    try:
        # Erstelle Chat-Proxy-Client
        dm_client = client.with_bsky_chat_proxy()
        
        # Sende Nachricht
        from atproto import models
        dm_client.chat.bsky.convo.send_message(
            models.ChatBskyConvoSendMessage.Data(
                convo_id=convo_id,
                message=models.ChatBskyConvoDefs.MessageInput(
                    text=safe_text
                )
            )
        )
        
        print("✅ DM erfolgreich gesendet!")
        return True
        
    except Exception as e:
        print(f"❌ Fehler beim Senden der DM: {e}")
        return False


def process_dm(client, dm, dry_run=False):
    """
    Verarbeitet eine einzelne Direktnachricht
    
    WICHTIG: Bot antwortet ÖFFENTLICH auf den referenzierten Post, nicht per DM!
    
    Workflow:
    1. Extrahiere referenzierten Post aus DM
    2. Lade Thread-Context des Posts
    3. Extrahiere URLs aus Post und Thread
    4. Lade Webseiten-Inhalte
    5. Generiere Antwort mit Claude (basierend auf referenziertem Post)
    6. Poste Antwort ÖFFENTLICH auf Bluesky (als Reply auf den Post)
    7. Markiere DM als gelesen
    
    Args:
        dry_run: Wenn True, wird nichts wirklich gepostet
    """
    print(f"\n{'='*60}")
    print(f"💌 Neue DM von @{dm['sender']}")
    if dm['text']:
        print(f"📝 Nachricht: {dm['text']}")
    print(f"{'='*60}")
    
    # 1. Hole referenzierten Post aus DM
    referenced_post = get_post_from_dm_embed(client, dm)
    
    if not referenced_post:
        print("⚠️ Kein Post in DM referenziert - überspringe")
        # Markiere trotzdem als gelesen um nicht erneut zu verarbeiten
        if not dry_run:
            mark_dm_as_read(client, dm['convo_id'])
        return False
    
    print(f"✅ Referenzierter Post von @{referenced_post['author']}:")
    print(f"   {referenced_post['text'][:150]}...")
    print(f"🎯 Bot wird ÖFFENTLICH auf diesen Post antworten!")
    
    # 2. Hole Thread-Context des referenzierten Posts
    thread_context = get_thread_context(client, referenced_post['uri'])
    
    # LOGGING: Thread-Context anzeigen
    if thread_context and len(thread_context) > 0:
        print(f"\n📜 THREAD-CONTEXT ({len(thread_context)} Posts):")
        print("="*60)
        for i, post in enumerate(thread_context, 1):
            print(f"{i}. @{post['author']}:")
            print(f"   {post['text'][:150]}{'...' if len(post['text']) > 150 else ''}")
            print()
        print("="*60)
    
    # 3. Sammle URLs aus dem Post und Thread
    all_urls = []
    
    # URLs aus dem referenzierten Post
    if 'record' in referenced_post and referenced_post['record']:
        post_urls = extract_urls_from_post(referenced_post['record'])
        all_urls.extend(post_urls)
        print(f"\n🔍 {len(post_urls)} URL(s) im referenzierten Post gefunden")
    
    # URLs aus Thread
    if thread_context:
        for post in thread_context:
            if 'record' in post and post['record']:
                post_urls = extract_urls_from_post(post['record'])
                all_urls.extend(post_urls)
        print(f"🔍 Insgesamt {len(all_urls)} URL(s) in Thread")
    
    # Duplikate entfernen
    urls = list(set(all_urls))
    url_contents = {}
    
    if urls:
        print(f"\n🔗 {len(urls)} eindeutige URL(s) gefunden:")
        # Lade max. 3 URLs
        for idx, url in enumerate(urls[:3], 1):
            print(f"\n  [{idx}] {url}")
            content = fetch_url_content(url)
            if content:
                url_contents[url] = content
                print(f"  ✅ Inhalt: {content[:200]}...")
            else:
                print(f"  ❌ Konnte nicht geladen werden")
        
        if len(urls) > 3:
            print(f"\n  ℹ️ {len(urls) - 3} weitere URL(s) ignoriert (Limit: 3)")
    
    # 4. Generiere Antwort mit Claude
    # Nutze den Text des referenzierten Posts als Basis
    print("\n🤖 Frage Claude nach Antwort zum referenzierten Post...")
    
    # Erstelle Kontext-Text für Claude
    context_text = f"Frage/Post von @{referenced_post['author']}:\n{referenced_post['text']}"
    
    # Optional: Füge DM-Text hinzu wenn vorhanden
    if dm['text']:
        context_text += f"\n\nZusätzliche Notiz vom Nutzer:\n{dm['text']}"
    
    response = generate_response_with_claude(
        context_text,
        thread_context=thread_context,
        url_contents=url_contents if url_contents else None
    )
    
    if not response:
        print("❌ Keine Antwort generiert - überspringe")
        # Markiere trotzdem als gelesen
        if not dry_run:
            mark_dm_as_read(client, dm['convo_id'])
        return False
    
    # 5. Poste Antwort ÖFFENTLICH auf Bluesky (als Reply auf den Post)
    print("\n🌐 Poste öffentliche Antwort auf Bluesky...")
    success = reply_to_mention(client, referenced_post, response, dry_run=dry_run)
    
    # 6. Markiere DM als gelesen (WICHTIG!)
    if not dry_run:
        mark_dm_as_read(client, dm['convo_id'])
    else:
        print("🧪 DRY RUN: DM wird NICHT als gelesen markiert")
    
    if success:
        print(f"\n✅ Post erfolgreich öffentlich beantwortet!")
        print(f"   Für @{dm['sender']}: Aktivierung per DM erfolgreich!")
        print(f"   Für andere: Bot hat von sich aus geantwortet")
    
    return success


def is_mention_empty(mention_text, bot_handle):
    """
    Prüft ob eine Mention "leer" ist (nur Bot-Mention, kein substantieller Text)
    
    Args:
        mention_text: Der Text der Mention
        bot_handle: Der Handle des Bots (z.B. "sagemate.bsky.social")
    """
    # Entferne alle @mentions aus dem Text
    text_without_mentions = re.sub(r'@[\w\.-]+', '', mention_text).strip()
    
    # Prüfe ob nach Entfernung der Mentions substantieller Text übrig bleibt
    # Weniger als 3 Zeichen = leer
    return len(text_without_mentions) < 3


def get_parent_post(client, mention):
    """
    Holt den Parent-Post einer Reply (falls vorhanden)
    
    Returns:
        Parent-Post Objekt oder None
    """
    try:
        # Prüfe ob Mention ein reply_to hat
        if not hasattr(mention['record'], 'reply'):
            return None
        
        reply_info = mention['record'].reply
        
        # Hole Parent-Post URI
        if hasattr(reply_info, 'parent') and hasattr(reply_info.parent, 'uri'):
            parent_uri = reply_info.parent.uri
            
            print(f"🔗 Mention ist Reply auf anderen Post: {parent_uri}")
            
            # Hole den vollständigen Parent-Post
            thread = client.get_post_thread(uri=parent_uri)
            
            if hasattr(thread, 'thread') and hasattr(thread.thread, 'post'):
                parent_post = thread.thread.post
                return {
                    'author': parent_post.author.handle if hasattr(parent_post.author, 'handle') else 'unknown',
                    'text': parent_post.record.text if hasattr(parent_post.record, 'text') else '',
                    'uri': parent_uri,
                    'cid': parent_post.cid if hasattr(parent_post, 'cid') else None,
                    'record': parent_post.record
                }
        
        return None
        
    except Exception as e:
        print(f"⚠️ Fehler beim Holen des Parent-Posts: {e}")
        return None


def reply_to_mention(client, mention, reply_text, dry_run=False):
    """
    Antwortet auf eine Mention
    
    Args:
        client: Bluesky Client
        mention: Mention-Objekt
        reply_text: Text der Antwort
        dry_run: Wenn True, wird nicht wirklich gepostet (nur geloggt)
    """
    # Sicherheit: Kürze auf Bluesky-Limit
    safe_text = truncate_for_bluesky(reply_text, max_length=280)
    
    if len(reply_text) > len(safe_text):
        print(f"⚠️ Antwort war zu lang ({len(reply_text)} Zeichen) - gekürzt auf {len(safe_text)}")
    
    print(f"\n{'='*60}")
    print(f"💬 ANTWORT ({len(safe_text)} Zeichen):")
    print(f"{'='*60}")
    print(safe_text)
    print(f"{'='*60}\n")
    
    # DRY RUN MODE - Nicht wirklich posten
    if dry_run:
        print("🧪 DRY RUN MODUS: Antwort wird NICHT gepostet!")
        return True
    
    # Wirklich auf Bluesky posten
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


def mark_dm_as_read(client, convo_id):
    """
    Markiert alle Nachrichten in einer Konversation als gelesen
    
    Args:
        client: Bluesky Client
        convo_id: Konversations-ID
    """
    try:
        # Erstelle Chat-Proxy-Client
        dm_client = client.with_bsky_chat_proxy()
        
        # Markiere Konversation als gelesen
        dm_client.chat.bsky.convo.update_read({
            'convo_id': convo_id
        })
        
        print("✅ DM-Konversation als gelesen markiert")
        return True
        
    except Exception as e:
        print(f"⚠️ Konnte DM nicht als gelesen markieren: {e}")
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


def process_mention(client, mention, dry_run=False):
    """
    Verarbeitet eine einzelne Mention mit vollem Kontext
    
    Workflow:
    1. Prüfe ob Mention leer ist & ob sie Reply auf anderen Post ist
    2. Thread-Context laden (alle vorherigen Posts)
    3. URLs aus Mention UND Thread extrahieren (aus facets/embeds!)
    4. Webseiten-Inhalte laden
    5. Claude um Antwort bitten (mit Kontext + URLs)
    6. Antwort auf Bluesky posten (entweder auf Mention oder auf Original-Post)
    
    Args:
        dry_run: Wenn True, wird nicht wirklich auf Bluesky gepostet
    """
    print(f"\n{'='*60}")
    print(f"📬 Neue Mention von @{mention['author']}")
    print(f"📝 Text: {mention['text']}")
    print(f"{'='*60}")
    
    # SPECIAL CASE: Leere Mention die auf anderen Post antwortet
    bot_handle = os.getenv('BLUESKY_HANDLE')
    reply_target = mention  # Default: Antworte auf Mention selbst
    
    if is_mention_empty(mention['text'], bot_handle):
        print("\n🔍 Mention ist leer (nur @mention ohne Text)")
        
        parent_post = get_parent_post(client, mention)
        
        if parent_post:
            print(f"✅ Bot wird auf Original-Post antworten:")
            print(f"   @{parent_post['author']}: {parent_post['text'][:100]}...")
            
            # WICHTIG: Ändere reply_target auf parent_post
            reply_target = parent_post
            
            # Nutze Text des Original-Posts als "Mention-Text" für Kontext
            mention_text_for_claude = parent_post['text']
        else:
            print("⚠️ Kein Parent-Post gefunden, antworte auf Mention")
            mention_text_for_claude = mention['text']
    else:
        mention_text_for_claude = mention['text']
    
    # 1. Hole Thread-Context (alle Posts die zu dieser Konversation gehören)
    # Nutze den reply_target URI (entweder Mention oder Parent)
    thread_context = get_thread_context(client, reply_target['uri'])
    
    # LOGGING: Thread-Context anzeigen
    if thread_context and len(thread_context) > 0:
        print(f"\n📜 THREAD-CONTEXT ({len(thread_context)} Posts):")
        print("="*60)
        for i, post in enumerate(thread_context, 1):
            print(f"{i}. @{post['author']}:")
            print(f"   {post['text'][:150]}{'...' if len(post['text']) > 150 else ''}")
            print()
        print("="*60)
    else:
        print("\n📭 Kein Thread-Context (direkte Mention ohne Vorgänger)")
    
    # 2. Sammle URLs aus der Mention/Parent UND aus dem gesamten Thread
    # WICHTIG: Nutze extract_urls_from_post() um URLs aus facets/embeds zu finden!
    all_urls = []
    
    # URLs aus dem Reply-Target (Mention oder Parent)
    if 'record' in reply_target and reply_target['record']:
        target_urls = extract_urls_from_post(reply_target['record'])
        all_urls.extend(target_urls)
        print(f"\n🔍 {len(target_urls)} URL(s) im Ziel-Post gefunden")
    
    # URLs aus allen Thread-Posts
    if thread_context:
        for post in thread_context:
            if 'record' in post and post['record']:
                post_urls = extract_urls_from_post(post['record'])
                all_urls.extend(post_urls)
        print(f"🔍 Insgesamt {len(all_urls)} URL(s) in Thread")
    
    # Duplikate entfernen
    urls = list(set(all_urls))
    url_contents = {}
    
    if urls:
        print(f"\n🔗 {len(urls)} eindeutige URL(s) im Thread gefunden:")
        # Lade max. 3 URLs um Kosten/Zeit zu sparen
        for idx, url in enumerate(urls[:3], 1):
            print(f"\n  [{idx}] {url}")
            content = fetch_url_content(url)
            if content:
                url_contents[url] = content
                # LOGGING: Zeige Anfang des extrahierten Inhalts
                print(f"  ✅ Inhalt: {content[:200]}...")
            else:
                print(f"  ❌ Konnte nicht geladen werden")
        
        if len(urls) > 3:
            print(f"\n  ℹ️ {len(urls) - 3} weitere URL(s) ignoriert (Limit: 3)")
    else:
        print("\n📭 Keine URLs im Thread gefunden")
    
    # 3. Generiere Antwort mit Claude (mit vollem Kontext)
    print("\n🤖 Frage Claude Sonnet nach Antwort (mit Kontext)...")
    response = generate_response_with_claude(
        mention_text_for_claude, 
        thread_context=thread_context,
        url_contents=url_contents if url_contents else None
    )
    
    if not response:
        print("❌ Keine Antwort generiert - überspringe")
        return False
    
    # 4. Poste Antwort auf Bluesky (auf reply_target - entweder Mention oder Parent)
    success = reply_to_mention(client, reply_target, response, dry_run=dry_run)
    
    if success:
        print(f"\n✅ Mention erfolgreich verarbeitet!")
    
    return success


def process_all_mentions(client, dry_run=False):
    """
    Verarbeitet alle neuen Mentions
    
    Args:
        dry_run: Wenn True, werden keine Antworten wirklich gepostet
    """
    print("\n" + "="*60)
    print("🔍 SUCHE NACH NEUEN MENTIONS")
    if dry_run:
        print("🧪 DRY RUN MODUS AKTIV - Keine Posts werden veröffentlicht!")
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
        if process_mention(client, mention, dry_run=dry_run):
            successful += 1
    
    # Markiere als gelesen
    if not dry_run:
        mark_notification_as_read(client)
    else:
        print("\n🧪 DRY RUN: Notifications werden NICHT als gelesen markiert")
    
    print(f"\n{'='*60}")
    print(f"✅ {successful}/{len(mentions)} Mentions erfolgreich verarbeitet")
    print(f"{'='*60}\n")
    
    return successful


def process_all_dms(client, dry_run=False):
    """
    Verarbeitet alle neuen Direktnachrichten mit Post-Referenzen
    
    Args:
        dry_run: Wenn True, werden keine Antworten wirklich gesendet
    """
    # Prüfe ob DMs bereits als nicht verfügbar markiert wurden
    if hasattr(client, '_dm_not_available') and client._dm_not_available:
        # Stille Rückkehr - keine Log-Nachricht bei jedem Check
        return 0
    
    print("\n" + "="*60)
    print("🔍 SUCHE NACH NEUEN DIREKTNACHRICHTEN")
    if dry_run:
        print("🧪 DRY RUN MODUS AKTIV - Keine DMs werden gesendet!")
    print("="*60)
    
    # Hole DMs
    dms = get_direct_messages(client)
    
    if not dms:
        print("📭 Keine neuen DMs mit Post-Referenz gefunden")
        return 0
    
    # Verarbeite jede DM
    successful = 0
    for i, dm in enumerate(dms, 1):
        print(f"\n[{i}/{len(dms)}]")
        if process_dm(client, dm, dry_run=dry_run):
            successful += 1
    
    print(f"\n{'='*60}")
    print(f"✅ {successful}/{len(dms)} DMs erfolgreich verarbeitet")
    print(f"{'='*60}\n")
    
    return successful


def run_bot_continuously(client, check_interval=60, dry_run=False):
    """
    Lässt den Bot dauerhaft laufen und prüft regelmäßig auf Mentions und DMs
    
    Der Bot läuft in einer Endlosschleife und:
    - Prüft alle X Sekunden auf neue Mentions und DMs (falls verfügbar)
    - Verarbeitet alle gefundenen Nachrichten
    - Behandelt Fehler gracefully und startet neu
    - Kann mit Ctrl+C gestoppt werden
    
    Args:
        check_interval: Sekunden zwischen Checks
        dry_run: Wenn True, werden keine Antworten wirklich gepostet/gesendet
    """
    print("\n" + "="*60)
    print(f"🤖 BOT LÄUFT DAUERHAFT")
    print(f"⏰ Prüft alle {check_interval} Sekunden auf neue Nachrichten")
    if dry_run:
        print("🧪 DRY RUN MODUS - Keine Nachrichten werden veröffentlicht!")
    print("="*60)
    print("💡 Drücke Ctrl+C um zu stoppen\n")
    
    # Prüfe einmalig ob DMs verfügbar sind
    print("ℹ️  Teste DM-Verfügbarkeit...")
    test_dms = get_direct_messages(client)
    dm_available = not (hasattr(client, '_dm_not_available') and client._dm_not_available)
    
    if dm_available:
        print("✅ DM-Support aktiv - Bot verarbeitet Mentions UND DMs\n")
    else:
        print("ℹ️  DM-Support nicht verfügbar - Bot verarbeitet nur Mentions\n")
    
    iteration = 0
    
    try:
        while True:  # Endlosschleife für 24/7 Betrieb
            iteration += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            print(f"\n⏰ [{timestamp}] Check #{iteration}")
            
            # Verarbeite Mentions
            mention_count = process_all_mentions(client, dry_run=dry_run)
            
            # Verarbeite DMs (nur wenn verfügbar)
            dm_count = 0
            if dm_available:
                dm_count = process_all_dms(client, dry_run=dry_run)
            
            if mention_count > 0 or dm_count > 0:
                if dm_available:
                    print(f"✅ {mention_count} Mention(s) + {dm_count} DM(s) bearbeitet")
                else:
                    print(f"✅ {mention_count} Mention(s) bearbeitet")
            
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
        run_bot_continuously(client, check_interval, dry_run=dry_run)


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
    
    # Prüfe ob Dry-Run-Modus aktiviert ist
    dry_run = (
        "--dry-run" in sys.argv or 
        os.getenv('DRY_RUN', 'false').lower() == 'true'
    )
    
    if dry_run:
        print("="*60)
        print("🧪 DRY RUN MODUS AKTIVIERT")
        print("   Keine Antworten werden auf Bluesky gepostet/gesendet!")
        print("   Zum Deaktivieren: Entferne --dry-run oder setze DRY_RUN=false")
        print("="*60)
        print()
    
    # Entscheide: Einmal oder Dauerbetrieb?
    if "--continuous" in sys.argv or os.getenv('BOT_MODE') == 'continuous':
        check_interval = int(os.getenv('CHECK_INTERVAL', '60'))
        run_bot_continuously(client, check_interval=check_interval, dry_run=dry_run)
    else:
        print("📋 TEST-MODUS (einmalig)")
        if not dry_run:
            print("💡 Für Dry-Run: python main.py --dry-run")
        print("💡 Für Dauerbetrieb: python main.py --continuous\n")
        
        # Verarbeite Mentions
        mention_count = process_all_mentions(client, dry_run=dry_run)
        
        # Teste DM-Verfügbarkeit und verarbeite falls verfügbar
        print("\nℹ️  Teste DM-Verfügbarkeit...")
        dm_count = process_all_dms(client, dry_run=dry_run)
        
        dm_available = not (hasattr(client, '_dm_not_available') and client._dm_not_available)
        
        if dm_available:
            print(f"\n✅ Test abgeschlossen! ({mention_count} Mentions + {dm_count} DMs)")
        else:
            print(f"\n✅ Test abgeschlossen! ({mention_count} Mentions)")
            print("ℹ️  DM-Support nicht verfügbar - Bot arbeitet im Mention-Modus")


if __name__ == "__main__":
    main()