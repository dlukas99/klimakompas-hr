# API

Baza je `/api/v1`. Odgovori su JSON, koordinate EPSG:4326, a greške RFC 9457 (`application/problem+json`). Interaktivna dokumentacija je na `/api/docs`, a shema na `/api/v1/openapi.json`.

| Metoda | Putanja | Opis |
|---|---|---|
| GET | `/health`, `/ready` | zdravlje i spremnost |
| GET | `/geocode?q=&limit=` | adrese, naselja, općine i gradovi |
| GET | `/card?lat=&lon=` | klimatska iskaznica |
| GET | `/jls`, `/jls/{code}`, `/jls/{code}/naselja`, `/jls/{code}/cells` | općine i gradovi |
| GET | `/rankings?metric=&hazard=&zupanija=&limit=` | rang-liste |
| GET | `/warnings/active?lat=&lon=` ili `?region=` | aktivna upozorenja |
| GET | `/air/stations`, `/air/stations/{id}/series`, `/air/stations/{id}/forecast` | kvaliteta zraka |
| GET | `/nature/nearby?lat=&lon=&radius_m=` | zaštićena područja |
| GET | `/sources`, `/quality` | izvori i kvaliteta |
| GET | `/exports`, `/export/{datoteka}` | izvedeni skupovi |
| GET | `/catalog.ttl`, `/catalog.jsonld` | DCAT-AP |
| GET | `/agent/status`, `/agent/quick?question=` | stanje asistenta i brza pitanja |
| POST | `/agent/chat` | asistent (SSE) |

**Pločice:** `/tiles/{sloj}/{z}/{x}/{y}`, slojevi `grid_risk`, `jls_risk`, `zupanije`, `naselja`, `nature`.

**OGC API – Features:** `/ogc`, kolekcije `grid_risk`, `jls_risk`, `aq_stations`, `warnings_active`.

## Primjer

```bash
curl "https://DEMO/api/v1/card?lat=45.555&lon=18.69"
```

Iskaznica vraća lokaciju, IKR s percentilom, četiri bloka opasnosti s razinom i ključnim vrijednostima, stanovništvo, živa upozorenja, zrak, prirodu u blizini i savjete. Polje `partial` kaže da neki živi izvor trenutno nije dostupan.
