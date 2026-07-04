"""
ЗОНА РИСКА — главный файл.
Запуск:  python main.py
Сборка в exe/.app — см. README.md
"""
import os
import sys
import math
import random

import pygame

from core import (load_settings, save_settings, add_highscore, is_highscore,
                  SoundFX, DIFF_MULT, DIFF_NAME, INTENSITY_MULT, DEFAULT_KEYS, DEFAULT_PAD,
                  fetch_online_scores)
from entities import (Player, make_enemy, draw_enemy, make_boss, draw_boss, gun_pos,
                      part_pos, fighter_icon, ENEMY_NAME, ENEMY_STATS, BOSS_NAMES, BOSS_HP,
                      enemy_reward, boss_atks,
                      WHITE, SHIP_FILL, SHIP_LINE, NACELLE, GLOW_BLUE, GOLD, AMBER, RED, GREEN,
                      SHIELD_C, ENEMY_COL)

W, H = 720, 560


# ---- SPRITE LOADER ----
def _resource_path(rel):
    """Путь к ресурсу — учитывает PyInstaller onefile."""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


SPRITE_CACHE = {}


def load_sprite(name, target_size=None):
    """Загружает PNG из assets/ с масштабированием. Возвращает None, если файл не найден."""
    key = (name, target_size)
    if key in SPRITE_CACHE:
        return SPRITE_CACHE[key]
    path = _resource_path(os.path.join("assets", name))
    if not os.path.exists(path):
        SPRITE_CACHE[key] = None
        return None
    try:
        img = pygame.image.load(path).convert_alpha()
    except Exception:
        SPRITE_CACHE[key] = None
        return None
    if target_size:
        # target_size = (w, h) — пропорциональное масштабирование
        tw, th = target_size
        iw, ih = img.get_size()
        scale = min(tw / iw, th / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        img = pygame.transform.smoothscale(img, (nw, nh))
    SPRITE_CACHE[key] = img
    return img
FPS = 60
TOTAL_SECTORS = 25  # игра выигрывается после 25-го сектора

# Список спрайтов астероидов. Когда придут новые PNG — добавить сюда:
# ASTEROID_SPRITES = ["asteroid.png", "asteroid2.png", "asteroid3.png"]
ASTEROID_SPRITES = ["asteroid.png"]

pygame.init()
try:
    pygame.joystick.init()
except Exception:
    pass

flags = pygame.RESIZABLE
# иконка окна (до set_mode) — берём из assets/icon.png, масштабируем до 32x32
try:
    _icon_path = _resource_path(os.path.join("assets", "icon.png"))
    if os.path.exists(_icon_path):
        _icon_img = pygame.image.load(_icon_path)
        # Windows отрисовывает иконку заголовка в 32x32; даём точный размер для чёткости
        _icon_img = pygame.transform.smoothscale(_icon_img, (32, 32))
        pygame.display.set_icon(_icon_img)
except Exception:
    pass
win = pygame.display.set_mode((W, H), flags)
pygame.display.set_caption("ЗОНА РИСКА")
canvas = pygame.Surface((W, H))   # фиксированный холст игры, масштабируется в окно
screen = canvas                    # все функции рисуют в canvas
_scale = {"k": 1.0, "ox": 0, "oy": 0}
_fullscreen = {"on": False}


def present():
    """Масштабирует холст в окно с сохранением пропорций (леттербокс)."""
    ww, wh = win.get_size()
    k = min(ww / W, wh / H)
    sw, sh = int(W * k), int(H * k)
    ox, oy = (ww - sw) // 2, (wh - sh) // 2
    _scale["k"], _scale["ox"], _scale["oy"] = k, ox, oy
    win.fill((0, 0, 0))
    if k == 1.0 and ox == 0 and oy == 0:
        win.blit(canvas, (0, 0))
    else:
        win.blit(pygame.transform.smoothscale(canvas, (sw, sh)), (ox, oy))
    pygame.display.flip()


def to_canvas(pos):
    """Координаты мыши окна -> координаты холста."""
    k = _scale["k"] or 1.0
    return ((pos[0] - _scale["ox"]) / k, (pos[1] - _scale["oy"]) / k)


def toggle_fullscreen():
    _fullscreen["on"] = not _fullscreen["on"]
    global win
    if _fullscreen["on"]:
        win = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    else:
        win = pygame.display.set_mode((W, H), pygame.RESIZABLE)
pygame.display.set_caption("ЗОНА РИСКА")
clock = pygame.time.Clock()

F_S = pygame.font.SysFont("consolas,menlo,monospace", 15)
F_M = pygame.font.SysFont("consolas,menlo,monospace", 20)
F_L = pygame.font.SysFont("consolas,menlo,monospace", 40, bold=True)
F_XL = pygame.font.SysFont("consolas,menlo,monospace", 56, bold=True)


def txt(s, text, font, col, x, y, center=False, right=False):
    img = font.render(text, True, col)
    r = img.get_rect()
    if center:
        r.center = (x, y)
    elif right:
        r.topright = (x, y)
    else:
        r.topleft = (x, y)
    s.blit(img, r)
    return r


# Имена клавиш для отображения
def key_label(name):
    m = {"space": "ПРОБЕЛ", "left shift": "L-SHIFT", "right shift": "R-SHIFT",
         "mouse_left": "ЛКМ", "mouse_middle": "СКМ", "mouse_right": "ПКМ",
         "return": "ENTER", "left": "←", "right": "→", "up": "↑", "down": "↓"}
    return m.get(name, name.upper())


class Game:
    def __init__(self, settings, sfx):
        self.cfg = settings
        self.sfx = sfx
        self.reset_state()

    # ---------------- состояние ----------------
    def reset_state(self):
        self.P = Player(W, H)
        self.bul = []; self.foe = []; self.fb = []; self.pt = []
        self.gld = []; self.rk = []; self.deb = []; self.rings = []; self.arcs = []
        self.beams = []; self.mines = []; self.bonuses = []; self.flashes = []
        self.boss = None; self.sta = None; self.cr = 50; self.score = 0
        self.wave = 1; self.wT = 0; self.wA = False; self.spawnQ = []
        self.shk = 0; self.bonT = 12; self.rkT = 1.2; self.dbT = 3
        self._hit_snd_cd = 0
        self.warp = 90; self.won = False
        self.boost_on = self.cfg.get("boost_default", False)

    @property
    def diff_mult(self):
        return DIFF_MULT.get(self.cfg.get("difficulty", "normal"), 1.0)

    def start_wave(self):
        if self.wave % 5 == 0 and self.wave <= TOTAL_SECTORS:
            self.boss = make_boss(W, self.wave, self.diff_mult)
            self.sfx.play("boss")
            self.wA = True
            return
        self.wA = True
        # интенсивность зависит от сложности: normal ×0.5, easy ×0.375 от прежнего
        intensity = INTENSITY_MULT.get(self.cfg.get("difficulty", "normal"), 0.5)
        base_n = 20 + int(self.wave * 7)
        n = max(3, int(base_n * intensity))
        # интервал спавна тоже растёт при меньшей интенсивности — реже наплыв
        gap = 0.8 / max(0.5, intensity)
        for i in range(n):
            self.spawnQ.append(i * gap)

    # ---------------- ввод ----------------
    def read_input(self, keys, mouse_buttons, pad):
        kc = self.cfg["keys"]

        def down(action):
            kname = kc.get(action, DEFAULT_KEYS[action])
            if kname.startswith("mouse_"):
                idx = {"mouse_left": 0, "mouse_middle": 1, "mouse_right": 2}[kname]
                return mouse_buttons[idx]
            try:
                code = pygame.key.key_code(kname)
                return keys[code]
            except Exception:
                return False

        up = down("up"); dn = down("down"); lf = down("left"); rt = down("right")
        fr = down("fire"); bo = down("boost")
        # геймпад
        if pad:
            ax_x = pad.get_axis(0) if pad.get_numaxes() > 0 else 0
            ax_y = pad.get_axis(1) if pad.get_numaxes() > 1 else 0
            if ax_x < -0.3: lf = True
            if ax_x > 0.3: rt = True
            if ax_y < -0.3: up = True
            if ax_y > 0.3: dn = True
            if pad.get_numbuttons() > 0 and pad.get_button(0): fr = True  # A
            if pad.get_numbuttons() > 5 and pad.get_button(5): bo = True  # RB
            try:
                hx, hy = pad.get_hat(0) if pad.get_numhats() > 0 else (0, 0)
                if hx < 0: lf = True
                if hx > 0: rt = True
                if hy > 0: up = True
                if hy < 0: dn = True
            except Exception:
                pass
        if self.boost_on:
            bo = True
        return up, dn, lf, rt, fr, bo

    # ---------------- логика ----------------
    def update(self, dt, keys, mouse_buttons, pad):
        if self.shk > 0:
            self.shk -= dt
        P = self.P
        P.inv = max(0, P.inv - dt)
        P.mine_cd = max(0, P.mine_cd - dt)
        P.torp_cd = max(0, P.torp_cd - dt)
        P.flash = max(0, P.flash - dt)
        self._hit_snd_cd = max(0, self._hit_snd_cd - dt)
        up, dn, lf, rt, fr, bo = self.read_input(keys, mouse_buttons, pad)

        dx = dy = 0
        if lf: dx -= 1
        if rt: dx += 1
        if up: dy -= 1
        if dn: dy += 1
        if dx and dy:
            dx *= 0.707; dy *= 0.707
        sp = P.speed * (1 + P.upg["speed"] * 0.18) * (1.35 if bo else 1)
        P.vx += (dx * sp - P.vx) * 10 * dt
        P.vy += (dy * sp - P.vy) * 10 * dt
        P.x = max(P.size, min(W - P.size, P.x + P.vx * dt))
        P.y = max(44, min(H - 22, P.y + P.vy * dt))
        self.warp = 90 + (80 if up else 0) + (260 if bo else 0)

        tick_stars(dt, self.warp)

        P.cool -= dt
        rate = P.rate * (1 - P.upg["gun"] * 0.06)
        if fr and P.cool <= 0:
            P.cool = rate
            self.player_fire()

        # щит НЕ восстанавливается сам — только через синие капсулы

        for i in range(len(self.spawnQ)):
            self.spawnQ[i] -= dt
        newq = []
        for tt in self.spawnQ:
            if tt <= 0:
                self.foe.append(self._spawn_limited())
            else:
                newq.append(tt)
        self.spawnQ = newq

        fl = max(0.4, self.warp / 180)
        if not self.boss:
            self.rkT -= dt * fl
            if self.rkT <= 0:
                self.rkT = random.uniform(1, 2.4); self.spawn_rock(random.random() < 0.5)
            self.dbT -= dt * fl
            if self.dbT <= 0:
                self.dbT = random.uniform(2.5, 5); self.spawn_debris()
        # бонусы L (реже)
        self.bonT -= dt
        if self.bonT <= 0:
            self.bonT = random.uniform(23, 40)   # реже на ~30%
            self.bonuses.append({"x": random.uniform(50, W - 50), "y": -30, "vy": random.uniform(40, 75), "kind": "life"})
        for b in self.bonuses:
            b["y"] += b["vy"] * dt
        kept = []
        for b in self.bonuses:
            if dist(b["x"], b["y"], P.x, P.y) < 22:
                if b.get("kind") == "shield":
                    if P.max_shield > 0:
                        P.shield = min(P.max_shield, P.shield + 1)
                        self.sfx.play("bonus"); self.burst(b["x"], b["y"], SHIELD_C, 10)
                        P.flash = 0.5; P.flash_col = (60, 160, 255)   # синяя вспышка
                    else:
                        kept.append(b); continue
                else:
                    P.lives = min(P.max_lives, P.lives + 1)
                    self.sfx.play("bonus"); self.burst(b["x"], b["y"], GREEN, 10)
                    P.flash = 0.5; P.flash_col = (80, 255, 120)       # зелёная вспышка
            elif b["y"] < H + 30:
                kept.append(b)
        self.bonuses = kept

        had = bool(self.foe) or self.boss   # ВАЖНО: считаем ДО удаления убитых врагов
        self.update_projectiles(dt)
        self.update_enemies(dt)
        if self.boss:
            self.update_boss(dt)
        self.update_hazards(dt)
        self.collisions(dt)
        self.cleanup(dt)

        # станция
        if self.sta:
            self.sta["y"] += self.warp * 0.45 * dt
            if self.sta["y"] > H + 110:
                self.sta = None
        near = self.sta and dist(P.x, P.y, self.sta["x"], self.sta["y"]) < self.sta["r"] * 2.1 + P.size
        P.near = self.sta if near else None

        if self.wA and not self.foe and not self.spawnQ and not self.boss and had:
            self.wA = False; self.wT = 4
        if not self.wA and not self.foe and not self.spawnQ and not self.boss:
            self.wT -= dt
            if self.wT <= 0:
                if self.wave >= TOTAL_SECTORS:
                    self.won = True
                    return "won"
                self.wave += 1
                self.start_wave()
        return None

    def player_fire(self):
        P = self.P
        self.sfx.play("shoot")
        self.bul.append({"x": P.x - 11, "y": P.y - 6, "vy": -580, "dm": 12 + P.upg["gun"] * 8, "sz": 3, "c": (159, 225, 203)})
        self.bul.append({"x": P.x + 11, "y": P.y - 6, "vy": -580, "dm": 12 + P.upg["gun"] * 8, "sz": 3, "c": (159, 225, 203)})
        if P.upg["gun"] >= 2:
            self.bul.append({"x": P.x, "y": P.y - 14, "vy": -620, "dm": 8 + P.upg["gun"] * 5, "sz": 3, "c": (133, 183, 235)})

    def fire_torpedo(self):
        """Отдельная стрельба торпедой — правая кнопка мыши."""
        P = self.P
        if P.torp <= 0 or P.torp_cd > 0:
            return
        P.torp -= 1
        P.torp_cd = 0.4    # кулдаун между торпедами
        self.sfx.play("rocket")
        self.bul.append({"x": P.x, "y": P.y - 16, "vy": -500, "dm": 50, "sz": 7, "c": GOLD, "tor": True})

    def drop_mine(self):
        P = self.P
        if P.mines <= 0 or P.mine_cd > 0:
            return
        P.mines -= 1; P.mine_cd = 1; self.sfx.play("mine")
        self.mines.append({"x": P.x, "y": P.y, "r": 20, "armed": 0.8, "t": 0, "dm": 160})

    def e_laser(self, x, y, ang, col, spd=340):
        self.fb.append({"k": "l", "x": x, "y": y, "vx": math.cos(ang) * spd, "vy": math.sin(ang) * spd, "sz": 4, "c": col, "ln": 18})

    def e_missile(self, x, y):
        a = math.atan2(self.P.y - y, self.P.x - x)
        self.fb.append({"k": "m", "x": x, "y": y, "ah": a, "sp": 130, "sz": 6, "tn": 1.2,
                        "tt": 0, "lf": 0, "fuel": 4.5,
                        "vx": math.cos(a) * 130, "vy": math.sin(a) * 130})
        self.sfx.play("rocket")

    def _spawn_limited(self):
        """Спавн врага с ограничениями по количеству на экране:
        GUNNER (клин 3 лазера) — не более 2, WARDEN — не более 2, SCATTERER (веер) — не более 1."""
        e = make_enemy(W, H, self.wave, self.diff_mult)
        for _ in range(5):   # до 5 попыток переролла
            ty = e["type"]
            if ty == 1:  # GUNNER
                cnt = sum(1 for f in self.foe if f["type"] == 1)
                if cnt >= 2:
                    e = make_enemy(W, H, self.wave, self.diff_mult, force_type=0); continue
            if ty == 4:  # WARDEN
                cnt = sum(1 for f in self.foe if f["type"] == 4)
                if cnt >= 2:
                    e = make_enemy(W, H, self.wave, self.diff_mult, force_type=0); continue
            if ty == 9:  # SCATTERER
                cnt = sum(1 for f in self.foe if f["type"] == 9)
                if cnt >= 1:
                    e = make_enemy(W, H, self.wave, self.diff_mult, force_type=0); continue
            break
        return e

    def spawn_rock(self, big):
        s = random.uniform(20, 30) if big else random.uniform(9, 16)
        v = [random.uniform(0.7, 1.15) for _ in range(8)]
        craters = [(random.uniform(-0.5, 0.5), random.uniform(-0.5, 0.5), random.uniform(0.12, 0.26))
                   for _ in range(random.randint(2, 4))]
        holds = big and self.wave >= 3 and random.random() < 0.4
        sprites = ASTEROID_SPRITES
        sprite = random.choice(sprites)
        # случайная орбита
        angle = random.choice([
            random.uniform(-0.12, 0.12),         # прямо вниз
            random.uniform(0.3, 0.65),            # вправо-вниз
            random.uniform(-0.65, -0.3),          # влево-вниз
            random.uniform(0.7, 1.1),             # сильно вбок
            random.uniform(-1.1, -0.7),
        ])
        speed = random.uniform(55, 120) if big else random.uniform(65, 140)
        self.rk.append({"x": random.uniform(30, W - 30), "y": -40,
                        "vy": math.cos(angle) * speed,
                        "vx": math.sin(angle) * speed,
                        "sz": s, "vt": v, "a": random.uniform(0, 6.28),
                        "sp": random.uniform(-2, 2), "hp": 38 if big else 16,
                        "craters": craters, "holds": holds, "sprite": sprite})

    def spawn_debris(self):
        # kind: 1 спутник, 2 станция, 3 обломок корабля, 4 большой обломок
        roll = random.random()
        if roll < 0.12:
            kind = 4
        elif roll < 0.32:
            kind = 3
        elif roll < 0.62:
            kind = 1
        else:
            kind = 2
        # не спавним если такой kind уже есть на экране
        if any(d.get("kind") == kind for d in self.deb):
            return
        big = kind in (3, 4)
        sz = random.uniform(24, 34) if big else random.uniform(16, 22)
        hp = (60 if kind == 4 else 40) if big else 20
        # случайная орбита: прямо, боком, под углом
        angle = random.choice([
            random.uniform(-0.15, 0.15),        # почти прямо вниз
            random.uniform(0.35, 0.7),           # под углом вправо
            random.uniform(-0.7, -0.35),         # под углом влево
            random.uniform(0.8, 1.2),            # сильно вбок вправо
            random.uniform(-1.2, -0.8),          # сильно вбок влево
        ])
        speed = random.uniform(28, 58) if big else random.uniform(32, 70)
        self.deb.append({"x": random.uniform(50, W - 50), "y": -60,
                         "vy": math.cos(angle) * speed,
                         "vx": math.sin(angle) * speed,
                         "a": random.uniform(0, 6.28),
                         "sp": random.uniform(-1.1, 1.1),
                         "hp": hp, "mhp": hp, "sz": sz, "kind": kind})

    def update_projectiles(self, dt):
        for b in self.bul:
            b["y"] += b["vy"] * dt
        self.bul = [b for b in self.bul if b["y"] > -20 and not b.get("dead")]
        P = self.P
        for b in self.fb:
            if b["k"] == "m":
                b["lf"] += dt
                if b["lf"] < b["fuel"]:
                    da = math.atan2(P.y - b["y"], P.x - b["x"])
                    df = da - b["ah"]
                    while df > math.pi: df -= 6.28
                    while df < -math.pi: df += 6.28
                    b["ah"] += max(-b["tn"] * dt, min(b["tn"] * dt, df))
                b["vx"] = math.cos(b["ah"]) * b["sp"]
                b["vy"] = math.sin(b["ah"]) * b["sp"]
            elif b["k"] == "p":
                # плазма — лёгкое самонаведение (если есть tn)
                b["lf"] += dt
                tn = b.get("tn", 0)
                if b["lf"] < b["fuel"] and tn > 0:
                    da = math.atan2(P.y - b["y"], P.x - b["x"])
                    df = da - b["ah"]
                    while df > math.pi: df -= 6.28
                    while df < -math.pi: df += 6.28
                    b["ah"] += max(-tn * dt, min(tn * dt, df))
                b["vx"] = math.cos(b["ah"]) * b["sp"]
                b["vy"] = math.sin(b["ah"]) * b["sp"]
            elif b["k"] == "om":
                # сброшенная мина — мигает, продолжает падать
                b["blink"] += dt
                # самоподрыв через mine_life секунд
                ml = b.get("mine_life", 3.0)
                if b["blink"] > ml:
                    # проверяем урон по игроку в радиусе 3x размера
                    blast_r = b["sz"] * 3
                    blast_dm = int(b["dm"] * 1.75)
                    if dist(b["x"], b["y"], P.x, P.y) < blast_r + P.size:
                        self.hit_player()
                    self.burst(b["x"], b["y"], RED, 16)
                    self.add_flash(b["x"], b["y"], max_r=int(blast_r), color=(255, 80, 40), life=0.5)
                    self.sfx.play("ship_explo")
                    # красные шарики — медленно летящие осколки
                    for _ in range(6):
                        a = random.uniform(0, 6.28)
                        sp = random.uniform(40, 90)
                        self.fb.append({"k": "p", "x": b["x"], "y": b["y"],
                                        "vx": math.cos(a) * sp, "vy": math.sin(a) * sp,
                                        "ah": a, "sp": sp, "sz": 4, "lf": 0, "fuel": 1.8,
                                        "dm": blast_dm // 6, "c": (220, 50, 40)})
                    b["dead"] = True
            b["x"] += b["vx"] * dt
            b["y"] += b["vy"] * dt
        self.fb = [b for b in self.fb if not b.get("dead") and -25 < b["x"] < W + 25 and -25 < b["y"] < H + 25
                   and not (b["k"] in ("m", "p") and b["lf"] > b["fuel"])]

    def update_enemies(self, dt):
        P = self.P
        for f in self.foe:
            ty = f["type"]
            # ---- KAMIKAZE ----
            if ty == 5:
                # из астероида — мгновенный рывок, без свечения и без задержки
                if f.get("from_rock"):
                    if f["kami"] < 2:
                        f["kami"] = 2
                        f["ka"] = math.atan2(P.y - f["y"], P.x - f["x"])
                        self.sfx.play("kamikaze_charge")
                        self.add_flash(f["x"], f["y"], max_r=60, color=(255, 160, 60), life=0.45)
                    sp = 550 + self.wave * 20
                    f["x"] += math.cos(f["ka"]) * sp * dt
                    f["y"] += math.sin(f["ka"]) * sp * dt
                    self.pt.append({"x": f["x"], "y": f["y"], "vx": random.uniform(-25, 25), "vy": random.uniform(-25, 25), "lf": 0.35, "c": AMBER})
                    continue
                if f["kami"] == 0:
                    f["y"] += f["vy"] * dt
                    f["x"] += math.sin(f["y"] * 0.02 + f["ph"]) * f["amp"] * dt
                    if 50 < f["y"] < H * 0.6:
                        f["kami"] = 1; f["kc"] = 0
                        f["ka"] = math.atan2(P.y - f["y"], P.x - f["x"])
                elif f["kami"] == 1:
                    f["kc"] += dt
                    # звук рычит ПОКА камикадзе застывает и готовится — это уже "разгон"
                    if f["kc"] > 0.55:
                        f["kami"] = 2
                        f["ka"] = math.atan2(P.y - f["y"], P.x - f["x"])
                        self.sfx.play("kamikaze_charge")
                        self.add_flash(f["x"], f["y"], max_r=70, color=(255, 160, 60), life=0.5)
                else:
                    sp = 550 + self.wave * 20
                    f["x"] += math.cos(f["ka"]) * sp * dt
                    f["y"] += math.sin(f["ka"]) * sp * dt
                    self.pt.append({"x": f["x"], "y": f["y"], "vx": random.uniform(-25, 25), "vy": random.uniform(-25, 25), "lf": 0.35, "c": AMBER})
                if dist(f["x"], f["y"], P.x, P.y) < f["sz"] + P.size - 3:
                    self.hit_player(); self.burst(f["x"], f["y"], RED, 9); f["hp"] = 0
                continue
            # RAIDER: обычный таранит; из матки/босса (shooter) — стреляет шариками
            if ty == 3:
                f["y"] += f["vy"] * dt
                f["x"] += math.sin(f["y"] * 0.02 + f["ph"]) * f["amp"] * dt
                if not f.get("shooter"):
                    # обычный райдер — таран
                    if dist(f["x"], f["y"], P.x, P.y) < f["sz"] + P.size - 3:
                        self.hit_player(); self.burst(f["x"], f["y"], RED, 9); f["hp"] = 0
                    continue
                else:
                    # райдер-стрелок — ядовитые шарики (кулдаун вдвое больше = 2.8с)
                    if 0 < f["y"] < H * 0.8:
                        f["sc"] -= dt
                        if f["sc"] <= 0:
                            f["sc"] = 2.8
                            ang = math.atan2(P.y - f["y"], P.x - f["x"])
                            sp = 130
                            self.fb.append({"k": "p", "x": f["x"], "y": f["y"] + 6,
                                            "vx": math.cos(ang) * sp, "vy": math.sin(ang) * sp,
                                            "ah": ang, "sp": sp, "sz": 5, "lf": 0, "fuel": 5.0,
                                            "dm": 8, "c": (170, 255, 60)})
                            self.sfx.play("enemy_laser")
                    continue
            # ---- общая логика движения и стрельбы ----
            f["y"] += f["vy"] * dt
            f["x"] += math.sin(f["y"] * 0.02 + f["ph"]) * f["amp"] * dt
            # для матки: спавнит 2 корабля каждые 5 сек, сама не стреляет
            if ty == 11:
                f.setdefault("spawn_cd", 0)
                f["spawn_cd"] -= dt
                if f["spawn_cd"] <= 0 and f["y"] > 30:
                    f["spawn_cd"] = 5.0
                    # спавним 2 райдера-стрелка рядом с маткой
                    for dx in (-25, 25):
                        child = make_enemy(W, H, self.wave, self.diff_mult, force_type=3)
                        child["x"] = f["x"] + dx
                        child["y"] = f["y"] + 20
                        child["shooter"] = True   # стреляет зелёными шариками, не таранит
                        child["sc"] = 2.8          # первый залп с задержкой
                        self.foe.append(child)
                # матка не стреляет — пропускаем atk
                continue

            if 0 < f["y"] < H * 0.78:
                f["sc"] -= dt
                if f["sc"] <= 0:
                    self._enemy_fire(f)
            if dist(f["x"], f["y"], P.x, P.y) < f["sz"] + P.size - 3:
                self.hit_player(); self.burst(f["x"], f["y"], RED, 9); f["hp"] = 0

    def _enemy_fire(self, f):
        """Атака врага в зависимости от его типа."""
        P = self.P
        atk = f["atk"]; ty = f["type"]
        ang = math.atan2(P.y - f["y"], P.x - f["x"])
        # cooldown зависит от типа
        cd = {"l": 1.9, "lh": 1.3, "m": 2.4, "lm": 1.6, "p": 1.8, "z": 2.0,
              "u": 2.2, "f": 7.0, "om": 3.0, "esc": 999, "lm2": 1.8, "ram": 999,
              "tox": 1.4}.get(atk, 2.0)
        f["sc"] = cd
        if atk == "l":
            if self.wave >= 3:
                self.e_laser(f["x"], f["y"], ang, (240, 149, 149))
                self.sfx.play("enemy_laser")
        elif atk == "tox":
            # ядовитый шарик — маленький, медленный, без самонаводки, по вектору вниз-к игроку
            sp = 130
            self.fb.append({"k": "p", "x": f["x"], "y": f["y"] + 6,
                            "vx": math.cos(ang) * sp, "vy": math.sin(ang) * sp,
                            "ah": ang, "sp": sp, "sz": 5, "lf": 0, "fuel": 5.0,
                            "dm": 8, "c": (170, 255, 60)})   # ядовито-зелёный
            self.sfx.play("enemy_laser")
        elif atk == "lh":
            # тяжёлый лазер — клин из трёх расходящихся лучей
            self.e_laser(f["x"], f["y"], ang, AMBER, 380)
            self.e_laser(f["x"], f["y"], ang - 0.22, AMBER, 380)
            self.e_laser(f["x"], f["y"], ang + 0.22, AMBER, 380)
            self.sfx.play("enemy_laser")
        elif atk == "m":
            self.e_missile(f["x"], f["y"])
        elif atk == "lm":
            self.e_laser(f["x"], f["y"], ang, (133, 183, 235))
            self.e_missile(f["x"], f["y"])
            self.sfx.play("enemy_laser")
        elif atk == "p":
            # плазма-шарик: медленный, самонаводящийся
            self.e_plasma(f["x"], f["y"], ang)
            self.sfx.play("enemy_laser")
        elif atk == "z":
            # цепная молния: дуга следует за кораблём, урон только в конце
            self.arcs.append({"owner": f, "x1": f["x"], "y1": f["y"],
                              "x2": P.x + random.uniform(-20, 20),
                              "y2": P.y + random.uniform(-20, 20),
                              "t": 0, "w": 0.4, "lf": 0.85, "hit": False})
            self.sfx.play("arc")
        elif atk == "u":
            # электро-кольцо с 4 просветами для уклонения
            self.rings.append({"cx": f["x"], "cy": f["y"], "r": 0, "mx": 420,
                               "sp": 200, "th": 12, "gaps": 4,
                               "ga": random.uniform(0, 6.28), "gw": 0.55,
                               "elec": True, "hit": False})
            self.sfx.play("arc")
        elif atk == "f":
            # веер из 5 лазеров
            for k in (-2, -1, 0, 1, 2):
                self.e_laser(f["x"], f["y"], ang + k * 0.18, (255, 200, 80), 300)
            self.sfx.play("enemy_laser")
        elif atk == "om":
            # сброс мины: 2x размер, 2x урон, самоподрыв через 2-3 сек
            self.fb.append({"k": "om", "x": f["x"], "y": f["y"] + 12,
                            "vx": random.uniform(-30, 30), "vy": 70,
                            "ah": 0, "sz": 12, "lf": 0, "fuel": 999,
                            "dm": 36, "blink": 0,
                            "mine_life": random.uniform(2.0, 3.0)})   # таймер самоподрыва
            self.sfx.play("mine")
        elif atk == "lm2":
            # гибрид: залп из 3 лазеров + ракета
            for k in (-1, 0, 1):
                self.e_laser(f["x"], f["y"], ang + k * 0.12, (255, 80, 80))
            self.e_missile(f["x"], f["y"])
            self.sfx.play("enemy_laser")

    def e_plasma(self, x, y, ang):
        """Плазма-шарик: медленный, слегка самонаводится, наносит урон при попадании."""
        self.fb.append({"k": "p", "x": x, "y": y, "ah": ang, "sp": 160,
                        "vx": math.cos(ang) * 160, "vy": math.sin(ang) * 160,
                        "sz": 7, "tt": 0, "lf": 0, "fuel": 4.0, "tn": 0.5})

    def update_boss(self, dt):
        b = self.boss; P = self.P
        b["cf"] = max(0, b["cf"] - dt * 3); b["ch"] = max(0, b["ch"] - dt)
        b["hitf"] = max(0, b.get("hitf", 0) - dt * 4)
        b["rot"] += dt * 0.35
        if b["shield"] < b["msh"]:
            b["shield"] = min(b["msh"], b["shield"] + 8 * dt)
        b["ams"] -= dt
        if b["ams"] <= 0:
            b["ams"] = 1.5
            for bl in self.bul:
                if bl.get("tor") and not bl.get("dead") and dist(bl["x"], bl["y"], b["x"], b["y"]) < b["coreR"] + 40:
                    bl["dead"] = True; self.burst(bl["x"], bl["y"], RED, 5)
        if b["enter"] > 0:
            b["y"] += 70 * dt
            if b["y"] >= 140:
                b["y"] = 140; b["enter"] = 0
            return
        # пока активен импульс-луч — босс стоит на месте (чтобы луч не «съезжал»)
        if not self.beams:
            b["x"] += b["vx"] * dt
            if b["x"] < 150 or b["x"] > W - 150:
                b["vx"] *= -1
            b["x"] = max(150, min(W - 150, b["x"]))
        b["pt"] -= dt
        if b["pt"] <= 0:
            # случайная фаза из доступных, не циклически
            b["phase"] = random.randint(0, len(b["atks"]) - 1)
            b["pt"] = self.boss_phase(b)
        # импульс-луч: тонкая быстрая полоса
        for bm in self.beams:
            bm["t"] += dt
            bm["y"] = bm["y0"] + bm["t"] * bm["spd"]
            if not bm["hit"] and abs(P.y - bm["y"]) < 12 and abs(P.x - bm["x"]) < bm["w"] / 2 + 4:
                self.hit_player(); bm["hit"] = True; self.burst(P.x, P.y, (255, 255, 255), 8)
        self.beams = [bm for bm in self.beams if bm["t"] < bm["life"] and bm["y"] < H + 20]
        if b["hp"] <= 0:
            self.boss_die()

    def boss_phase(self, b):
        """Универсальный диспетчер фаз — берёт атаку из b['atks'] по индексу phase."""
        d = b["diff"]; P = self.P
        live = [g for g in b["parts"] if g["hp"] > 0]
        atk = b["atks"][b["phase"]]
        # чуть быстрее интервалы между атаками: x0.85
        if atk == "beam":
            self.sfx.play("beam"); b["cf"] = 1; self.shk = 0.3
            self.beams.append({"x": b["x"], "y0": b["y"], "y": b["y"],
                               "spd": 720 * d, "w": 7, "t": 0, "life": 0.9, "hit": False})
            return 1.4 / d
        if atk == "laser3":
            for g in live[:6]:
                gx, gy = part_pos(b, g)
                self.e_laser(gx, gy, math.atan2(P.y - gy, P.x - gx), (240, 149, 149), 360)
            self.sfx.play("enemy_laser"); return 1.25 / d
        if atk == "miss":
            for _ in range(round(5 * d)):
                self.e_missile(b["x"] + random.uniform(-60, 60), b["y"] + random.uniform(20, 50))
            return 1.7 / d
        if atk == "fan":
            b["cf"] = 1
            for k in range(-4, 5):
                self.e_laser(b["x"], b["y"] + b["coreR"] * 0.6,
                             math.pi / 2 + k * 0.12, GOLD, 320)
            return 1.7 / d
        if atk == "chain":
            b["ch"] = 0.55
            self.sfx.play("arc")
            for c in live[:5]:
                gx, gy = part_pos(b, c)
                self.arcs.append({"x1": gx, "y1": gy,
                                  "x2": P.x + random.uniform(-30, 30), "y2": P.y + random.uniform(-30, 30),
                                  "t": 0, "w": 0.5, "lf": 1.0, "hit": False})
            return 1.5 / d
        if atk == "spawn":
            # ZONE LORD выпускает 5 райдеров-стрелков (зелёные шарики)
            for _ in range(5):
                child = make_enemy(W, H, self.wave, self.diff_mult, force_type=3)
                child["x"] = b["x"] + random.uniform(-90, 90)
                child["y"] = b["y"] + random.uniform(40, 90)
                child["shooter"] = True
                child["sc"] = random.uniform(1.5, 3.0)
                self.foe.append(child)
            self.sfx.play("enemy_laser")
            return 3.5 / d
        if atk == "ring":
            for _ in range(2):
                self.rings.append(self.make_ring(b, 170 * d))
            return 1.7 / d
        if atk == "echo":
            for _ in range(3):
                self.rings.append({"cx": b["x"], "cy": b["y"], "r": 0, "mx": 500,
                                   "sp": 260 * d, "th": 12,
                                   "ga": random.uniform(0, 6.28), "gw": 1.0, "hit": False})
            return 2.0 / d
        return 1.5 / d

    def make_ring(self, b, sp):
        return {"cx": b["x"], "cy": b["y"], "r": 0, "mx": 600, "sp": sp, "th": 15,
                "ga": random.uniform(0, 6.28), "gw": 0.8, "hit": False}

    def boss_hit(self, bl):
        b = self.boss
        if b["enter"] > 0:
            return False
        for g in b["parts"]:
            if g["hp"] > 0:
                gx, gy = part_pos(b, g)
                if dist(bl["x"], bl["y"], gx, gy) < 14:
                    if b["shield"] > 0:
                        b["shield"] -= bl["dm"] * 0.7; self.burst(bl["x"], bl["y"], SHIELD_C, 4)
                    else:
                        g["hp"] -= bl["dm"]; self.burst(bl["x"], bl["y"], AMBER, 4)
                    b["hitf"] = 1.0
                    return True
        prot = any(g["hp"] > 0 for g in b["parts"])
        if dist(bl["x"], bl["y"], b["x"], b["y"]) < b["coreR"]:
            if b["shield"] > 0:
                b["shield"] -= bl["dm"] * (0.4 if bl.get("tor") else 0.6)
            else:
                b["hp"] -= bl["dm"] * (0.3 if prot else 1.2)
            b["cf"] = min(1, b["cf"] + 0.3)
            b["hitf"] = 1.0    # вспышка попадания (краснота экрана)
            self.burst(bl["x"], bl["y"], SHIELD_C if b["shield"] > 0 else GOLD, 5)
            return True
        return False

    def boss_die(self):
        b = self.boss
        # награда за босса: основа 1500 + 500*num (1500..5000 кредитов)
        reward = 1500 + 700 * b["num"]
        self.score += reward * 2; self.cr += reward
        self.burst(b["x"], b["y"], GOLD, 60); self.shk = 0.7; self.sfx.play_loud("boss_explo")
        for _ in range(12):
            self.gld.append({"x": b["x"] + random.uniform(-90, 90), "y": b["y"] + random.uniform(-50, 50), "vy": random.uniform(60, 110), "lf": 8})
        self.boss = None; self.rings = []; self.arcs = []; self.beams = []
        self.wA = False; self.wT = 5
        self.sta = {"x": random.uniform(150, W - 150), "y": -100, "r": 34, "sty": random.randint(0, 2)}

    def update_hazards(self, dt):
        P = self.P
        for a in self.arcs:
            a["t"] += dt
            # дуга следует за кораблём-владельцем
            owner = a.get("owner")
            if owner and owner.get("hp", 0) > 0:
                a["x1"] = owner["x"]; a["y1"] = owner["y"]
            else:
                # владелец уничтожен — дуга быстро гаснет
                a["lf"] = min(a["lf"], a["t"] + 0.15)
            # урон только в КОНЦЕ дуги (x2, y2)
            if a["t"] > a["w"] and not a["hit"]:
                if dist(P.x, P.y, a["x2"], a["y2"]) < 24:
                    self.hit_player(); a["hit"] = True; self.burst(P.x, P.y, (191, 230, 255), 6)
        self.arcs = [a for a in self.arcs if a["t"] < a["lf"]]
        for r in self.rings:
            r["r"] += r["sp"] * dt
            # последние 25% радиуса — кольцо затухает, урона нет
            fade_start = r["mx"] * 0.75
            still_dangerous = r["r"] < fade_start
            if r["r"] > 0 and not r["hit"] and still_dangerous:
                dd = dist(P.x, P.y, r["cx"], r["cy"])
                if abs(dd - r["r"]) < r["th"]:
                    an = math.atan2(P.y - r["cy"], P.x - r["cx"])
                    ngaps = r.get("gaps", 1)
                    gw = r["gw"]
                    in_gap = False
                    for gi in range(ngaps):
                        gap_center = r["ga"] + gi * (6.28 / ngaps)
                        da = an - gap_center
                        while da > math.pi: da -= 6.28
                        while da < -math.pi: da += 6.28
                        if abs(da) < gw / 2:
                            in_gap = True; break
                    if not in_gap:
                        self.hit_player(); r["hit"] = True; self.burst(P.x, P.y, (150, 210, 255), 6)
        self.rings = [r for r in self.rings if r["r"] < r["mx"]]
        for m in self.mines:
            m["t"] += dt
            m.setdefault("auto_det", random.uniform(2.0, 3.0))
            for f in self.foe:
                if m["t"] > m["armed"] and dist(m["x"], m["y"], f["x"], f["y"]) < m["r"] + f["sz"] + 10:
                    blast_r = m["r"] * 3 + 25
                    # прямой урон цели + область
                    self.hit_foe(f, m["dm"])
                    for f2 in self.foe:
                        if f2 is not f and dist(m["x"], m["y"], f2["x"], f2["y"]) < blast_r + f2["sz"]:
                            self.hit_foe(f2, int(m["dm"] * 0.6))
                    for r in self.rk:
                        if dist(m["x"], m["y"], r["x"], r["y"]) < blast_r + r["sz"]:
                            r["hp"] = 0; self.burst(r["x"], r["y"], (185, 153, 170), 8)
                    for d in self.deb:
                        if dist(m["x"], m["y"], d["x"], d["y"]) < blast_r + d["sz"]:
                            d["hp"] = 0; self.burst(d["x"], d["y"], (170, 170, 187), 6)
                    for b in self.fb:
                        if dist(m["x"], m["y"], b["x"], b["y"]) < blast_r + b.get("sz", 5):
                            b["dead"] = True; self.burst(b["x"], b["y"], (255, 180, 120), 5)
                    self.burst(m["x"], m["y"], RED, 18)
                    self.add_flash(m["x"], m["y"], max_r=int(blast_r * 1.4), color=(255, 200, 100), life=0.5)
                    self.add_flash(m["x"], m["y"], max_r=45, color=(255, 240, 200), life=0.3)
                    m["dead"] = True; self.sfx.play("ship_explo")
            if self.boss and not self.boss["enter"] and m["t"] > m["armed"] and dist(m["x"], m["y"], self.boss["x"], self.boss["y"]) < m["r"] + self.boss["coreR"]:
                if self.boss["shield"] > 0: self.boss["shield"] -= m["dm"]
                else: self.boss["hp"] -= m["dm"]
                self.burst(m["x"], m["y"], GOLD, 18)
                self.add_flash(m["x"], m["y"], max_r=90, color=(255, 200, 100), life=0.55)
                m["dead"] = True; self.sfx.play("ship_explo")
            # самоподрыв: если не взорвалась от врага — взрывается сама
            if not m.get("dead") and m["t"] > m["auto_det"]:
                blast_r = m["r"] * 3 + 25   # радиус увеличен на 25
                blast_dm = int(m["dm"] * 1.75)
                # урон всем врагам в радиусе
                for f in self.foe:
                    if dist(m["x"], m["y"], f["x"], f["y"]) < blast_r + f["sz"]:
                        self.hit_foe(f, blast_dm)
                if self.boss and not self.boss["enter"]:
                    if dist(m["x"], m["y"], self.boss["x"], self.boss["y"]) < blast_r + self.boss["coreR"]:
                        if self.boss["shield"] > 0: self.boss["shield"] -= blast_dm
                        else: self.boss["hp"] -= blast_dm
                # уничтожаем астероиды в радиусе
                for r in self.rk:
                    if dist(m["x"], m["y"], r["x"], r["y"]) < blast_r + r["sz"]:
                        r["hp"] = 0
                        self.burst(r["x"], r["y"], (185, 153, 170), 8)
                # уничтожаем обломки в радиусе
                for d in self.deb:
                    if dist(m["x"], m["y"], d["x"], d["y"]) < blast_r + d["sz"]:
                        d["hp"] = 0
                        self.burst(d["x"], d["y"], (170, 170, 187), 6)
                # сбиваем вражеские снаряды/ракеты/мины в радиусе
                for b in self.fb:
                    if dist(m["x"], m["y"], b["x"], b["y"]) < blast_r + b.get("sz", 5):
                        b["dead"] = True
                        self.burst(b["x"], b["y"], (255, 180, 120), 5)
                self.burst(m["x"], m["y"], RED, 20)
                self.add_flash(m["x"], m["y"], max_r=int(blast_r * 1.4), color=(255, 120, 60), life=0.6)
                self.add_flash(m["x"], m["y"], max_r=int(blast_r), color=(255, 220, 150), life=0.4)
                self.sfx.play("ship_explo")
                m["dead"] = True
        self.mines = [m for m in self.mines if not m.get("dead") and m["t"] < 12]
        for r in self.rk:
            r["y"] += r["vy"] * dt; r["x"] += r["vx"] * dt; r["a"] += r["sp"] * dt
            if dist(r["x"], r["y"], P.x, P.y) < r["sz"] + P.size - 4:
                self.hit_player(); self.burst(r["x"], r["y"], (185, 153, 170), 8); r["hp"] = 0
        for d in self.deb:
            d["y"] += d["vy"] * dt; d["x"] += d["vx"] * dt; d["a"] += d["sp"] * dt
            if dist(d["x"], d["y"], P.x, P.y) < d["sz"] + P.size - 4:
                self.hit_player(); self.burst(d["x"], d["y"], (170, 170, 187), 5); d["hp"] = 0

    def collisions(self, dt):
        P = self.P
        for b in self.bul:
            hit = False
            for f in self.foe:
                if dist(b["x"], b["y"], f["x"], f["y"]) < f["sz"] + 4:
                    self.hit_foe(f, b["dm"]); self.burst(b["x"], b["y"], SHIELD_C if f["shield"] > 0 else (159, 225, 203), 3)
                    # звук попадания с ограничением частоты
                    if self._hit_snd_cd <= 0:
                        self.sfx.play("hit"); self._hit_snd_cd = 0.05
                    if not b.get("tor"): b["dead"] = True
                    hit = True; break
            if hit: continue
            if self.boss and self.boss_hit(b):
                if not b.get("tor"): b["dead"] = True
                continue
            for m in self.fb:
                if m["k"] == "m" and not m.get("dead") and dist(b["x"], b["y"], m["x"], m["y"]) < m["sz"] + 4:
                    m["dead"] = True; self.score += 3; self.burst(b["x"], b["y"], AMBER, 7)
                    if not b.get("tor"): b["dead"] = True
                    break
            if b.get("dead"): continue
            for r in self.rk:
                if dist(b["x"], b["y"], r["x"], r["y"]) < r["sz"]:
                    r["hp"] -= b["dm"]; self.burst(b["x"], b["y"], (203, 187, 170), 3)
                    if not b.get("tor"): b["dead"] = True
                    break
            if b.get("dead"): continue
            for d in self.deb:
                if dist(b["x"], b["y"], d["x"], d["y"]) < d["sz"]:
                    d["hp"] -= b["dm"]; self.burst(b["x"], b["y"], (187, 204, 221), 3)
                    if not b.get("tor"): b["dead"] = True
                    break
        self.bul = [b for b in self.bul if not b.get("dead")]
        for b in self.fb:
            if not b.get("dead"):
                # радиус попадания зависит от типа: плазма-шарик и сброшенная мина больше
                rad = P.size + {"m": 5, "p": 9, "om": 8}.get(b["k"], 4)
                if dist(b["x"], b["y"], P.x, P.y) < rad:
                    self.hit_player(); b["dead"] = True
                    col = (255, 100, 220) if b["k"] == "p" else RED
                    self.burst(b["x"], b["y"], col, 8 if b["k"] in ("m", "p", "om") else 4)
        self.fb = [b for b in self.fb if not b.get("dead")]

    def cleanup(self, dt):
        P = self.P
        newfoe = []
        for f in self.foe:
            if f["hp"] <= 0:
                rw = enemy_reward(f["type"], self.wave)
                # элитные дают +50%
                if f.get("elite"):
                    rw = int(rw * 1.5)
                self.cr += rw; self.score += rw
                self.burst(f["x"], f["y"], GOLD, 13); self.sfx.play("ship_explo")
                if random.random() < 0.4:
                    self.gld.append({"x": f["x"], "y": f["y"], "vy": 90, "lf": 7})
                if random.random() < 0.15:
                    P.mines = min(P.mines + 1, 8)
            elif f["y"] < H + 80 and -80 < f["x"] < W + 80:
                newfoe.append(f)
        self.foe = newfoe
        newrk = []
        for r in self.rk:
            if r["hp"] <= 0:
                self.sfx.play("rock_explo")
                self.score += 5; self.burst(r["x"], r["y"], (203, 187, 170), 12)
                if r.get("holds"):
                    # внутри прятался камикадзе — мгновенный рывок, без свечения
                    k = make_enemy(W, H, max(3, self.wave), self.diff_mult, force_type=5)
                    k["x"] = r["x"]; k["y"] = r["y"]
                    k["kami"] = 2; k["kc"] = 0
                    k["ka"] = math.atan2(self.P.y - r["y"], self.P.x - r["x"])
                    k["from_rock"] = True
                    self.foe.append(k)
                    self.burst(r["x"], r["y"], (255, 140, 60), 14)
                    self.sfx.play("kamikaze_charge")
                elif r["sz"] > 20:
                    # большой астероид: редко роняет синюю капсулу щита (15%)
                    if self.P.upg["shield"] > 0 and random.random() < 0.15:
                        self.bonuses.append({"x": r["x"], "y": r["y"], "vy": random.uniform(40, 70), "kind": "shield"})
                    # разваливается на 2-3 маленьких с новыми формами
                    for _ in range(random.randint(2, 3)):
                        new_vt = [random.uniform(0.7, 1.15) for _ in range(8)]
                        self.rk.append({"x": r["x"] + random.uniform(-14, 14), "y": r["y"],
                                        "vy": random.uniform(60, 130),
                                        "vx": random.uniform(-50, 50),
                                        "sz": random.uniform(9, 15), "vt": new_vt,
                                        "a": random.uniform(0, 6.28),
                                        "sp": random.uniform(-3, 3), "hp": 14,
                                        "craters": [(random.uniform(-0.5, 0.5), random.uniform(-0.5, 0.5),
                                                     random.uniform(0.12, 0.26)) for _ in range(2)],
                                        "holds": False, "sprite": r.get("sprite", "asteroid.png")})
            elif r["y"] < H + 50:
                newrk.append(r)
        self.rk = newrk
        # обломки: разрушение
        newdeb = []
        for d in self.deb:
            if d["hp"] <= 0:
                kind = d.get("kind", 0)
                self.burst(d["x"], d["y"], (187, 204, 221), 12)
                self.sfx.play("rock_explo")
                if kind == 4:
                    # большой обломок корабля — 50% шанс дропа, тип 50/50 жизнь или щит
                    if random.random() < 0.5:
                        # если куплен Дефлектор — 50/50 щит или жизнь, иначе всегда жизнь
                        if self.P.upg["shield"] > 0:
                            drop_kind = "shield" if random.random() < 0.5 else "life"
                        else:
                            drop_kind = "life"
                        self.bonuses.append({"x": d["x"], "y": d["y"], "vy": random.uniform(40, 70), "kind": drop_kind})
                # обломки не распадаются на мелкие, за них денег не дают
            elif d["y"] < H + 50:
                newdeb.append(d)
        self.deb = newdeb
        kept = []
        for g in self.gld:
            g["y"] += g["vy"] * dt; g["lf"] -= dt
            if dist(g["x"], g["y"], P.x, P.y) < 22:
                self.cr += 5; self.score += 5; self.burst(g["x"], g["y"], GOLD, 4)
            elif g["lf"] > 0 and g["y"] < H + 20:
                kept.append(g)
        self.gld = kept
        for p in self.pt:
            p["x"] += p["vx"] * dt; p["y"] += p["vy"] * dt; p["vx"] *= 0.92; p["vy"] *= 0.92; p["lf"] -= dt
        self.pt = [p for p in self.pt if p["lf"] > 0]
        for f in self.flashes:
            f["t"] += dt
        self.flashes = [f for f in self.flashes if f["t"] < f["life"]]

    def hit_player(self):
        P = self.P
        if P.inv > 0:
            return
        if P.shield > 0:
            P.shield -= 1; self.sfx.play("hit_player"); return
        P.lives -= 1; self.shk = 0.3; self.sfx.play("hit_player")
        # апгрейды навсегда — при попадании не теряются
        P.inv = 1.5
        if P.lives <= 0:
            return "dead"

    def hit_foe(self, f, dm):
        if f["shield"] > 0:
            f["shield"] -= dm
            if f["shield"] < 0:
                f["hp"] += f["shield"]; f["shield"] = 0
        else:
            f["hp"] -= dm

    def burst(self, x, y, c, n):
        for _ in range(n):
            a = random.uniform(0, 6.28); s = random.uniform(40, 160)
            self.pt.append({"x": x, "y": y, "vx": math.cos(a) * s, "vy": math.sin(a) * s, "lf": random.uniform(0.3, 0.8), "c": c})

    def add_flash(self, x, y, max_r=70, color=(255, 220, 120), life=0.45):
        """Расходящаяся яркая вспышка (для взрывов мин, разгона камикадзе и т.п.)."""
        self.flashes.append({"x": x, "y": y, "t": 0, "life": life, "max_r": max_r, "c": color})


def dist(x, y, a, b):
    return math.hypot(x - a, y - b)


# Звёздное поле (общее): [x, y, speed_mult, size, color, blink_phase]
STARS = []
def make_stars():
    STARS.clear()
    # 3 слоя: дальние (медленные, тусклые), средние, ближние (быстрые, яркие)
    # slot: (кол-во, базовая скорость, макс. размер)
    for n, base_sp, sz in ((90, 0.5, 1.4), (160, 1.2, 1.0), (130, 2.4, 0.6)):
        layer = []
        for _ in range(n):
            # вариация скорости в пределах слоя (не все одинаковые)
            speed = base_sp * random.uniform(0.6, 1.5)
            # ~15% звёзд — с красноватым оттенком (пыль, туманности)
            reddish = random.random() < 0.15
            # ~10% мигают
            blinks = random.random() < 0.1
            layer.append({
                "x": random.uniform(0, W), "y": random.uniform(0, H),
                "sp": speed, "sz": random.uniform(0.4, sz),
                "reddish": reddish, "blinks": blinks,
                "phase": random.uniform(0, 6.28),
            })
        STARS.append(layer)
make_stars()


# ============================================================================
#  ОТРИСОВКА ИГРЫ
# ============================================================================
_NEBULA_OFFSET = [0.0]   # накопленное смещение фона (параллакс)


def tick_stars(dt, warp):
    """Двигает звёзды, объекты меню и сдвигает фон туманности."""
    for layer in STARS:
        for s in layer:
            s["y"] += s["sp"] * (warp * 0.7) * dt
            s["phase"] += dt * 4
            if s["y"] > H:
                s["y"] -= H; s["x"] = random.uniform(0, W)
    # параллакс фона: очень медленно (хватит на всю игру без заметного зацикливания)
    _NEBULA_OFFSET[0] += warp * 0.008 * dt
    # объекты меню
    for obj in _MENU_OBJECTS:
        obj["x"] += obj["vx"] * dt
        obj["y"] += obj["vy"] * dt
        obj["a"] += obj["sp"] * dt
        margin = obj["sz"] + 30
        # ушёл за любой край — возрождаем с СЛУЧАЙНОГО края с новой орбитой
        off = (obj["x"] < -margin or obj["x"] > W + margin or
               obj["y"] < -margin or obj["y"] > H + margin)
        if off:
            edge = random.choice(["top", "bottom", "left", "right"])
            speed = random.uniform(14, 30)
            if edge == "top":
                obj["x"] = random.uniform(40, W - 40); obj["y"] = -margin
                ang = random.uniform(-0.5, 0.5); obj["vx"] = math.sin(ang) * speed; obj["vy"] = math.cos(ang) * speed
            elif edge == "bottom":
                obj["x"] = random.uniform(40, W - 40); obj["y"] = H + margin
                ang = random.uniform(-0.5, 0.5); obj["vx"] = math.sin(ang) * speed; obj["vy"] = -math.cos(ang) * speed
            elif edge == "left":
                obj["x"] = -margin; obj["y"] = random.uniform(40, H - 40)
                obj["vx"] = speed; obj["vy"] = random.uniform(-speed, speed) * 0.5
            else:
                obj["x"] = W + margin; obj["y"] = random.uniform(40, H - 40)
                obj["vx"] = -speed; obj["vy"] = random.uniform(-speed, speed) * 0.5


_NEBULA_CACHE = {}

def draw_stars(surface, warp):
    # --- фон: звёздное небо (если файл есть) или тёмный цвет ---
    neb = _NEBULA_CACHE.get("img", "?")
    if neb == "?":
        import os
        path = _resource_path(os.path.join("assets", "nebula_bg.jpg"))
        if os.path.exists(path) and os.path.getsize(path) > 100:
            try:
                raw = pygame.image.load(path).convert()
                iw, ih = raw.get_size()
                # масштаб COVER по ширине; высота вытянута для вертикального параллакса
                scale = W / iw
                nw = W
                nh = int(ih * scale)
                if nh < H * 2:   # хотим запас по высоте для прокрутки
                    nh = H * 2
                    scale2 = nh / ih
                    nw = int(iw * scale2)
                neb = pygame.transform.smoothscale(raw, (nw, nh))
                # затемняем один раз при загрузке
                dark = pygame.Surface(neb.get_size())
                dark.fill((0, 0, 0)); dark.set_alpha(120)
                neb.blit(dark, (0, 0))
            except Exception as e:
                print("Фон не загружен:", e)
                neb = None
        else:
            neb = None
        _NEBULA_CACHE["img"] = neb

    if neb:
        nw, nh = neb.get_size()
        total_scroll = nh - H
        oy = int(_NEBULA_OFFSET[0]) % total_scroll if total_scroll > 0 else 0
        ox = (nw - W) // 2   # центрируем по ширине
        surface.blit(neb, (0, 0), (ox, oy, W, H))
    else:
        surface.fill((5, 5, 18))
    boost = max(0, (warp - 170) / 350)
    for li, layer in enumerate(STARS):
        base_col = [(110, 112, 135), (185, 187, 210), (245, 248, 255)][li]  # ярче
        for st in layer:
            # красноватый оттенок?
            if st["reddish"]:
                col = (min(255, base_col[0] + 60), max(0, base_col[1] - 30), max(0, base_col[2] - 40))
            else:
                col = base_col
            # мигание
            if st["blinks"]:
                bl = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(st["phase"]))
                col = (int(col[0] * bl), int(col[1] * bl), int(col[2] * bl))
            ln = int(1 + boost * 20 * (li * 0.5 + 0.4) + warp * 0.014 * li)
            pygame.draw.rect(surface, col, (st["x"], st["y"], st["sz"], st["sz"] + ln))


def draw_ring(s, r):
    if r["r"] <= 0:
        return
    a = max(0.1, min(0.85, 1 - r["r"] / r["mx"]))
    rad = r["r"]
    srf = pygame.Surface((rad * 2 + 24, rad * 2 + 24), pygame.SRCALPHA)
    cx = cy = int(rad + 12)
    ngaps = r.get("gaps", 1)
    gw = r["gw"]
    elec = r.get("elec", False)
    th = int(r["th"] * 0.7)
    # рисуем сегменты между просветами
    seg_count = ngaps
    for si in range(seg_count):
        gap_c = r["ga"] + si * (6.28 / ngaps)
        seg_start = gap_c + gw / 2
        seg_end = gap_c + (6.28 / ngaps) - gw / 2
        pts = []
        steps = 24
        for i in range(steps + 1):
            ang = seg_start + (seg_end - seg_start) * i / steps
            rr = rad
            if elec:
                # электрическое дрожание по радиусу
                rr += math.sin(ang * 14 + r["r"] * 0.3) * 4 + random.uniform(-2, 2)
            pts.append((cx + math.cos(ang) * rr, cy + math.sin(ang) * rr))
        if len(pts) > 1:
            if elec:
                # свечение
                pygame.draw.lines(srf, (100, 180, 255, int(a * 120)), False, pts, th + 4)
                pygame.draw.lines(srf, (180, 230, 255, int(a * 255)), False, pts, th)
                pygame.draw.lines(srf, (255, 255, 255, int(a * 255)), False, pts, max(1, th // 2))
            else:
                pygame.draw.lines(srf, (255, 150, 70, int(a * 255)), False, pts, th)
    s.blit(srf, (r["cx"] - cx, r["cy"] - cy))


def draw_arc(s, a):
    if a["t"] < a["w"]:
        col = (150, 210, 255)
        if int(a["t"] * 30) % 2 == 0:
            pygame.draw.line(s, col, (a["x1"], a["y1"]), (a["x2"], a["y2"]), 1)
    else:
        seg = 6
        pts = [(a["x1"], a["y1"])]
        for i in range(1, seg):
            t = i / seg
            pts.append((a["x1"] + (a["x2"] - a["x1"]) * t + random.uniform(-9, 9),
                        a["y1"] + (a["y2"] - a["y1"]) * t + random.uniform(-9, 9)))
        pts.append((a["x2"], a["y2"]))
        pygame.draw.lines(s, (200, 240, 255), False, pts, 3)


def draw_beam(s, bm):
    """Импульс-луч: тонкая яркая белая полоса, без круга на конце."""
    fade = max(0.3, 1 - bm["t"] / bm["life"])
    x = int(bm["x"]); y0 = int(max(0, bm["y0"])); y1 = int(bm["y"])
    glow = pygame.Surface((bm["w"] + 12, abs(y1 - y0) + 4), pygame.SRCALPHA)
    pygame.draw.rect(glow, (180, 220, 255, int(120 * fade)), (0, 0, bm["w"] + 12, glow.get_height()))
    pygame.draw.rect(glow, (255, 255, 255, int(240 * fade)), (6, 0, bm["w"], glow.get_height()))
    s.blit(glow, (x - (bm["w"] + 12) // 2, min(y0, y1)))


def draw_station(s, sta, t, near):
    cx, cy, R = sta["x"], sta["y"], sta["r"]
    sp = load_sprite("station.png", target_size=(int(R * 4.5), int(R * 4.5)))
    if sp:
        # медленное вращение станции
        ang = t * 12  # градусов/сек
        rot = pygame.transform.rotozoom(sp, ang, 1.0)
        rw, rh = rot.get_size()
        s.blit(rot, (int(cx) - rw // 2, int(cy) - rh // 2))
        # мигающие посадочные огни по кольцу (вращаются вместе со станцией)
        n_lights = 8
        for i in range(n_lights):
            la = i / n_lights * 6.28 + math.radians(ang)
            lr = R * 1.7
            lx = cx + math.cos(la) * lr
            ly = cy + math.sin(la) * lr
            # каждый огонёк мигает со своей фазой
            blink = 0.5 + 0.5 * math.sin(t * 4 + i * 0.9)
            if near:
                col = (int(120 + blink * 135), 255, int(120 + blink * 100))  # зелёные при доке
            else:
                col = (int(120 + blink * 135), int(180 + blink * 75), 40)     # янтарные
            pygame.draw.circle(s, col, (int(lx), int(ly)), 3)
            if blink > 0.7:
                pygame.draw.circle(s, (255, 255, 220), (int(lx), int(ly)), 1)
    else:
        # fallback — процедурная станция
        pygame.draw.circle(s, WHITE if near else (45, 185, 140), (int(cx), int(cy)), int(R), int(R * 0.14))
        pygame.draw.circle(s, (15, 92, 70), (int(cx), int(cy)), int(R * 0.6))
        for i in range(8):
            a = i / 8 * 6.28 + t * 0.6
            col = AMBER if i % 2 == 0 else (122, 90, 32)
            pygame.draw.circle(s, col, (int(cx + math.cos(a) * R * 0.42), int(cy + math.sin(a) * R * 0.42)), int(R * 0.05))
    if near:
        txt(s, "[E] стыковка", F_S, WHITE, int(cx), int(cy + R * 2.4 + 6), center=True)


def draw_fb(s, b):
    k = b["k"]
    if k == "l":
        a = math.atan2(b.get("vy", 0), b.get("vx", 0))
        x1, y1 = b["x"], b["y"]
        x2, y2 = b["x"] - math.cos(a) * b["ln"], b["y"] - math.sin(a) * b["ln"]
        col = b["c"]
        # мягкое свечение — локальный surface вокруг луча
        minx, maxx = int(min(x1, x2)) - 6, int(max(x1, x2)) + 6
        miny, maxy = int(min(y1, y2)) - 6, int(max(y1, y2)) + 6
        gw, gh = max(1, maxx - minx), max(1, maxy - miny)
        glow_srf = pygame.Surface((gw, gh), pygame.SRCALPHA)
        pygame.draw.line(glow_srf, (col[0], col[1], col[2], 45),
                         (x1 - minx, y1 - miny), (x2 - minx, y2 - miny), 4)
        s.blit(glow_srf, (minx, miny), special_flags=pygame.BLEND_RGBA_ADD)
        # яркое тонкое ядро
        pygame.draw.line(s, col, (x1, y1), (x2, y2), 2)
        pygame.draw.line(s, (255, 255, 255), (x1, y1), (x2, y2), 1)
    elif k == "p":
        # плазма-шарик — пульсирующий круг с ореолом; цвет берётся из "c" если задан
        cx, cy = int(b["x"]), int(b["y"])
        col = b.get("c", (255, 150, 230))
        sz = int(b.get("sz", 8))
        r_out = max(10, sz + 5)
        srf = pygame.Surface((r_out * 2 + 4, r_out * 2 + 4), pygame.SRCALPHA)
        c = r_out + 2
        pygame.draw.circle(srf, (*col, 80), (c, c), r_out)
        pygame.draw.circle(srf, (*col, 180), (c, c), max(6, sz))
        pygame.draw.circle(srf, (255, 255, 255, 255), (c, c), max(2, sz // 2))
        s.blit(srf, (cx - c, cy - c))
    elif k == "om":
        # сброшенная мина — серый шар с миганием
        cx, cy = int(b["x"]), int(b["y"])
        col = (226, 75, 74) if math.sin(b["blink"] * 8) > 0 else (90, 90, 90)
        pygame.draw.circle(s, col, (cx, cy), 7)
        pygame.draw.circle(s, AMBER, (cx, cy), 7, 1)
    else:
        armed = b["lf"] < b["fuel"]
        heading = b.get("ah", math.atan2(b.get("vy", 1), b.get("vx", 0)))
        sp = load_sprite("rocket.png", target_size=(30, 30))
        if sp:
            # спрайт нарисован носом ВВЕРХ; направление полёта heading (0=вправо).
            # угол поворота: чтобы нос смотрел по heading, поворачиваем на -(heading+90°)
            deg = -math.degrees(heading + math.pi / 2)
            rot = pygame.transform.rotozoom(sp, deg, 1.0)
            rw, rh = rot.get_size()
            s.blit(rot, (int(b["x"]) - rw // 2, int(b["y"]) - rh // 2))
            # огонёк из дюзы (сзади по курсу)
            if armed:
                fp = rot_pt(0, 12, b["x"], b["y"], heading + math.pi / 2)
                flc = (250, 199, 117) if math.sin(b["lf"] * 40) > 0 else (255, 150, 60)
                pygame.draw.circle(s, flc, (int(fp[0]), int(fp[1])), 3)
        else:
            ang = heading + math.pi / 2
            body = rot_pts([(-2.5, -6), (2.5, -6), (2.5, 5), (-2.5, 5)], b["x"], b["y"], ang)
            pygame.draw.polygon(s, (204, 211, 218), body)
            tip = rot_pts([(-2.5, -6), (0, -12), (2.5, -6)], b["x"], b["y"], ang)
            pygame.draw.polygon(s, RED, tip)
            flame = (250, 199, 117) if armed else (130, 130, 130)
            fp = rot_pt(0, 8, b["x"], b["y"], ang)
            pygame.draw.circle(s, flame, (int(fp[0]), int(fp[1])), 3 if armed else 2)


def rot_pt(px, py, cx, cy, ang):
    ca, sa = math.cos(ang), math.sin(ang)
    return (cx + px * ca - py * sa, cy + px * sa + py * ca)
def rot_pts(pts, cx, cy, ang):
    return [rot_pt(p[0], p[1], cx, cy, ang) for p in pts]


def render_game(s, g, t):
    off = (random.uniform(-1, 1) * g.shk * 10, random.uniform(-1, 1) * g.shk * 10) if g.shk > 0 else (0, 0)
    base = pygame.Surface((W, H))
    draw_stars(base, g.warp)
    if g.sta:
        draw_station(base, g.sta, t, g.P.near is g.sta)
    _DEBRIS_SPRITE = {1: "debris_sputnik.png", 2: "debris_station.png",
                      3: "debris_wreck.png", 4: "debris_wreck.png"}
    for d in g.deb:
        kind = d.get("kind", 3)
        cx, cy = int(d["x"]), int(d["y"])
        ang = d["a"]
        # спрайт масштабируется под коллизионный размер (крупнее, чтобы детали читались)
        # масштаб спрайта под тип обломка
        _scale = {1: 4.2,   # спутник (+0.4)
                  2: 5.7,   # станция (в 1.5 раза больше базовых 3.8)
                  3: 4.6, 4: 4.6}   # обломки кораблей
        target = int(d["sz"] * _scale.get(kind, 4.6))
        fname = _DEBRIS_SPRITE.get(kind, "debris_wreck.png")
        sp = load_sprite(fname, target_size=(target, target))
        if sp:
            rot = pygame.transform.rotozoom(sp, math.degrees(ang), 1.0)
            rw, rh = rot.get_size()
            base.blit(rot, (cx - rw // 2, cy - rh // 2))
        else:
            # запасная процедурная отрисовка, если PNG не найден
            pygame.draw.circle(base, (110, 100, 88), (cx, cy), int(d["sz"]))
            pygame.draw.circle(base, (150, 140, 120), (cx, cy), int(d["sz"]), 2)
    for r in g.rk:
        target = int(r["sz"] * 2.2)
        sp = load_sprite(r.get("sprite", "asteroid.png"), target_size=(target, target))
        if sp:
            rot = pygame.transform.rotozoom(sp, math.degrees(r["a"]), 1.0)
            rw, rh = rot.get_size()
            base.blit(rot, (int(r["x"]) - rw // 2, int(r["y"]) - rh // 2))
        else:
            pts = [(r["x"] + math.cos(i / len(r["vt"]) * 6.28 + r["a"]) * r["sz"] * r["vt"][i],
                    r["y"] + math.sin(i / len(r["vt"]) * 6.28 + r["a"]) * r["sz"] * r["vt"][i]) for i in range(len(r["vt"]))]
            pygame.draw.polygon(base, (90, 84, 76), pts)
            pygame.draw.polygon(base, (130, 121, 108), pts, 2)
        # астероид с камикадзе внутри — никак не выдаём себя
    for b in g.bonuses:
        glow = 0.5 + 0.5 * math.sin(t * 5)
        is_shield = b.get("kind") == "shield"
        sp_name = "bonus_shield.png" if is_shield else "bonus_life.png"
        sp = load_sprite(sp_name, target_size=(108, 108))
        if sp:
            # лёгкое мерцание яркости через alpha
            alpha = int(180 + glow * 75)
            sp_glow = sp.copy()
            sp_glow.set_alpha(alpha)
            sw, sh = sp.get_size()
            base.blit(sp_glow, (int(b["x"]) - sw // 2, int(b["y"]) - sh // 2))
        else:
            rim_col = SHIELD_C if is_shield else GREEN
            letter = "S" if is_shield else "L"
            txt_col = (int(80 + glow * 140), int(170 + glow * 85), 255) if is_shield else (int(120 + glow * 100), 255, 200)
            pygame.draw.circle(base, (20, 40, 70) if is_shield else (26, 58, 42), (int(b["x"]), int(b["y"])), 10)
            pygame.draw.circle(base, rim_col, (int(b["x"]), int(b["y"])), 10, 2)
            txt(base, letter, F_S, txt_col, int(b["x"]), int(b["y"]), center=True)
    for m in g.mines:
        armed = m["t"] > m["armed"]
        cx, cy = int(m["x"]), int(m["y"])
        # PNG-спрайт мины (масштабированный)
        mine_sp = load_sprite("mine.png", target_size=(70, 70))
        if mine_sp:
            sw, sh = mine_sp.get_size()
            base.blit(mine_sp, (cx - sw // 2, cy - sh // 2))
            if armed:
                # мигаем жёлтым центром
                blink = 0.5 + 0.5 * math.sin(t * 10)
                srf = pygame.Surface((28, 28), pygame.SRCALPHA)
                pygame.draw.circle(srf, (255, 220, 50, int(180 * blink)), (14, 14), 8)
                pygame.draw.circle(srf, (255, 255, 100, int(255 * blink)), (14, 14), 4)
                base.blit(srf, (cx - 14, cy - 14))
        else:
            pygame.draw.circle(base, (226, 75, 74) if armed else (136, 136, 136), (cx, cy), m["r"])
            pygame.draw.circle(base, AMBER, (cx, cy), m["r"], 1)
            if armed and math.sin(t * 8) > 0.5:
                pygame.draw.circle(base, (255, 100, 50), (cx, cy), 3)
    for p in g.pt:
        al = max(0, min(255, int(p["lf"] / 0.8 * 255)))
        pygame.draw.circle(base, p["c"], (int(p["x"]), int(p["y"])), 2)
    # яркие расходящиеся вспышки (взрывы мин, разгон камикадзе)
    for f in g.flashes:
        prog = f["t"] / f["life"]
        r = int(prog * f["max_r"])
        if r < 1:
            continue
        alpha_outer = int(220 * (1 - prog))
        alpha_inner = int(255 * (1 - prog) ** 2)
        srf = pygame.Surface((r * 2 + 8, r * 2 + 8), pygame.SRCALPHA)
        # ободок-фронт волны
        pygame.draw.circle(srf, (*f["c"], alpha_outer), (r + 4, r + 4), r, 3)
        # яркое ядро
        core_r = max(1, int(r * 0.35))
        pygame.draw.circle(srf, (255, 255, 220, alpha_inner), (r + 4, r + 4), core_r)
        # мягкое свечение
        pygame.draw.circle(srf, (*f["c"], alpha_inner // 2), (r + 4, r + 4), int(r * 0.7))
        base.blit(srf, (f["x"] - r - 4, f["y"] - r - 4))
    for r in g.rings:
        draw_ring(base, r)
    for bm in g.beams:
        draw_beam(base, bm)
    if g.boss:
        draw_boss(base, g.boss, g.P.x, g.P.y, t)
    for f in g.foe:
        draw_enemy(base, f, t)
    for a in g.arcs:
        draw_arc(base, a)
    for b in g.bul:
        if b.get("tor"):
            # торпеда — маленький спрайт
            sp = load_sprite("torpedo.png", target_size=(49, 49))
            if sp:
                sw, sh = sp.get_size()
                base.blit(sp, (int(b["x"]) - sw // 2, int(b["y"]) - sh // 2))
            else:
                pygame.draw.rect(base, b["c"], (b["x"] - b["sz"] / 2, b["y"] - b["sz"], b["sz"], b["sz"] * 2.6))
        else:
            pygame.draw.rect(base, b["c"], (b["x"] - b["sz"] / 2, b["y"] - b["sz"], b["sz"], b["sz"] * 2.6))
    for b in g.fb:
        draw_fb(base, b)
    g.P.draw(base, t, g.warp)
    s.blit(base, off)
    # мигание красным при ПОПАДАНИИ по боссу (hitf), не при его стрельбе
    if g.boss and g.boss.get("hitf", 0) > 0.05:
        hf = g.boss["hitf"]
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((180, 30, 30, int(hf * 60)))
        s.blit(overlay, (0, 0))
    draw_hud(s, g, t)


def draw_hud(s, g, t):
    P = g.P
    pygame.draw.rect(s, (0, 0, 0), (0, 0, W, 30))
    # жизни — истребители
    for i in range(P.max_lives):
        ix = 14 + i * 20
        col = (159, 225, 203) if i < P.lives else (68, 68, 68)
        fighter_icon(s, ix + 8, 15, 8, col)
    sx = 16 + P.max_lives * 20
    if P.max_shield > 0:
        txt(s, "SH", F_S, (55, 138, 221), sx, 8)
        for i in range(P.max_shield):
            c = (55, 138, 221) if i < P.shield else (51, 51, 51)
            pygame.draw.circle(s, c, (sx + 26 + i * 14, 15), 5)
        sx += 26 + P.max_shield * 14 + 8
    txt(s, f"Торпеды: {P.torp}", F_S, GOLD, sx, 8); sx += 130
    txt(s, f"Мины: {P.mines}", F_S, RED, sx, 8)
    # правая часть HUD: кредиты, счёт, уровень·сектор — по строкам без наложения
    _lvl = (g.wave - 1) // 5 + 1
    txt(s, f"Ур.{_lvl} Сектор {g.wave}", F_S, (170, 200, 255), W - 12, 8, right=True)
    txt(s, f"Кредиты: {g.cr}", F_S, GOLD, W - 230, 8, right=True)
    txt(s, f"{g.score}", F_S, WHITE, W - 380, 8, right=True)
    if g.boss and g.boss["enter"] <= 0:
        pygame.draw.rect(s, (0, 0, 0), (W / 2 - 200, 36, 400, 22))
        b = g.boss
        hpP = max(0, min(1, b["hp"] / b["mhp"])); shP = max(0, min(1, b["shield"] / b["msh"]))
        pygame.draw.rect(s, (58, 13, 13), (W / 2 - 190, 42, 380, 10))
        pygame.draw.rect(s, RED, (W / 2 - 190, 42, 380 * hpP, 10))
        pygame.draw.rect(s, (94, 170, 235), (W / 2 - 190, 42, 380 * shP, 10))
        txt(s, f"БОСС — {math.ceil(hpP*100)}%", F_S, AMBER, W // 2, 64, center=True)
    if g.boss and g.boss["enter"] > 0:
        # мигающий предупреждающий баннер
        if math.sin(t * 6) > 0:
            txt(s, "ВНИМАНИЕ!", F_L, RED, W // 2, H // 2, center=True)
    # «Сектор N зачищен» убран по запросу — переход между волнами молчаливый


# ============================================================================
#  МЕНЮ И ЭКРАНЫ
# ============================================================================
_BTN_SPRITE = {}   # кэш масштабированных спрайтов кнопок

class Button:
    def __init__(self, x, y, w, h, label, action, col=(0, 220, 255)):
        self.rect = pygame.Rect(x, y, w, h); self.label = label
        self.action = action; self.col = col

    def draw(self, s, hover):
        r = self.rect
        col = self.col

        key = (r.w, r.h)
        if key not in _BTN_SPRITE:
            sp = load_sprite("menu_btn.png", target_size=(r.w, r.h))
            _BTN_SPRITE[key] = sp
        sp = _BTN_SPRITE.get(key)

        # тёмный фон
        pygame.draw.rect(s, (8, 14, 24) if hover else (5, 10, 18), r, border_radius=4)

        if sp:
            dim = sp.copy()
            dim.set_alpha(130 if hover else 90)
            s.blit(dim, r.topleft)

        # только угловые засечки, без общей рамки
        n = 7
        rim = (min(col[0]+30,255), min(col[1]+30,255), min(col[2]+30,255)) if hover else col
        for sx,sy,ex,ey in [
            (r.x,r.y+n,r.x,r.y),(r.x,r.y,r.x+n,r.y),
            (r.right-n,r.y,r.right,r.y),(r.right,r.y,r.right,r.y+n),
            (r.x,r.bottom-n,r.x,r.bottom),(r.x,r.bottom,r.x+n,r.bottom),
            (r.right-n,r.bottom,r.right,r.bottom),(r.right,r.bottom-n,r.right,r.bottom),
        ]:
            pygame.draw.line(s, rim, (sx,sy), (ex,ey), 2)

        tc = (255,255,255) if hover else col
        txt(s, self.label, F_M, tc, r.centerx, r.centery, center=True)

    def hit(self, pos):
        return self.rect.collidepoint(pos)


_MENU_OBJECTS = []   # медленно летящие объекты в меню

def _init_menu_objects():
    """Инициализация объектов фона меню."""
    _MENU_OBJECTS.clear()
    for _ in range(2):   # 1-2 астероида
        angle = random.uniform(-0.5, 0.5)
        speed = random.uniform(18, 35)
        _MENU_OBJECTS.append({
            "kind": "rock", "sprite": "asteroid.png",
            "x": random.uniform(60, W - 60), "y": random.uniform(-60, H * 0.4),
            "vx": math.sin(angle) * speed, "vy": math.cos(angle) * speed,
            "a": random.uniform(0, 6.28), "sp": random.uniform(-0.5, 0.5),
            "sz": random.uniform(35, 55),
        })
    for kind, fname in [("sputnik", "debris_sputnik.png"), ("station", "debris_station.png"),
                        ("wreck", "debris_wreck.png")]:
        angle = random.choice([random.uniform(-0.3, 0.3),
                                random.uniform(0.4, 0.8), random.uniform(-0.8, -0.4)])
        speed = random.uniform(14, 28)
        _MENU_OBJECTS.append({
            "kind": kind, "sprite": fname,
            "x": random.uniform(60, W - 60), "y": random.uniform(-80, H * 0.5),
            "vx": math.sin(angle) * speed, "vy": math.cos(angle) * speed,
            "a": random.uniform(0, 6.28), "sp": random.uniform(-0.6, 0.6),
            "sz": random.uniform(60, 90),
        })
_init_menu_objects()


def draw_title_bg(s, t):
    draw_stars(s, 380)
    # медленно летящие объекты
    for obj in _MENU_OBJECTS:
        sp = load_sprite(obj["sprite"], target_size=(int(obj["sz"]), int(obj["sz"])))
        if sp:
            rot = pygame.transform.rotozoom(sp, math.degrees(obj["a"]), 1.0)
            rw, rh = rot.get_size()
            s.blit(rot, (int(obj["x"]) - rw // 2, int(obj["y"]) - rh // 2))


# ============================================================================
# ИНТРО — брифинг перед игрой
# ============================================================================
INTRO_TEXT = [
    "КОСМИЧЕСКОЕ КОМАНДОВАНИЕ ЗЕМЛИ · ДИРЕКТИВА 77-ГАММА",
    "Пилот, ситуация критическая. Ксеносы прорвали периметр обороны Земли.",
    "Флот Альянса уничтожен. Ты — последний боевой пилот в секторе Дельта-9.",
    "Задача: полная зачистка района от сил противника.",
    "Уничтожь командные корабли ксеносов до единого.",
    "За тобой — только Земля. Отступать некуда.",
    "Удачи, пилот. Она тебе понадобится.",
]

LINES_PER_PAGE = 3   # строк текста видно за раз (окно низкое)


def draw_cosmonaut_icon(s, x, y, sz=64):
    """Пиксельный портрет космонавта — голова в шлеме, профиль вправо."""
    pygame.draw.rect(s, (14, 18, 32), (x, y, sz, sz))
    pygame.draw.rect(s, (60, 80, 120), (x, y, sz, sz), 2)
    ps = max(1, sz // 16)
    ox, oy = x + ps, y + ps

    def px(gx, gy, col):
        pygame.draw.rect(s, col, (ox + gx * ps, oy + gy * ps, ps, ps))

    # палитра
    BG = (14, 18, 32)
    SILVER = (185, 195, 215)
    DS = (130, 140, 160)
    VISOR = (55, 145, 225)
    DV = (30, 80, 170)
    LV = (120, 200, 255)
    SKIN = (215, 175, 135)
    DSKN = (175, 135, 95)
    HAIR = (60, 40, 30)
    ORG = (225, 125, 40)
    DORG = (165, 85, 28)
    WHT = (230, 235, 245)

    # шлем — овал (профиль слегка вправо)
    # ряд 0-1: верхушка шлема
    for gx in range(5, 12): px(gx, 0, DS)
    for gx in range(4, 13): px(gx, 1, SILVER)
    # ряды 2-8: тело шлема
    for gy in range(2, 9):
        for gx in range(3, 14): px(gx, gy, SILVER)
    # ряд 9: низ шлема
    for gx in range(4, 13): px(gx, 9, DS)

    # визор (прозрачная часть шлема — лицо видно)
    for gy in range(3, 8):
        for gx in range(6, 12): px(gx, gy, VISOR)
    # блик на визоре
    px(7, 3, LV); px(8, 3, WHT); px(9, 3, LV)
    px(6, 4, DV); px(6, 5, DV)

    # лицо внутри визора
    for gx in range(7, 11): px(gx, 5, SKIN)
    for gx in range(7, 11): px(gx, 6, SKIN)
    for gx in range(8, 11): px(gx, 7, DSKN)
    # глаз
    px(9, 5, (40, 40, 40))
    px(10, 5, WHT)
    # бровь
    px(9, 4, HAIR); px(10, 4, HAIR)
    # нос
    px(10, 6, DSKN)
    # рот
    px(9, 7, (180, 100, 90))

    # скафандр — оранжевый (ряды 10-14)
    for gy in range(10, 15):
        for gx in range(4, 13): px(gx, gy, ORG)
    # воротник
    for gx in range(5, 12): px(gx, 10, DS)
    # тёмные швы
    for gy in range(11, 15): px(4, gy, DORG); px(12, gy, DORG)
    # нашивка на груди
    for gy in range(12, 14):
        for gx in range(6, 8): px(gx, gy, (40, 60, 180))
    # шланг
    for gy in range(11, 14): px(10, gy, (90, 100, 110))
    # плечо
    for gy in range(10, 13): px(3, gy, DORG); px(13, gy, DORG)


class IntroState:
    """Брифинг: текст печатается посимвольно в окошке, по страницам."""
    def __init__(self, sfx):
        self.sfx = sfx
        self.lines = list(INTRO_TEXT)
        self.page = 0
        self.char_idx = 0      # символ в текущей видимой строке
        self.line_idx = 0      # строка внутри страницы
        self.timer = 0
        self.speed = 0.032
        self.page_done = False  # страница полностью напечатана
        self.all_done = False   # весь текст показан
        self.blink = 0
        # плавающие обломки/астероиды (макс 4)
        self.floaters = []
        for _ in range(4):
            self._add_floater(True)

    def _add_floater(self, anywhere=False):
        """Добавить случайный летящий обломок (крупный PNG-спрайт с вращением)."""
        # kind: спрайт-обломки кораблей/станций + процедурный камень
        kind = random.choice(["wreck", "sputnik", "station", "rock", "rock"])
        # крупные, чтобы не терялась детализация
        target = {"wreck": 130, "sputnik": 110, "station": 150, "rock": 70}[kind]
        self.floaters.append({
            "x": random.uniform(60, W - 60),
            "y": random.uniform(-40, H) if anywhere else random.uniform(-160, -80),
            "vy": random.uniform(18, 40), "vx": random.uniform(-14, 14),
            "a": random.uniform(0, 6.28),
            "sp": random.uniform(-0.8, 0.8),   # хаотичное вращение
            "target": target, "kind": kind,
            "verts": [random.uniform(0.7, 1.15) for _ in range(9)] if kind == "rock" else [],
        })

    def _page_lines(self):
        """Строки текущей страницы."""
        start = self.page * LINES_PER_PAGE
        return self.lines[start:start + LINES_PER_PAGE]

    def update(self, dt):
        self.blink += dt
        if self.page_done or self.all_done:
            return
        self.timer += dt
        while self.timer >= self.speed:
            self.timer -= self.speed
            plines = self._page_lines()
            if self.line_idx >= len(plines):
                self.page_done = True
                if (self.page + 1) * LINES_PER_PAGE >= len(self.lines):
                    self.all_done = True
                return
            cur = plines[self.line_idx]
            if self.char_idx < len(cur):
                ch = cur[self.char_idx]
                self.char_idx += 1
                if ch not in (' ', '\n'):
                    self.sfx.play("type" if self.char_idx % 3 != 0 else "type2")
            else:
                # перевод на следующую строку
                self.line_idx += 1
                self.char_idx = 0
                self.timer = max(self.timer, -0.12)

    def press(self):
        """Нажатие клавиши: ускорить/перелистнуть/завершить."""
        if not self.page_done:
            # допечатать страницу мгновенно
            self.line_idx = len(self._page_lines())
            self.char_idx = 0
            self.page_done = True
            if (self.page + 1) * LINES_PER_PAGE >= len(self.lines):
                self.all_done = True
            return False
        if self.all_done:
            return True   # выйти из интро → старт игры
        # следующая страница
        self.page += 1
        self.line_idx = 0
        self.char_idx = 0
        self.page_done = False
        if (self.page + 1) * LINES_PER_PAGE >= len(self.lines):
            pass  # последняя страница — допечатаем и покажем
        return False

    # алиас для совместимости
    def skip(self):
        return self.press()

    def draw(self, s, t):
        # фон — бегущие звёзды
        tick_stars(1 / 60, 380)
        draw_stars(s, 380)

        # плавающие обломки (крупные PNG-спрайты, хаотично вращаются)
        dt = 1 / 60
        sprite_map = {"wreck": "debris_wreck.png", "sputnik": "debris_sputnik.png",
                      "station": "debris_station.png"}
        alive = []
        for f in self.floaters:
            f["y"] += f["vy"] * dt; f["x"] += f["vx"] * dt; f["a"] += f["sp"] * dt
            if f["y"] > H + 120:
                continue
            alive.append(f)
            if f["kind"] == "rock":
                sp = load_sprite("asteroid.png", target_size=(f["target"], f["target"]))
                if sp:
                    rot = pygame.transform.rotozoom(sp, math.degrees(f["a"]), 1.0)
                    rw, rh = rot.get_size()
                    s.blit(rot, (int(f["x"]) - rw // 2, int(f["y"]) - rh // 2))
            else:
                sp = load_sprite(sprite_map[f["kind"]], target_size=(f["target"], f["target"]))
                if sp:
                    rot = pygame.transform.rotozoom(sp, math.degrees(f["a"]), 1.0)
                    rw, rh = rot.get_size()
                    s.blit(rot, (int(f["x"]) - rw // 2, int(f["y"]) - rh // 2))
        self.floaters = alive
        while len(self.floaters) < 4:
            self._add_floater(False)

        # рамка дисплея внизу экрана — стала выше, чтобы поместить крупный портрет
        # --- иконка космонавта: отдельный блок слева, БЕЗ рамки ---
        # Оригинал 1112x607 (~1.83:1). Вписываем ПРОПОРЦИОНАЛЬНО в область
        # шириной ~180, высота посчитается сама (~98) → натуральные пропорции.
        icon_max_w = 150
        icon_x = 20
        try:
            import sys as _sys, os as _os
            base_dir = getattr(_sys, '_MEIPASS', _os.path.dirname(_os.path.abspath(__file__)))
            path = _os.path.join(base_dir, "assets", "astronaut.png")
            if _os.path.exists(path):
                cache_key = ("_astronaut_prop", icon_max_w)
                sp = SPRITE_CACHE.get(cache_key)
                if sp is None:
                    raw = pygame.image.load(path).convert_alpha()
                    iw, ih = raw.get_size()
                    scale = icon_max_w / iw
                    icon_w_r = icon_max_w
                    icon_h_r = int(ih * scale)
                    sp = pygame.transform.smoothscale(raw, (icon_w_r, icon_h_r))
                    SPRITE_CACHE[cache_key] = sp
                icon_w, icon_h = sp.get_size()
                icon_y = H - icon_h - 20
                s.blit(sp, (icon_x, icon_y))
            else:
                icon_w, icon_h = 180, 100
                icon_y = H - icon_h - 20
                draw_cosmonaut_icon(s, icon_x, icon_y, min(icon_w, icon_h))
        except Exception:
            icon_w, icon_h = 180, 100
            icon_y = H - icon_h - 20
            draw_cosmonaut_icon(s, icon_x, icon_y, min(icon_w, icon_h))

        # --- рамка ТОЛЬКО с текстом (справа от иконки), высота уменьшена вдвое ---
        frame_x = icon_x + icon_w + 16
        frame_h = 93
        frame_y = H - frame_h - 20       # у нижнего края, вровень с иконкой
        frame_w = W - frame_x - 20
        pygame.draw.rect(s, (10, 14, 28), (frame_x, frame_y, frame_w, frame_h))
        pygame.draw.rect(s, (50, 70, 110), (frame_x, frame_y, frame_w, frame_h), 2)
        # ретро-скан
        scan_y = frame_y + int((t * 30) % frame_h)
        pygame.draw.line(s, (40, 60, 90), (frame_x + 2, scan_y), (frame_x + frame_w - 2, scan_y), 1)

        # текст — во всю ширину рамки
        text_x = frame_x + 12
        text_y = frame_y + 10
        text_max_w = frame_w - 24        # доступная ширина под текст (для обрезки)
        line_h = 19
        plines = self._page_lines()

        # Word-wrap: разбить длинные строки под ширину рамки
        def wrap(line):
            if not line:
                return [""]
            words = line.split(" ")
            out = []
            cur = ""
            for w in words:
                trial = w if not cur else cur + " " + w
                if F_S.size(trial)[0] <= text_max_w:
                    cur = trial
                else:
                    if cur:
                        out.append(cur)
                    cur = w
            if cur:
                out.append(cur)
            return out

        # Строим список визуальных строк с учётом текущего прогресса печати
        vis_lines = []
        for i, full_line in enumerate(plines):
            if i > self.line_idx:
                break
            if i < self.line_idx:
                wrapped = wrap(full_line)
                vis_lines.extend(wrapped)
            else:  # i == self.line_idx — печатается сейчас
                partial = full_line[:self.char_idx]
                wrapped = wrap(partial)
                vis_lines.extend(wrapped)

        # ограничим количество отображаемых строк (минус место под подсказку внизу)
        max_visible = max(1, (frame_h - 34) // line_h)
        if len(vis_lines) > max_visible:
            vis_lines = vis_lines[-max_visible:]

        for idx, line in enumerate(vis_lines):
            if line:
                txt(s, line, F_S, (0, 255, 65), text_x, text_y + idx * line_h)

        # мигающий курсор — в конце последней видимой строки
        if not self.page_done or math.sin(self.blink * 5) > 0:
            cur_vis = vis_lines[-1] if vis_lines else ""
            cy = (len(vis_lines) - 1) if vis_lines else 0
            cw = F_S.size(cur_vis)[0] if cur_vis else 0
            pygame.draw.rect(s, (0, 255, 65), (text_x + cw + 2, text_y + cy * line_h, 8, 14))

        # подсказка внизу рамки
        if self.page_done:
            hint = "[ПРОБЕЛ] — продолжить" if not self.all_done else "[ПРОБЕЛ] — в бой!"
            pulse = 0.6 + 0.4 * math.sin(self.blink * 4)
            col = (int(170 * pulse), int(200 * pulse), int(160 * pulse))
            txt(s, hint, F_S, col, frame_x + frame_w // 2, frame_y + frame_h - 14, center=True)


TRACK_TITLES = [
    ("game_music.mp3",  "Штурм в тишине"),
    ("game_music2.mp3", "Протокол Космического Удара"),
    ("game_music3.mp3", "Наступление во тьме"),
    ("game_music4.mp3", "Вектор возмездия"),
    ("game_music5.mp3", "Дрейф в пустоте"),
    ("game_music6.mp3", "Звёздная аномалия"),
    ("menu_music.mp3",  "Сироты небес (главная тема)"),
]


def _play_preview(sfx, music_state, toggle=False):
    """Проигрывает трек-превью в разделе Об игре (использует _current)."""
    idx = _play_preview._idx
    fname = TRACK_TITLES[idx][0]
    if toggle and _play_preview._playing:
        sfx.stop_music()
        _play_preview._playing = False
        music_state["track"] = None
        return
    sfx.play_music(_resource_path(os.path.join("assets", fname)))
    _play_preview._playing = True
    music_state["track"] = "preview"
_play_preview._idx = 0
_play_preview._playing = False


SHOP = [("gun", "Фазеры", "Урон и доп. луч", 2000, 4),
        ("shield", "Дефлектор", "Поглощает попадания", 2000, 4),
        ("speed", "Импульс", "Манёвренность", 1800, 4),
        ("hp", "Корпус", "+1 жизнь", 2200, 4),
        ("heal", "Ремонт", "Восстановить жизнь", 300, 99),
        ("ammo", "Торпеды", "+20 торпед", 500, 99),
        ("mines", "Мины", "+10 мин", 400, 99)]


def shop_price(item, lvl):
    """L0→L1: база; далее ×1.6 за уровень. Расходники: фикс."""
    if item[4] <= 4:
        return int(item[3] * (1.6 ** lvl))   # 2000 → 3200 → 5120 → 8192
    return item[3]


def buy(g, iid):
    P = g.P
    for it in SHOP:
        if it[0] != iid:
            continue
        lvl = P.upg.get(iid, 0)
        if lvl >= it[4]:
            return
        price = shop_price(it, lvl)
        if g.cr < price:
            return
        g.cr -= price; g.sfx.play("menu")
        if iid == "heal":
            P.lives = min(P.max_lives, P.lives + 1)
        elif iid == "ammo":
            P.torp += 20
        elif iid == "mines":
            P.mines += 10
        else:
            P.upg[iid] += 1
            if iid == "shield":
                P.max_shield = P.upg["shield"] * 2; P.shield = P.max_shield
            if iid == "hp":
                P.max_lives = 5 + P.upg["hp"]; P.lives = min(P.lives + 1, P.max_lives)
        return


def main():
    global win
    settings = load_settings()
    sfx = SoundFX(settings.get("sound", True), settings.get("volume", 0.6), settings.get("music_vol", 0.55))

    # загружаем онлайн-рекорды с Supabase в фоне (не блокирует запуск)
    import threading
    threading.Thread(target=fetch_online_scores, args=(settings,), daemon=True).start()
    pad = None
    if pygame.joystick.get_count() > 0:
        pad = pygame.joystick.Joystick(0); pad.init()

    state = "menu"
    intro = None
    g = Game(settings, sfx)
    menu_sel = 0
    name_input = ""
    remap_action = None     # какое действие переназначаем
    msg = ""
    t = 0.0

    # фоновая музыка меню
    _music = {"track": None}   # None / "menu" / "game"
    def set_music(track):
        """track: 'menu', 'game' или None."""
        if _music["track"] == track:
            return
        _music["track"] = track
        if track == "menu":
            sfx.play_music(_resource_path(os.path.join("assets", "menu_music.mp3")))
        elif track == "game":
            # перемешанная очередь: трек не повторяется, пока не сыграют все
            if not _music.get("bag"):
                bag = ["game_music.mp3", "game_music2.mp3", "game_music3.mp3",
                       "game_music4.mp3", "game_music5.mp3", "game_music6.mp3"]
                random.shuffle(bag)
                # избегаем повтора последнего трека на стыке перемешиваний
                if _music.get("last") and bag[0] == _music["last"] and len(bag) > 1:
                    bag[0], bag[1] = bag[1], bag[0]
                _music["bag"] = bag
            fname = _music["bag"].pop(0)
            _music["last"] = fname
            sfx.play_music(_resource_path(os.path.join("assets", fname)))
        else:
            sfx.stop_music()
    def ensure_menu_music(want):   # совместимость со старым кодом
        set_music("menu" if want else None)
    set_music("menu")

    def menu_buttons():
        cx = W // 2
        CYAN = (0, 200, 240)
        BLUE = (60, 140, 220)
        RED  = (220, 70, 70)
        return [
            Button(cx - 130, 240, 260, 44, "ИГРАТЬ",    "play",    CYAN),
            Button(cx - 130, 292, 260, 38, "НАСТРОЙКИ", "settings",BLUE),
            Button(cx - 130, 338, 260, 38, "ОБ ИГРЕ",   "about",   BLUE),
            Button(cx - 130, 384, 260, 38, "РЕКОРДЫ",   "scores",  (200, 180, 0)),
            Button(cx - 130, 430, 260, 38, "ВЫХОД",     "quit",    RED),
        ]

    running = True
    while running:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)
        t += dt
        mouse = to_canvas(pygame.mouse.get_pos())
        mb = pygame.mouse.get_pressed()
        keys = pygame.key.get_pressed()
        
        # Автоматическое скрытие/показ курсора + захват мыши в окне
        if state == "play":
            pygame.mouse.set_visible(False)
            pygame.event.set_grab(True)    # мышь не выходит за окно → нет случайных кликов вне игры
        else:
            pygame.mouse.set_visible(True)
            pygame.event.set_grab(False)

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False

            elif e.type == pygame.VIDEORESIZE and not _fullscreen["on"]:
                win = pygame.display.set_mode((max(W, e.w), max(H, e.h)), pygame.RESIZABLE)

            elif e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
                toggle_fullscreen()

            elif e.type == pygame.JOYDEVICEADDED:
                pad = pygame.joystick.Joystick(e.device_index); pad.init()

            elif state == "intro":
                if e.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.JOYBUTTONDOWN):
                    if intro.skip():
                        g = Game(settings, sfx); g.start_wave(); state = "play"

            elif state == "menu":
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    for b in menu_buttons():
                        if b.hit(mouse):
                            sfx.play("menu")
                            act = b.action
                            if act == "play":
                                intro = IntroState(sfx)
                                state = "intro"
                            elif act == "diff":
                                order = ["easy", "normal", "hard"]
                                settings["difficulty"] = order[(order.index(settings["difficulty"]) + 1) % 3]
                                save_settings(settings)
                            elif act == "settings":
                                state = "settings"
                            elif act == "controls":
                                state = "controls"; remap_action = None
                            elif act == "fs":
                                toggle_fullscreen()
                            elif act == "sound":
                                settings["sound"] = not settings["sound"]; sfx.set_enabled(settings["sound"]); save_settings(settings)
                                _music["track"] = None
                                if settings["sound"]:
                                    set_music("menu")
                            elif act == "scores":
                                state = "scores"
                            elif act == "about":
                                state = "about"; g._about_track = 0
                            elif act == "quit":
                                running = False

            elif state == "settings":
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    state = "menu"
                elif e.type == pygame.MOUSEBUTTONDOWN:
                    cx = W // 2
                    rects = [pygame.Rect(cx - 130, 140 + i * 68, 260, 44) for i in range(4)]
                    back_r = pygame.Rect(cx - 100, 430, 200, 38)
                    if rects[0].collidepoint(mouse):
                        state = "controls"; remap_action = None
                    elif rects[1].collidepoint(mouse):
                        state = "sound_sub"
                    elif rects[2].collidepoint(mouse):
                        state = "screen_sub"
                    elif rects[3].collidepoint(mouse):
                        order = ["easy", "normal", "hard"]
                        settings["difficulty"] = order[(order.index(settings["difficulty"]) + 1) % 3]
                        save_settings(settings)
                    elif back_r.collidepoint(mouse):
                        state = "menu"

            elif state == "sound_sub":
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    state = "settings"
                elif e.type == pygame.MOUSEBUTTONDOWN:
                    cx = W // 2
                    snd_r = pygame.Rect(cx - 130, 120, 260, 44)
                    back_r = pygame.Rect(cx - 100, 380, 200, 40)
                    if snd_r.collidepoint(mouse):
                        settings["sound"] = not settings["sound"]
                        sfx.set_enabled(settings["sound"]); save_settings(settings)
                        _music["track"] = None
                        if settings["sound"]: set_music("menu")
                    elif back_r.collidepoint(mouse):
                        state = "settings"; save_settings(settings)
                    else:
                        for sy, key, is_music in [(230, "volume", False), (295, "music_vol", True)]:
                            track = pygame.Rect(cx - 150, sy, 300, 14)
                            if pygame.Rect(track.x, track.y - 10, track.w, 34).collidepoint(mouse):
                                v = max(0.0, min(1.0, (mouse[0] - track.x) / track.w))
                                settings[key] = v
                                if is_music: sfx.music_volume(v)
                                else: sfx.set_volume(v); sfx.play("shoot")
                                save_settings(settings)
                elif e.type == pygame.MOUSEMOTION and e.buttons[0]:
                    cx = W // 2
                    for sy, key, is_music in [(230, "volume", False), (295, "music_vol", True)]:
                        track = pygame.Rect(cx - 150, sy, 300, 14)
                        if pygame.Rect(track.x, track.y - 10, track.w, 34).collidepoint(mouse):
                            v = max(0.0, min(1.0, (mouse[0] - track.x) / track.w))
                            settings[key] = v
                            if is_music: sfx.music_volume(v)
                            else: sfx.set_volume(v)
                            save_settings(settings)

            elif state == "screen_sub":
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    state = "settings"
                elif e.type == pygame.MOUSEBUTTONDOWN:
                    cx = W // 2
                    fs_r = pygame.Rect(cx - 130, 180, 260, 48)
                    back_r = pygame.Rect(cx - 100, 310, 200, 40)
                    if fs_r.collidepoint(mouse):
                        toggle_fullscreen()
                    elif back_r.collidepoint(mouse):
                        state = "settings"

            elif state == "controls":
                mode = settings.get("input_mode", "keyboard")
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        state = "settings"; remap_action = None
                    elif remap_action and mode == "keyboard":
                        settings["keys"][remap_action] = pygame.key.name(e.key)
                        save_settings(settings); remap_action = None
                elif e.type == pygame.JOYBUTTONDOWN and remap_action and mode == "gamepad":
                    settings.setdefault("pad", dict(DEFAULT_PAD))[remap_action] = e.button
                    save_settings(settings); remap_action = None
                elif e.type == pygame.MOUSEBUTTONDOWN:
                    # переключатель режима
                    kb_r = pygame.Rect(W // 2 - 180, 74, 175, 30)
                    gp_r = pygame.Rect(W // 2 + 5, 74, 175, 30)
                    if kb_r.collidepoint(mouse):
                        settings["input_mode"] = "keyboard"; save_settings(settings); remap_action = None
                    elif gp_r.collidepoint(mouse):
                        settings["input_mode"] = "gamepad"; save_settings(settings); remap_action = None
                    elif remap_action and mode == "keyboard":
                        mn = {1: "mouse_left", 2: "mouse_middle", 3: "mouse_right"}.get(e.button)
                        if mn:
                            settings["keys"][remap_action] = mn; save_settings(settings); remap_action = None
                    else:
                        if mode == "keyboard":
                            actions = list(DEFAULT_KEYS.keys()); y0, rowh = 138, 32
                        else:
                            actions = list(DEFAULT_PAD.keys()); y0, rowh = 138, 34
                        clicked = False
                        for i, a in enumerate(actions):
                            r = pygame.Rect(W // 2 - 180, y0 + i * rowh, 360, 28 if mode == "keyboard" else 30)
                            if r.collidepoint(mouse):
                                remap_action = a; clicked = True
                        if not clicked and mouse[1] > y0 + len(actions) * rowh:
                            state = "settings"; remap_action = None

            elif state == "scores":
                if (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE) or e.type == pygame.MOUSEBUTTONDOWN:
                    state = "menu"

            elif state == "about":
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    state = "menu"; set_music("menu"); _music["track"] = "menu"
                elif e.type == pygame.MOUSEBUTTONDOWN:
                    # кнопки плеера и назад
                    for r, act in g._about_btns:
                        if r.collidepoint(mouse):
                            if act == "back":
                                state = "menu"; set_music("menu"); _music["track"] = "menu"
                            elif act == "prev":
                                g._about_track = (g._about_track - 1) % len(TRACK_TITLES)
                                _play_preview._idx = g._about_track
                                _play_preview(sfx, _music)
                            elif act == "next":
                                g._about_track = (g._about_track + 1) % len(TRACK_TITLES)
                                _play_preview._idx = g._about_track
                                _play_preview(sfx, _music)
                            elif act == "playpause":
                                _play_preview._idx = g._about_track
                                _play_preview(sfx, _music, toggle=True)
                            break
                    else:
                        pass
                # прокрутка треков стиком геймпада
                elif e.type == pygame.JOYHATMOTION and e.value[0] != 0:
                    g._about_track = (g._about_track + (1 if e.value[0] > 0 else -1)) % len(TRACK_TITLES)
                    _play_preview._idx = g._about_track
                    _play_preview(sfx, _music)

            elif state == "play":
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        state = "pause"
                        continue
                    # чит-коды: Shift+Ctrl+Alt + 1-5 = прыжок к уровню
                    mods = pygame.key.get_mods()
                    if (mods & pygame.KMOD_SHIFT) and (mods & pygame.KMOD_CTRL) and (mods & pygame.KMOD_ALT):
                        cheat_map = {pygame.K_1: 1, pygame.K_2: 6, pygame.K_3: 11, pygame.K_4: 16, pygame.K_5: 21}
                        if e.key in cheat_map:
                            g = Game(settings, sfx)
                            g.wave = cheat_map[e.key]
                            g.cr = [0, 5000, 15000, 35000, 70000][(e.key - pygame.K_1)]
                            # сразу станция для закупки
                            g.sta = {"x": W // 2, "y": 120, "r": 34, "sty": random.randint(0, 2)}
                            g.wT = 8  # пауза перед волной
                            g.start_wave()
                    kc = settings["keys"]
                    kn = pygame.key.name(e.key)
                    if kn == kc.get("dock", "e") and g.P.near:
                        state = "dock"; g.dock_t = 0; g._shop_sel = 0; g.sfx.play("dock")
                    if kc.get("mine") and not kc["mine"].startswith("mouse_") and kn == kc["mine"]:
                        g.drop_mine()
                    if kc.get("torpedo") and not kc["torpedo"].startswith("mouse_") and kn == kc["torpedo"]:
                        g.fire_torpedo()
                elif e.type == pygame.MOUSEBUTTONDOWN:
                    kc = settings["keys"]
                    mn = {1: "mouse_left", 2: "mouse_middle", 3: "mouse_right"}.get(e.button)
                    if mn and kc.get("mine") == mn:
                        g.drop_mine()
                    elif mn and kc.get("torpedo") == mn:
                        g.fire_torpedo()
                elif e.type == pygame.JOYBUTTONDOWN:
                    pad_cfg = settings.get("pad", DEFAULT_PAD)
                    if e.button == 7:   # Start = пауза
                        state = "pause"; _menu_sel[0] = 0
                    elif e.button == pad_cfg.get("mine", 1):
                        g.drop_mine()
                    elif e.button == pad_cfg.get("torpedo", 2):
                        g.fire_torpedo()
                    elif e.button == pad_cfg.get("dock", 3) and g.P.near:
                        state = "dock"; g.dock_t = 0; g._shop_sel = 0

            elif state == "pause":
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        state = "play"
                    elif e.key == pygame.K_q:
                        state = "menu"
                elif e.type == pygame.JOYBUTTONDOWN:
                    if e.button in (0, 7):   # A или Start — выбрать
                        if _menu_sel[0] == 0:
                            state = "play"
                        else:
                            state = "menu"
                    elif e.button == 1:      # B — продолжить
                        state = "play"
                elif e.type == pygame.JOYHATMOTION:
                    if e.value[1] != 0:
                        _menu_sel[0] = (_menu_sel[0] + (1 if e.value[1] < 0 else -1)) % 2
                elif e.type == pygame.JOYAXISMOTION and e.axis == 1:
                    if abs(e.value) > 0.6:
                        _menu_sel[0] = 1 if e.value > 0 else 0
                elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    if pygame.Rect(W//2 - 100, H//2 - 10, 200, 40).collidepoint(mouse):
                        state = "play"
                    elif pygame.Rect(W//2 - 100, H//2 + 40, 200, 40).collidepoint(mouse):
                        state = "menu"

            elif state == "dock":
                if e.type == pygame.KEYDOWN and pygame.key.name(e.key) == settings["keys"].get("dock", "e"):
                    state = "play"
                elif e.type == pygame.JOYBUTTONDOWN:
                    pad_cfg = settings.get("pad", DEFAULT_PAD)
                    if e.button == pad_cfg.get("dock", 3):   # Y = расстыковка
                        state = "play"
                    elif e.button == 0:   # A = купить выбранный
                        if hasattr(g, '_shop_sel'):
                            btns = g._shop_btns
                            if 0 <= g._shop_sel < len(btns):
                                if btns[g._shop_sel][1] == "leave":
                                    state = "play"
                                else:
                                    buy(g, btns[g._shop_sel][1])
                elif e.type == pygame.JOYHATMOTION:
                    if e.value[1] != 0 and hasattr(g, '_shop_btns'):
                        n = len(g._shop_btns)
                        if not hasattr(g, '_shop_sel'): g._shop_sel = 0
                        g._shop_sel = (g._shop_sel + (-1 if e.value[1] > 0 else 1)) % n
                elif e.type == pygame.JOYAXISMOTION and e.axis == 1:
                    if abs(e.value) > 0.6 and hasattr(g, '_shop_btns'):
                        n = len(g._shop_btns)
                        if not hasattr(g, '_shop_sel'): g._shop_sel = 0
                        g._shop_sel = (g._shop_sel + (1 if e.value > 0 else -1)) % n
                elif e.type == pygame.MOUSEBUTTONDOWN:
                    for b in g._shop_btns:
                        if b[0].collidepoint(mouse):
                            if b[1] == "leave":
                                state = "play"
                            else:
                                buy(g, b[1])

            elif state == "dead":
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_RETURN:
                        if is_highscore(settings, g.score):
                            add_highscore(settings, name_input or "PILOT", g.score, g.wave)
                        state = "menu"; name_input = ""
                    elif e.key == pygame.K_BACKSPACE:
                        name_input = name_input[:-1]
                    elif len(name_input) < 12 and e.unicode.isprintable():
                        name_input += e.unicode

            elif state == "won":
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_RETURN:
                        if is_highscore(settings, g.score):
                            add_highscore(settings, name_input or "PILOT", g.score, g.wave)
                        state = "menu"; name_input = ""
                    elif e.key == pygame.K_BACKSPACE:
                        name_input = name_input[:-1]
                    elif len(name_input) < 12 and e.unicode.isprintable():
                        name_input += e.unicode

        # ---- музыка по состоянию ----
        if state in ("play", "pause"):
            set_music("game")
        elif state == "about":
            pass   # в разделе Об игре музыкой управляет плеер-превью
        else:
            set_music("menu")

        # ---- обновление и отрисовка по состоянию ----
        if state == "intro":
            intro.update(dt)
            intro.draw(screen, t)

        elif state == "play":
            res = g.update(dt, keys, mb, pad)
            if g.P.lives <= 0:
                state = "dead"; name_input = ""
            elif res == "won":
                state = "won"; name_input = ""
            render_game(screen, g, t)

        elif state == "dock":
            g.dock_t = getattr(g, "dock_t", 0) + dt
            render_dock(screen, g, t)

        elif state == "menu":
            tick_stars(dt, 380)
            draw_title_bg(screen, t)
            txt(screen, "ЗОНА РИСКА", F_XL, WHITE, W // 2, 150, center=True)
            for b in menu_buttons():
                b.draw(screen, b.hit(mouse))

        elif state == "pause":
            render_game(screen, g, t)
            # затемнение
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 160))
            screen.blit(ov, (0, 0))
            txt(screen, "ПАУЗА", F_XL, WHITE, W // 2, H // 2 - 80, center=True)
            txt(screen, "ESC — продолжить · Q — в меню", F_S, (170, 180, 200), W // 2, H // 2 - 30, center=True)
            pygame.draw.rect(screen, (26, 32, 42), pygame.Rect(W // 2 - 100, H // 2 - 10, 200, 40), border_radius=8)
            pygame.draw.rect(screen, GREEN, pygame.Rect(W // 2 - 100, H // 2 - 10, 200, 40), 1, border_radius=8)
            txt(screen, "Продолжить", F_M, GREEN, W // 2, H // 2 + 10, center=True)
            pygame.draw.rect(screen, (26, 32, 42), pygame.Rect(W // 2 - 100, H // 2 + 40, 200, 40), border_radius=8)
            pygame.draw.rect(screen, RED, pygame.Rect(W // 2 - 100, H // 2 + 40, 200, 40), 1, border_radius=8)
            txt(screen, "В меню", F_M, RED, W // 2, H // 2 + 60, center=True)

        elif state == "settings":
            render_settings(screen, settings, mouse)

        elif state == "sound_sub":
            render_sound(screen, settings, mouse)

        elif state == "screen_sub":
            render_screen_sub(screen, settings, mouse)

        elif state == "controls":
            render_controls(screen, settings, remap_action, mouse)

        elif state == "scores":
            render_scores(screen, settings)

        elif state == "about":
            render_about(screen, g, t)

        elif state == "dead":
            render_game(screen, g, t)
            render_end(screen, g, "КОРАБЛЬ ПОТЕРЯН", RED, name_input, settings)

        elif state == "won":
            render_game(screen, g, t)
            render_end(screen, g, "ЗОНА РИСКА ПРОЙДЕНА!", GREEN, name_input, settings)

        present()

    save_settings(settings)
    pygame.quit()
    sys.exit()


def render_dock(s, g, t):
    s.fill((4, 6, 13))
    pygame.draw.rect(s, (12, 21, 32), (8, 8, W - 16, 34), border_radius=10)
    txt(s, "◈ ОРБИТАЛЬНАЯ ВЕРФЬ", F_M, (159, 225, 203), 22, 14)
    txt(s, f"cr: {g.cr}", F_M, GOLD, W - 22, 14, right=True)
    P = g.P
    txt(s, f"Жизни {P.lives}/{P.max_lives}   Щит {int(P.shield)}/{P.max_shield}   Торпеды {P.torp}   Мины {P.mines}",
        F_S, (170, 187, 204), 22, 54)
    g._shop_btns = []
    rx, rw, y0, rh, gap = 22, W - 44, 74, 48, 3
    for i, it in enumerate(SHOP):
        iid, name, desc, base, maxl = it
        lvl = P.upg.get(iid, 0)
        ry = y0 + i * (rh + gap)
        maxed = lvl >= maxl
        price = shop_price(it, lvl)
        afford = g.cr >= price
        pygame.draw.rect(s, (13, 17, 25), (rx, ry, rw, rh), border_radius=9)
        pygame.draw.rect(s, (42, 51, 68), (rx, ry, rw, rh), 1, border_radius=9)
        shop_icon(s, iid, rx + 26, ry + 24)
        suffix = f"  ({lvl}/{maxl})" if maxl <= 4 and lvl > 0 else ""
        txt(s, name + suffix, F_M, WHITE, rx + 52, ry + 6)
        txt(s, desc, F_S, (122, 130, 144), rx + 52, ry + 28)
        txt(s, "МАКС" if maxed else f"{price} cr", F_S, (119, 119, 119) if maxed else (GOLD if afford else (165, 85, 85)),
            rx + rw - 110, ry + 16, right=True)
        bw, bh = 90, 26
        br = pygame.Rect(rx + rw - bw - 10, ry + (rh - bh) // 2, bw, bh)
        en = (not maxed) and afford
        pygame.draw.rect(s, (28, 58, 48) if en else (19, 23, 31), br, border_radius=7)
        pygame.draw.rect(s, (93, 202, 165) if en else (51, 51, 51), br, 1, border_radius=7)
        txt(s, "макс" if maxed else ("купить" if afford else "мало"), F_S,
            (159, 225, 203) if en else (85, 85, 85), br.centerx, br.centery, center=True)
        if en:
            g._shop_btns.append((br, iid))
    lb = pygame.Rect(rx, y0 + len(SHOP) * (rh + gap) + 4, rw, 34)
    pygame.draw.rect(s, (16, 19, 26), lb, border_radius=8)
    pygame.draw.rect(s, (159, 225, 203), lb, 1, border_radius=8)
    txt(s, "Расстыковка (E)", F_M, (159, 225, 203), lb.centerx, lb.centery, center=True)
    g._shop_btns.append((lb, "leave"))


def shop_icon(s, iid, x, y):
    if iid == "gun":
        pygame.draw.line(s, (159, 225, 203), (x - 5, y + 8), (x - 5, y - 8), 2)
        pygame.draw.line(s, (159, 225, 203), (x + 5, y + 8), (x + 5, y - 8), 2)
    elif iid == "shield":
        pygame.draw.arc(s, (133, 183, 235), (x - 9, y - 6, 18, 18), 3.6, 5.8, 2)
    elif iid == "speed":
        for o in (-6, 0, 6):
            pygame.draw.lines(s, (159, 225, 203), False, [(x + o - 3, y - 7), (x + o + 3, y), (x + o - 3, y + 7)], 2)
    elif iid == "hp":
        pygame.draw.polygon(s, (174, 184, 196), [(x, y - 9), (x + 8, y - 3), (x + 8, y + 6), (x, y + 9), (x - 8, y + 6), (x - 8, y - 3)], 1)
    elif iid == "heal":
        pygame.draw.rect(s, GREEN, (x - 3, y - 9, 6, 18)); pygame.draw.rect(s, GREEN, (x - 9, y - 3, 18, 6))
    elif iid == "ammo":
        pygame.draw.ellipse(s, GOLD, (x - 4, y - 9, 8, 16))
    elif iid == "mines":
        pygame.draw.circle(s, (200, 60, 50), (x, y), 7)
        for a in range(8):
            ang = a / 8 * 6.28
            pygame.draw.line(s, (150, 40, 35), (x, y),
                             (int(x + math.cos(ang) * 10), int(y + math.sin(ang) * 10)), 2)
        pygame.draw.circle(s, (255, 220, 60), (x, y), 3)


PAD_BTN_NAMES = {0: "A", 1: "B", 2: "X", 3: "Y", 4: "LB", 5: "RB",
                 6: "Back", 7: "Start", 8: "LS", 9: "RS"}


def render_settings(s, settings, mouse):
    draw_stars(s, 90)
    txt(s, "НАСТРОЙКИ", F_L, (0, 200, 240), W // 2, 50, center=True)
    cx = W // 2
    items = [
        ("УПРАВЛЕНИЕ",                                        "controls",   (60, 140, 220)),
        ("ЗВУК",                                              "sound_sub",  (0, 200, 240)),
        ("ЭКРАН",                                             "screen_sub", (60, 140, 220)),
        ("СЛОЖНОСТЬ: " + DIFF_NAME[settings["difficulty"]],  "diff",       (180, 140, 0)),
    ]
    btns = []
    for i, (lbl, act, col) in enumerate(items):
        r = pygame.Rect(cx - 130, 140 + i * 68, 260, 44)
        b = Button(r.x, r.y, r.w, r.h, lbl, act, col)
        b.draw(s, r.collidepoint(mouse))
        btns.append(r)

    back_r = pygame.Rect(cx - 100, 430, 200, 38)
    b_back = Button(back_r.x, back_r.y, back_r.w, back_r.h, "Назад (Esc)", "back_menu", (159, 225, 203))
    b_back.draw(s, back_r.collidepoint(mouse))
    return btns, back_r


def render_sound(s, settings, mouse):
    """Подменю настроек звука."""
    draw_stars(s, 90)
    txt(s, "ЗВУК", F_L, (0, 220, 255), W // 2, 50, center=True)
    cx = W // 2

    # тумблер звука
    snd_r = pygame.Rect(cx - 130, 120, 260, 44)
    on = settings.get("sound", True)
    col = (0, 200, 100) if on else (200, 60, 60)
    b = Button(snd_r.x, snd_r.y, snd_r.w, snd_r.h,
               "ЗВУК: ВКЛ" if on else "ЗВУК: ВЫКЛ", "sound_toggle", col)
    b.draw(s, snd_r.collidepoint(mouse))

    # ползунки
    def slider(y, label, val, col):
        txt(s, label, F_S, (180, 190, 210), cx - 150, y - 22)
        track = pygame.Rect(cx - 150, y, 300, 14)
        pygame.draw.rect(s, (20, 26, 38), track, border_radius=7)
        fw = int(300 * val)
        pygame.draw.rect(s, col, (track.x, track.y, fw, 14), border_radius=7)
        hx = track.x + fw
        pygame.draw.circle(s, (240, 248, 255), (hx, track.y + 7), 10)
        pygame.draw.circle(s, col, (hx, track.y + 7), 10, 2)
        txt(s, f"{int(val * 100)}%", F_S, WHITE, track.right + 44, y - 2, right=True)

    slider(230, "Громкость эффектов", settings.get("volume", 0.6), (133, 183, 235))
    slider(295, "Громкость музыки",   settings.get("music_vol", 0.55), (200, 130, 220))

    back_r = pygame.Rect(cx - 100, 380, 200, 40)
    b2 = Button(back_r.x, back_r.y, back_r.w, back_r.h, "Назад (Esc)", "back", (159, 225, 203))
    b2.draw(s, back_r.collidepoint(mouse))
    return snd_r, back_r


def render_screen_sub(s, settings, mouse):
    """Подменю настроек экрана."""
    draw_stars(s, 90)
    txt(s, "ЭКРАН", F_L, (0, 220, 255), W // 2, 50, center=True)
    cx = W // 2

    fs_r = pygame.Rect(cx - 130, 180, 260, 48)
    fs_on = _fullscreen["on"]
    col = (0, 220, 255) if fs_on else (60, 160, 255)
    b = Button(fs_r.x, fs_r.y, fs_r.w, fs_r.h,
               "ПОЛНЫЙ ЭКРАН: ВКЛ" if fs_on else "ПОЛНЫЙ ЭКРАН: ВЫКЛ", "fs", col)
    b.draw(s, fs_r.collidepoint(mouse))

    back_r = pygame.Rect(cx - 100, 310, 200, 40)
    b2 = Button(back_r.x, back_r.y, back_r.w, back_r.h, "Назад (Esc)", "back", (159, 225, 203))
    b2.draw(s, back_r.collidepoint(mouse))
    return fs_r, back_r


def render_controls(s, settings, remap_action, mouse):
    draw_stars(s, 90)
    mode = settings.get("input_mode", "keyboard")
    txt(s, "УПРАВЛЕНИЕ", F_L, WHITE, W // 2, 40, center=True)

    # переключатель режима
    kb_r = pygame.Rect(W // 2 - 180, 74, 175, 30)
    gp_r = pygame.Rect(W // 2 + 5, 74, 175, 30)
    for r, m, lbl in [(kb_r, "keyboard", "КЛАВИАТУРА"), (gp_r, "gamepad", "ГЕЙМПАД")]:
        on = mode == m
        pygame.draw.rect(s, (40, 60, 90) if on else (16, 19, 26), r, border_radius=6)
        pygame.draw.rect(s, (120, 200, 255) if on else (60, 70, 84), r, 2 if on else 1, border_radius=6)
        txt(s, lbl, F_S, WHITE if on else (120, 130, 144), r.centerx, r.centery, center=True)

    if mode == "keyboard":
        txt(s, "клик по действию → нажми новую клавишу/кнопку мыши", F_S, (160, 170, 187), W // 2, 118, center=True)
        labels = {"up": "Вперёд", "down": "Назад", "left": "Влево", "right": "Вправо",
                  "fire": "Огонь", "mine": "Мина", "torpedo": "Торпеда", "dock": "Стыковка", "boost": "Форсаж"}
        actions = list(DEFAULT_KEYS.keys())
        y0, rowh = 138, 32
        for i, a in enumerate(actions):
            r = pygame.Rect(W // 2 - 180, y0 + i * rowh, 360, 28)
            hov = r.collidepoint(mouse); active = remap_action == a
            pygame.draw.rect(s, (40, 30, 18) if active else ((26, 32, 42) if hov else (16, 19, 26)), r, border_radius=6)
            pygame.draw.rect(s, AMBER if active else (60, 70, 84), r, 1, border_radius=6)
            txt(s, labels[a], F_S, WHITE, r.x + 14, r.y + 6)
            val = "нажми клавишу..." if active else key_label(settings["keys"].get(a, DEFAULT_KEYS[a]))
            txt(s, val, F_S, AMBER if active else (159, 225, 203), r.right - 14, r.y + 6, right=True)
        back_y = y0 + len(actions) * rowh + 10
    else:
        txt(s, "клик по действию → нажми кнопку геймпада", F_S, (160, 170, 187), W // 2, 118, center=True)
        labels = {"fire": "Огонь", "mine": "Мина", "torpedo": "Торпеда", "dock": "Стыковка", "boost": "Форсаж"}
        actions = list(DEFAULT_PAD.keys())
        pad = settings.get("pad", DEFAULT_PAD)
        y0, rowh = 138, 34
        for i, a in enumerate(actions):
            r = pygame.Rect(W // 2 - 180, y0 + i * rowh, 360, 30)
            hov = r.collidepoint(mouse); active = remap_action == a
            pygame.draw.rect(s, (40, 30, 18) if active else ((26, 32, 42) if hov else (16, 19, 26)), r, border_radius=6)
            pygame.draw.rect(s, AMBER if active else (60, 70, 84), r, 1, border_radius=6)
            txt(s, labels[a], F_S, WHITE, r.x + 14, r.y + 7)
            btn = pad.get(a, DEFAULT_PAD[a])
            val = "нажми кнопку..." if active else PAD_BTN_NAMES.get(btn, f"Кн.{btn}")
            txt(s, val, F_S, AMBER if active else (159, 225, 203), r.right - 14, r.y + 7, right=True)
        txt(s, "движение — левый стик / крестовина", F_S, (120, 130, 144), W // 2, y0 + len(actions) * rowh + 6, center=True)
        back_y = y0 + len(actions) * rowh + 28

    back = pygame.Rect(W // 2 - 90, back_y, 180, 34)
    pygame.draw.rect(s, (16, 19, 26), back, border_radius=8)
    pygame.draw.rect(s, (159, 225, 203), back, 1, border_radius=8)
    txt(s, "Назад (Esc)", F_S, (159, 225, 203), back.centerx, back.centery, center=True)


def render_about(s, g, t):
    draw_stars(s, 90)

    cx = W // 2
    # логотип вверху
    icon = load_sprite("icon.png", target_size=(80, 80))
    if icon:
        s.blit(icon, (cx - 40, 30))
    txt(s, "ЗОНА РИСКА", F_L, (159, 225, 203), cx, 120, center=True)

    # авторы
    y = 178
    txt(s, "Авторы: James Rocket & Claude AI", F_S, (200, 210, 230), cx, y, center=True); y += 22
    txt(s, "Музыка: Orphans of the sky (remix Suno)", F_S, (200, 210, 230), cx, y, center=True); y += 36

    # ---- плеер треков ----
    idx = getattr(g, "_about_track", 0)
    _play_preview._idx = idx
    title = TRACK_TITLES[idx][1]
    # рамка плеера с пульсацией при воспроизведении
    playing = _play_preview._playing
    pulse = 0.5 + 0.5 * math.sin(t * 3) if playing else 0
    br_col = (int(40 + pulse * 30), int(70 + pulse * 40), int(120 + pulse * 50))
    pygame.draw.rect(s, (10, 16, 28), (cx - 220, y, 440, 88), border_radius=14)
    pygame.draw.rect(s, br_col, (cx - 220, y, 440, 88), 2, border_radius=14)
    txt(s, "ФОНОТЕКА", F_S, (100, 130, 180), cx, y + 12, center=True)
    # название трека с мягким свечением
    t_col = (255, 230, 150) if not playing else (int(200 + pulse * 55), int(200 + pulse * 55), int(100 + pulse * 80))
    txt(s, title, F_M, t_col, cx, y + 36, center=True)
    txt(s, f"{idx + 1} / {len(TRACK_TITLES)}", F_S, (110, 120, 140), cx, y + 62, center=True)

    g._about_btns = []
    by = y + 100
    # стильные кнопки — без стрелочек, с иконками и подсветкой
    btn_w, btn_h = 90, 38
    gap = 14
    total = btn_w * 3 + gap * 2
    bx = cx - total // 2

    buttons = [
        (pygame.Rect(bx, by, btn_w, btn_h), "ПРЕД.", "prev", (80, 140, 200)),
        (pygame.Rect(bx + btn_w + gap, by, btn_w, btn_h),
         "СТОП" if playing else "СЛУШАТЬ", "playpause",
         (200, 90, 90) if playing else (60, 180, 130)),
        (pygame.Rect(bx + (btn_w + gap) * 2, by, btn_w, btn_h), "СЛЕД.", "next", (80, 140, 200)),
    ]
    mouse_pos = pygame.mouse.get_pos()
    for r, lbl, act, col in buttons:
        hov = r.collidepoint(mouse_pos)
        # фон кнопки с градиентом
        bg = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        base_a = 90 if hov else 50
        pygame.draw.rect(bg, (*col, base_a), (0, 0, r.w, r.h), border_radius=10)
        s.blit(bg, r.topleft)
        # рамка
        pygame.draw.rect(s, col if hov else tuple(c // 2 for c in col), r, 2, border_radius=10)
        txt(s, lbl, F_S, (255, 255, 255) if hov else col, r.centerx, r.centery, center=True)
        g._about_btns.append((r, act))

    # назад
    back = pygame.Rect(cx - 100, by + 56, 200, 38)
    hov_b = back.collidepoint(mouse_pos)
    pygame.draw.rect(s, (20, 26, 36) if hov_b else (12, 16, 22), back, border_radius=10)
    pygame.draw.rect(s, (159, 225, 203) if hov_b else (80, 110, 95), back, 1, border_radius=10)
    txt(s, "Назад (Esc)", F_S, (159, 225, 203), back.centerx, back.centery, center=True)
    g._about_btns.append((back, "back"))


def render_scores(s, settings):
    draw_stars(s, 90)
    txt(s, "РЕКОРДЫ", F_L, AMBER, W // 2, 36, center=True)
    # онлайн-индикатор
    dot_col = (60, 220, 120)
    pygame.draw.circle(s, dot_col, (W // 2 + 95, 44), 5)
    txt(s, "онлайн", F_S, dot_col, W // 2 + 104, 38)
    hs = settings.get("highscores", [])
    if not hs:
        txt(s, "пока пусто — стань первым!", F_M, (160, 170, 187), W // 2, 200, center=True)
    row_h = 24
    for i, r in enumerate(hs[:20]):
        y = 76 + i * row_h
        # подсветка топ-3
        if i == 0:   col = (255, 215, 60)
        elif i == 1: col = (200, 200, 200)
        elif i == 2: col = (200, 140, 80)
        else:        col = (180, 185, 200)
        txt(s, f"{i+1:2}.", F_S, (120, 130, 144), W // 2 - 195, y)
        txt(s, r["name"], F_S, col, W // 2 - 165, y)
        txt(s, f"{r['score']}", F_S, GOLD, W // 2 + 90, y, right=True)
        txt(s, f"сектор {r['sector']}", F_S, (133, 183, 235), W // 2 + 195, y, right=True)
    txt(s, "клик / Esc — назад", F_S, (120, 130, 144), W // 2, H - 30, center=True)


def render_end(s, g, title, col, name_input, settings):
    ov = pygame.Surface((W, H), pygame.SRCALPHA); ov.fill((0, 2, 14, 200)); s.blit(ov, (0, 0))
    txt(s, title, F_L, col, W // 2, H // 2 - 110, center=True)
    txt(s, f"Очки: {g.score}    Сектор: {g.wave}", F_M, WHITE, W // 2, H // 2 - 60, center=True)
    if is_highscore(settings, g.score):
        txt(s, "НОВЫЙ РЕКОРД! Введи имя:", F_M, AMBER, W // 2, H // 2 - 16, center=True)
        box = pygame.Rect(W // 2 - 130, H // 2 + 14, 260, 40)
        pygame.draw.rect(s, (16, 19, 26), box, border_radius=8)
        pygame.draw.rect(s, AMBER, box, 1, border_radius=8)
        cursor = "_" if int(pygame.time.get_ticks() / 400) % 2 == 0 else " "
        txt(s, (name_input or "") + cursor, F_M, WHITE, box.centerx, box.centery, center=True)
        txt(s, "Enter — сохранить", F_S, (160, 170, 187), W // 2, H // 2 + 70, center=True)
    else:
        txt(s, "Enter — в меню", F_S, (160, 170, 187), W // 2, H // 2 + 20, center=True)


if __name__ == "__main__":
    main()