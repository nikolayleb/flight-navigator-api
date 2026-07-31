import os
from dotenv import load_dotenv
import customtkinter as ctk
import threading
import re
import requests
import webbrowser
from datetime import date, timedelta, datetime

# Загружаем переменные окружения
load_dotenv()

# ================= НАСТРОЙКА КЛЮЧЕЙ =================
TRAVELPAYOUTS_TOKEN = os.getenv("TRAVELPAYOUTS_TOKEN")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
# ===================================================

# Настройка темы CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# Глобальные параметры для поиска
max_results_param = 15
search_mode_name = "deep"
link_counter = 0

# База локализации
TRANSLATIONS = {
    "RU": {
        "title": "✈️ МультиАвиаНавигатор AI",
        "subtitle": "Сравнение цен Aviasales и Google Flights в евро (€) на 2026 год",
        "lbl_origin": "Откуда:",
        "lbl_destination": "Куда:",
        "lbl_details": "Пожелания / Дата:",
        "lbl_search_mode": "Режим поиска:",
        "placeholder_origin": "Например: Хельсинки",
        "placeholder_destination": "Например: Барселона",
        "placeholder_details": "Например: на сентябрь",
        "btn_search": "🔍 Найти авиабилеты",
        "btn_searching": "Поиск...",
        "lbl_status_ready": "Готов к поиску",
        "lbl_results": "Результаты поиска и логи работы агента:",
        "status_planning": "Определение IATA кодов и даты...",
        "status_searching": "Поиск авиабилетов (Aviasales + Google)...",
        "status_analyzing": "Форматирование результатов...",
        "status_success": "Поиск завершен успешно!",
        "status_error": "Ошибка поиска!",
        "validation_error": "⚠️ Заполните поля 'Откуда' и 'Куда' перед поиском.",
        "log_start": "🚀 Запуск агента поиска авиабилетов...",
        "log_request": "📋 Запрос: С перелетом из {} в {}. Детали: {}\n",
        "log_search_mode_fast": "⚡ Запуск поиска (анализ до 5 лучших предложений)...",
        "log_search_mode_deep": "🔍 Запуск глубокого поиска (анализ до 15 лучших предложений)...",
        "log_plan": "🧠 Поиск IATA-кодов городов и разбор даты...",
        "log_done": "\n✨ [Анализ завершен! Сравнение цен]:\n" + "="*50 + "\n",
        "log_error": "\n❌ Произошла ошибка выполнения: {}",
        "no_offers_found": "На эту дату предложений не найдено. Попробуйте сменить параметры."
    },
    "EN": {
        "title": "✈️ FlightNavigator AI",
        "subtitle": "Compare Aviasales & Google Flights prices in Euros (€) for 2026",
        "lbl_origin": "From:",
        "lbl_destination": "To:",
        "lbl_details": "Preferences / Date:",
        "lbl_search_mode": "Search Mode:",
        "placeholder_origin": "e.g., Helsinki",
        "placeholder_destination": "e.g., Barcelona",
        "placeholder_details": "e.g., in September",
        "btn_search": "🔍 Search Flights",
        "btn_searching": "Searching...",
        "lbl_status_ready": "Ready to search",
        "lbl_results": "Search results and agent execution logs:",
        "status_planning": "Resolving IATA & date...",
        "status_searching": "Searching flights (Aviasales + Google)...",
        "status_analyzing": "Formatting results...",
        "status_success": "Search completed successfully!",
        "status_error": "Search error!",
        "validation_error": "⚠️ Please fill 'From' and 'To' fields before searching.",
        "log_start": "🚀 Starting Flight Search Agent...",
        "log_request": "📋 Request: Flight from {} to {}. Details: {}\n",
        "log_search_mode_fast": "⚡ Starting search (analyzing up to 5 best offers)...",
        "log_search_mode_deep": "🔍 Starting deep search (analyzing up to 15 best offers)...",
        "log_plan": "🧠 Mapping city names to IATA and parsing date...",
        "log_done": "\n✨ [Analysis completed! Price Matrix]:\n" + "="*50 + "\n",
        "log_error": "\n❌ Execution error occurred: {}",
        "no_offers_found": "No flights found for this date. Please try changing parameters."
    }
}

current_lang = "RU"

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

def get_aviasales_booking_url(origin, destination, date_str):
    """Строит ссылку на поиск авиабилетов в Aviasales"""
    parts = date_str.split("-")
    if len(parts) == 3:
        ddmm = parts[2] + parts[1]
    else:
        ddmm = "1509"
    return f"https://www.aviasales.ru/search/{origin}{ddmm}{destination}1?marker=555664"

def query_travelpayouts_matrix(origin_code, dest_code, date_str):
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

def query_serpapi_flights(origin_code, dest_code, date_str):
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
    
    # Таймаут установлен в 25 секунд
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
        
        # Получаем ссылку на бронирование
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

def format_multisearch_report(flights, origin_iata, destination_iata, departure_date, lang):
    """Генерирует форматированный текстовый отчет по рейсам Aviasales + Google Flights на чистом Python"""
    t = TRANSLATIONS[lang]
    if not flights:
        return t["no_offers_found"]
        
    if lang == "RU":
        report = [
            f"✈️ СРАВНИТЕЛЬНЫЙ ОТЧЕТ ПО АВИАБИЛЕТАМ ({origin_iata} ➔ {destination_iata})",
            f"📅 Дата поиска: {departure_date}",
            f"📊 Всего найдено предложений: {len(flights)}",
            "=" * 50,
            ""
        ]
    else:
        report = [
            f"✈️ FLIGHT OPTIONS COMPARISON ({origin_iata} ➔ {destination_iata})",
            f"📅 Search Date: {departure_date}",
            f"📊 Total options found: {len(flights)}",
            "=" * 50,
            ""
        ]
        
    for idx, flight in enumerate(flights):
        source = flight.get("source", "Unknown")
        price = flight.get("price", 0)
        airline = flight.get("airline", "Unknown Carrier")
        dep_date = flight.get("departure_date", "")
        dep_time = flight.get("departure_time", "")
        changes = flight.get("number_of_changes", 0)
        is_nearest = flight.get("is_nearest", False)
        booking_url = flight.get("booking_url", "")
        
        # Форматирование пересадок
        if lang == "RU":
            changes_str = "Без пересадок" if changes == 0 else f"Пересадок: {changes}"
            nearest_label = " (ближайшая дата)" if is_nearest else ""
        else:
            changes_str = "Direct" if changes == 0 else f"Stops: {changes}"
            nearest_label = " (nearest date)" if is_nearest else ""
            
        dep_date_str = f"{dep_date}{nearest_label}"
        time_str = f" в {dep_time}" if dep_time else ""
        
        # Ссылка на бронирование в формате Markdown
        if source == "Aviasales":
            link_text = "👉 Купить билет на Aviasales" if lang == "RU" else "👉 Buy ticket on Aviasales"
        else:
            link_text = "👉 Купить билет на Google Flights" if lang == "RU" else "👉 Buy ticket on Google Flights"
            
        booking_markdown = f"[{link_text}]({booking_url})"
        
        report.append(f"[{source}] Option #{idx + 1}")
        report.append(f"  Авиакомпания / Airline: {airline}" if lang == "RU" else f"  Airline: {airline}")
        report.append(f"  Цена / Price: {price} €")
        report.append(f"  Вылет / Departure: {dep_date_str}{time_str}" if lang == "RU" else f"  Departure: {dep_date_str}{time_str}")
        report.append(f"  Пересадки / Stops: {changes_str}" if lang == "RU" else f"  Stops: {changes_str}")
        report.append(f"  Ссылка на покупку: {booking_markdown}" if lang == "RU" else f"  Booking Link: {booking_markdown}")
        report.append("-" * 30)
        report.append("")
        
    return "\n".join(report)

def change_language(new_lang):
    """Мгновенно меняет язык элементов интерфейса и полей ввода"""
    global current_lang
    current_lang = new_lang
    t = TRANSLATIONS[new_lang]
    
    lbl_title.configure(text=t["title"])
    lbl_subtitle.configure(text=t["subtitle"])
    lbl_origin.configure(text=t["lbl_origin"])
    lbl_destination.configure(text=t["lbl_destination"])
    lbl_details.configure(text=t["lbl_details"])
    lbl_search_mode.configure(text=t["lbl_search_mode"])
    lbl_results.configure(text=t["lbl_results"])
    
    # Обновляем кнопку поиска
    if btn_search.cget("state") == "normal":
        btn_search.configure(text=t["btn_search"])
    else:
        btn_search.configure(text=t["btn_searching"])
        
    # Текст статуса по умолчанию
    if lbl_status.cget("text") in [TRANSLATIONS["RU"]["lbl_status_ready"], TRANSLATIONS["EN"]["lbl_status_ready"]]:
        lbl_status.configure(text=t["lbl_status_ready"])
    
    # Обновляем значения переключателя режимов
    current_val = segmented_button.get()
    if new_lang == "EN":
        new_val = "Fast" if current_val == "Быстрый" else "Deep"
        segmented_button.configure(values=["Fast", "Deep"])
        segmented_button.set(new_val)
    else: # RU
        new_val = "Быстрый" if current_val == "Fast" else "Глубокий"
        segmented_button.configure(values=["Быстрый", "Глубокий"])
        segmented_button.set(new_val)
        
    # Обновляем плейсхолдеры
    entry_origin.configure(placeholder_text=t["placeholder_origin"])
    entry_destination.configure(placeholder_text=t["placeholder_destination"])
    entry_details.configure(placeholder_text=t["placeholder_details"])
    
    # Динамически переводим дефолтные значения в полях ввода
    orig_text = entry_origin.get().strip()
    dest_text = entry_destination.get().strip()
    det_text = entry_details.get().strip()
    
    ru_orig = "Хельсинки"
    en_orig = "Helsinki"
    ru_dest = "Барселона"
    en_dest = "Barcelona"
    ru_det = "на сентябрь"
    en_det = "in September"
    
    if new_lang == "EN":
        if orig_text == ru_orig:
            entry_origin.delete(0, "end")
            entry_origin.insert(0, en_orig)
        if dest_text == ru_dest:
            entry_destination.delete(0, "end")
            entry_destination.insert(0, en_dest)
        if det_text == ru_det:
            entry_details.delete(0, "end")
            entry_details.insert(0, en_det)
    else: # RU
        if orig_text == en_orig:
            entry_origin.delete(0, "end")
            entry_origin.insert(0, ru_orig)
        if dest_text == en_dest:
            entry_destination.delete(0, "end")
            entry_destination.insert(0, ru_dest)
        if det_text == en_det:
            entry_details.delete(0, "end")
            entry_details.insert(0, ru_det)

def update_status(text: str):
    """Потокобезопасное обновление текста статуса"""
    root.after(0, lambda: lbl_status.configure(text=text))

def log_to_ui(message: str):
    """Потокобезопасное добавление сообщений в текстовое лог-поле"""
    root.after(0, lambda: append_message(message))

def append_message(message: str):
    global link_counter
    widget = result_text
    widget.configure(state="normal")
    
    # Регулярное выражение для разбора Markdown ссылок [Текст](Ссылка)
    pattern = r"\[([^\]]+)\]\((https?://[^\)]+)\)"
    matches = list(re.finditer(pattern, message))
    
    if matches:
        last_idx = 0
        for match in matches:
            start_pos = match.start()
            end_pos = match.end()
            anchor = match.group(1)
            url = match.group(2)
            
            # Вставляем обычный текст перед ссылкой
            widget.insert("end", message[last_idx:start_pos])
            
            # Вставляем кликабельный текст с тегом
            tag_name = f"link_{link_counter}"
            widget.insert("end", anchor, tag_name)
            
            # Стилизуем ссылку синим цветом с подчеркиванием
            widget.tag_config(tag_name, foreground="#38bdf8", underline=True)
            # Привязываем открытие ссылки и курсор руки
            widget.tag_bind(tag_name, "<Button-1>", lambda event, u=url: webbrowser.open(u))
            widget.tag_bind(tag_name, "<Enter>", lambda event: widget.configure(cursor="hand2"))
            widget.tag_bind(tag_name, "<Leave>", lambda event: widget.configure(cursor="arrow"))
            
            link_counter += 1
            last_idx = end_pos
            
        widget.insert("end", message[last_idx:] + "\n")
    else:
        widget.insert("end", message + "\n")
        
    widget.see("end")
    widget.configure(state="disabled")

def clear_ui_results():
    result_text.configure(state="normal")
    result_text.delete("1.0", "end")
    result_text.configure(state="disabled")

def start_search_thread():
    """Запускает поиск в отдельном потоке, чтобы интерфейс не зависал"""
    global max_results_param, search_mode_name
    origin = entry_origin.get().strip()
    destination = entry_destination.get().strip()
    details = entry_details.get().strip()
    
    t = TRANSLATIONS[current_lang]
    
    if not origin or not destination:
        log_to_ui(t["validation_error"])
        return
        
    # Определяем параметры глубины поиска (считываем с основного потока)
    selected_mode = segmented_button.get()
    if selected_mode in ["Быстрый", "Fast"]:
        max_results_param = 5
        search_mode_name = "fast"
    else:
        max_results_param = 15
        search_mode_name = "deep"
        
    clear_ui_results()
    btn_search.configure(state="disabled", text=t["btn_searching"])
    
    # Запускаем прогресс-бар и статус
    progress_bar.start()
    update_status(t["status_planning"])
    
    # Запуск потока
    thread = threading.Thread(target=perform_search, args=(origin, destination, details))
    thread.daemon = True
    thread.start()

def perform_search(origin, destination, details):
    t = TRANSLATIONS[current_lang]
    log_to_ui(t["log_start"])
    log_to_ui(t["log_request"].format(origin, destination, details if details else "..."))
    
    # Логируем выбранный режим поиска
    if search_mode_name == "fast":
        log_to_ui(t["log_search_mode_fast"])
    else:
        log_to_ui(t["log_search_mode_deep"])
        
    try:
        # Шаг 1: Определение IATA-кодов и даты перелета на чистом Python
        log_to_ui(t["log_plan"])
        origin_iata = resolve_iata(origin, is_destination=False)
        destination_iata = resolve_iata(destination, is_destination=True)
        date_type, departure_date = parse_date_input(details)
        
        log_to_ui(f"🔍 [Разбор параметров]: {origin} -> {origin_iata}, {destination} -> {destination_iata}")
        
        # Логируем тип даты в логах приложения
        if date_type == "specific":
            log_mode_str = f"📅 Режим поиска: Конкретная дата ({departure_date})" if current_lang == "RU" else f"📅 Search mode: Specific date ({departure_date})"
        else:
            target_month = departure_date[:7]
            log_mode_str = f"📅 Режим поиска: Обзор за весь месяц ({target_month})" if current_lang == "RU" else f"📅 Search mode: Month overview ({target_month})"
        log_to_ui(log_mode_str)
        
        # Шаг 2: Выполнение параллельных запросов
        update_status(t["status_searching"])
        log_to_ui(f"🌐 Поиск авиабилетов (Aviasales + Google Flights) для {origin_iata} -> {destination_iata}...")
        
        aviasales_result = []
        aviasales_error = None
        google_result = []
        google_error = None
        
        def fetch_aviasales():
            nonlocal aviasales_result, aviasales_error
            try:
                # Всегда запрашиваем месяц-матрицу
                res = query_travelpayouts_matrix(origin_iata, destination_iata, departure_date)
                
                # Если ищется конкретная дата
                if date_type == "specific":
                    filtered = [f for f in res if f.get("departure_date") == departure_date]
                    
                    # Если на эту дату нет цен в кэше Aviasales, выводим ближайшие найденные даты месяца с пометкой
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
                
                # Навешиваем сгенерированные глубокие ссылки на поиск/покупку Aviasales
                for f in aviasales_result:
                    f_date = f.get("departure_date", departure_date)
                    f["booking_url"] = get_aviasales_booking_url(origin_iata, destination_iata, f_date)
            except Exception as e:
                aviasales_error = e
                
        def fetch_google():
            nonlocal google_result, google_error
            try:
                google_result = query_serpapi_flights(origin_iata, destination_iata, departure_date)
            except Exception as e:
                google_error = e
                
        # Запускаем запросы в параллельных потоках
        t1 = threading.Thread(target=fetch_aviasales)
        t2 = threading.Thread(target=fetch_google)
        
        t1.start()
        t2.start()
        
        # Ждем завершения обоих потоков
        t1.join()
        t2.join()
        
        # Логируем результаты выполнения потоков
        if aviasales_error:
            log_to_ui(f"❌ [Aviasales Error]: {str(aviasales_error)}")
        else:
            log_to_ui(f"✅ [Aviasales]: Найдено предложений: {len(aviasales_result)}")
            
        if google_error:
            log_to_ui(f"❌ [Google Flights Error]: {str(google_error)}")
        else:
            log_to_ui(f"✅ [Google Flights]: Найдено предложений: {len(google_result)}")
            
        combined_flights = aviasales_result + google_result
        
        log_to_ui(f"📊 [МультиПоиск]: Всего найдено предложений: {len(combined_flights)}")
        
        # Если билетов нет - сразу выводим локализованное сообщение и останавливаем процесс
        if len(combined_flights) == 0:
            log_to_ui(t["no_offers_found"])
            update_status(t["status_success"])
            return
            
        # Сортируем офферы по цене (от самых дешевых к дорогим)
        try:
            sorted_flights = sorted(combined_flights, key=lambda f: float(f.get("price", 0)))
        except Exception:
            sorted_flights = combined_flights
            
        # Лимит вывода в зависимости от режима поиска (до 5 для Быстрого, до 15 для Глубокого)
        selected_flights = sorted_flights[:max_results_param]
        
        # Шаг 3: Форматируем найденные офферы и выводим в интерфейс
        update_status(t["status_analyzing"])
        report_text = format_multisearch_report(selected_flights, origin_iata, destination_iata, departure_date, current_lang)
        
        log_to_ui(t["log_done"])
        log_to_ui(report_text)
        update_status(t["status_success"])
        
    except Exception as e:
        log_to_ui(t["log_error"].format(str(e)))
        update_status(t["status_error"])
        
    finally:
        # Сброс интерфейса в нормальное состояние
        root.after(0, lambda: (
            btn_search.configure(state="normal", text=t["btn_search"]),
            progress_bar.stop(),
            progress_bar.set(0)
        ))

# --- Графический интерфейс с CustomTkinter ---
root = ctk.CTk()
root.title("МультиАвиаНавигатор AI - Compare Prices")
root.geometry("780x750")

# --- Верхний контейнер (заголовки + переключатель языка) ---
frame_header = ctk.CTkFrame(root, fg_color="transparent")
frame_header.pack(fill="x", padx=24, pady=(20, 10))

# Тексты (левая часть)
frame_titles = ctk.CTkFrame(frame_header, fg_color="transparent")
frame_titles.pack(side="left")

lbl_title = ctk.CTkLabel(
    frame_titles, 
    text="✈️ МультиАвиаНавигатор AI", 
    font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
    text_color="#818cf8",
    anchor="w"
)
lbl_title.pack(anchor="w")

lbl_subtitle = ctk.CTkLabel(
    frame_titles, 
    text="Сравнение цен Aviasales и Google Flights в евро (€) на 2026 год", 
    font=ctk.CTkFont(family="Segoe UI", size=12),
    text_color="#94a3b8",
    anchor="w"
)
lbl_subtitle.pack(anchor="w")

# Выпадающий список выбора языка (правая часть)
lang_menu = ctk.CTkOptionMenu(
    frame_header, 
    values=["RU", "EN"], 
    width=65, 
    height=28,
    corner_radius=8,
    fg_color="#334155",
    button_color="#475569",
    button_hover_color="#64748b",
    command=change_language
)
lang_menu.pack(side="right", anchor="n", pady=(5, 0))
lang_menu.set("RU")

# --- Контейнер ввода параметров ---
frame_inputs = ctk.CTkFrame(root, corner_radius=12)
frame_inputs.pack(fill="x", padx=24, pady=5)
frame_inputs.grid_columnconfigure(1, weight=1)

# Поле Откуда / From
lbl_origin = ctk.CTkLabel(frame_inputs, text="Откуда:", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"))
lbl_origin.grid(row=0, column=0, sticky="w", padx=20, pady=12)

entry_origin = ctk.CTkEntry(
    frame_inputs, 
    font=ctk.CTkFont(family="Segoe UI", size=12),
    placeholder_text="Например: Хельсинки",
    corner_radius=8,
    height=35
)
entry_origin.grid(row=0, column=1, sticky="ew", padx=(0, 20), pady=12)
entry_origin.insert(0, "Хельсинки")

# Поле Куда / To
lbl_destination = ctk.CTkLabel(frame_inputs, text="Куда:", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"))
lbl_destination.grid(row=1, column=0, sticky="w", padx=20, pady=6)

entry_destination = ctk.CTkEntry(
    frame_inputs, 
    font=ctk.CTkFont(family="Segoe UI", size=12),
    placeholder_text="Например: Барселона",
    corner_radius=8,
    height=35
)
entry_destination.grid(row=1, column=1, sticky="ew", padx=(0, 20), pady=6)
entry_destination.insert(0, "Барселона")

# Поле Детали / Preferences
lbl_details = ctk.CTkLabel(frame_inputs, text="Пожелания / Дата:", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"))
lbl_details.grid(row=2, column=0, sticky="w", padx=20, pady=12)

entry_details = ctk.CTkEntry(
    frame_inputs, 
    font=ctk.CTkFont(family="Segoe UI", size=12),
    placeholder_text="Например: на сентябрь",
    corner_radius=8,
    height=35
)
entry_details.grid(row=2, column=1, sticky="ew", padx=(0, 20), pady=12)
entry_details.insert(0, "на сентябрь")

# Поле Режим поиска / Search Mode
lbl_search_mode = ctk.CTkLabel(frame_inputs, text="Режим поиска:", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"))
lbl_search_mode.grid(row=3, column=0, sticky="w", padx=20, pady=12)

segmented_button = ctk.CTkSegmentedButton(
    frame_inputs, 
    values=["Быстрый", "Глубокий"], 
    height=32,
    corner_radius=8,
    fg_color="#0f172a",
    selected_color="#4f46e5",
    selected_hover_color="#6366f1"
)
segmented_button.grid(row=3, column=1, sticky="w", padx=(0, 20), pady=12)
segmented_button.set("Быстрый")

# Кнопка запуска
btn_search = ctk.CTkButton(
    root,
    text="🔍 Найти авиабилеты",
    font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
    fg_color="#4f46e5",
    hover_color="#6366f1",
    corner_radius=8,
    height=40,
    command=start_search_thread
)
btn_search.pack(fill="x", padx=24, pady=15)

# --- Блок статуса и прогресс-бара ---
frame_status = ctk.CTkFrame(root, fg_color="transparent")
frame_status.pack(fill="x", padx=24, pady=(5, 5))

lbl_status = ctk.CTkLabel(
    frame_status, 
    text="Готов к поиску", 
    font=ctk.CTkFont(family="Segoe UI", size=12, slant="italic"),
    text_color="#a855f7"
)
lbl_status.pack(side="left", padx=(5, 10))

progress_bar = ctk.CTkProgressBar(
    frame_status, 
    orientation="horizontal", 
    mode="indeterminate",
    height=8,
    progress_color="#4f46e5"
)
progress_bar.pack(side="right", fill="x", expand=True, padx=(0, 5))
progress_bar.set(0)

# Метка области результатов
lbl_results = ctk.CTkLabel(
    root, 
    text="Результаты поиска и логи работы агента:", 
    font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
    text_color="#f8fafc",
    anchor="w"
)
lbl_results.pack(anchor="w", padx=24, pady=(10, 2))

# Текстовое поле
result_text = ctk.CTkTextbox(
    root, 
    font=ctk.CTkFont(family="Consolas", size=12),
    corner_radius=12,
    wrap="word",
    border_width=1,
    border_color="#334155"
)
result_text.pack(fill="both", expand=True, padx=24, pady=(0, 20))
result_text.configure(state="disabled")

# Запуск GUI
root.mainloop()
