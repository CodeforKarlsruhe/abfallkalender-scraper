# Scraper für Müllabfuhrtermine in Karlsruhe

Dieser Scraper befreit die Müllabfuhrtermine der Stadt Karlsruhe von der
[Webseite](http://web3.karlsruhe.de/service/abfall/akal/akal.php) und exportiert
sie als CSV.


## Installation und Nutzung

1. [virtualenv](https://virtualenv.pypa.io) einrichten und aktivieren:

        virtualenv venv
        source venv/bin/activate

2. Abhängigkeiten installieren:

        pip install -r requirements.txt

3. Scrapen:

        python scrape.py


## Ergebnisformat

`scrape.py` produziert 2 CSV-Dateien, `services.csv` und `dates.csv`.

`services.csv` enthält eine simple Liste von Abfuhrdiensten, jeweils mit ID und Titel (z.B. `ka-bio-7` für `Biomüll (wöchentlich)`).

`dates.csv` enthält die Abfuhrtermine. Jede Zeile beschreibt einen Termin für einen Straßenteil und besteht aus den folgenden Spalten:

- Stadt (immer `Karlsruhe`)
- Normalisierter Straßenname
- Anfangshausnummer (inklusive)
- Endhausnummer (inklusive)
- Service-ID (siehe `services.csv`)
- Datum (im Format `YYYY-MM-DD`)

Die Hausnummern können jeweils `0` sein, die entsprechende Grenze fällt dann weg (`0, 10` gilt also bis 10, `12, 0` ab 12 und `0, 0` für alle Nummern). Die Bereiche gelten jeweils nur für gerade bzw. ungerade Hausnummern: z.B. gilt `3, 7` für die Hausnummern 3, 5, 7 (nicht aber für 4 und 6). `0, 0` gilt für gerade und ungerade Hausnummern gemeinsam.


## Lizenz

MIT

