# Provjera izvora podataka

Datoteku generira `make sources-verify`. Bilješke dolaze iz `config/sources.yaml`.

Zadnja provjera: 01. 11. 2026. u 16:35 UTC.

| Izvor | Prioritet | Stanje | Licenca |
|---|---|---|---|
| `dgu_au` | P0 | ✅ radi | Otvorena dozvola (zapis na Portalu) |
| `dgu_ad` | P0 | ✅ radi | Otvorena dozvola (zapis na Portalu) |
| `dzs_naselja_2021` | P0 | ✅ radi | Otvorena dozvola prema SPEC-u; TODO(verify) točan zapis na Portalu |
| `estat_census_grid_2021` | P0 | ✅ radi | TODO(verify) - ponovna uporaba uz navođenje izvora (Eurostat) |
| `jrc_efas_flood` | P0 | ✅ radi | TODO(verify) - proturječno: copyright.txt navodi CC BY 4.0, a katalog i README ODbL 1.0 |
| `hv_flood_wms` | P1 | ➖ bez automatskog dohvata | TODO(verify) - NIPP: izrađeno za Plan upravljanja rizicima od poplava, korištenje na vlastitu odgovornost |
| `eea_pm25_1km` | P0 | ✅ radi | TODO(verify) - EEA ponovna uporaba uz navođenje |
| `azo_aq_rest` | P0 | ✅ radi | TODO(verify) |
| `dhmz_cap` | P0 | ✅ radi | Otvorena dozvola; obavezno navesti DHMZ kao izvor |
| `dhmz_heatwave` | P0 | ✅ radi | Otvorena dozvola; obavezno navesti DHMZ kao izvor |
| `dhmz_fire_index` | P1 | ✅ radi | Otvorena dozvola; obavezno navesti DHMZ kao izvor |
| `dhmz_weather` | P1 | ✅ radi | Otvorena dozvola; obavezno navesti DHMZ kao izvor |
| `dhmz_climate` | P2 | ✅ radi | Otvorena dozvola; obavezno navesti DHMZ kao izvor |
| `bioportal_wfs` | P1 | ✅ radi | Javno dostupno (AccessConstraints) – TODO(verify) licenca |
| `ecde` | P0/P1 | ✅ radi | CC BY 4.0 (CDS katalog) |
| `landsat_lst` | P0/P1 | ✅ radi | Javna domena (USGS) prema SPEC-u; STAC navodi „proprietary”: TODO(verify) |
| `esa_worldcover` | P0 | ✅ radi | CC BY 4.0 |
| `burnt_areas` | P1 | ✅ radi | TODO(verify) - STAC navodi „other” |
| `open_meteo` | P1 | ➖ bez automatskog dohvata | CC BY 4.0, uz navođenje; besplatno za nekomercijalnu uporabu |
| `ckan` | P0 | ✅ radi | TODO(verify) |
| `dgu_dof` | P2 | ✅ radi | TODO(verify) |
| `basemap` | P0 | ✅ radi | ODbL, samo za prikaz; OSM ne ulazi u izvedene skupove |
| `jrc_flood_events` | P2 | ✅ radi | TODO(verify) |

## `dgu_au`: Upravne jedinice INSPIRE

- Izdavač: Državna geodetska uprava
- robots.txt `geoportal.dgu.hr`: pravila pročitana
- ✅ `GET https://geoportal.dgu.hr/services/atom/xml`: HTTP 200 · application/xml;charset=UTF-8 · 17,1 kB · zapisa: 10
  - uzorak: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?> <feed xmlns:inspire_dls="http://inspire.ec.europa.eu/schemas/ins`
- ✅ `GET https://geoportal.dgu.hr/services/atom/au/xml`: HTTP 200 · application/xml;charset=UTF-8 · 2,1 kB · zapisa: 1
  - uzorak: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?> <feed xmlns="http://www.w3.org/2005/Atom" xmlns:georss="http://w`
- ✅ `ZIP https://geoportal.dgu.hr/services/atom/INSPIRE_Administrative_Units_(AU).zip`: HTTP 206 · application/zip · 208,8 MB · zapisa: 1 · Range: da
  - uzorak: `AdministrativeUnit.gml`
- ✅ `GET https://geoportal.dgu.hr/services/inspire/au/wms?service=WMS&request=GetCapabilities`: HTTP 200 · text/xml · 9,1 kB · zapisa: 2
  - uzorak: `<?xml version="1.0" encoding="UTF-8"?><WMS_Capabilities xmlns:inspire_common="http://inspire.ec.europa.eu/schemas/common`
- Portal: `upravne-jedinice-inspire` · Državna geodetska uprava · licenca: Otvorena dozvola (OD) · izmjena: 2026-10-22T06:48:05.491626
- Bilješka (01. 11. 2026.): ATOM nudi INSPIRE GML 3.2.1 u ETRS89/LAEA (EPSG:3035), a ne SHP u EPSG:3765 kako navodi SPEC. Zip ima oko 209 MB. ATOM servis u polju rights navodi „ograničenje javnog pristupa prema članku 13 stavku 1 točki (e) INSPIRE Direktive”, a Portal Otvorenu dozvolu: mjerodavnim smatramo zapis na Portalu. Nazive polja sa šiframa treba utvrditi iz podataka u Fazi 1.

## `dgu_ad`: Adrese INSPIRE

- Izdavač: Državna geodetska uprava
- robots.txt `geoportal.dgu.hr`: pravila pročitana
- ✅ `GET https://geoportal.dgu.hr/services/atom/ad/xml`: HTTP 200 · application/xml;charset=UTF-8 · 2,0 kB · zapisa: 1
  - uzorak: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?> <feed xmlns="http://www.w3.org/2005/Atom" xmlns:georss="http://w`
- ✅ `ZIP https://geoportal.dgu.hr/services/atom/INSPIRE_Addresses_(AD).zip`: HTTP 206 · application/zip · 90,0 MB · zapisa: 4 · Range: da
  - uzorak: `PostalDescriptor.gml, ThoroughfareName.gml, Address.gml, AdminUnitName.gml`
- Portal: `adrese-inspire` · Državna geodetska uprava · licenca: Otvorena dozvola (OD) · izmjena: 2026-10-22T06:47:02.818231
- Bilješka (01. 11. 2026.): GML u EPSG:3035 preko ATOM-a. WFS traži authKey i ne koristimo ga.

## `dzs_naselja_2021`: Popis 2021.: stanovništvo po naseljima

- Izdavač: Državni zavod za statistiku
- robots.txt `podaci.dzs.hr`: nema datoteke (404)
- ✅ `HEAD https://podaci.dzs.hr/media/rqybclnx/popis_2021-stanovnistvo_po_naseljima.xlsx`: HTTP 200 · application/vnd.openxmlformats-officedocument.spreadsheetml.sheet · 3,1 MB · Last-Modified: Thu, 05 Jun 2025 10:56:28 GMT
- Portal, kandidati iz pretrage: `popis-stanovni-tva-2011-stanovni-tvo-po-naseljima`, `statistika-u-nizu-popis-stanovnistva-kucanstava-i-stanova-2021`, `stanovnistvo-grada-rijeke-prema-mo-i-povrsina-mo-popis-2011`, `naselja-i-stanovni-tvo-republike-hrvatske-1857-2001`
- Bilješka (01. 11. 2026.): Datoteka postoji, oko 3 MB. Zapis na Portalu i tablicu „starost i spol po naseljima” treba potvrditi.

## `estat_census_grid_2021`: Census 2021 population grid, 1 km

- Izdavač: Eurostat GISCO (iz podataka DZS-a)
- robots.txt `ec.europa.eu`: pravila pročitana
- robots.txt `gisco-services.ec.europa.eu`: pravila pročitana
- ✅ `GET https://ec.europa.eu/eurostat/web/gisco/geodata/population-distribution/population-grids`: HTTP 200 · text/html;charset=UTF-8 · 201,2 kB
  - uzorak: `<!DOCTYPE html>`
- ✅ `ZIP https://gisco-services.ec.europa.eu/census/2021/Eurostat_Census-GRID_2021_V3.zip`: HTTP 206 · application/zip · 566,1 MB · zapisa: 9 · Range: da · Last-Modified: Fri, 19 Jun 2026 11:29:37 GMT
  - uzorak: `Eurostat_Census-GRID_2021_V3/, Eurostat_Census-GRID_2021_V3/ESTAT_Census_2021_country.csv.zip, Eurostat_Census-GRID_2021_V3/ESTAT_Census_2021_LAND_SURFACE_V3.tiff, Eurostat_Census-GRID_2021_V3/ESTAT_Census_2021_V3.csv`
- Bilješka (01. 11. 2026.): Dostupna je novija verzija V3 (izmjena 19. 6. 2026., oko 566 MB) od verzije V2.2 iz SPEC-a. Koristimo V3. Stupce, oznake prikrivenih vrijednosti i oblik GRD_ID treba potvrditi na podacima u Fazi 1.

## `jrc_efas_flood`: River flood hazard maps for Europe and the Mediterranean Basin (v3.1.1)

- Izdavač: European Commission, Joint Research Centre (CEMS-EFAS)
- robots.txt `jeodpp.jrc.ec.europa.eu`: nema datoteke (404)
- ✅ `GET https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-EFAS/flood_hazard/README.txt`: HTTP 200 · text/plain; charset=utf-8 · 2,1 kB · Last-Modified: Wed, 21 Oct 2026 10:39:25 GMT
  - uzorak: `GENERAL INFORMATION  G01. Dataset version 3.1.1 G02. Name of the dataset: River flood hazard maps for Europe and the`
- ✅ `GET https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-EFAS/flood_hazard/copyright.txt`: HTTP 200 · text/plain; charset=utf-8 · 0,4 kB · Last-Modified: Thu, 05 Mar 2026 12:26:53 GMT
  - uzorak: `Copyright notice ------------------  (c) European Union, 1995-2026  The Commission's reuse policy is implemented by th`
- ✅ `RANGE https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-EFAS/flood_hazard/Europe_RP10_filled_depth.tif`: HTTP 206 · image/tiff · 272,3 MB · Range: da · Last-Modified: Tue, 03 Mar 2026 15:45:13 GMT
- ✅ `RANGE https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-EFAS/flood_hazard/Europe_RP100_filled_depth.tif`: HTTP 206 · image/tiff · 323,1 MB · Range: da · Last-Modified: Thu, 05 Mar 2026 09:29:28 GMT
- ✅ `RANGE https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-EFAS/flood_hazard/Europe_RP500_filled_depth.tif`: HTTP 206 · image/tiff · 349,9 MB · Range: da · Last-Modified: Thu, 05 Mar 2026 10:06:04 GMT
- Bilješka (01. 11. 2026.): Trenutna verzija je 3.1.1, a rezolucija 3 lučne sekunde (oko 90 m) u WGS84. Datoteke imaju 272–350 MB i podržavaju HTTP Range, pa je prozorsko čitanje izvedivo. Licenca je proturječna i treba je razjasniti prije objave izvedenih skupova (dopis u docs/dopisi/).

## `hv_flood_wms`: Karte opasnosti od poplava 2019. i karte rizika

- Izdavač: Hrvatske vode
- robots.txt `servisi.voda.hr`: nedostupan, dohvat nije dopušten
- Bilješka (01. 11. 2026.): Bez harvesta i serverskog proxyja. Jednokratni ručni GetCapabilities (HTTP 200, WMS 1.3.0) potvrdio je nazive slojeva, podršku za EPSG:3857 i zaglavlje Access-Control-Allow-Origin: *, pa su prikaz i GetFeatureInfo iz preglednika izvedivi. Na robots.txt je server tog dana vratio HTTP 503, što tretiramo kao zabranu automatiziranog dohvata.

## `eea_pm25_1km`: EEA interpolirani PM2,5, godišnji prosjek, 1 km (2023.)

- Izdavač: European Environment Agency
- robots.txt `sdi.eea.europa.eu`: pravila pročitana
- ✅ `RANGE https://sdi.eea.europa.eu/datastore/public/eea_r_3035_1_km_aq-interpolated-pm25_p_2023_v01_r00/pm25_avg_23.tif`: HTTP 206 · image/tiff · 82,2 MB · Range: da · Last-Modified: Thu, 01 May 2025 08:00:44 GMT
- Bilješka (01. 11. 2026.): Datoteka je pm25_avg_23.tif, oko 82 MB, pa je preuzimanje jednostavno. Stara putanja /webdav/ preusmjerava na /datastore/public/. Licencu treba potvrditi u zapisu kataloga.

## `azo_aq_rest`: Kvaliteta zraka u RH – RESTful servis

- Izdavač: Ministarstvo zaštite okoliša i zelene tranzicije
- robots.txt `iszz.azo.hr`: nema datoteke (404)
- ✅ `GET https://iszz.azo.hr/iskzl/rs/podatak/export/json?postaja=155&polutant=5&tipPodatka=0&vrijemeOd=29.10.2026&vrijemeDo=31.10.2026`: HTTP 200 · application/json · 5,0 kB · zapisa: 72
  - uzorak: `[{"vrijednost":62.4,"mjernaJedinica":"µg/m3","vrijeme":1793232000000},{"vrijednost":62.3,"mjernaJedinica":"µg/m3","vrije`
- ✅ `GET https://iszz.azo.hr/iskzl/rs/podatak/export/json?postaja=155&polutant=5&tipPodatka=4&vrijemeOd=29.10.2026&vrijemeDo=31.10.2026`: HTTP 200 · application/json · 0,2 kB · zapisa: 3
  - uzorak: `[{"vrijednost":23.657,"mjernaJedinica":"µg/m3","vrijeme":1793228400000},{"vrijednost":15.067,"mjernaJedinica":"µg/m3","v`
- ✅ `GET https://iszz.azo.hr/iskzl/rs/podatak/export/json?postaja=300&polutant=28&tipPodatka=0&vrijemeOd=29.10.2026&vrijemeDo=31.10.2026`: HTTP 200 · application/json · 0,0 kB · zapisa: 0
  - uzorak: `[]`
- ✅ `GET https://iszz.azo.hr/iskzl/koordinate.htm`: HTTP 200 · text/html;charset=UTF-8 · 8,7 kB
  - uzorak: `<!DOCTYPE html> <html> <head> <title>Kvaliteta zraka u Republici Hrvatskoj </title> <meta http-equiv="X-UA-Compatibl`
- ✅ `GET https://iszz.azo.hr/iskzl/status.htm`: HTTP 200 · text/html;charset=UTF-8 · 9,2 kB
  - uzorak: `<!DOCTYPE html> <html> <head> <title>Kvaliteta zraka u Republici Hrvatskoj </title> <meta http-equiv="X-UA-Compatibl`
- Portal, kandidati iz pretrage: `kvaliteta-zraka-u-republici-hrvatskoj-inspire`, `indeks-kvalitete-zraka-u-republici-hrvatskoj-inspire`
- Bilješka (01. 11. 2026.): tipPodatka=0 vraća satne vrijednosti (do 48 zapisa za 2 dana), a tipPodatka=4 dnevne (2 zapisa za 2 dana). Vrijednosti 1, 2, 3 i 5 na testiranoj postaji vraćaju prazan popis. Stvarni oblik zapisa je ravan: {vrijednost, mjernaJedinica, vrijeme}, a vrijeme je Unix epoha u milisekundama, a ne ugniježđeni objekt s ISO vremenom iz SPEC-a. Servis ograničava učestalost: uz razmak od 0,5 s svaki drugi zahtjev dobiva HTTP 429 bez Retry-After, a uz razmak od 4 s svih 15 zahtjeva je prošlo. Worker zato mora razmaknuti pozive; točnu donju granicu još treba utvrditi. PM2,5 za 29.–31. 10. 2026. vratile su postaje 155, 156, 157, 159, 161, 162, 165, 255 i 275, a prazno su vratile 160 (Osijek-1), 168, 277, 278, 286 i 300 (Osijek – PPI), pa Osijek u tom razdoblju nema trenutni PM2,5. Validiranost podataka još nije utvrđena: TODO(verify).

## `dhmz_cap`: Upozorenja DHMZ-a (CAP 1.2) i poligoni regija

- Izdavač: Državni hidrometeorološki zavod
- robots.txt `meteo.hr`: nema datoteke (404)
- ✅ `GET https://meteo.hr/upozorenja/cap_hr_today.xml`: HTTP 200 · text/xml · 46,9 kB · zapisa: 40 · Last-Modified: Sun, 01 Nov 2026 16:32:33 GMT
  - uzorak: `<?xml version="1.0" encoding="UTF-8"?> <alert xmlns="urn:oasis:names:tc:emergency:cap:1.2"> 	<identifier>2.49.0.0.191.0.`
- ✅ `GET https://meteo.hr/upozorenja/cap_hr_tomorrow.xml`: HTTP 200 · text/xml · 42,6 kB · zapisa: 36 · Last-Modified: Sun, 01 Nov 2026 16:32:33 GMT
  - uzorak: `<?xml version="1.0" encoding="UTF-8"?> <alert xmlns="urn:oasis:names:tc:emergency:cap:1.2"> 	<identifier>2.49.0.0.191.0.`
- ✅ `GET https://meteo.hr/upozorenja/cap_hr_day_after_tomorrow.xml`: HTTP 200 · text/xml · 95,4 kB · zapisa: 48 · Last-Modified: Sun, 01 Nov 2026 16:32:33 GMT
  - uzorak: `<?xml version="1.0" encoding="UTF-8"?> <alert xmlns="urn:oasis:names:tc:emergency:cap:1.2"> 	<identifier>2.49.0.0.191.0.`
- ✅ `HEAD https://meteo.hr/upozorenja/CroatiaRegionsCounties.tar.xz`: HTTP 200 · application/octet-stream · 4,7 MB · Last-Modified: Wed, 23 Sep 2026 12:33:36 GMT
- ✅ `HEAD https://meteo.hr/upozorenja/Croatia_Sea_Regions.tar`: HTTP 200 · application/octet-stream · 1,1 MB · Last-Modified: Thu, 07 Nov 2019 14:28:43 GMT
- ✅ `HEAD https://meteo.hr/upozorenja/Croatia_MA_regions.pdf`: HTTP 200 · application/pdf · 26,5 kB · Last-Modified: Wed, 23 Sep 2026 09:59:44 GMT
- Portal: pretraga nije našla zapis
- Bilješka (01. 11. 2026.): Svako upozorenje ima dva info bloka, hrvatski i engleski. Razina je u parametru awareness_level (npr. „2; yellow; Moderate”), a vrsta u awareness_type. Područje ima geokodove EMMA_ID i NUTS3. onset i expires imaju razmak umjesto slova T, pa ih parser mora prihvatiti.

## `dhmz_heatwave`: Upozorenje na toplinske valove

- Izdavač: Državni hidrometeorološki zavod
- robots.txt `prognoza.hr`: nema datoteke (404)
- ✅ `GET https://prognoza.hr/toplinskival_5.xml`: HTTP 200 · text/xml · 0,3 kB · zapisa: 1 · Last-Modified: Sun, 13 Sep 2026 12:42:00 GMT
  - uzorak: `<?xml version="1.0" encoding="ISO-8859-1" ?> <TriVis version="1.1" creator="ask - Innovative Visualisierungslösungen Gmb`
- Bilješka (01. 11. 2026.): Izvan sezone datoteka ima kodiranje ISO-8859-1, korijen TriVis i prazan element section, a zadnja izmjena je od 13. 9. 2026. Strukturu aktivnog upozorenja nije moguće vidjeti do sezone, pa je parser za to stanje TODO(verify).

## `dhmz_fire_index`: Indeks opasnosti od šumskih požara

- Izdavač: Državni hidrometeorološki zavod
- robots.txt `vrijeme.hr`: nema datoteke (404)
- ✅ `GET https://vrijeme.hr/indeks.xml`: HTTP 200 · text/xml · 11,2 kB · zapisa: 35 · Last-Modified: Sun, 01 Nov 2026 15:31:02 GMT
  - uzorak: `<?xml version="1.0" encoding="UTF-8"?> <opasnost>   <datum>01.11.2026.</datum>   <vwdatum>0</vwdatum>   <postaja>     <c`
- Bilješka (01. 11. 2026.): Datoteka se 1. 11. još osvježava (35 postaja s kodom, FWI i kategorijom), pa ne vraća stanje „izvan sezone” sama od sebe. UI mora sezonu odrediti po datumu ili po vwdatum: TODO(verify).

## `dhmz_weather`: Vrijeme u Hrvatskoj: Tmax, Tmin, oborina, temperatura rijeka

- Izdavač: Državni hidrometeorološki zavod
- robots.txt `vrijeme.hr`: nema datoteke (404)
- ✅ `GET https://vrijeme.hr/hrvatska_n.xml`: HTTP 200 · text/xml · 19,0 kB · Last-Modified: Sun, 01 Nov 2026 16:26:01 GMT
  - uzorak: `<?xml version="1.0" encoding="UTF-8"?> <Hrvatska> <DatumTermin> <Datum>01.11.2026</Datum> <Termin>17</Termin> </DatumTer`
- ✅ `GET https://vrijeme.hr/tx.xml`: HTTP 200 · text/xml · 4,9 kB · Last-Modified: Sun, 01 Nov 2026 07:58:07 GMT
  - uzorak: `<?xml version="1.0" encoding="UTF-8"?> <maksimalnatemperatura>   <datumtermin>     <datum>31.10.2026</datum>     <termin`
- ✅ `GET https://vrijeme.hr/tn.xml`: HTTP 200 · text/xml · 4,1 kB · Last-Modified: Sun, 01 Nov 2026 07:58:04 GMT
  - uzorak: `<?xml version="1.0" encoding="UTF-8"?> <minimalnatemperatura>   <datumtermin>     <datum>01.11.2026</datum>     <termin>`
- ✅ `GET https://vrijeme.hr/oborina.xml`: HTTP 200 · text/xml · 2,4 kB · Last-Modified: Sun, 01 Nov 2026 07:58:01 GMT
  - uzorak: `<?xml version="1.0" encoding="UTF-8"?> <dnevna_oborina> 	<datumtermin> 		<datum>01.11.2026.</datum> 		<termin>7</termin>`
- ✅ `GET https://vrijeme.hr/temp_vode.xml`: HTTP 200 · text/xml · 59,9 kB · Last-Modified: Sun, 01 Nov 2026 16:10:40 GMT
  - uzorak: `<?xml version="1.0" encoding="UTF-8"?> <kitsxml version="1.1" creator="KiIOSys/KiTS-XML-Exporter" date="2026-11-01T16:1`

## `dhmz_climate`: Srednje mjesečne vrijednosti i mjesečne oborine

- Izdavač: Državni hidrometeorološki zavod
- robots.txt `klima.hr`: nema datoteke (404)
- ✅ `GET https://klima.hr/k1/tablice/osijek.xml`: HTTP 200 · text/xml · 5,5 kB · Last-Modified: Mon, 09 Jun 2025 09:57:40 GMT
  - uzorak: `<?xml version="1.0" encoding="UTF-8"?> <srednjaci>   <postaja>Osijek</postaja>   <interval>1899-2024</interval>   <podac`
- ✅ `GET https://klima.hr/k2/2025/oborina_2025.xml`: HTTP 200 · text/xml · 50,6 kB · Last-Modified: Mon, 16 Feb 2026 06:32:06 GMT
  - uzorak: `<?xml version="1.0" encoding="UTF-8"?> <godisnja_oborina>   <godina>2025</godina> <postaja>   <ime_postaje>Bakar</ime_po`

## `bioportal_wfs`: Zaštićena područja, Natura 2000, staništa (Bioportal)

- Izdavač: Ministarstvo zaštite okoliša i zelene tranzicije
- robots.txt `services.bioportal.hr`: pravila pročitana
- ✅ `GET https://services.bioportal.hr/wfs?service=WFS&request=GetCapabilities`: HTTP 200 · application/xml · 191,1 kB · zapisa: 125
  - uzorak: `<?xml version="1.0" encoding="UTF-8"?><wfs:WFS_Capabilities version="2.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-`
- ✅ `GET https://services.bioportal.hr/dzzpnpis/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=dzzpnpis:ramsar&outputFormat=application/json&count=1&srsName=EPSG:4326`: HTTP 200 · application/json;charset=UTF-8 · 10,8 kB · zapisa: 1
  - uzorak: `{"type":"FeatureCollection","features":[{"type":"Feature","id":"ramsar.1","geometry":{"type":"MultiPolygon","coordinates`
- Portal: `ekolo-ka-mre-a-natura-2000` · Hrvatska agencija za okoliš i prirodu (NEAKTIVAN) · licenca: – · izmjena: 2026-07-20T07:11:18.801457
- Bilješka (01. 11. 2026.): Zapis za Naturu 2000 na Portalu nema licencu: nalaz za izvješće o kvaliteti.

## `ecde`: ECDE klimatski indikatori (Copernicus C3S)

- Izdavač: Copernicus Climate Change Service (ECMWF)
- robots.txt `cds.climate.copernicus.eu`: pravila pročitana
- ✅ `GET https://cds.climate.copernicus.eu/api/catalogue/v1/collections/sis-ecde-climate-indicators`: HTTP 200 · application/json · 2,4 kB
  - uzorak: `{"type":"Collection","id":"sis-ecde-climate-indicators","stac_version":"1.1.0","title":"Climate indicators for Europe fr`
- ✅ `GET https://cds.climate.copernicus.eu/api/retrieve/v1/processes/sis-ecde-climate-indicators`: HTTP 200 · application/json · 7,3 kB
  - uzorak: `{"title":"Climate indicators for Europe from 1940 to 2100 derived from reanalysis and climate projections","description"`
- Bilješka (01. 11. 2026.): Javni opis procesa potvrđuje varijable hot_days, tropical_nights, days_with_high_fire_danger i fire_weather_index, origin reanalysis i projections, temporal_aggregation te spatial_aggregation gridded. Stvarno preuzimanje traži token; točan zahtjev se slaže u Fazi 2 iz opisa procesa, bez pogađanja.

## `landsat_lst`: Landsat 8/9 Collection 2 Level-2, površinska temperatura

- Izdavač: USGS (preko Microsoft Planetary Computera)
- robots.txt `planetarycomputer.microsoft.com`: pravila pročitana
- ✅ `GET https://planetarycomputer.microsoft.com/api/stac/v1/collections/landsat-c2-l2`: HTTP 200 · application/json; charset=utf-8 · 19,6 kB
  - uzorak: `{"id":"landsat-c2-l2","type":"Collection","links":[{"rel":"items","type":"application/geo\u002Bjson","href":"https://pla`
- Bilješka (01. 11. 2026.): Asseti lwir11 i qa_pixel postoje; asset ST_B10 ne postoji. Skaliranje se čita iz metapodataka.

## `esa_worldcover`: ESA WorldCover 2021, 10 m

- Izdavač: European Space Agency
- robots.txt `planetarycomputer.microsoft.com`: pravila pročitana
- ✅ `GET https://planetarycomputer.microsoft.com/api/stac/v1/collections/esa-worldcover`: HTTP 200 · application/json; charset=utf-8 · 7,3 kB
  - uzorak: `{"id":"esa-worldcover","type":"Collection","links":[{"rel":"items","type":"application/geo\u002Bjson","href":"https://pl`
- Bilješka (01. 11. 2026.): STAC kolekcija navodi CC-BY-4.0 i asset map.

## `burnt_areas`: Povijest opožarenih površina (MODIS MCD64A1)

- Izdavač: NASA LP DAAC (preko Microsoft Planetary Computera)
- robots.txt `planetarycomputer.microsoft.com`: pravila pročitana
- ✅ `GET https://planetarycomputer.microsoft.com/api/stac/v1/collections/modis-64A1-061`: HTTP 200 · application/json; charset=utf-8 · 5,9 kB
  - uzorak: `{"id":"modis-64A1-061","type":"Collection","links":[{"rel":"items","type":"application/geo\u002Bjson","href":"https://pl`
- Bilješka (01. 11. 2026.): Kolekcija i asset Burn_Date postoje. EFFIS još nije provjeren.

## `open_meteo`: Open-Meteo: prognoza, povijesni ERA5 i CAMS kvaliteta zraka

- Izdavač: Open-Meteo
- robots.txt `api.open-meteo.com`: pravila pročitana, dohvat nije dopušten
- robots.txt `archive-api.open-meteo.com`: pravila pročitana, dohvat nije dopušten
- robots.txt `air-quality-api.open-meteo.com`: pravila pročitana, dohvat nije dopušten
- Bilješka (01. 11. 2026.): robots.txt na sva tri API hosta ima „Disallow: /”, iako je API javno dokumentiran s ograničenjima poziva. Sva tri servisa odgovorila su na po jedan probni poziv prije nego što je ovo uočeno. Verifikacija ih više ne poziva dok se ne odluči smije li se koristiti.

## `ckan`: Portal otvorenih podataka (CKAN Action API i DCAT)

- Izdavač: Ministarstvo pravosuđa, uprave i digitalne transformacije
- robots.txt `data.gov.hr`: pravila pročitana
- ✅ `GET https://data.gov.hr/ckan/api/3/action/package_search?q=upravne+jedinice&rows=2`: HTTP 200 · application/json;charset=utf-8 · 17,0 kB · zapisa: 3
  - uzorak: `{"help": "https://data.gov.hr/ckan/api/3/action/help_show?name=package_search", "success": true, "result": {"count": 3,`
- ✅ `GET https://data.gov.hr/ckan/catalog.xml`: HTTP 200 · application/rdf+xml · 535,8 kB · zapisa: 100
  - uzorak: `<?xml version="1.0" encoding="utf-8"?> <rdf:RDF   xmlns:hydra="http://www.w3.org/ns/hydra/core#"   xmlns:rdf="http://www`
- Bilješka (01. 11. 2026.): API i DCAT rade. API je povremeno spor: jedan poziv istekao je nakon 25 s.

## `dgu_dof`: DOF 2020 WMS

- Izdavač: Državna geodetska uprava
- robots.txt `geoportal.dgu.hr`: pravila pročitana
- ✅ `GET https://geoportal.dgu.hr/services/inspire/orthophoto_2020/wms?service=WMS&request=GetCapabilities`: HTTP 200 · text/xml · 8,7 kB · zapisa: 2
  - uzorak: `<?xml version="1.0" encoding="UTF-8"?><WMS_Capabilities xmlns:inspire_common="http://inspire.ec.europa.eu/schemas/common`

## `basemap`: Vektorska podloga (OpenFreeMap, podaci OpenStreetMap)

- Izdavač: OpenFreeMap / OpenStreetMap contributors
- robots.txt `tiles.openfreemap.org`: nema datoteke (403)
- ✅ `GET https://tiles.openfreemap.org/styles/positron`: HTTP 200 · application/json · 25,2 kB · Last-Modified: Sun, 01 Nov 2026 02:35:06 GMT
  - uzorak: `{"version":8,"sources":{"ne2_shaded":{"maxzoom":6,"tileSize":256,"tiles":["https://tiles.openfreemap.org/natural_earth/n`
- Bilješka (01. 11. 2026.): Stil radi. OpenFreeMap navodi da javna instanca nema ograničenja, registracije ni kolačića.

## `jrc_flood_events`: Katalog satelitski detektiranih poplava u Europi 2015.–2024.

- Izdavač: European Commission, Joint Research Centre
- robots.txt `data.jrc.ec.europa.eu`: nema datoteke (404)
- ✅ `GET https://data.jrc.ec.europa.eu/collection/id-0054`: HTTP 200 · text/html; charset=utf-8 · 36,3 kB
  - uzorak: `<!DOCTYPE html> <html lang="en"><head><meta charset="utf-8">     <meta name="viewport" content="width=device-width, init`
- Bilješka (01. 11. 2026.): Stranica kolekcije postoji; datoteke i licenca nisu provjerene (P2).
