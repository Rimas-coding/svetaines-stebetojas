# Svetainės Stebėtojas (Website Monitor)

Svetainės Stebėtojas yra lengva ir patogi aplikacija, skirta automatiškai stebėti pasirinktos interneto svetainės pokyčius. Pasikeitus svetainės turiniui, programa realiu laiku informuoja vartotoją per **vietinius Windows pranešimus (Toasts)** ir/arba siunčia žinutes per **Discord Webhook**.

## 🚀 Funkcijos

* **Realaus laiko stebėjimas:** Automatiškai tikrina svetainės turinį jūsų nurodytu intervalu.
* **Moderni Vartotojo Sąsaja (UI):** Patogus valdymo skydelis nustatymų keitimui per naršyklę (sukurta naudojant TailwindCSS).
* **Valdymo Pultas:** Galimybė Pradėti, Pristabdyti (Pauzė), Sustabdyti stebėjimą ir Išvalyti įvykių istoriją.
* **Dvilypė pranešimų sistema:**
  * **Discord Integracija:** Automatiškai siunčia žinutes į nurodytą Discord kanalą, kai aptinkamas svetainės pokytis.
  * **Windows Pranešimai:** Vietiniai "iššokantys" pranešimai jūsų ekrane (nereikalauja trečiųjų šalių paslaugų).
* **Išmani Diagnostika:** Komplekte yra integruotas AI paremtas agentas (`troubleshooter_agent.py`), kuris gali perskaityti klaidų žurnalus (logs), patikrinti konfigūraciją ir padėti išspręsti kylančias problemas.

## 🛠️ Reikalavimai

Norint paleisti šią programą, jūsų kompiuteryje turi būti įdiegta:
* [Python 3.8+](https://www.python.org/downloads/)
* Pip (Python paketų tvarkyklė)

## 📥 Įdiegimas

1. **Atsisiųskite repozitoriją:**
   Klonuokite šią repozitoriją į savo kompiuterį arba atsisiųskite kaip ZIP archyvą.
   ```bash
   git clone https://github.com/Rimas-coding/svetaines-stebetojas.git
   cd svetaines-stebetojas
   ```

2. **Sukurkite ir aktyvuokite virtualią aplinką:**
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   ```

3. **Įdiekite reikiamas bibliotekas:**
   ```bash
   pip install fastapi uvicorn requests pydantic plyer google-adk python-dotenv
   ```

## 🎮 Naudojimas

### Programos Paleidimas

Pateikiami patogūs `.bat` failai greitam programos paleidimui Windows operacinėje sistemoje:

1. **`paleisti_stebetoja.bat`**
   Dukart spustelėjus šį failą:
   - Fone bus paleistas FastAPI serveris.
   - Automatiškai atsidarys naršyklės langas (`http://127.0.0.1:8000`), kuriame matysite valdymo skydelį.
   - Įveskite svetainės adresą, intervalą, pasirenkamą Discord Webhook nuorodą ir spauskite **Pradėti**.

2. **`paleisti_agenta.bat`** (Problemų Sprendimo Asistentas)
   Jeigu iškilo problemų (nepareina pranešimai ar sistema stringa):
   - Paleiskite šį failą.
   - Atsidarys terminalas, kuriame galėsite tiesiog parašyti savo problemą (pvz., *"Neveikia Discord pranešimai"*). Asistentas automatiškai išanalizuos `app.log` ir `config.json` bei pasiūlys sprendimą.

### Valdymo Mygtukai (Vartotojo Sąsajoje)
* **Pradėti:** Aktyvuoja foninį svetainės tikrinimą pagal jūsų nurodytą laiko intervalą.
* **Pauzė:** Laikinai sustabdo atgalinį laikmatį, bet išsaugo visus duomenis.
* **Stop:** Pilnai atšaukia dabartinį stebėjimo procesą.
* **Išvalyti:** Ištrina ankstesnių įvykių sąrašą iš ekrano ir išvalo seną turinio hash'ą.

## ⚙️ Konfigūracija

Visi jūsų nustatymai yra automatiškai saugomi `config.json` faile šakniniame aplanke (generuojamas automatiškai išsaugojus nustatymus per UI). Saugumo sumetimais šis failas nėra keliamas į GitHub repozitoriją (`.gitignore`).

## 👨‍💻 Architektūra

* **Backend:** Python / FastAPI
* **Frontend:** HTML / Vanilla JS / TailwindCSS
* **Pranešimai:** `plyer` biblioteka Windows pranešimams, `requests` Discord integracijai.
* **AI Palaikymas:** Integruotas per `google-adk` biblioteką kaip pagalbinis įrankis vartotojui.

---
*Sukurta Aivarui.*
