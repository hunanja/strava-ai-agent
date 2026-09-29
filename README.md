# Strava AI Agent

Oppimisprojekti, jonka tarkoituksena on ymmärtää, miten MCP-palvelimet toimivat yhdessä agenttien kanssa. Projektissa on kaksi osaa:

- **`strava_server.py`**: yksinkertainen oma MCP-palvelin, joka tarjoaa Strava-datan työkaluina.
- **`agent.py`**: oma agenttisilmukka (Anthropic API), joka toimii MCP-asiakkaana, hakee työkalut palvelimelta ja vastaa kysymyksiin treenidatasta.

Sama palvelin toimii myös Claude Desktopissa ilman agenttikoodia.

```
Käyttäjä → agent.py (agenttisilmukka + Claude API)
              │  stdio
              ▼
        strava_server.py (MCP-palvelin)
              │  HTTPS
              ▼
          Strava API
```

## Työkalut

| Työkalu | Kuvaus |
|---|---|
| `get_recent_activities` | Palauttaa Strava-aktiviteetit valitulta ajanjaksolta (max 60 päivää) ja tarvittaessa lajin mukaan rajattuna (esim. `Run`, `Ride`). |
| `weekly_load` | Palauttaa viikoittaisen harjoituskuorman (juoksu- ja pyöräilykilometrit, tunnit, nousumetrit, treenimäärä, muutos edelliseen viikkoon). Max 12 viikkoa. Kuluva viikko on merkitty keskeneräiseksi. |

Kuorman mittarina on liikkumisaika, ei sykepohjainen kuormitus. Palvelin on vain lukuoikeuksilla eikä muuta Strava-dataa.

## Vaatimukset

- Python 3.10 tai uudempi
- Strava-tili ja oma Strava API -sovellus
- Anthropic API -avain ja krediittejä (vain `agent.py`:n käyttöön; Claude Desktop käyttää Claude-tilausta)

## Asennus

1. **Kloonaa projekti ja luo virtuaaliympäristö**

   ```bash
   git clone <REPOSITORION_URL>
   cd <KANSIO>
   python3 -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

   > `mcp`-kirjasto on kiinnitetty versioon 1.x (`mcp<2`), koska koodi käyttää `FastMCP`-rajapintaa, joka on nimetty uudelleen versiossa 2.

2. **Luo Strava API -sovellus**

   Mene osoitteeseen <https://www.strava.com/settings/api>, luo sovellus (Authorization Callback Domain: `localhost`) ja kopioi *Client ID* ja *Client Secret*.

3. **Hanki Strava-tokenit**

   Sovelluksen sivulla näkyvät oletustokenit eivät riitä, koska tarvitset oikeuden `activity:read_all`. Tee valtuutus näin:

   1. Avaa selaimessa (korvaa `CLIENT_ID`):

      ```
      https://www.strava.com/oauth/authorize?client_id=CLIENT_ID&response_type=code&redirect_uri=http://localhost&approval_prompt=force&scope=activity:read_all
      ```

   2. Hyväksy oikeudet. Selain ohjautuu osoitteeseen `http://localhost/?code=...` (sivu ei lataudu, se on normaalia). Kopioi osoitteesta `code`-arvo.
   3. Vaihda koodi tokeneiksi:

      ```bash
      curl -X POST https://www.strava.com/oauth/token \
        -d client_id=CLIENT_ID \
        -d client_secret=CLIENT_SECRET \
        -d code=KOODI \
        -d grant_type=authorization_code
      ```

   Vastauksesta löytyvät `access_token` ja `refresh_token`.

4. **Luo `.env`-tiedosto projektin juureen**

   ```
   ANTHROPIC_API_KEY=sk-ant-...
   STRAVA_CLIENT_ID=...
   STRAVA_CLIENT_SECRET=...
   STRAVA_ACCESS_TOKEN=...
   STRAVA_REFRESH_TOKEN=...
   ```

### Oma agentti (terminaali)

```bash
python3 agent.py
```

Agentti käynnistää palvelimen aliprosessina, hakee työkalulistan ja odottaa kysymyksiä. Esimerkkejä:

- "Kuinka monta kilometriä juoksin viimeisen 7 päivän aikana?"
- "Vertaa juoksu- ja pyöräilykilometrejäni viimeisen kahden viikon ajalta."
- "Miten viikkokuormani on kehittynyt?"

Tyhjä rivi lopettaa ohjelman. Terminaalissa näkyy jokainen agentin tekemä työkalukutsu (`→ työkalu(argumentit)`).

### Claude Desktop

Lisää palvelin Clauden asetustiedostoon (Settings → Developer → Edit Config; macOS:llä `~/Library/Application Support/Claude/claude_desktop_config.json`). Käytä täysiä polkuja:

```json
{
  "mcpServers": {
    "strava-basic": {
      "command": "/POLKU/PROJEKTIIN/.venv/bin/python",
      "args": ["/POLKU/PROJEKTIIN/strava_server.py"]
    }
  }
}
```

Käynnistä Claude Desktop kokonaan uudelleen. Palvelin näkyy nimellä `strava-basic`.

## Tietoturva

- Palvelin lukee dataa, mutta ei kirjoita mitään Stravaan.
- Pidä `.env` poissa versionhallinnasta. Jos avain vuotaa, luo uusi avain ja poista vanha.