# Sprint Board Time Tracker — Streamlit

Dashboard wizualizujący czas spędzany przez tickety w poszczególnych kolumnach Sprint Boardu w Jira. Zbudowany w całości w Pythonie z użyciem Streamlit — jeden plik, jeden proces, zero JavaScriptu.

## Spis treści

- [Opis](#opis)
- [Funkcjonalności](#funkcjonalności)
- [Architektura](#architektura)
- [Struktura projektu](#struktura-projektu)
- [Wymagania](#wymagania)
- [Instalacja](#instalacja)
- [Uruchomienie](#uruchomienie)
- [Konfiguracja](#konfiguracja)
- [Integracja z Jira](#integracja-z-jira)
- [Udostępnianie w sieci](#udostępnianie-w-sieci)
- [Znane ograniczenia](#znane-ograniczenia)

---

## Opis

Narzędzie analizuje historię zmian statusów ticketów (Jira changelog) i oblicza ile godzin każdy ticket spędził w każdej kolumnie tablicy (np. „In Progress", „Code Review", „Testing"). Pozwala identyfikować wąskie gardła w procesie zespołu.

Projekt jest przepisaną, uproszczoną wersją dashboardu [sprint-dashboard](https://github.com/Bredson/sprint-dashboard) (FastAPI + React). Zamiast dwóch procesów i ~15 plików — jeden plik Python.

---

## Funkcjonalności

- **Wybór tablicy** — lista 10 wybranych tablic scrum zespołów
- **Wybór sprintu** — 20 ostatnich sprintów (active + closed), posortowane od najnowszego; domyślnie ostatni zakończony
- **Zakres dat** — pola From/To pre-wypełnione datami sprintu; zmiana dat przełącza w tryb custom (sprint ignorowany)
- **Filtr typów ticketów** — Story, Task, Bug, Defect (checkboxy, minimum jeden)
- **Przycisk Refresh** — czyści cache i pobiera świeże dane z Jira
- **Statystyki sumaryczne** — 4 karty KPI: liczba ticketów, done/closed, średni cycle time, kolumna-bottleneck
- **Wykres słupkowy** — średni czas per kolumna (Plotly, interaktywny)
- **Heat map** — tickety × kolumny z gradientem niebieski→pomarańczowy→czerwony (Plotly)
- **Tabela ticketów** — z wyszukiwarką, kolorowaniem komórek wg intensywności, linki do Jira

---

## Architektura

```
Jira REST API
     │
     ▼
jira_client.py  ←  pobieranie danych + obliczenia czasu w kolumnie
     │
     ▼
app.py  ←  Streamlit UI (sidebar + wykresy + tabela)
     │
     ▼
Przeglądarka  →  http://localhost:8501
```

Cały stack to **jeden proces Python**. Streamlit serwuje interfejs użytkownika bezpośrednio — nie ma osobnego backendu ani frontendu.

---

## Struktura projektu

```
dashboard_Streamlit/
├── app.py              # Cały dashboard — UI, logika, wykresy
├── jira_client.py      # Klient Jira API + silnik obliczania czasu w kolumnie
├── requirements.txt    # Zależności Python
├── .env                # Credentials Jira (NIE commitować!)
├── .env.example        # Szablon .env (bezpieczny do commitowania)
├── .gitignore
├── README.md           # Dokumentacja (polski)
├── README.en.md        # Dokumentacja (angielski)
└── .venv/              # Wirtualne środowisko Python (auto-generowane)
```

### Opis plików

| Plik | Opis |
|------|------|
| `app.py` | Główny plik aplikacji. Zawiera: konfigurację strony, CSS, cachowane loadery danych, sidebar z filtrami, karty KPI, wykres słupkowy Plotly, heat mapę Plotly, tabelę ticketów z wyszukiwarką i kolorowaniem. |
| `jira_client.py` | Klient Jira REST API. Pobiera tablice, sprinty, kolumny, tickety z changelogiem. Oblicza czas spędzony w każdej kolumnie na podstawie historii przejść statusów. Szczegóły w sekcji [Integracja z Jira](#integracja-z-jira). |
| `requirements.txt` | Cztery zależności: `streamlit`, `plotly`, `pandas`, `python-dotenv`. |
| `.env` | Plik z danymi do połączenia z Jira — nie trafia do repozytorium. |
| `.env.example` | Szablon `.env` z pustymi wartościami — trafia do repozytorium. |

---

## Wymagania

- Python 3.11+
- Dostęp do Jira Cloud (`finago-products.atlassian.net`)
- Jira API Token — wygeneruj na: https://id.atlassian.com/manage-profile/security/api-tokens

---

## Instalacja

```bash
# 1. Sklonuj repozytorium
git clone https://github.com/Bredson/dashboard_Streamlit.git
cd dashboard_Streamlit

# 2. Utwórz wirtualne środowisko
python3 -m venv .venv

# 3. Zainstaluj zależności
.venv/bin/pip install -r requirements.txt

# 4. Skonfiguruj credentials
cp .env.example .env
# Edytuj .env — wpisz JIRA_URL, JIRA_EMAIL, JIRA_TOKEN
```

---

## Uruchomienie

```bash
.venv/bin/streamlit run app.py
```

Dashboard otworzy się automatycznie w przeglądarce pod adresem `http://localhost:8501`.

Aby uruchomić na innym porcie:

```bash
.venv/bin/streamlit run app.py --server.port 8502
```

---

## Konfiguracja

### Plik `.env`

```
JIRA_URL=https://finago-products.atlassian.net
JIRA_EMAIL=twoj.email@finago.com
JIRA_TOKEN=<twój_api_token>
```

> **Uwaga:** Token Jira wygasa po 1 roku. Gdy wygaśnie, dashboard zwraca błąd `401 Unauthorized`. Aby odnowić: wygeneruj nowy token na https://id.atlassian.com/manage-profile/security/api-tokens, zaktualizuj `JIRA_TOKEN` w `.env` i zrestartuj aplikację.

---

### Lista tablic (`jira_client.py`)

Tablice dostępne w selektorze są zdefiniowane jako stała `ALLOWED_BOARDS` w `jira_client.py`:

```python
ALLOWED_BOARDS = [
    {"id": 23,  "name": "Flycatcher"},
    {"id": 70,  "name": "Team Parrot"},
    {"id": 72,  "name": "Team Roadrunner"},
    {"id": 98,  "name": "Spectre"},
    {"id": 96,  "name": "Team Eagle"},
    {"id": 115, "name": "Team Pike"},
    {"id": 259, "name": "Team Fenix"},
    {"id": 66,  "name": "Team Kiwi"},
    {"id": 216, "name": "Team Paw Patrol"},
    {"id": 130, "name": "Team Sparrow"},
]
```

Aby dodać lub usunąć tablicę — edytuj tę listę. ID tablicy znajdziesz w URL Jiry gdy otworzysz daną tablicę: `.../jira/software/projects/.../boards/<ID>`.

---

### Cache

Dane z Jira są cachowane przez Streamlit (`@st.cache_data`). Aby odświeżyć dane — kliknij przycisk **Refresh** na pasku bocznym. Czyści on cache wszystkich loaderów i pobiera świeże dane.

---

## Integracja z Jira

### Jak obliczany jest czas w kolumnie

Dla każdego ticketu pobierany jest pełny `changelog` z Jira API. Algorytm w `jira_client._compute_column_times()`:

1. Rekonstruuje oś czasu przejść statusów (od najstarszego do najnowszego)
2. Mapuje nazwy statusów Jira na nazwy kolumn tablicy (dopasowanie rozmyte — substring)
3. Dla każdego segmentu oblicza przecięcie z żądanym oknem dat
4. Sumuje godziny per kolumna

```
Ticket DEV-74351:
  2024-03-20  ──►  In Implementation  (106 h)
  2024-04-02  ──►  IN REVIEW          (110 h)
  2024-04-03  ──►  Ready for Testing  ( 59 h)
  2024-04-05  ──►  In Testing         (  9 h)
  2024-04-05  ──►  Closed
```

### Tryby pobierania danych

| Tryb | Kiedy | Źródło |
|------|-------|--------|
| **Sprint** | Daty zgodne z datami sprintu | `GET /board/{id}/sprint/{id}/issue` — wszystkie tickety sprintu |
| **Date range** | Użytkownik zmienił daty ręcznie | `GET /search/jql` — tickety zaktualizowane w danym przedziale |

> Uwaga: Stary endpoint `GET /rest/api/3/search` jest wycofany przez Atlassian (HTTP 410). Dashboard używa nowego `GET /rest/api/3/search/jql` z paginacją opartą na `nextPageToken`.

---

## Udostępnianie w sieci

### Sieć lokalna / VPN

```bash
.venv/bin/streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

Sprawdź swoje IP:

```bash
# macOS
ifconfig | grep "inet " | grep -v "127.0.0.1"

# Windows
ipconfig
```

Wyślij adres VPN (np. `http://192.168.240.37:8501`) osobom połączonym przez VPN firmowy. Adres WiFi (`192.168.x.x`) działa tylko w tej samej sieci lokalnej.

---

## Znane ograniczenia

- Tryb date range zwraca maksymalnie 100 ticketów na zapytanie
- Czas w kolumnie liczony jest jako czas kalendarzowy (nie roboczy)
- Token Jira API wygasa po 1 roku
- Heat mapa wyświetla maksymalnie 20 ticketów (top 20 wg całkowitego czasu)
