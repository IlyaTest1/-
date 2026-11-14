import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
import threading
import random
import json
import os
import csv
import hashlib
import logging
from pathlib import Path

# ============ ЛОГИРОВАНИЕ ============
LOG_DIR = Path.home() / ".local" / "share" / "cbr_app"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_DIR / "app.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("cbr_app")

# ============ ТЕМЫ ============
THEMES = {
    "dark": {
        "BG": "#000000", "BG_CARD": "#141420", "BG_HEADER": "#0a0a12",
        "ACCENT": "#e63946", "ACCENT_H": "#c1121f", "TEXT": "#eaeaea",
        "TEXT_DIM": "#9a9ab0", "GREEN": "#4caf50", "RED": "#e63946",
        "GOLD": "#f4c542", "ORANGE": "#ff8c00", "BORDER": "#2a2a44",
        "GRID_MAJOR": "#5a5a7a", "GRID_MINOR": "#3a3a5a",
        "STARS": True,
    },
    "light": {
        "BG": "#f4f4f8", "BG_CARD": "#ffffff", "BG_HEADER": "#e8e8f0",
        "ACCENT": "#c1121f", "ACCENT_H": "#a00e1a", "TEXT": "#1a1a22",
        "TEXT_DIM": "#5a5a6a", "GREEN": "#2e7d32", "RED": "#c1121f",
        "GOLD": "#b8860b", "ORANGE": "#d2691e", "BORDER": "#c8c8d8",
        "GRID_MAJOR": "#b0b0c0", "GRID_MINOR": "#d8d8e0",
        "STARS": False,
    },
}

BG = BG_CARD = BG_HEADER = ACCENT = ACCENT_H = TEXT = TEXT_DIM = ""
GREEN = RED = GOLD = ORANGE = BORDER = GRID_MAJOR = GRID_MINOR = ""
STARS_ENABLED = True


def apply_theme(name: str):
    global BG, BG_CARD, BG_HEADER, ACCENT, ACCENT_H, TEXT, TEXT_DIM
    global GREEN, RED, GOLD, ORANGE, BORDER, GRID_MAJOR, GRID_MINOR, STARS_ENABLED
    t = THEMES[name]
    BG = t["BG"]; BG_CARD = t["BG_CARD"]; BG_HEADER = t["BG_HEADER"]
    ACCENT = t["ACCENT"]; ACCENT_H = t["ACCENT_H"]; TEXT = t["TEXT"]; TEXT_DIM = t["TEXT_DIM"]
    GREEN = t["GREEN"]; RED = t["RED"]; GOLD = t["GOLD"]; ORANGE = t["ORANGE"]
    BORDER = t["BORDER"]; GRID_MAJOR = t["GRID_MAJOR"]; GRID_MINOR = t["GRID_MINOR"]
    STARS_ENABLED = t["STARS"]


apply_theme("dark")

# ============ КОНФИГ ============
CONFIG_DIR = Path.home() / ".config" / "cbr_app"
CONFIG_FILE = CONFIG_DIR / "config.json"
CACHE_DIR = Path.home() / ".cache" / "cbr_app"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    try:
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text("utf-8"))
    except Exception as e:
        log.warning("Не удалось прочитать конфиг: %s", e)
    return {}


def save_config(cfg: dict):
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), "utf-8")
    except Exception as e:
        log.warning("Не удалось сохранить конфиг: %s", e)


# ============ КЭШ ============
def _cache_key(prefix: str, payload: str) -> Path:
    h = hashlib.md5(payload.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{prefix}_{h}.cache"


def cache_get(prefix: str, payload: str, ttl_seconds: int):
    p = _cache_key(prefix, payload)
    if not p.exists():
        return None
    try:
        if datetime.now().timestamp() - p.stat().st_mtime > ttl_seconds:
            return None
        return p.read_text("utf-8")
    except Exception:
        return None


def cache_set(prefix: str, payload: str, text: str):
    try:
        _cache_key(prefix, payload).write_text(text, "utf-8")
    except Exception as e:
        log.warning("Кэш не записан: %s", e)


def cached_request(prefix: str, payload: str, ttl: int, method: str, url: str, **kw) -> str:
    hit = cache_get(prefix, payload, ttl)
    if hit is not None:
        return hit
    encoding = kw.pop("encoding", None)
    if method == "GET":
        resp = requests.get(url, **kw)
    else:
        resp = requests.post(url, **kw)
    resp.raise_for_status()
    if encoding:
        resp.encoding = encoding
    text = resp.text
    cache_set(prefix, payload, text)
    return text


# ============ ВАЛЮТЫ / МЕТАЛЛЫ / ПЕРИОДЫ ============
CURRENCIES = {
    "USD": {"name": "Доллар США",           "flag": "🇺🇸"},
    "EUR": {"name": "Евро",                 "flag": "🇪🇺"},
    "CNY": {"name": "Китайский юань",       "flag": "🇨🇳"},
    "KZT": {"name": "Казахстанский тенге",  "flag": "🇰🇿"},
    "TRY": {"name": "Турецкая лира",        "flag": "🇹🇷"},
    "AED": {"name": "Дирхам ОАЭ",           "flag": "🇦🇪"},
    "UAH": {"name": "Украинская гривна",    "flag": "🇺🇦"},
    "BYN": {"name": "Белорусский рубль",    "flag": "🇧🇾"},
    "THB": {"name": "Таиландский бат",      "flag": "🇹🇭"},
    "JPY": {"name": "Японская йена",        "flag": "🇯🇵"},
    "UZS": {"name": "Узбекский сум",        "flag": "🇺🇿"},
    "GEL": {"name": "Грузинский лари",      "flag": "🇬🇪"},
    "GBP": {"name": "Фунт стерлингов",      "flag": "🇬🇧"},
    "AZN": {"name": "Азербайджанский манат","flag": "🇦🇿"},
    "KGS": {"name": "Киргизский сом",       "flag": "🇰🇬"},
    "TJS": {"name": "Таджикский сомони",    "flag": "🇹🇯"},
}

METALS = {
    "GOLD":      {"name": "Золото",   "codmet": "1"},
    "SILVER":    {"name": "Серебро",  "codmet": "2"},
    "PLATINUM":  {"name": "Платина",  "codmet": "3"},
    "PALLADIUM": {"name": "Палладий", "codmet": "4"},
}

PERIODS = {
    "Месяц":     30,
    "Год":       365,
    "Всё время": 3650,
}

_CBR_CODES = {}
_CBR_CODES_LOCK = threading.Lock()


def _load_cbr_codes():
    global _CBR_CODES
    with _CBR_CODES_LOCK:
        if _CBR_CODES:
            return
        text = cached_request(
            "valfull", "all", 24 * 3600, "GET",
            "https://www.cbr.ru/scripts/XML_valFull.asp",
            timeout=20, encoding="windows-1251",
        )
        root = ET.fromstring(text)
        for item in root.findall("Item"):
            iso = item.find("ISO_Char_Code").text
            vid = item.get("ID")
            if iso and vid:
                _CBR_CODES[iso] = vid


# ============ ОШИБКИ ============
def human_error(e: Exception) -> str:
    if isinstance(e, requests.exceptions.ConnectionError):
        return "Нет соединения с интернетом"
    if isinstance(e, requests.exceptions.Timeout):
        return "ЦБ РФ не отвечает (таймаут)"
    if isinstance(e, requests.exceptions.HTTPError):
        return "ЦБ РФ вернул ошибку"
    if isinstance(e, ET.ParseError):
        return "Не удалось разобрать ответ ЦБ"
    return str(e)


# ============ API: КУРСЫ ВАЛЮТ ============
def get_current_rates() -> dict:
    _load_cbr_codes()
    text = cached_request(
        "daily", datetime.now().strftime("%Y-%m-%d"), 3600, "GET",
        "https://www.cbr.ru/scripts/XML_daily.asp",
        timeout=15, encoding="windows-1251",
    )
    root = ET.fromstring(text)
    rates = {}
    for valute in root.findall("Valute"):
        code = valute.find("CharCode").text
        if code in CURRENCIES:
            value = float(valute.find("Value").text.replace(",", "."))
            nominal_el = valute.find("Nominal")
            nominal = int(nominal_el.text) if nominal_el is not None and nominal_el.text else 1
            rates[code] = value / nominal if nominal > 1 else value
    return rates


def get_dynamic_rates(currency_code: str, days: int):
    _load_cbr_codes()
    cbr_id = _CBR_CODES.get(currency_code)
    if not cbr_id:
        raise Exception(f"Код '{currency_code}' не найден в справочнике ЦБ")
    date_to = datetime.now()
    date_from = date_to - timedelta(days=days)
    payload = f"{cbr_id}_{date_from:%Y%m%d}_{date_to:%Y%m%d}"
    params = {
        "date_req1": date_from.strftime("%d/%m/%Y"),
        "date_req2": date_to.strftime("%d/%m/%Y"),
        "VAL_NM_RQ": cbr_id,
    }
    text = cached_request(
        "dynamic", payload, 3600, "GET",
        "https://www.cbr.ru/scripts/XML_dynamic.asp",
        timeout=20, encoding="windows-1251", params=params,
    )
    root = ET.fromstring(text)
    dates, values = [], []
    for record in root.findall("Record"):
        d = datetime.strptime(record.get("Date"), "%d.%m.%Y")
        v = float(record.find("Value").text.replace(",", "."))
        nominal_el = record.find("Nominal")
        nominal = int(nominal_el.text) if nominal_el is not None and nominal_el.text else 1
        dates.append(d)
        values.append(v / nominal if nominal > 1 else v)
    return dates, values


def get_daily_change(currency_code: str):
    try:
        dates, values = get_dynamic_rates(currency_code, 7)
        if len(values) >= 2:
            return values[-1], values[-2]
        if values:
            return values[-1], None
    except Exception as e:
        log.info("daily_change fail %s: %s", currency_code, e)
    return None, None


# ============ API: МЕТАЛЛЫ ============
def _soap_metals(date_from, date_to):
    url = "https://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx"
    soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <DragMetDynamic xmlns="http://web.cbr.ru/">
      <fromDate>{date_from.strftime("%Y-%m-%dT00:00:00")}</fromDate>
      <ToDate>{date_to.strftime("%Y-%m-%dT00:00:00")}</ToDate>
    </DragMetDynamic>
  </soap:Body>
</soap:Envelope>"""
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": "http://web.cbr.ru/DragMetDynamic",
    }
    payload = f"{date_from:%Y%m%d}_{date_to:%Y%m%d}"
    return cached_request("metals_soap", payload, 3600, "POST", url,
                          data=soap_body.encode("utf-8"), headers=headers, timeout=25)


def get_metal_history(metal_key: str, days: int):
    codmet = METALS[metal_key]["codmet"]
    date_to = datetime.now()
    date_from = date_to - timedelta(days=days)
    xml_text = _soap_metals(date_from, date_to)

    start = xml_text.find("<DRG_MET>")
    if start == -1:
        start = xml_text.find("<diffgr:diffgram")
        if start == -1:
            raise Exception("ЦБ не вернул данные металлов")
        end = xml_text.find("</diffgr:diffgram>") + len("</diffgr:diffgram>")
    else:
        end = xml_text.find("</DRG_MET>") + len("</DRG_MET>")

    inner = xml_text[start:end]
    wrapped = f"<root>{inner}</root>"
    root = ET.fromstring(wrapped)

    dates, values = [], []
    for rec in root.iter():
        tag = rec.tag.split("}")[-1] if "}" in rec.tag else rec.tag
        if tag.lower() in ("drg_met", "drgmet", "record"):
            date_el = price_el = cod_el = None
            for child in rec:
                ctag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if ctag.lower() in ("datemet", "date"):
                    date_el = child
                elif ctag.lower() in ("price", "value"):
                    price_el = child
                elif ctag.lower() in ("codmet", "cod"):
                    cod_el = child
            if date_el is not None and price_el is not None:
                if cod_el is not None and cod_el.text != codmet:
                    continue
                try:
                    d = datetime.strptime(date_el.text[:10], "%Y-%m-%d")
                except ValueError:
                    try:
                        d = datetime.strptime(date_el.text[:10], "%d.%m.%Y")
                    except ValueError:
                        continue
                try:
                    v = float(price_el.text.replace(",", "."))
                except ValueError:
                    continue
                dates.append(d)
                values.append(v)

    if not dates:
        raise Exception("Не удалось разобрать данные металлов ЦБ")
    paired = sorted(zip(dates, values), key=lambda x: x[0])
    return [p[0] for p in paired], [p[1] for p in paired]


def get_metal_current(metal_key: str):
    dates, values = get_metal_history(metal_key, 10)
    return values[-1] if values else None


# ============ ФОРМАТИРОВАНИЕ ============
def fmt_money(v, decimals=4) -> str:
    if v is None:
        return "—"
    s = f"{v:,.{decimals}f}"
    return s.replace(",", " ").replace(".", ",")


def fmt_pct(v) -> str:
    if v is None:
        return ""
    return f"{v:+.2f}%".replace(".", ",")


# ============ ЗВЁЗДЫ ============
_STAR_CACHE = {}


def draw_starfield(canvas, width, height, seed=42):
    canvas.delete("bg")
    canvas.configure(bg=BG)
    canvas.create_rectangle(0, 0, width, height, fill=BG, outline="", tags="bg")
    if not STARS_ENABLED:
        canvas.tag_lower("bg")
        return

    key = (width, height, seed)
    stars = _STAR_CACHE.get(key)
    if stars is None:
        rng = random.Random(seed)
        stars = []
        n_small = max(80, (width * height) // 6000)
        for _ in range(n_small):
            x = rng.randint(0, max(1, width - 1))
            y = rng.randint(0, max(1, height - 1))
            r = rng.choice([1, 1, 1, 2])
            shade = rng.choice(["#ffffff", "#dddddd", "#aaaaaa", "#8888aa", "#aaccff"])
            stars.append((x, y, r, shade, False))
        n_big = max(6, width // 150)
        for _ in range(n_big):
            x = rng.randint(0, max(1, width - 1))
            y = rng.randint(0, max(1, height - 1))
            r = rng.choice([2, 3])
            stars.append((x, y, r, "#ffffff", True))
        _STAR_CACHE[key] = stars

    for x, y, r, shade, big in stars:
        if big:
            canvas.create_oval(x - r, y - r, x + r, y + r,
                               fill=shade, outline="#aaccff", tags="bg")
        else:
            canvas.create_oval(x, y, x + r, y + r, fill=shade, outline="", tags="bg")
    canvas.tag_lower("bg")


# ============ ФОНОВЫЙ КАНВАС СО ЗВЁЗДАМИ ============
def make_star_canvas(parent, seed=7):
    """Canvas со звёздным фоном + вертикальный скролл.
    Возвращает (canvas, inner_frame, window_id)."""
    canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
    canvas.pack(side="left", fill="both", expand=True)

    scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    scrollbar.pack(side="right", fill="y")
    canvas.configure(yscrollcommand=scrollbar.set)

    inner = tk.Frame(canvas, bg=BG)
    window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    def _on_canvas_resize(event):
        canvas.itemconfig(window_id, width=event.width)
        draw_starfield(canvas, event.width, event.height, seed=seed)
        canvas.tag_lower("bg")

    def _on_inner_resize(event):
        # Обновляем scrollregion и «подтягиваем» высоту окна
        bbox = canvas.bbox("all")
        if bbox:
            canvas.configure(scrollregion=bbox)

    canvas.bind("<Configure>", _on_canvas_resize)
    inner.bind("<Configure>", _on_inner_resize)

    # Колесо мыши для прокрутки
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-event.delta / 120), "units")
    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    return canvas, inner, window_id
# ============ ИНТЕРФЕЙС ============
class App:
    AUTO_REFRESH_MS = 10 * 60 * 1000  # 10 минут

    def __init__(self, root):
        self.root = root
        self.cfg = load_config()
        apply_theme("dark")

        self.root.title("Курсы валют и металлов")
        self.root.geometry("1200x860")
        self.root.configure(bg=BG)
        self.root.minsize(960, 640)

        self._chart_request_id = 0
        self._last_update_ts = None
        self._thresholds = self.cfg.get("thresholds", {})
        self._threshold_alerted = set()
        self._current_rates = {}
        self._current_metals = {}

        self._build_style()
        self._build_header()

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=16, pady=16)

        self.tab_cur = ttk.Frame(self.notebook)
        self.tab_raw = ttk.Frame(self.notebook)
        self.tab_chart = ttk.Frame(self.notebook)
        self.tab_conv = ttk.Frame(self.notebook)
        self.tab_port = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_cur, text="$  Валюты")
        self.notebook.add(self.tab_raw, text="▰  Металлы (ЦБ)")
        self.notebook.add(self.tab_chart, text="📈  График")
        self.notebook.add(self.tab_conv, text="⇄  Конвертер")
        self.notebook.add(self.tab_port, text="💼  Портфель")

        self._build_currency_tab()
        self._build_raw_tab()
        self._build_chart_tab()
        self._build_converter_tab()
        self._build_portfolio_tab()

        self._bind_hotkeys()
        self.root.after(100, self.load_all_async)
        self.root.after(self.AUTO_REFRESH_MS, self._auto_refresh)

    # ---------- СТИЛЬ ----------
    def _build_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG_CARD, foreground=TEXT,
                        padding=[20, 10], font=("Segoe UI", 11, "bold"), borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", BG_HEADER)],
                  foreground=[("selected", GOLD)])
        style.configure("TFrame", background=BG)
        style.configure("TCombobox", fieldbackground="#ffffff", background="#ffffff",
                        foreground="black", arrowcolor="black", borderwidth=0)
        style.map("TCombobox",
                  fieldbackground=[("readonly", "#ffffff")],
                  foreground=[("readonly", "black")])

    def _build_header(self):
        self.header = tk.Frame(self.root, bg=BG_HEADER, height=72)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)
        tk.Label(self.header, text="$  Курсы валют и металлов",
                 font=("Segoe UI", 20, "bold"), bg=BG_HEADER, fg=GOLD
                 ).pack(side="left", padx=18, pady=16)

        right = tk.Frame(self.header, bg=BG_HEADER)
        right.pack(side="right", padx=12, pady=16)

        tk.Button(right, text="🔔 Пороги", command=self._edit_thresholds,
                  font=("Segoe UI", 10, "bold"), bg=BG_CARD, fg=TEXT,
                  relief="flat", padx=12, pady=6, cursor="hand2", bd=0
                  ).pack(side="right", padx=4)

        tk.Frame(self.header, bg=ACCENT, height=3).pack(fill="x", side="bottom")

    # ---------- ПОРОГИ ----------
    def _edit_thresholds(self):
        win = tk.Toplevel(self.root)
        win.title("Пороги уведомлений")
        win.configure(bg=BG_CARD)
        win.geometry("420x460")
        tk.Label(win, text="Уведомлять, если курс ≥ значения (₽)",
                 font=("Segoe UI", 11, "bold"), bg=BG_CARD, fg=TEXT
                 ).pack(pady=10)
        entries = {}
        for code in CURRENCIES:
            row = tk.Frame(win, bg=BG_CARD)
            row.pack(fill="x", padx=16, pady=2)
            tk.Label(row, text=code, width=6, anchor="w",
                     bg=BG_CARD, fg=TEXT, font=("Segoe UI", 10, "bold")
                     ).pack(side="left")
            e = tk.Entry(row, width=12, font=("Segoe UI", 10))
            val = self._thresholds.get(code)
            if val is not None:
                e.insert(0, str(val))
            e.pack(side="left", padx=6)
            entries[code] = e

        def _save():
            new = {}
            for c, e in entries.items():
                s = e.get().strip().replace(",", ".")
                if s:
                    try:
                        new[c] = float(s)
                    except ValueError:
                        pass
            self._thresholds = new
            self.cfg["thresholds"] = new
            save_config(self.cfg)
            self._threshold_alerted.clear()
            win.destroy()

        tk.Button(win, text="Сохранить", command=_save, bg=ACCENT, fg="white",
                  relief="flat", padx=16, pady=6, cursor="hand2", bd=0
                  ).pack(pady=12)

    def _check_thresholds(self, rates):
        for code, threshold in self._thresholds.items():
            val = rates.get(code)
            if val is None:
                continue
            key = (code, round(threshold, 4))
            if val >= threshold and key not in self._threshold_alerted:
                self._threshold_alerted.add(key)
                messagebox.showwarning(
                    "Порог достигнут",
                    f"{code}: {fmt_money(val, 4)} ₽ ≥ {fmt_money(threshold, 2)} ₽",
                )

    # ---------- ГОРЯЧИЕ КЛАВИШИ ----------
    def _bind_hotkeys(self):
        self.root.bind("<Control-r>", lambda e: self.load_all_async())
        self.root.bind("<Control-R>", lambda e: self.load_all_async())
        self.root.bind("<Control-Key-1>", lambda e: self.notebook.select(0))
        self.root.bind("<Control-Key-2>", lambda e: self.notebook.select(1))
        self.root.bind("<Control-Key-3>", lambda e: self.notebook.select(2))
        self.root.bind("<Control-Key-4>", lambda e: self.notebook.select(3))
        self.root.bind("<Control-Key-5>", lambda e: self.notebook.select(4))
        self.root.bind("<Escape>", lambda e: self._clear_selection())

    def _clear_selection(self):
        self.currency_var.set(self.currency_display[0])
        self.metal_var.set(self.metal_display[0])
        self.manual_code.set("")
        self.update_chart_async()

    # ---------- КЛИКИ ПО КАРТОЧКАМ ----------
    def _bind_card(self, widget, on_left=None, on_right=None):
        if on_left:
            widget.bind("<Button-1>", on_left, add="+")
        if on_right:
            widget.bind("<Button-3>", on_right, add="+")
        try:
            widget.configure(cursor="hand2")
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._bind_card(child, on_left, on_right)

    def _flash_card(self, card):
        try:
            card.configure(highlightbackground=GOLD)
            self.root.after(200, lambda: card.configure(highlightbackground=BORDER))
        except tk.TclError:
            pass

    def _copy_to_clipboard(self, text, note="Скопировано"):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self._toast(note)
        except Exception:
            pass

    def _toast(self, text):
        if hasattr(self, "status_label"):
            prev = self.status_label.cget("text")
            self.status_label.config(text=f"✔ {text}", fg=GREEN)
            self.root.after(1500, lambda: self.status_label.config(text=prev))

    def _goto_chart_for_currency(self, code):
        for item in self.currency_display:
            if item.startswith("—"):
                continue
            parts = item.split()
            if len(parts) > 1 and parts[1] == code:
                self.currency_var.set(item)
                break
        self.metal_var.set(self.metal_display[0])
        self.manual_code.set("")
        self.notebook.select(self.tab_chart)
        self.update_chart_async()

    def _goto_chart_for_metal(self, key):
        name = METALS[key]["name"]
        for item in self.metal_display:
            if item == name:
                self.metal_var.set(item)
                break
        self.currency_var.set(self.currency_display[0])
        self.manual_code.set("")
        self.notebook.select(self.tab_chart)
        self.update_chart_async()

    # ============ ВКЛАДКА ВАЛЮТ ============
    def _build_currency_tab(self):
        frame = self.tab_cur
        self.bg_canvas = tk.Canvas(frame, bg=BG, highlightthickness=0)
        self.bg_canvas.pack(fill="both", expand=True)

        scrollbar = tk.Scrollbar(frame, orient="vertical", command=self.bg_canvas.yview)
        scrollbar.place(relx=1.0, rely=0, relheight=1.0, anchor="ne")

        self.scroll_frame = tk.Frame(self.bg_canvas, bg=BG)
        self.scroll_window = self.bg_canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.bg_canvas.configure(yscrollcommand=scrollbar.set)

        def _on_resize(event):
            self.bg_canvas.itemconfig(self.scroll_window, width=event.width)
            draw_starfield(self.bg_canvas, event.width, event.height)
            self.bg_canvas.tag_lower("bg")

        self.bg_canvas.bind("<Configure>", _on_resize)
        self.scroll_frame.bind("<Configure>",
            lambda e: self.bg_canvas.configure(scrollregion=self.bg_canvas.bbox("all")))

        self.rate_labels = {}
        self.delta_labels = {}
        self.spark_canvases = {}
        self._currency_cards = {}

        for i, (code, info) in enumerate(CURRENCIES.items()):
            row, col = divmod(i, 4)
            card = tk.Frame(self.scroll_frame, bg=BG_CARD, padx=14, pady=10,
                            highlightbackground=BORDER, highlightthickness=1)
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            self.scroll_frame.columnconfigure(col, weight=1)
            self._currency_cards[code] = card

            tk.Label(card, text=f"{info['flag']} {info['name']}",
                     font=("Segoe UI", 12, "bold"), bg=BG_CARD, fg=TEXT
                     ).pack(anchor="w")
            tk.Frame(card, bg=ACCENT, height=2).pack(fill="x", pady=(6, 8))

            row2 = tk.Frame(card, bg=BG_CARD)
            row2.pack(anchor="w", fill="x")

            lbl = tk.Label(row2, text="—", font=("Segoe UI", 20, "bold"),
                           bg=BG_CARD, fg=ORANGE)
            lbl.pack(side="left")
            self.rate_labels[code] = lbl

            delta = tk.Label(row2, text="", font=("Segoe UI", 10, "bold"),
                             bg=BG_CARD, fg=TEXT_DIM)
            delta.pack(side="left", padx=(8, 0), pady=(6, 0))
            self.delta_labels[code] = delta

            tk.Label(card, text="руб. за 1 ед.", font=("Segoe UI", 8),
                     bg=BG_CARD, fg=TEXT_DIM).pack(anchor="w")

            spark = tk.Canvas(card, width=160, height=28, bg=BG_CARD, highlightthickness=0)
            spark.pack(anchor="w", pady=(6, 0))
            self.spark_canvases[code] = spark

            self._bind_card(
                card,
                on_left=lambda e, c=code, w=card: (self._flash_card(w),
                                                   self._goto_chart_for_currency(c)),
                on_right=lambda e, c=code: self._copy_to_clipboard(
                    fmt_money(self._current_rates.get(c), 4),
                    f"{c} скопирован"),
            )

        btn = tk.Button(self.scroll_frame, text="🔄  Обновить", command=self.load_all_async,
                        font=("Segoe UI", 12, "bold"), bg=ACCENT, fg="white",
                        activebackground=ACCENT_H, activeforeground="white",
                        relief="flat", padx=28, pady=10, cursor="hand2", bd=0)
        btn.grid(row=(len(CURRENCIES) + 3) // 4, column=0, columnspan=4, pady=18)

        self.status_label = tk.Label(self.scroll_frame, text="",
                                     font=("Segoe UI", 10), bg=BG, fg=TEXT_DIM)
        self.status_label.grid(row=(len(CURRENCIES) + 3) // 4 + 1, column=0, columnspan=4)
    # ============ ВКЛАДКА МЕТАЛЛОВ ============
    def _build_raw_tab(self):
        frame = self.tab_raw
        self.raw_labels = {}
        self.raw_delta_labels = {}
        self.raw_sparks = {}

        self.raw_canvas = tk.Canvas(frame, bg=BG, highlightthickness=0)
        self.raw_canvas.pack(fill="both", expand=True)

        inner = tk.Frame(self.raw_canvas, bg=BG)
        self.raw_window = self.raw_canvas.create_window((0, 0), window=inner, anchor="nw")

        def _resize(event):
            self.raw_canvas.itemconfig(self.raw_window, width=event.width)
            draw_starfield(self.raw_canvas, event.width, event.height, seed=99)
            self.raw_canvas.tag_lower("bg")

        self.raw_canvas.bind("<Configure>", _resize)
        inner.bind("<Configure>",
            lambda e: self.raw_canvas.configure(scrollregion=self.raw_canvas.bbox("all")))

        metals_frame = tk.Frame(inner, bg=BG)
        metals_frame.pack(fill="x", pady=(24, 12), padx=10)
        tk.Label(metals_frame, text="Драгоценные металлы (учётные цены ЦБ РФ)",
                 font=("Segoe UI", 13, "bold"), bg=BG, fg=GOLD
                 ).pack(anchor="w", padx=4, pady=(0, 12))

        grid = tk.Frame(metals_frame, bg=BG)
        grid.pack(fill="x")
        for i, (key, info) in enumerate(METALS.items()):
            card = tk.Frame(grid, bg=BG_CARD, padx=20, pady=16,
                            highlightbackground=BORDER, highlightthickness=1)
            card.grid(row=0, column=i, padx=10, sticky="nsew")
            grid.columnconfigure(i, weight=1)

            tk.Label(card, text=info["name"], font=("Segoe UI", 13, "bold"),
                     bg=BG_CARD, fg=TEXT).pack(anchor="w")
            tk.Frame(card, bg=ACCENT, height=2).pack(fill="x", pady=(8, 10))

            row2 = tk.Frame(card, bg=BG_CARD)
            row2.pack(anchor="w", fill="x")
            lbl = tk.Label(row2, text="—", font=("Segoe UI", 20, "bold"),
                           bg=BG_CARD, fg=ORANGE)
            lbl.pack(side="left")
            self.raw_labels[key] = lbl

            delta = tk.Label(row2, text="", font=("Segoe UI", 10, "bold"),
                             bg=BG_CARD, fg=TEXT_DIM)
            delta.pack(side="left", padx=(8, 0), pady=(6, 0))
            self.raw_delta_labels[key] = delta

            tk.Label(card, text="руб./грамм", font=("Segoe UI", 8),
                     bg=BG_CARD, fg=TEXT_DIM).pack(anchor="w")

            spark = tk.Canvas(card, width=160, height=28,
                              bg=BG_CARD, highlightthickness=0)
            spark.pack(anchor="w", pady=(6, 0))
            self.raw_sparks[key] = spark

            self._bind_card(
                card,
                on_left=lambda e, k=key, w=card: (self._flash_card(w),
                                                  self._goto_chart_for_metal(k)),
                on_right=lambda e, k=key: self._copy_to_clipboard(
                    fmt_money(self._current_metals.get(k), 2),
                    f"{METALS[k]['name']} скопирован"),
            )

        self.raw_status = tk.Label(inner, text="", font=("Segoe UI", 10), bg=BG, fg=TEXT_DIM)
        self.raw_status.pack(pady=20)

    # ============ ВКЛАДКА ГРАФИКА ============
    def _build_chart_tab(self):
        frame = self.tab_chart
        controls = tk.Frame(frame, bg=BG)
        controls.pack(fill="x", pady=(0, 10), padx=10)

        tk.Label(controls, text="Валюта:", font=("Segoe UI", 11, "bold"),
                 bg=BG, fg=TEXT).pack(side="left", padx=(0, 8))

        self.currency_display = ["— (не выбрана)"]
        for code, info in CURRENCIES.items():
            self.currency_display.append(f"{info['flag']} {code} — {info['name']}")

        self.currency_var = tk.StringVar(value=self.currency_display[1])
        self.cb_cur = ttk.Combobox(controls, textvariable=self.currency_var,
                                   values=self.currency_display, state="readonly",
                                   width=24, font=("Segoe UI", 10))
        self.cb_cur.pack(side="left", padx=(0, 10))
        self.cb_cur.bind("<<ComboboxSelected>>", self._on_currency_selected)

        tk.Label(controls, text="или код:", font=("Segoe UI", 10),
                 bg=BG, fg=TEXT_DIM).pack(side="left", padx=(0, 4))
        self.manual_code = tk.StringVar(value="")
        entry = tk.Entry(controls, textvariable=self.manual_code, width=6,
                         font=("Segoe UI", 11, "bold"), bg="#ffffff", fg="black",
                         insertbackground="black", relief="flat", bd=0)
        entry.pack(side="left", padx=(0, 12), ipady=4)
        entry.bind("<Return>", lambda e: self.update_chart_async())

        tk.Label(controls, text="Металл:", font=("Segoe UI", 11, "bold"),
                 bg=BG, fg=TEXT).pack(side="left", padx=(0, 6))
        self.metal_display = ["— (не выбран)"]
        for key, info in METALS.items():
            self.metal_display.append(info["name"])
        self.metal_var = tk.StringVar(value=self.metal_display[0])
        self.cb_metal = ttk.Combobox(controls, textvariable=self.metal_var,
                                     values=self.metal_display, state="readonly",
                                     width=14, font=("Segoe UI", 10))
        self.cb_metal.pack(side="left", padx=(0, 12))
        self.cb_metal.bind("<<ComboboxSelected>>", self._on_metal_selected)

        tk.Label(controls, text="Период:", font=("Segoe UI", 11, "bold"),
                 bg=BG, fg=TEXT).pack(side="left", padx=(0, 6))
        self.period_var = tk.StringVar(value=self.cfg.get("period", "Месяц"))
        cb2 = ttk.Combobox(controls, textvariable=self.period_var,
                           values=list(PERIODS.keys()), state="readonly",
                           width=10, font=("Segoe UI", 10))
        cb2.pack(side="left", padx=(0, 12))
        cb2.bind("<<ComboboxSelected>>", self._on_period_changed)

        # Чекбокс «с прошлым» — сохраняем ссылку, чтобы прятать при «Всё время»
        self.compare_prev_var = tk.BooleanVar(value=False)
        self.compare_prev_cb = tk.Checkbutton(
            controls, text="с прошлым", variable=self.compare_prev_var,
            bg=BG, fg=TEXT, selectcolor=BG_CARD, activebackground=BG,
            command=self.update_chart_async)
        self.compare_prev_cb.pack(side="left", padx=(0, 8))

        tk.Button(controls, text="⤓ PNG", command=self._export_png,
                  bg=BG_CARD, fg=TEXT, relief="flat", padx=10, pady=4,
                  cursor="hand2", bd=0).pack(side="right", padx=4)
        tk.Button(controls, text="⤓ CSV", command=self._export_csv,
                  bg=BG_CARD, fg=TEXT, relief="flat", padx=10, pady=4,
                  cursor="hand2", bd=0).pack(side="right", padx=4)

        self.chart_frame = tk.Frame(frame, bg=BG_CARD,
                                    highlightbackground=BORDER, highlightthickness=1)
        self.chart_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        plt.rcParams.update({
            "figure.facecolor": BG_CARD, "axes.facecolor": BG_CARD,
            "axes.edgecolor": BORDER, "axes.labelcolor": TEXT,
            "xtick.color": TEXT_DIM, "ytick.color": TEXT_DIM, "text.color": TEXT,
            "grid.color": GRID_MAJOR, "grid.alpha": 0.55, "grid.linewidth": 1.3,
            "font.size": 11,
        })
        self.fig, self.ax = plt.subplots(figsize=(8, 4), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.chart_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        self._last_chart_data = ([], [], "")
        self.update_chart_async()

    # ============ ЭКСПОРТ ============
    def _export_png(self):
        path = filedialog.asksaveasfilename(defaultextension=".png",
            filetypes=[("PNG", "*.png")], title="Сохранить график")
        if not path:
            return
        try:
            self.fig.savefig(path, dpi=150, facecolor=BG_CARD)
            self._toast(f"Сохранено: {path}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def _export_csv(self):
        dates, values, label = self._last_chart_data
        if not dates:
            messagebox.showinfo("Экспорт", "Нет данных для экспорта")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv",
            filetypes=[("CSV", "*.csv")], title="Сохранить данные")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["date", label])
                for d, v in zip(dates, values):
                    w.writerow([d.strftime("%Y-%m-%d"), f"{v:.4f}"])
            self._toast(f"Сохранено: {path}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
    # ============ ВКЛАДКА КОНВЕРТЕРА ============
    def _build_converter_tab(self):
        frame = self.tab_conv
        self.conv_canvas, inner, _ = make_star_canvas(frame, seed=21)

        card = tk.Frame(inner, bg=BG_CARD, padx=40, pady=30,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(pady=40)

        tk.Label(card, text="⇄  Конвертер валют",
                 font=("Segoe UI", 16, "bold"), bg=BG_CARD, fg=GOLD
                 ).pack(pady=(0, 20))

        top = tk.Frame(card, bg=BG_CARD)
        top.pack()

        tk.Label(top, text="Сумма:", font=("Segoe UI", 12, "bold"),
                 bg=BG_CARD, fg=TEXT).grid(row=0, column=0, padx=8, pady=8, sticky="e")
        self.conv_amount = tk.StringVar(value="100")
        tk.Entry(top, textvariable=self.conv_amount, width=16,
                 font=("Segoe UI", 13, "bold"), bg="#ffffff", fg="black"
                 ).grid(row=0, column=1, padx=8, pady=8, ipady=6)

        self.conv_units = ["RUB — Российский рубль"]
        for code, info in CURRENCIES.items():
            self.conv_units.append(f"{code} — {info['name']}")
        for key, info in METALS.items():
            self.conv_units.append(f"METAL:{key} — {info['name']} (г)")

        tk.Label(top, text="Из:", font=("Segoe UI", 12, "bold"),
                 bg=BG_CARD, fg=TEXT).grid(row=1, column=0, padx=8, pady=8, sticky="e")
        self.conv_from = tk.StringVar(value=self.conv_units[0])
        ttk.Combobox(top, textvariable=self.conv_from, values=self.conv_units,
                     state="readonly", width=32, font=("Segoe UI", 10)
                     ).grid(row=1, column=1, padx=8, pady=8)

        tk.Label(top, text="В:", font=("Segoe UI", 12, "bold"),
                 bg=BG_CARD, fg=TEXT).grid(row=2, column=0, padx=8, pady=8, sticky="e")
        self.conv_to = tk.StringVar(
            value=self.conv_units[1] if len(self.conv_units) > 1 else self.conv_units[0])
        ttk.Combobox(top, textvariable=self.conv_to, values=self.conv_units,
                     state="readonly", width=32, font=("Segoe UI", 10)
                     ).grid(row=2, column=1, padx=8, pady=8)

        tk.Button(card, text="Пересчитать", command=self._convert,
                  bg=ACCENT, fg="white", relief="flat", padx=24, pady=10,
                  font=("Segoe UI", 11, "bold"), cursor="hand2", bd=0
                  ).pack(pady=18)

        # Аккуратная двойная рамка результата
        self.conv_result_frame = tk.Frame(
            card, bg=BG, highlightbackground=BORDER, highlightthickness=1)
        self.conv_result_frame.pack(pady=6)
        inner_res = tk.Frame(self.conv_result_frame, bg=BG,
                             highlightbackground=ACCENT, highlightthickness=2)
        inner_res.pack(padx=3, pady=3)

        self.conv_result = tk.Label(inner_res, text="—",
                                    font=("Segoe UI", 22, "bold"),
                                    bg=BG, fg=GOLD, padx=20, pady=8)
        self.conv_result.pack()

        tk.Label(card, text="Курсы берутся из ЦБ РФ. Металлы — ₽ за грамм.",
                 font=("Segoe UI", 9), bg=BG_CARD, fg=TEXT_DIM).pack(pady=(12, 0))

    def _convert(self):
        try:
            amount = float(self.conv_amount.get().replace(",", "."))
        except ValueError:
            self.conv_result.config(text="Введите число", fg=RED)
            return

        def unit_value(u):
            if u.startswith("RUB"):
                return 1.0
            if u.startswith("METAL:"):
                key = u.split(":", 1)[1].split(" ")[0]
                v = self._current_metals.get(key)
                if v is None:
                    raise Exception(f"Нет курса {key}")
                return v
            code = u.split()[0]
            v = self._current_rates.get(code)
            if v is None:
                raise Exception(f"Нет курса {code}")
            return v

        try:
            from_v = unit_value(self.conv_from.get())
            to_v = unit_value(self.conv_to.get())
            result = amount * from_v / to_v
            self.conv_result.config(text=f"{fmt_money(result, 4)}", fg=GOLD)
        except Exception as e:
            self.conv_result.config(text=human_error(e), fg=RED)

    # ============ ВКЛАДКА ПОРТФЕЛЯ ============
    def _build_portfolio_tab(self):
        frame = self.tab_port
        self.port_canvas, inner, _ = make_star_canvas(frame, seed=55)

        header = tk.Frame(inner, bg=BG)
        header.pack(fill="x", pady=(16, 8))
        tk.Label(header, text="💼  Портфель",
                 font=("Segoe UI", 16, "bold"), bg=BG, fg=GOLD).pack()

        tk.Label(inner, text="Введите количество валюты / граммов металла",
                 font=("Segoe UI", 12, "bold"), bg=BG, fg=TEXT
                 ).pack(pady=(0, 8))

        container = tk.Frame(inner, bg=BG_CARD, padx=16, pady=12,
                             highlightbackground=BORDER, highlightthickness=1)
        container.pack(fill="x", padx=20, pady=8)
        self.port_entries = {}

        cols = tk.Frame(container, bg=BG_CARD)
        cols.pack(fill="x")
        tk.Label(cols, text="Инструмент", width=24, anchor="w",
                 font=("Segoe UI", 11, "bold"), bg=BG_CARD, fg=TEXT
                 ).grid(row=0, column=0, sticky="w")
        tk.Label(cols, text="Кол-во", width=12,
                 font=("Segoe UI", 11, "bold"), bg=BG_CARD, fg=TEXT
                 ).grid(row=0, column=1)
        tk.Label(cols, text="₽", width=16,
                 font=("Segoe UI", 11, "bold"), bg=BG_CARD, fg=TEXT
                 ).grid(row=0, column=2)
        tk.Label(cols, text="Δ за день", width=14,
                 font=("Segoe UI", 11, "bold"), bg=BG_CARD, fg=TEXT
                 ).grid(row=0, column=3)

        self._portfolio_divider(cols, 1)

        row = 2
        for code, info in CURRENCIES.items():
            tk.Label(cols, text=f"{info['flag']} {code} — {info['name']}", anchor="w",
                     bg=BG_CARD, fg=TEXT, font=("Segoe UI", 10)
                     ).grid(row=row, column=0, sticky="w", pady=3)
            e = tk.Entry(cols, width=10, font=("Segoe UI", 10))
            e.grid(row=row, column=1, padx=4, pady=3)
            self.port_entries[("CUR", code)] = e
            self._portfolio_divider(cols, row + 1)
            row += 2

        for key, info in METALS.items():
            tk.Label(cols, text=f"▰ {info['name']} (г)", anchor="w",
                     bg=BG_CARD, fg=TEXT, font=("Segoe UI", 10)
                     ).grid(row=row, column=0, sticky="w", pady=3)
            e = tk.Entry(cols, width=10, font=("Segoe UI", 10))
            e.grid(row=row, column=1, padx=4, pady=3)
            self.port_entries[("MET", key)] = e
            self._portfolio_divider(cols, row + 1)
            row += 2

        self.port_values = {}
        self.port_deltas = {}
        for (kind, key), entry in self.port_entries.items():
            r = entry.grid_info()["row"]
            lbl = tk.Label(cols, text="—", bg=BG_CARD, fg=ORANGE,
                           font=("Segoe UI", 10, "bold"))
            lbl.grid(row=r, column=2, pady=3)
            self.port_values[(kind, key)] = lbl
            d = tk.Label(cols, text="", bg=BG_CARD, fg=TEXT_DIM,
                         font=("Segoe UI", 10))
            d.grid(row=r, column=3, pady=3)
            self.port_deltas[(kind, key)] = d

        tk.Button(inner, text="Пересчитать портфель", command=self._calc_portfolio,
                  bg=ACCENT, fg="white", relief="flat", padx=20, pady=10,
                  font=("Segoe UI", 12, "bold"), cursor="hand2", bd=0
                  ).pack(pady=12)

        # Итог — в отдельной «плашке», чтобы точно был виден
        total_box = tk.Frame(inner, bg=BG_CARD, padx=24, pady=14,
                             highlightbackground=ACCENT, highlightthickness=2)
        total_box.pack(pady=(0, 20))

        self.port_total = tk.Label(total_box, text="Итого: —",
                                   font=("Segoe UI", 22, "bold"),
                                   bg=BG_CARD, fg=GOLD)
        self.port_total.pack()
        self.port_total_delta = tk.Label(total_box, text="",
                                         font=("Segoe UI", 13, "bold"),
                                         bg=BG_CARD, fg=TEXT_DIM)
        self.port_total_delta.pack(pady=(4, 0))

    def _portfolio_divider(self, parent, row):
        sep = tk.Frame(parent, bg=BORDER, height=1)
        sep.grid(row=row, column=0, columnspan=4, sticky="ew")

    def _calc_portfolio(self):
        total = 0.0
        total_delta = 0.0
        for (kind, key), entry in self.port_entries.items():
            s = entry.get().strip().replace(",", ".")
            if not s:
                self.port_values[(kind, key)].config(text="—")
                self.port_deltas[(kind, key)].config(text="")
                continue
            try:
                qty = float(s)
            except ValueError:
                self.port_values[(kind, key)].config(text="?", fg=RED)
                continue

            if kind == "CUR":
                price = self._current_rates.get(key)
                today, prev = get_daily_change(key)
            else:
                price = self._current_metals.get(key)
                today, prev = price, None

            if price is None:
                self.port_values[(kind, key)].config(text="—", fg=TEXT_DIM)
                continue
            value = qty * price
            total += value
            self.port_values[(kind, key)].config(text=fmt_money(value, 2), fg=ORANGE)

            if today is not None and prev is not None and prev != 0:
                delta_abs = qty * (today - prev)
                total_delta += delta_abs
                pct = (today - prev) / prev * 100
                col = GREEN if delta_abs >= 0 else RED
                self.port_deltas[(kind, key)].config(text=fmt_pct(pct), fg=col)
            else:
                self.port_deltas[(kind, key)].config(text="")

        self.port_total.config(text=f"Итого: {fmt_money(total, 2)} ₽")
        if total_delta != 0 and total != 0:
            base = total - total_delta
            pct = total_delta / base * 100 if base != 0 else 0
            col = GREEN if total_delta >= 0 else RED
            sign = "+" if total_delta >= 0 else ""
            self.port_total_delta.config(
                text=f"{sign}{fmt_money(total_delta, 2)} ₽ ({fmt_pct(pct)}) за день",
                fg=col)
        else:
            self.port_total_delta.config(text="")

    # ============ ВЗАИМОИСКЛЮЧЕНИЕ / ПЕРИОД ============
    def _on_currency_selected(self, event=None):
        self.metal_var.set(self.metal_display[0])
        self.manual_code.set("")
        self._save_state()
        self.update_chart_async()

    def _on_metal_selected(self, event=None):
        if not self.metal_var.get().startswith("—"):
            self.currency_var.set(self.currency_display[0])
            self.manual_code.set("")
            self._save_state()
            self.update_chart_async()

    def _on_period_changed(self, event=None):
        if self.period_var.get() == "Всё время":
            self.compare_prev_cb.pack_forget()
            self.compare_prev_var.set(False)
        else:
            if not self.compare_prev_cb.winfo_ismapped():
                self.compare_prev_cb.pack(side="left", padx=(0, 8))
        self._save_state()
        self.update_chart_async()

    def _save_state(self):
        self.cfg["currency"] = self.currency_var.get()
        self.cfg["metal"] = self.metal_var.get()
        self.cfg["period"] = self.period_var.get()
        save_config(self.cfg)
    # ============ АСИНХРОННАЯ ЗАГРУЗКА ============
    def load_all_async(self):
        self.status_label.config(text="Загрузка...", fg=TEXT_DIM)
        threading.Thread(target=self._load_all_worker, daemon=True).start()

    def _load_all_worker(self):
        try:
            rates = get_current_rates()
            self.root.after(0, lambda: self._update_rates_ui(rates))

            metals_vals = {}
            for key in METALS:
                try:
                    metals_vals[key] = get_metal_current(key)
                except Exception as e:
                    log.warning("metal %s: %s", key, e)
                    metals_vals[key] = None

            self.root.after(0, lambda: self._update_raw_ui(metals_vals))
        except Exception as e:
            msg = human_error(e)
            log.error("load_all: %s", e)
            self.root.after(0, lambda: self.status_label.config(
                text=f"Ошибка: {msg}", fg=RED))

    def _update_rates_ui(self, rates):
        self._current_rates = rates
        for code, val in rates.items():
            if code in self.rate_labels:
                self.rate_labels[code].config(text=fmt_money(val, 4))

        threading.Thread(target=self._enrich_currency_cards, daemon=True).start()

        self._last_update_ts = datetime.now()
        self._tick_status()
        self._check_thresholds(rates)

    def _enrich_currency_cards(self):
        for code in CURRENCIES:
            try:
                dates, values = get_dynamic_rates(code, 30)
                today, prev = (values[-1], values[-2]) if len(values) >= 2 else (None, None)
                self.root.after(0, lambda c=code, vals=list(values), t=today, p=prev:
                                self._draw_spark_and_delta(c, vals, t, p))
            except Exception as e:
                log.info("enrich %s: %s", code, e)

    def _draw_spark_and_delta(self, code, values, today, prev):
        spark = self.spark_canvases.get(code)
        if spark is not None and values:
            spark.delete("all")
            w, h = 160, 28
            mn, mx = min(values), max(values)
            rng = mx - mn if mx > mn else 1
            n = len(values)
            pts = []
            for i, v in enumerate(values):
                x = i * (w - 2) / max(1, n - 1) + 1
                y = h - 2 - (v - mn) / rng * (h - 4)
                pts.append((x, y))
            color = GREEN if values[-1] >= values[0] else RED
            for i in range(len(pts) - 1):
                spark.create_line(*pts[i], *pts[i + 1], fill=color, width=1)

        if today is not None and prev is not None and prev != 0:
            pct = (today - prev) / prev * 100
            col = GREEN if pct >= 0 else RED
            arrow = "▲" if pct >= 0 else "▼"
            self.delta_labels[code].config(text=f"{arrow} {fmt_pct(pct)}", fg=col)

    def _update_raw_ui(self, metals_vals):
        self._current_metals = metals_vals
        for key, val in metals_vals.items():
            if key in self.raw_labels:
                self.raw_labels[key].config(text=fmt_money(val, 2) if val else "—")
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        self.raw_status.config(text=f"Обновлено: {now}  •  ЦБ РФ", fg=GREEN)

        threading.Thread(target=self._enrich_metal_cards, daemon=True).start()

        self.update_chart_async()

    def _enrich_metal_cards(self):
        for key in METALS:
            try:
                dates, values = get_metal_history(key, 30)
                if not values:
                    continue
                today = values[-1]
                prev = values[-2] if len(values) >= 2 else None
                self.root.after(0, lambda k=key, vals=list(values), t=today, p=prev:
                                self._draw_metal_spark_and_delta(k, vals, t, p))
            except Exception as e:
                log.info("metal enrich %s: %s", key, e)

    def _draw_metal_spark_and_delta(self, key, values, today, prev):
        spark = self.raw_sparks.get(key)
        if spark is not None and values:
            spark.delete("all")
            w, h = 160, 28
            mn, mx = min(values), max(values)
            rng = mx - mn if mx > mn else 1
            n = len(values)
            pts = []
            for i, v in enumerate(values):
                x = i * (w - 2) / max(1, n - 1) + 1
                y = h - 2 - (v - mn) / rng * (h - 4)
                pts.append((x, y))
            color = GREEN if values[-1] >= values[0] else RED
            for i in range(len(pts) - 1):
                spark.create_line(*pts[i], *pts[i + 1], fill=color, width=1)

        if today is not None and prev is not None and prev != 0:
            pct = (today - prev) / prev * 100
            col = GREEN if pct >= 0 else RED
            arrow = "▲" if pct >= 0 else "▼"
            self.raw_delta_labels[key].config(text=f"{arrow} {fmt_pct(pct)}", fg=col)
        else:
            self.raw_delta_labels[key].config(text="")

    def _tick_status(self):
        if self._last_update_ts is None:
            return
        mins = int((datetime.now() - self._last_update_ts).total_seconds() // 60)
        now = self._last_update_ts.strftime("%H:%M")
        self.status_label.config(
            text=f"Обновлено: {now}  •  {mins} мин назад  •  ЦБ РФ", fg=GREEN)
        self.root.after(30_000, self._tick_status)

    def _auto_refresh(self):
        self.load_all_async()
        self.root.after(self.AUTO_REFRESH_MS, self._auto_refresh)

    # ============ ГРАФИК ============
    def update_chart_async(self):
        self._chart_request_id += 1
        rid = self._chart_request_id
        self.ax.clear()
        self.ax.set_facecolor(BG_CARD)
        self.ax.text(0.5, 0.5, "Загрузка…", ha="center", va="center",
                     transform=self.ax.transAxes, color=TEXT_DIM, fontsize=13)
        self.canvas.draw()
        threading.Thread(target=self._update_chart_worker, args=(rid,),
                         daemon=True).start()

    def _update_chart_worker(self, rid):
        try:
            days = PERIODS[self.period_var.get()]
            metal_label = self.metal_var.get()
            compare_prev = self.compare_prev_var.get()

            series = []
            ylabel = "Руб."

            if metal_label and not metal_label.startswith("—"):
                metal_key = next(
                    (k for k, i in METALS.items() if i["name"] == metal_label), None)
                if not metal_key:
                    raise Exception("Металл не найден")
                dates, values = get_metal_history(metal_key, days)
                series.append((METALS[metal_key]["name"], dates, values, ACCENT))
                ylabel = "Руб./грамм"

                if compare_prev:
                    prev_dates, prev_values = get_metal_history(metal_key, days * 2)
                    split = len(prev_values) // 2
                    prev_dates = prev_dates[:split]
                    prev_values = prev_values[:split]
                    if prev_values and dates:
                        shift = dates[0] - prev_dates[0]
                        shifted = [d + shift for d in prev_dates]
                        series.append((f"{METALS[metal_key]['name']} (прошлый)",
                                       shifted, prev_values, TEXT_DIM))
            else:
                manual = self.manual_code.get().strip().upper()
                if manual:
                    code = manual
                else:
                    selected = self.currency_var.get()
                    if selected.startswith("—"):
                        raise Exception("Выберите валюту или металл")
                    code = selected.split()[1] if len(selected.split()) > 1 else "USD"
                dates, values = get_dynamic_rates(code, days)
                series.append((code, dates, values, ACCENT))

                if compare_prev:
                    prev_dates, prev_values = get_dynamic_rates(code, days * 2)
                    split = len(prev_values) // 2
                    prev_dates = prev_dates[:split]
                    prev_values = prev_values[:split]
                    if prev_values and dates:
                        shift = dates[0] - prev_dates[0]
                        shifted = [d + shift for d in prev_dates]
                        series.append((f"{code} (прошлый)",
                                       shifted, prev_values, TEXT_DIM))

            if rid != self._chart_request_id:
                return  # устаревший запрос

            if series:
                self._last_chart_data = (series[0][1], series[0][2], series[0][0])
            else:
                self._last_chart_data = ([], [], "")

            self.root.after(0, lambda: self._draw_chart(series, ylabel, days))
        except Exception as e:
            log.error("chart: %s", e)
            msg = human_error(e)
            self.root.after(0, lambda: self._draw_error(msg))

    def _draw_chart(self, series, ylabel, days=30):
        self.ax.clear()
        self.ax.set_facecolor(BG_CARD)

        if not series or not series[0][1]:
            self.ax.text(0.5, 0.5, "Нет данных за выбранный период",
                         ha="center", va="center",
                         transform=self.ax.transAxes, color=TEXT_DIM, fontsize=12)
            self.canvas.draw()
            return

        for label, dates, values, color in series:
            style = "--" if "прошлый" in label else "-"
            self.ax.plot(dates, values, color=color, linewidth=2.2,
                         linestyle=style, label=label,
                         marker="o", markersize=3 if len(dates) < 60 else 0)

        if len(series) > 1:
            self.ax.legend(loc="best", facecolor=BG_CARD, edgecolor=BORDER,
                           labelcolor=TEXT, fontsize=9)

        self.ax.set_ylabel(ylabel, fontsize=12, color=TEXT)
        self.ax.tick_params(axis="x", colors=TEXT_DIM, labelsize=10)
        self.ax.tick_params(axis="y", colors=TEXT_DIM, labelsize=10)
        self.ax.grid(True, which="major", linestyle="--",
                     linewidth=1.4, alpha=0.6, color=GRID_MAJOR)
        self.ax.minorticks_on()
        self.ax.grid(True, which="minor", linestyle=":",
                     linewidth=1.0, alpha=0.35, color=GRID_MINOR)

        if days <= 31:
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
        elif days <= 365:
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        else:
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

        for spine in ["top", "right"]:
            self.ax.spines[spine].set_visible(False)
        for spine in ["left", "bottom"]:
            self.ax.spines[spine].set_color(BORDER)

        self.fig.autofmt_xdate(rotation=30)
        self.fig.tight_layout()
        self.canvas.draw()

    def _draw_error(self, msg):
        self.ax.clear()
        self.ax.set_facecolor(BG_CARD)
        self.ax.text(0.5, 0.5, f"Ошибка: {msg}", ha="center", va="center",
                     transform=self.ax.transAxes, color=ACCENT, fontsize=11)
        self.canvas.draw()


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()