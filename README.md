# sagemate

Ein Bluesky-Bot, der auf Mentions und Direktnachrichten reagiert und mit Claude AI kontextbezogene Antworten generiert.

Durch den mitgegebenen System-Prompt agiert der Bot als weiser Freund der das grosse Ganze im Blick hat und gütig antwortet.

## 🌟 Features

### 📬 Mentions
- Reagiert auf öffentliche Mentions (`@sagemate.bsky.social`)
- Antwortet auf den Original-Post bei leeren Mentions
- Analysiert Thread-Context für fundierte Antworten

### 💌 Direktnachrichten
- Empfängt Posts per "Per Direktnachricht senden"
- Antwortet **öffentlich** auf den geteilten Post
- Bot wirkt eigenständig - niemand sieht die DM-Aktivierung

### 🔗 URL-Verarbeitung
- Extrahiert URLs aus Posts (Text, Facets, Embeds)
- Lädt Webseiten-Inhalte mit Trafilatura
- Analysiert bis zu 3 URLs pro Post

### 🧵 Thread-Analyse
- Lädt kompletten Konversations-Verlauf
- Berücksichtigt alle vorherigen Posts
- Generiert kontextbezogene Antworten

### 🤖 Claude Integration
- Nutzt Claude Sonnet 4.5
- System-Prompt aus Datei
- Max. 280 Zeichen (Bluesky-Limit)

## 📋 Voraussetzungen

- Python 3.8+
- Bluesky-Account
- Anthropic API Key

## 🚀 Installation

```bash
# Repository klonen
git clone https://github.com/grandgrue/sagemate.git
cd sagemate

# Dependencies installieren
pip install -r requirements.txt
```

## ⚙️ Konfiguration

### 1. Umgebungsvariablen

Erstelle `.env`:

```env
BLUESKY_HANDLE=dein.bot.bsky.social
BLUESKY_PASSWORD=dein-app-passwort
ANTHROPIC_API_KEY=sk-ant-...
```

**Wichtig:** App-Passwort muss DM-Berechtigung haben!

### 2. System-Prompt (optional)

Erstelle `system_prompt.txt`:

```
Du bist ein hilfreicher Bot auf Bluesky.
Antworte kurz, prägnant und freundlich.
```

## 🎮 Verwendung

### Test-Modus (einmalig)
```bash
python main.py
```

### Dry-Run (ohne Posten)
```bash
python main.py --dry-run
```

### Dauerbetrieb
```bash
python main.py --continuous
```

Oder über Umgebungsvariable:
```env
BOT_MODE=continuous
CHECK_INTERVAL=60  # Sekunden
```

## 🌐 Deployment (Railway)

### 1. Railway-Projekt erstellen
- Verknüpfe GitHub-Repository
- Wähle Python als Umgebung

### 2. Umgebungsvariablen setzen
```
BLUESKY_HANDLE=...
BLUESKY_PASSWORD=...
ANTHROPIC_API_KEY=...
BOT_MODE=continuous
CHECK_INTERVAL=60
```

### 3. Start-Command
```
python main.py --continuous
```

## 💡 Use Cases

### Via Mention (öffentlich)
```
@user: "@sagemate.bsky.social erkläre mir das"
@sagemate.bsky.social: "Gerne! Das bedeutet..."
```

### Via DM (diskret)
```
Nutzer: [Sendet Post per DM]
Bot: [Antwortet öffentlich auf Post]
→ Alle sehen die Antwort
→ Niemand sieht, dass Bot per DM aktiviert wurde
```

## 🛠️ Technische Details

### Architektur
- **atproto**: Bluesky AT Protocol SDK
- **anthropic**: Claude AI API
- **trafilatura**: Webseiten-Extraktion
- **beautifulsoup4**: HTML-Parsing (Fallback)

### Workflow: Mention-Verarbeitung
1. Hole ungelesene Mentions
2. Prüfe ob Reply auf anderen Post
3. Lade Thread-Context
4. Extrahiere URLs aus Post + Thread
5. Lade Webseiten-Inhalte
6. Generiere Antwort mit Claude
7. Poste Antwort
8. Markiere als gelesen

### Workflow: DM-Verarbeitung
1. Hole DMs mit Post-Referenzen
2. Extrahiere referenzierten Post
3. Lade Thread-Context
4. Extrahiere URLs
5. Lade Webseiten-Inhalte
6. Generiere Antwort mit Claude
7. Poste **öffentliche** Antwort auf Post
8. **Lösche DM** (verhindert Duplikate)

## 📊 Features im Detail

### Leere Mentions
```python
@user: "@sagemate.bsky.social" (als Reply auf Post)
→ Bot antwortet auf Original-Post statt Mention
```

### URL-Extraktion
```python
# Aus Text
"Schau mal: https://example.com"

# Aus Facets (strukturierte Links)
[Link mit Ankertext]

# Aus Embeds (Link-Cards)
[Preview-Card mit URL]
```

### Thread-Context
```python
Post A: "Was ist X?"
Post B: "Ich denke Y..."
@sagemate.bsky.social (als Reply auf B)
→ Bot sieht A + B und antwortet fundiert
```

## 🔒 Privacy & Transparenz

### Öffentlich
- ✅ Bot-Antworten
- ✅ Dass Bot geantwortet hat
- ✅ Bot ist klar als Bot erkennbar

### Privat
- 🔒 DM-Aktivierung
- 🔒 Zusätzliche Notizen in DM
- 🔒 Wer den Bot aktiviert hat

## ⚠️ Wichtige Hinweise

### App-Passwort
- Erstelle in Bluesky-Einstellungen
- ✅ **Aktiviere "Direct Messages" Berechtigung**
- Ohne DM-Berechtigung: Nur Mentions funktionieren

### Rate Limits
- Bluesky hat API-Limits
- Bot wartet zwischen Checks (default: 60s)
- Claude hat eigene API-Limits

### DM-Löschung
- Bot löscht DMs nach Verarbeitung
- Nur für Bot gelöscht (Nutzer sieht weiterhin)
- Verhindert Duplikate bei Neustart

## 🐛 Troubleshooting

### Bot antwortet nicht
```bash
# Prüfe Logs
python main.py --dry-run

# Prüfe Umgebungsvariablen
python main.py
# Zeigt Status aller Variablen
```

### DM-Fehler "XRPCNotSupported"
```
→ App-Passwort hat keine DM-Berechtigung
→ Erstelle neues mit DM-Checkbox aktiviert
```

### Mehrfache Antworten
```
→ DM-Löschung fehlgeschlagen?
→ Prüfe Logs für Fehler
```

## 📚 Dokumentation

Ausführliche Anleitungen im `/docs` Ordner:
- `DM_SETUP_ANLEITUNG.md` - DM-Support einrichten
- `OEFFENTLICHE_ANTWORT_FEATURE.md` - Wie DM-zu-Post funktioniert
- `DM_LOESCHEN_LOESUNG.md` - Duplikate-Vermeidung

## 🤝 Contributing

Contributions sind willkommen! Bitte:
1. Fork das Repository
2. Erstelle Feature-Branch
3. Committe Änderungen
4. Pushe zu Branch
5. Erstelle Pull Request

## 📄 License

MIT License - siehe `LICENSE` Datei

## 👤 Autor

Entwickelt mit Claude AI

## 🙏 Credits

- [AT Protocol](https://atproto.com/) - Bluesky Protocol
- [Anthropic](https://anthropic.com/) - Claude AI
- [Trafilatura](https://trafilatura.readthedocs.io/) - Web Scraping

---

**Status:** ✅ Produktionsreif | **Version:** 1.0 | **Python:** 3.8+
