import os
import re
import requests
import asyncio
from datetime import date, timedelta, datetime
from typing import List, Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TRAVELPAYOUTS_TOKEN = os.getenv("TRAVELPAYOUTS_TOKEN")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

app = FastAPI(title="Flight Navigator API", version="1.0")

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def resolve_iata(city_name: str, is_destination: bool = False) -> str:
    """Сопоставляет название города и IATA-коды аэропортов"""
    c = city_name.strip().lower()
    
    # Если пользователь вводит код из 3 букв напрямую, приводим к верхнему регистру и используем
    if len(c) == 3 and c.isalpha():
        return c.upper()
        
    mapping = {
        # Хельсинки
        "хельсинки": "HEL", "helsinki": "HEL", "hel": "HEL",
        # Мюнхен
        "мюнхен": "MUC", "munich": "MUC", "muc": "MUC",
        # Таллинн
        "таллин": "TLL", "таллинн": "TLL", "tallinn": "TLL", "tll": "TLL",
        # Рига
        "рига": "RIX", "riga": "RIX", "rix": "RIX",
        # Берлин
        "берлин": "BER", "berlin": "BER", "ber": "BER",
        # Париж
        "париж": "CDG", "paris": "CDG", "cdg": "CDG", "par": "CDG",
        # Рим
        "рим": "FCO", "rome": "FCO", "fco": "FCO",
        # Амстердам
        "амстердам": "AMS", "amsterdam": "AMS", "ams": "AMS",
        # Вена
        "вена": "VIE", "vienna": "VIE", "vie": "VIE",
        # Прага
        "прага": "PRG", "prague": "PRG", "prg": "PRG",
        # Стокгольм
        "стокгольм": "ARN", "stockholm": "ARN", "arn": "ARN",
        # Мадрид
        "мадрид": "MAD", "madrid": "MAD", "mad": "MAD",
        # Милан
        "милан": "MXP", "milan": "MXP", "mxp": "MXP",
        # Лондон
        "лондон": "LHR", "london": "LHR", "lhr": "LHR",
        # Дубай
        "дубай": "DXB", "dubai": "DXB", "dxb": "DXB",
        # Барселона
        "барселона": "BCN", "barcelona": "BCN", "bcn": "BCN"
    }
    
    if c in mapping:
        return mapping[c]
        
    # Если города нет в словаре, очищаем и берем первые 3 буквы заглавными
    cleaned = "".join([char for char in c if char.isalpha()])
    if len(cleaned) >= 3:
        return cleaned[:3].upper()
        
    return "DXB" if is_destination else "LHR"

def parse_date_input(date_text: str):
    """
    Разбирает тип ввода даты.
    Возвращает кортеж (тип_даты, departure_date),
    где тип_даты может быть "specific" или "month",
    а departure_date - строка в формате YYYY-MM-DD.
    """
    t = date_text.strip().lower()
    
    # 1. Поиск точной даты YYYY-MM-DD
    match_ymd = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", t)
    if match_ymd:
        return "specific", match_ymd.group(0)
        
    # 2. Поиск точной даты DD.MM.YYYY или DD.MM.YY
    match_dmy = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})\b", t)
    if match_dmy:
        d, m, y = match_dmy.groups()
        if len(y) == 2:
            y = "20" + y
        d = d.zfill(2)
        m = m.zfill(2)
        return "specific", f"{y}-{m}-{d}"
        
    # 3. Разбор текстового названия месяца
    months_map = {
        "янв": "01", "jan": "01",
        "фев": "02", "feb": "02",
        "мар": "03", "mar": "03",
        "апр": "04", "apr": "04",
        "май": "05", "мая": "05", "may": "05",
        "июн": "06", "jun": "06",
        "июл": "07", "jul": "07",
        "авг": "08", "aug": "08",
        "сен": "09", "sep": "09",
        "окт": "10", "oct": "10",
        "ноя": "11", "nov": "11",
        "дек": "12", "dec": "12"
    }
    
    resolved_month = None
    for name, num in months_map.items():
        if name in t:
            resolved_month = num
            break
            
    # Если месяц введен числом (например, "09" или "9")
    if not resolved_month:
        match_num = re.search(r"\b(0?[1-9]|1[0-2])\b", t)
        if match_num:
            resolved_month = match_num.group(1).zfill(2)
            
    if resolved_month:
        # Для обзора за месяц берём 1-е число месяца
        return "month", f"2026-{resolved_month}-01"
        
    # Фоллбек: конкретная дата через 14 дней от текущей
    fallback_date = (date.today() + timedelta(days=14)).strftime("%Y-%m-%d")
    return "specific", fallback_date

def get_aviasales_booking_url(origin: str, destination: str, date_str: str) -> str:
    """Строит ссылку на поиск авиабилетов в Aviasales"""
    parts = date_str.split("-")
    if len(parts) == 3:
        ddmm = parts[2] + parts[1]
    else:
        ddmm = "1509"
    return f"https://www.aviasales.ru/search/{origin}{ddmm}{destination}1?marker=555664"

def query_travelpayouts_matrix(origin_code: str, dest_code: str, date_str: str) -> list:
    """Делает прямой HTTP-запрос к Travelpayouts Month Matrix API с таймаутом"""
    url = "https://api.travelpayouts.com/v2/prices/month-matrix"
    month_start = date_str[:8] + "01" if len(date_str) >= 10 else date_str
    
    params = {
        "origin": origin_code,
        "destination": dest_code,
        "month": month_start,
        "show_to_affiliates": "false",
        "token": TRAVELPAYOUTS_TOKEN,
        "currency": "eur"
    }
    
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    flights = []
    for item in data.get("data", []):
        price = item.get("value") or item.get("price", 0)
        gate = item.get("gate") or item.get("airline", "Unknown Carrier")
        dep_date = item.get("depart_date") or item.get("departure_at") or ""
        changes = item.get("number_of_changes", 0)
        
        flights.append({
            "source": "Aviasales",
            "price": price,
            "airline": gate,
            "departure_date": dep_date,
            "departure_time": "",
            "number_of_changes": changes,
            "gate": gate
        })
    return flights

def query_serpapi_flights(origin_code: str, dest_code: str, date_str: str) -> list:
    """Делает прямой HTTP-запрос к SerpApi Google Flights API с типом поездки One Way и таймаутом 25с"""
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_flights",
        "departure_id": origin_code,
        "arrival_id": dest_code,
        "outbound_date": date_str,
        "type": 2,  # One way
        "currency": "EUR",
        "hl": "ru",
        "gl": "fi",
        "api_key": SERPAPI_KEY
    }
    
    response = requests.get(url, params=params, timeout=25)
    response.raise_for_status()
    data = response.json()
    
    google_flights_url = data.get("search_metadata", {}).get("google_flights_url", "https://www.google.com/travel/flights")
    
    flights = []
    best = data.get("best_flights", [])
    other = data.get("other_flights", [])
    
    for item in best + other:
        price = item.get("price")
        if price is None:
            continue
            
        segments = item.get("flights", [])
        airlines = list(set([seg.get("airline") for seg in segments if seg.get("airline")]))
        airline_name = ", ".join(airlines) if airlines else "Unknown Airline"
        
        dep_time = ""
        if segments:
            dep_time = segments[0].get("departure_airport", {}).get("time", "")
            
        stops = len(segments) - 1 if len(segments) > 0 else 0
        
        booking_link = item.get("booking_token") or item.get("booking_link")
        if not booking_link or not str(booking_link).startswith("http"):
            booking_link = google_flights_url
            
        flights.append({
            "source": "Google Flights",
            "price": price,
            "airline": airline_name,
            "departure_date": dep_time.split(" ")[0] if dep_time else date_str,
            "departure_time": dep_time.split(" ")[-1] if " " in dep_time else dep_time,
            "number_of_changes": stops,
            "gate": airline_name,
            "booking_url": booking_link
        })
    return flights

def fetch_aviasales_sync(origin_iata: str, destination_iata: str, departure_date: str, date_type: str) -> list:
    try:
        res = query_travelpayouts_matrix(origin_iata, destination_iata, departure_date)
        if date_type == "specific":
            filtered = [f for f in res if f.get("departure_date") == departure_date]
            if not filtered and res:
                target_dt = datetime.strptime(departure_date, "%Y-%m-%d")
                def get_diff_days(f):
                    f_date_str = f.get("departure_date", "")
                    try:
                        f_dt = datetime.strptime(f_date_str[:10], "%Y-%m-%d")
                        return abs((f_dt - target_dt).days)
                    except Exception:
                        return 9999
                sorted_by_distance = sorted(res, key=get_diff_days)
                for f in sorted_by_distance:
                    f["is_nearest"] = True
                aviasales_result = sorted_by_distance
            else:
                aviasales_result = filtered
        else:
            aviasales_result = res

        # Attach booking URLs
        for f in aviasales_result:
            f_date = f.get("departure_date", departure_date)
            f["booking_url"] = get_aviasales_booking_url(origin_iata, destination_iata, f_date)
        return aviasales_result
    except Exception as e:
        print(f"Error fetching from Aviasales: {e}")
        return []

def fetch_google_sync(origin_iata: str, destination_iata: str, departure_date: str) -> list:
    try:
        return query_serpapi_flights(origin_iata, destination_iata, departure_date)
    except Exception as e:
        print(f"Error fetching from Google Flights: {e}")
        return []

@app.get("/")
def read_root():
    return {"message": "Welcome to Flight Navigator API. Use GET /api/search to find flights."}

@app.get("/api/search")
async def search(
    origin: str = Query(..., description="Origin city or airport code (e.g. Helsinki, HEL)"),
    destination: str = Query(..., description="Destination city or airport code (e.g. Barcelona, BCN)"),
    date: str = Query(..., description="Travel date or description (e.g. 2026-09-01, September)"),
    mode: str = Query("deep", description="Search mode: 'fast' or 'deep'"),
):
    if not origin.strip() or not destination.strip():
        raise HTTPException(status_code=400, detail="Parameters 'origin' and 'destination' must not be empty.")
    
    # 1. Resolve params
    origin_iata = resolve_iata(origin, is_destination=False)
    destination_iata = resolve_iata(destination, is_destination=True)
    date_type, departure_date = parse_date_input(date)
    
    # 2. Run queries in parallel threads to prevent event loop blocking
    aviasales_task = asyncio.to_thread(
        fetch_aviasales_sync, origin_iata, destination_iata, departure_date, date_type
    )
    google_task = asyncio.to_thread(
        fetch_google_sync, origin_iata, destination_iata, departure_date
    )
    
    aviasales_res, google_res = await asyncio.gather(aviasales_task, google_task)
    
    combined_flights = aviasales_res + google_res
    
    # 3. Sort options by price ascending
    try:
        sorted_flights = sorted(combined_flights, key=lambda f: float(f.get("price", 0)))
    except Exception:
        sorted_flights = combined_flights
        
    # 4. Limit options based on search mode
    limit = 5 if mode == "fast" else 15
    selected_flights = sorted_flights[:limit]
    
    return {
        "origin_iata": origin_iata,
        "destination_iata": destination_iata,
        "departure_date": departure_date,
        "date_type": date_type,
        "results": selected_flights
    }
