"""
ЗОНА РИСКА — ядро: настройки, сохранения, синтез звука, рекорды.
Всё хранится в JSON рядом с игрой (или в папке пользователя, если игра — .exe/.app).
"""
import os
import sys
import json
import math
import array
import random

import pygame

# ----------------------------------------------------------------------------
# Пути к данным (работает и в обычном запуске, и внутри PyInstaller-сборки)
# ----------------------------------------------------------------------------
def data_dir():
    """Папка для сохранений: рядом с .exe/.app, либо рядом со скриптом."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    # на macOS .app внутренности read-only — пишем в домашнюю папку
    try:
        test = os.path.join(base, ".write_test")
        with open(test, "w") as f:
            f.write("x")
        os.remove(test)
        return base
    except Exception:
        home = os.path.join(os.path.expanduser("~"), ".zona_riska")
        os.makedirs(home, exist_ok=True)
        return home


SAVE_PATH = os.path.join(data_dir(), "zona_riska_save.json")

DEFAULT_KEYS = {
    "up": "w", "down": "s", "left": "a", "right": "d",
    "fire": "mouse_left", "mine": "mouse_middle", "torpedo": "mouse_right",
    "dock": "e", "boost": "left shift",
}

# раскладка геймпада (номера кнопок XInput). Стик/крестовина — движение.
DEFAULT_PAD = {
    "fire": 0,      # A
    "mine": 1,      # B
    "torpedo": 2,   # X
    "dock": 3,      # Y
    "boost": 5,     # RB
}

DEFAULT_SETTINGS = {
    "keys": dict(DEFAULT_KEYS),
    "pad": dict(DEFAULT_PAD),
    "input_mode": "keyboard",   # keyboard / gamepad
    "difficulty": "normal",   # easy / normal / hard
    "boost_default": False,    # форсаж включён по умолчанию (тоггл)
    "sound": True,
    "volume": 0.6,
    "music_vol": 0.55,
    "highscores": [],          # список {name, score, sector}
}


def load_settings():
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        s = dict(DEFAULT_SETTINGS)
        s.update(data)
        merged = dict(DEFAULT_KEYS)
        merged.update(s.get("keys", {}))
        s["keys"] = merged
        mpad = dict(DEFAULT_PAD)
        mpad.update(s.get("pad", {}))
        s["pad"] = mpad
        return s
    except Exception:
        return json.loads(json.dumps(DEFAULT_SETTINGS))


def save_settings(s):
    try:
        with open(SAVE_PATH, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Не удалось сохранить настройки:", e)


# ── Supabase ──────────────────────────────────────────────────────────────────
SUPABASE_URL = "https://dlkiyyptfmwiggpwbyfp.supabase.co"
SUPABASE_KEY = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
                "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRsa2l5eXB0Zm13aWdncHdieWZwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODMxNTY2MTgsImV4cCI6MjA5ODczMjYxOH0."
                "zdQlYU4n5warclVj8kS3hfO0mmEtaVgJa9z8RBZkAPo")
_HEADERS = {"apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"}


def supabase_get_scores():
    """Получить топ-20 с Supabase. Возвращает список или [] при ошибке."""
    try:
        import urllib.request, json, ssl
        url = (SUPABASE_URL +
               "/rest/v1/highscores?select=name,score,sector"
               "&order=score.desc&limit=20")
        req = urllib.request.Request(url, headers=_HEADERS)
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=3, context=ctx) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print("Supabase GET error:", e)
        return []


def supabase_post_score(name, score, sector):
    """Отправить рекорд на Supabase. Тихо игнорирует ошибки."""
    try:
        import urllib.request, json, ssl
        url = SUPABASE_URL + "/rest/v1/highscores"
        data = json.dumps({"name": name, "score": int(score),
                           "sector": int(sector)}).encode()
        req = urllib.request.Request(url, data=data,
                                     headers=_HEADERS, method="POST")
        ctx = ssl.create_default_context()
        urllib.request.urlopen(req, timeout=3, context=ctx).close()
    except Exception as e:
        print("Supabase POST error:", e)


def fetch_online_scores(settings):
    """Загрузить онлайн-рекорды и смержить с локальными."""
    online = supabase_get_scores()
    if not online:
        return
    combined = list(settings.get("highscores", []))
    existing = {(r["name"], r["score"]) for r in combined}
    for r in online:
        key = (r.get("name", ""), r.get("score", 0))
        if key not in existing:
            combined.append({"name": r.get("name", "?"),
                             "score": r.get("score", 0),
                             "sector": r.get("sector", 0)})
    combined.sort(key=lambda r: r["score"], reverse=True)
    settings["highscores"] = combined[:20]
    save_settings(settings)
# ──────────────────────────────────────────────────────────────────────────────


def add_highscore(settings, name, score, sector):
    hs = settings.get("highscores", [])
    hs.append({"name": name[:12] if name else "PILOT", "score": int(score), "sector": int(sector)})
    hs.sort(key=lambda r: r["score"], reverse=True)
    settings["highscores"] = hs[:20]
    save_settings(settings)
    # отправляем на Supabase в фоновом потоке — игра не зависает
    import threading
    threading.Thread(target=supabase_post_score,
                     args=(name[:12] if name else "PILOT", score, sector),
                     daemon=True).start()


def is_highscore(settings, score):
    hs = settings.get("highscores", [])
    if len(hs) < 10:
        return True
    return score > min(r["score"] for r in hs)


# ----------------------------------------------------------------------------
# Синтез ретро-звуков (Dendy/NES и Sega Mega Drive стайл).
# ----------------------------------------------------------------------------
class SoundFX:
    RATE = 44100

    def __init__(self, enabled=True, volume=0.6, mus_vol=0.55):
        self.enabled = enabled
        self.volume = volume
        self.mus_vol = mus_vol
        self.cache = {}
        self.ok = False
        try:
            if pygame.mixer.get_init() is None:
                # предынициализация с большим буфером для стабильности
                pygame.mixer.pre_init(frequency=self.RATE, size=-16, channels=2, buffer=1024)
                pygame.mixer.init()
            # много каналов — с запасом, чтобы ни один звук не потерялся
            pygame.mixer.set_num_channels(64)
            self.ok = True
        except Exception as e:
            print("Аудио недоступно:", e)
            self.ok = False
        if self.ok:
            self._build()

    def _tone(self, freq, ms, vol=0.5, wave="square", sweep=0.0, noise=0.0, decay=True, duty=0.5, fm_mod=0.0, fm_mult=1.0):
        n = int(self.RATE * ms / 1000.0)
        buf = array.array("h")
        amp = int(32767 * vol)
        for i in range(n):
            t = i / self.RATE
            f = freq + sweep * (i / max(1, n))
            
            # --- Генерация формы волны ---
            if wave == "pulse" or wave == "square":
                # Dendy/NES: пульсовая волна с разной скважностью (duty cycle)
                phase = (f * t) % 1.0
                v = 1.0 if phase < duty else -1.0
            elif wave == "fm":
                # Sega: простейший FM-синтез (частотная модуляция)
                # fm_mult - частота модулятора, fm_mod - сила искажения
                modulator = math.sin(2 * math.pi * (f * fm_mult) * t)
                v = math.sin(2 * math.pi * f * t + fm_mod * modulator)
            elif wave == "saw":
                v = 2.0 * ((f * t) % 1.0) - 1.0
            elif wave == "tri":
                v = 2.0 * abs(2.0 * ((f * t) % 1.0) - 1.0) - 1.0
            else: # sine
                v = math.sin(2 * math.pi * f * t)
                
            # Подмешиваем шум
            if noise > 0:
                v = v * (1.0 - noise) + (random.random() * 2 - 1) * noise
                
            # Огибающая (затухание)
            env = 1.0
            if decay:
                env = 1.0 - (i / n)
                
            s = int(amp * v * env)
            s = max(-32767, min(32767, s))
            buf.append(s)
            buf.append(s)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def _build(self):
        try:
            # 1. Выстрел игрока: короткий "клик" + "пуш"
            self.cache["shoot"] = self._tone(880, 50, 0.15, "pulse", sweep=-400, duty=0.25)
            
            # 2. Звук камикадзе: НАРАСТАЮЩИЙ ГУЛ
            self.cache["kamikaze_charge"] = self._tone(150, 1000, 0.4, "saw", sweep=2000, decay=False)
            
            # 3. Взрыв: мощный "бабах" с шумом
            self.cache["explo"] = self._tone(100, 400, 0.5, "saw", noise=0.9, sweep=-80)
            
            # 4. Лазер босса (SEGA FM-style)
            self.cache["laser"] = self._tone(220, 200, 0.25, "fm", fm_mod=5.0, fm_mult=1.5)
            self.cache["beam"]  = self._tone(220, 500, 0.35, "fm", sweep=-50, fm_mod=4.0, fm_mult=0.5)
            
            # 5. Босс (угрожающий бас)
            self.cache["boss"]  = self._tone(60, 800, 0.4, "fm", fm_mod=8.0, fm_mult=0.5, noise=0.2)
            
            # Дополнительные звуки
            self.cache["hit"]   = self._tone(160, 100, 0.2, "pulse", noise=0.3, duty=0.1)
            self.cache["torp"]  = self._tone(300, 200, 0.25, "saw", sweep=-150)
            self.cache["mine"]  = self._tone(120, 160, 0.3, "tri", sweep=-60, noise=0.2)
            self.cache["dock"]  = self._tone(330, 300, 0.2, "tri", sweep=100)
            # звук печатной машинки для интро (короткий высокий бип)
            self.cache["type"]  = self._tone(1200, 20, 0.08, "pulse", duty=0.5)
            self.cache["type2"] = self._tone(900, 25, 0.06, "pulse", duty=0.3)  # вариация
            self.cache["menu"]  = self._tone(660, 60, 0.15, "pulse", duty=0.5)
            self.cache["bonus"] = self._tone(440, 180, 0.2, "pulse", sweep=500, duty=0.125)

            # --- внешние звуковые файлы (перекрывают синтез, если найдены) ---
            self._load_file("shoot", "sfx_laser.wav")          # выстрел лазера игрока
            self._load_file("rock_explo", "sfx_asteroid.mp3")  # взрыв астероида
            self._load_file("ship_explo", "sfx_explosion.mp3") # взрыв корабля
            self._load_file("enemy_laser", "sfx_enemy_laser.mp3")  # лазер противника
            self._load_file("rocket", "sfx_rocket.mp3")            # запуск ракеты
            self._load_file("arc", "sfx_arc.mp3")                  # электро-дуга
            # если файлов лазера/дуги нет — синтетический запасной
            if "enemy_laser" not in self.cache:
                self.cache["enemy_laser"] = self._tone(180, 160, 0.22, "fm", fm_mod=6.0, fm_mult=1.8, sweep=80)
            # звук попадания — короткий сухой «тук»
            self.cache["hit"] = self._tone(160, 70, 0.22, "tri", sweep=-60, noise=0.6)
            self.cache["hit_player"] = self._tone(90, 130, 0.32, "square", sweep=-40, noise=0.7)
            # взрыв босса — тот же файл
            self._load_file("boss_explo", "sfx_explosion.mp3")
        except Exception as e:
            print("Ошибка синтеза звука:", e)
            self.ok = False

    def _load_file(self, name, filename):
        """Загружает звук из assets/. Тихо игнорирует отсутствие."""
        import os
        import sys as _sys
        base = getattr(_sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, "assets", filename)
        if not os.path.exists(path):
            return
        try:
            self.cache[name] = pygame.mixer.Sound(path)
        except Exception as e:
            print(f"Не удалось загрузить {filename}:", e)

    def play(self, name):
        if not (self.ok and self.enabled):
            return
        s = self.cache.get(name)
        if s is None and name in ("ship_explo", "rock_explo", "boss_explo"):
            s = self.cache.get("explo")   # запасной синтезированный взрыв
        if not s:
            return
        # КАЖДЫЙ звук форсированно берёт канал (find_channel(True) вытесняет
        # самый старый при переполнении) — так ни один звук не теряется молча
        try:
            ch = pygame.mixer.find_channel(True)
            if ch is not None:
                ch.set_volume(self.volume)
                ch.play(s)
                return
        except Exception:
            pass
        # запасной путь
        try:
            s.set_volume(self.volume)
            s.play()
        except Exception:
            pass

    def play_loud(self, name, vol_mult=1.5):
        """Громкий звук (для взрыва босса) — максимальная громкость + эхо через 120мс."""
        if not (self.ok and self.enabled):
            return
    def play_loud(self, name, vol_mult=1.5):
        """Громкий звук (взрыв босса) — форсированный канал + эхо."""
        if not (self.ok and self.enabled):
            return
        s = self.cache.get(name)
        if s is None:
            s = self.cache.get("explo")
        if not s:
            return
        vol = min(1.0, self.volume * vol_mult)
        try:
            ch = pygame.mixer.find_channel(True)
            if ch is not None:
                ch.set_volume(vol); ch.play(s)
            else:
                s.set_volume(vol); s.play()
            import threading, time
            def _echo():
                time.sleep(0.12)
                try:
                    c2 = pygame.mixer.find_channel(True)
                    if c2 is not None:
                        c2.set_volume(vol * 0.6); c2.play(s)
                except: pass
            threading.Thread(target=_echo, daemon=True).start()
        except Exception:
            pass

    def set_volume(self, v):
        self.volume = max(0.0, min(1.0, v))

    def set_enabled(self, b):
        self.enabled = b
        # при выключении звука — глушим и музыку
        if not b:
            self.stop_music()

    # ---- фоновая музыка ----
    def __init_music_vol(self):
        pass

    def play_music(self, path, loop=True):
        """Запускает фоновую музыку (mp3/ogg). Тихо игнорирует ошибки."""
        if not self.ok:
            return
        import os
        if not os.path.exists(path):
            return
        try:
            self._music_path = path
            pygame.mixer.music.load(path)
            mv = getattr(self, "mus_vol", 0.55)
            pygame.mixer.music.set_volume(mv if self.enabled else 0.0)
            pygame.mixer.music.play(-1 if loop else 0)
        except Exception as e:
            print("Музыка недоступна:", e)

    def stop_music(self):
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass

    def music_volume(self, v):
        self.mus_vol = max(0.0, min(1.0, v))
        try:
            pygame.mixer.music.set_volume(self.mus_vol if self.enabled else 0.0)
        except Exception:
            pass


# Множитель здоровья врагов от сложности
DIFF_MULT = {"easy": 0.8, "normal": 1.0, "hard": 1.5}
DIFF_NAME = {"easy": "ЛЁГКИЙ", "normal": "НОРМАЛЬНЫЙ", "hard": "СЛОЖНЫЙ"}
# множитель КОЛИЧЕСТВА врагов (интенсивность потока), отдельно от HP
INTENSITY_MULT = {"easy": 0.235, "normal": 0.35, "hard": 0.4375}