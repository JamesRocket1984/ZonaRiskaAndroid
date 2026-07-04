"""
ЗОНА РИСКА — игровые сущности и отрисовка.
v9: 12 типов врагов с разными атаками, 5 уникальных боссов разной формы,
без HP-полос на врагах, рой-эскорт у крупных кораблей.
"""
import math
import random

import pygame

# Палитра
WHITE = (255, 255, 255)
SHIP_FILL = (215, 221, 228)
SHIP_LINE = (170, 178, 189)
NACELLE = (174, 184, 196)
GLOW_BLUE = (55, 138, 221)
GOLD = (239, 159, 39)
AMBER = (250, 199, 117)
RED = (226, 75, 74)
GREEN = (93, 202, 165)
SHIELD_C = (94, 170, 235)

ENEMY_COL = [
    (212, 83, 126),   # 0 SCOUT
    (224, 138, 58),   # 1 GUNNER
    (142, 107, 216),  # 2 CRUISER
    (107, 216, 158),  # 3 RAIDER
    (91, 143, 216),   # 4 WARDEN
    (226, 75, 74),    # 5 KAMIKAZE
    (255, 110, 200),  # 6 PLASMER
    (180, 220, 255),  # 7 STORMER
    (200, 255, 200),  # 8 ECHOER
    (255, 200, 80),   # 9 SCATTERER
    (150, 100, 60),   # 10 MINER
    (255, 180, 240),  # 11 MOTHERSHIP
    (255, 80, 80),    # 12 HYBRID
]

ENEMY_NAME = ["SCOUT", "GUNNER", "CRUISER", "RAIDER", "WARDEN", "KAMIKAZE",
              "PLASMER", "STORMER", "ECHOER", "SCATTERER", "MINER",
              "MOTHERSHIP", "HYBRID"]

# Параметры врагов: type, min_wave, base_hp, speed, sz, base_reward, hp_per_wave, rw_per_wave, atk
#                                                                                    
# ЛВЛ 1 (секторы 1-5):  SCOUT(1), RAIDER(2), CRUISER(4)
# ЛВЛ 2 (секторы 6-10): KAMIKAZE(6), GUNNER(8), PLASMER(9)
# ЛВЛ 3 (секторы 11-15): SCATTERER(11), WARDEN(13), STORMER(14)
# ЛВЛ 4 (секторы 16-20): ECHOER(16), MINER(18)
# ЛВЛ 5 (секторы 21-25): MOTHERSHIP(21), HYBRID(23)
ENEMY_STATS = [
    (0,  1,  18,  78,  14, 3,  6,  1,  "l"),     # SCOUT — лазер
    (1,  11, 100, 48,  18, 8,  16, 3,  "lh"),    # GUNNER — тяж.лазер клин (лвл3, HP от WARDEN)
    (2,  4,  130, 32,  26, 22, 26, 5,  "m"),     # CRUISER — ракета
    (3,  2,  14,  115, 11, 4,  4,  2,  "ram"),   # RAIDER — таран (шарики только у матки/босса)
    (4,  13, 60,  28,  24, 30, 22, 6,  "lm"),    # WARDEN — лазер+ракета, щит (сектор 13, лвл3)
    (5,  6,  22,  60,  13, 7,  5,  2,  "ram"),   # KAMIKAZE — рывок
    (6,  6,  50,  40,  18, 12, 14, 4,  "p"),     # PLASMER — плазма-шар (сектор 6, лвл2)
    (7,  14, 70,  36,  20, 16, 16, 4,  "z"),     # STORMER — молния (конец лвл3)
    (8,  16, 90,  30,  22, 20, 18, 5,  "u"),     # ECHOER — ультразвук (лвл4)
    (9,  16, 80,  40,  20, 18, 16, 4,  "f"),     # SCATTERER — веер (лвл4, кд 7с, max 1)
    (10, 18, 120, 32,  22, 22, 20, 5,  "om"),    # MINER — мины (лвл4)
    (11, 21, 220, 24,  30, 40, 30, 8,  "esc"),   # MOTHERSHIP — рой (лвл5)
    (12, 23, 140, 38,  24, 28, 24, 6,  "lm2"),   # HYBRID — залп+ракета (лвл5)
]


def rotpoly(ctx_pts, cx, cy, ang):
    out = []
    ca, sa = math.cos(ang), math.sin(ang)
    for px, py in ctx_pts:
        out.append((cx + px * ca - py * sa, cy + px * sa + py * ca))
    return out


def enemy_reward(etype, wave):
    s = ENEMY_STATS[etype]
    return s[5] + wave * s[6]


def pick_enemy_type(wave):
    pool = [s[0] for s in ENEMY_STATS if s[1] <= wave]
    weights = []
    for et in pool:
        bhp = ENEMY_STATS[et][2]
        w = max(0.6, 3.0 - bhp / 60)
        if et in (3, 5):
            w *= 0.6
        if et in (11, 12):
            w *= 0.35
        weights.append(w)
    r = random.uniform(0, sum(weights))
    s = 0
    for et, w in zip(pool, weights):
        s += w
        if r <= s:
            return et
    return pool[-1]


# ----------------------------------------------------------------------------
# Игрок
# ----------------------------------------------------------------------------
class Player:
    def __init__(self, w, h):
        self.W, self.H = w, h
        self.x = w / 2
        self.y = h - 70
        self.vx = self.vy = 0
        self.lives = 5
        self.max_lives = 5
        self.shield = 0
        self.max_shield = 0
        self.speed = 250
        self.size = 22   # соответствует новому размеру спрайта
        self.cool = 0
        self.rate = 0.15
        self.torp = 0
        self.mines = 3
        self.inv = 0
        self.mine_cd = 0
        self.torp_cd = 0                    # кулдаун торпеды (ПКМ)
        self.upg = {"gun": 0, "shield": 0, "speed": 0, "hp": 0}
        self.flash = 0                      # длительность вспышки
        self.flash_col = (0, 255, 0)        # цвет вспышки (зелёный/синий)

    def _draw_thrusters(self, s, x, y, warp, boost, t):
        """Двойное процедурное пламя из двух дюз. 3 слоя + мерцание."""
        # Спрайт ship.png ~66px по высоте, центр в (x, y). Низ спрайта = y + 33.
        # Сопла — прямо под нижней кромкой корпуса, слегка отступив от центра.
        # компенсация оптического центра спрайта ship.png (не идеально симметричен)
        FLAME_X_OFFSET = 2
        NOZZLE_Y = 30
        NOZZLES = [(-9 + FLAME_X_OFFSET, NOZZLE_Y), (9 + FLAME_X_OFFSET, NOZZLE_Y)]

        # Длина пламени: базовая + буст + небольшой шум
        # (0.3-2.0 при обычном полёте, 3-5 при форсаже)
        base_len = 14 + boost * 40
        idle_flicker = 0.85 + 0.15 * math.sin(t * 30)      # быстрое мерцание
        length = base_len * idle_flicker

        # Ширина слоёв
        w_outer = 8 + boost * 4
        w_mid = 5 + boost * 2
        w_core = 2.5 + boost * 1.2

        # цвета (RGB — альфа задаётся отдельно)
        # тёплое пламя, немного с синим ободком у ядра для «плазменности»
        c_outer = (255, 100, 30)     # снаружи оранжево-красный ореол
        c_mid = (255, 200, 80)       # средний слой жёлтый
        c_core = (255, 255, 220)     # ярко-белое ядро

        # рисуем в отдельный slrfa surface с additive, чтобы слои складывались красиво
        overlay = pygame.Surface((80, int(length + 20)), pygame.SRCALPHA)
        for (dx, dy_base) in NOZZLES:
            # локальные координаты в overlay: центр по X = 40
            lx = 40 + dx
            ly = 0
            # длина конкретной дюзы (небольшая рандомизация по времени)
            phase = math.sin(t * 27 + dx * 0.3)
            L = int(length * (0.92 + 0.08 * phase))

            # 1) Внешнее свечение — вытянутый эллипс
            self._flame_ellipse(overlay, lx, ly + L // 2, w_outer, L, c_outer, 110)
            # 2) Средний слой
            self._flame_ellipse(overlay, lx, ly + L // 2, w_mid, int(L * 0.85), c_mid, 190)
            # 3) Ядро — самый яркий, короче
            self._flame_ellipse(overlay, lx, ly + int(L * 0.4), w_core, int(L * 0.7), c_core, 235)

        # блитим с additive blend — цвета складываются, получается яркое горение
        s.blit(overlay, (x - 40, y + NOZZLE_Y), special_flags=pygame.BLEND_RGBA_ADD)

        # Хвост из мерцающих искр (совсем чуть-чуть, 2-3 на кадр)
        for (dx, _) in NOZZLES:
            if math.sin(t * 25 + dx) > 0.3:
                spark_y = y + NOZZLE_Y + int(length * (0.4 + 0.6 * ((t * 7 + dx) % 1)))
                spark_x = int(x + dx + math.sin(t * 40 + dx) * 2)
                spark_col = (255, 240, 200) if (spark_y % 2) else (255, 180, 100)
                pygame.draw.circle(s, spark_col, (spark_x, spark_y), 1)

    @staticmethod
    def _flame_ellipse(surf, cx, cy, w, h, color, alpha):
        """Вспомогательный: эллипс с заданной прозрачностью в overlay."""
        if h < 2 or w < 1:
            return
        pygame.draw.ellipse(surf, (*color, alpha),
                            (int(cx - w), int(cy - h // 2), int(w * 2), int(h)))

    def draw(self, s, t, warp):
        if self.inv > 0 and math.sin(t * 25) > 0:
            return
        x, y = self.x, self.y

        # вспышка от подобранного бонуса
        if self.flash > 0:
            alpha = int(180 * (self.flash / 0.5))
            srf = pygame.Surface((68, 68), pygame.SRCALPHA)
            pygame.draw.circle(srf, (*self.flash_col, alpha), (34, 34), 32, 3)
            pygame.draw.circle(srf, (*self.flash_col, alpha // 3), (34, 34), 30)
            s.blit(srf, (x - 34, y - 34))

        boost = max(0, (warp - 170) / 350)
        # ---- ПРОЦЕДУРНОЕ ПЛАМЯ ДЮЗ ----
        # Двойное пламя из двух сопел (левое/правое). Каждое — 3 слоя с additive blend
        # + мерцающий хвост частиц. Длина зависит от boost.
        self._draw_thrusters(s, x, y, warp, boost, t)

        # попытка использовать PNG-спрайт
        try:
            import sys, os
            base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            sp_path = os.path.join(base, "assets", "ship.png")
            if os.path.exists(sp_path):
                # кэш через модуль
                cache_key = "_ship_sprite"
                sp = getattr(Player, cache_key, None)
                if sp is None:
                    raw = pygame.image.load(sp_path).convert_alpha()
                    # масштабируем — корабль в 1.5 раза больше (~66px по высоте)
                    iw, ih = raw.get_size()
                    scale = 66 / ih
                    sp = pygame.transform.smoothscale(raw, (int(iw * scale), int(ih * scale)))
                    setattr(Player, cache_key, sp)
                sw, sh = sp.get_size()
                s.blit(sp, (x - sw // 2, y - sh // 2))
                if self.shield > 0:
                    srf = pygame.Surface((sw + 12, sh + 12), pygame.SRCALPHA)
                    pygame.draw.ellipse(srf, (55, 138, 221, 150), (0, 0, sw + 10, sh + 10), 2)
                    s.blit(srf, (x - (sw + 12) // 2, y - (sh + 12) // 2))
                return
        except Exception:
            pass

        # fallback — процедурная отрисовка
        wing_col = (120, 132, 150)
        pygame.draw.polygon(s, wing_col, [(x - 4, y - 4), (x - 22, y + 12), (x - 6, y + 10)])
        pygame.draw.polygon(s, wing_col, [(x + 4, y - 4), (x + 22, y + 12), (x + 6, y + 10)])
        for sg in (-1, 1):
            nx = x + sg * 13
            pygame.draw.ellipse(s, NACELLE, (nx - 3, y - 4, 6, 22))
            pygame.draw.ellipse(s, GLOW_BLUE, (nx - 2, y + 14, 4, 6))
        pygame.draw.polygon(s, SHIP_FILL,
                            [(x, y - 20), (x + 9, y - 2), (x + 7, y + 14),
                             (x - 7, y + 14), (x - 9, y - 2)])
        pygame.draw.polygon(s, SHIP_LINE,
                            [(x, y - 20), (x + 9, y - 2), (x + 7, y + 14),
                             (x - 7, y + 14), (x - 9, y - 2)], 1)
        pygame.draw.polygon(s, (198, 206, 216), [(x, y - 20), (x + 5, y - 6), (x - 5, y - 6)])
        pygame.draw.circle(s, (120, 200, 255), (int(x), int(y - 4)), 3)
        if self.shield > 0:
            srf = pygame.Surface((56, 60), pygame.SRCALPHA)
            pygame.draw.ellipse(srf, (55, 138, 221, 150), (0, 0, 52, 58), 2)
            s.blit(srf, (x - 26, y - 4 - 29))


def fighter_icon(s, cx, cy, sz, color):
    pts = [(cx, cy - sz), (cx + sz * .35, cy - sz * .2), (cx + sz * .9, cy + sz * .3),
           (cx + sz * .9, cy + sz * .7), (cx + sz * .35, cy + sz * .3),
           (cx + sz * .15, cy + sz), (cx - sz * .15, cy + sz), (cx - sz * .35, cy + sz * .3),
           (cx - sz * .9, cy + sz * .7), (cx - sz * .9, cy + sz * .3), (cx - sz * .35, cy - sz * .2)]
    pygame.draw.polygon(s, color, pts)


# ----------------------------------------------------------------------------
# Враги
# ----------------------------------------------------------------------------
def make_enemy(W, H, wave, diff_mult, force_type=None):
    et = force_type if force_type is not None else pick_enemy_type(wave)
    stat = ENEMY_STATS[et]
    base_hp = stat[2] + wave * stat[6]
    hp = base_hp * diff_mult
    speed = stat[3] + wave * 3
    sz = stat[4]
    shielded = (et == 4) or (wave >= 7 and et in (2, 12) and random.random() < 0.35)
    f = {
        "x": random.uniform(40, W - 40), "y": -34,
        "vy": speed, "hp": hp, "mhp": hp, "sz": sz, "type": et,
        "sc": random.uniform(0.6, 2.0), "ph": random.uniform(0, 6.28),
        "amp": random.uniform(15, 55), "atk": stat[8],
        "shield": hp * 0.7 if shielded else 0, "msh": hp * 0.7 if shielded else 0,
        "kami": 0, "ka": 0, "kc": 0,
        "esc": [], "esc_st": 0, "esc_t": 0,
        "wave": wave,
    }
    if wave >= 11 and et in (1, 2, 6, 7, 9) and random.random() < 0.25:
        f["elite"] = True
        f["mhp"] = f["hp"] = hp * 1.4
        f["sz"] = int(sz * 1.15)
    if et == 11:
        # MOTHERSHIP: щит (80% HP), самый медленный, сам не стреляет
        f["shield"] = hp * 0.8
        f["msh"] = hp * 0.8
        f["vy"] = max(18, speed * 0.4)   # самый медленный
    return f


def draw_enemy(s, f, t):
    x, y, sz = f["x"], f["y"], f["sz"]
    ty = f["type"]
    col = ENEMY_COL[ty]

    if ty == 5:
        # свечение при разгоне (только у обычных, не от астероида)
        glow = min(1, f["kc"] / 0.55) if f["kami"] == 1 else (1 if f["kami"] == 2 else 0)
        if glow > 0 and not f.get("from_rock"):
            srf = pygame.Surface((int((sz + 22) * 2),) * 2, pygame.SRCALPHA)
            pygame.draw.circle(srf, (255, 120, 40, int(glow * 150)),
                               (int(sz + 22), int(sz + 22)), int(sz + 8 + glow * 14))
            s.blit(srf, (x - sz - 22, y - sz - 22))
        # спрайт (нос уже вниз — flip=False)
        if not _try_enemy_sprite(s, "kamikaze.png", x, y, sz, target_h=int(sz * 4.8), flip=False):
            c2 = (255, 204, 68) if glow > 0.5 else (160, 48, 32)
            pygame.draw.polygon(s, c2, [(x, y + sz), (x + sz * .8, y - sz * .5), (x - sz * .8, y - sz * .5)])
            pygame.draw.polygon(s, AMBER, [(x, y + sz), (x + sz * .8, y - sz * .5), (x - sz * .8, y - sz * .5)], 2)
            pygame.draw.circle(s, (255, 208, 160), (int(x), int(y)), 3)

    elif ty == 0:
        if not _try_enemy_sprite(s, "scout.png", x, y, sz, target_h=int(sz * 3.5), flip=False):
            pygame.draw.polygon(s, (90, 39, 64), [(x - sz, y - sz * .4), (x - sz * .3, y - sz * .1), (x - sz * .3, y + sz * .5)])
            pygame.draw.polygon(s, (90, 39, 64), [(x + sz, y - sz * .4), (x + sz * .3, y - sz * .1), (x + sz * .3, y + sz * .5)])
            pygame.draw.polygon(s, col, [(x, y + sz), (x + sz * .4, y - sz * .6), (x - sz * .4, y - sz * .6)])

    elif ty == 1:
        if not _try_enemy_sprite(s, "gunner.png", x, y, sz, target_h=int(sz * 6.0), flip=False):
            pygame.draw.rect(s, (122, 74, 26), (x - sz * .95, y - sz * .3, sz * .5, sz * 1.2))
            pygame.draw.rect(s, (122, 74, 26), (x + sz * .45, y - sz * .3, sz * .5, sz * 1.2))
            pygame.draw.polygon(s, col, [(x, y + sz), (x + sz * .55, y - sz * .7), (x, y - sz * .4), (x - sz * .55, y - sz * .7)])

    elif ty == 2:
        # нос корабля направлен вниз — flip=False
        if not _try_enemy_sprite(s, "cruiser.png", x, y, sz, target_h=int(sz * 4.5), flip=False):
            pygame.draw.polygon(s, (58, 45, 99), [(x, y + sz), (x + sz, y + sz * .3), (x + sz, y - sz * .5), (x + sz * .4, y - sz), (x - sz * .4, y - sz), (x - sz, y - sz * .5), (x - sz, y + sz * .3)])
            pygame.draw.polygon(s, col, [(x, y + sz * .8), (x + sz * .6, y), (x, y - sz * .7), (x - sz * .6, y)])

    elif ty == 3:
        # истребитель, нос направлен вверх — переворачиваем (flip=True)
        if not _try_enemy_sprite(s, "raider.png", x, y, sz, target_h=int(sz * 4.8), flip=True):
            pygame.draw.circle(s, (29, 110, 79), (int(x), int(y)), int(sz * .7))
            pygame.draw.polygon(s, col, [(x, y + sz), (x + sz * .7, y - sz * .3), (x - sz * .7, y - sz * .3)])

    elif ty == 4:
        if not _try_enemy_sprite(s, "warden.png", x, y, sz, target_h=int(sz * 4.5), flip=False):
            pygame.draw.polygon(s, (39, 74, 115), [(x, y + sz), (x + sz * .9, y + sz * .2), (x + sz * .7, y - sz * .7), (x, y - sz * .5), (x - sz * .7, y - sz * .7), (x - sz * .9, y + sz * .2)])
            pygame.draw.polygon(s, col, [(x, y + sz * .6), (x + sz * .5, y - sz * .2), (x, y - sz * .4), (x - sz * .5, y - sz * .2)])

    elif ty == 6:
        if not _try_enemy_sprite(s, "plasmer.png", x, y, sz, target_h=int(sz * 4.2), flip=False):
            pygame.draw.circle(s, (80, 35, 80), (int(x), int(y)), int(sz * 0.9))
            pygame.draw.circle(s, col, (int(x), int(y)), int(sz * 0.6))
            for sg in (-1, 1):
                cx2, cy2 = x + sg * sz * 0.7, y - sz * 0.3
                pygame.draw.circle(s, (200, 80, 180), (int(cx2), int(cy2)), 3)

    elif ty == 7:
        # STORMER — симметричный шар (+10%)
        if not _try_enemy_sprite(s, "stormer.png", x, y, sz, target_h=int(sz * 4.62), flip=False):
            pygame.draw.polygon(s, (40, 60, 110), [(x - sz, y), (x, y - sz), (x + sz, y), (x, y + sz)])
            pygame.draw.polygon(s, col, [(x - sz * 0.6, y), (x, y - sz * 0.6), (x + sz * 0.6, y), (x, y + sz * 0.6)])

    elif ty == 8:
        if not _try_enemy_sprite(s, "echoer.png", x, y, sz, target_h=int(sz * 4.2), flip=False):
            pygame.draw.circle(s, (30, 80, 60), (int(x), int(y)), int(sz))
            pygame.draw.circle(s, col, (int(x), int(y)), int(sz * 0.5))
            pulse = (t * 2) % 1
            pygame.draw.circle(s, col, (int(x), int(y)), int(sz + pulse * 6), 1)

    elif ty == 9:
        # SCATTERER (+15%)
        if not _try_enemy_sprite(s, "scatterer.png", x, y, sz, target_h=int(sz * 5.18), flip=False):
            pygame.draw.polygon(s, (100, 70, 20), [(x - sz, y + sz * 0.3), (x + sz, y + sz * 0.3),
                                                    (x + sz * 0.7, y - sz * 0.5), (x - sz * 0.7, y - sz * 0.5)])

    elif ty == 10:
        # MINER
        if not _try_enemy_sprite(s, "miner.png", x, y, sz, target_h=int(sz * 4.5), flip=False):
            pygame.draw.rect(s, (70, 50, 30), (x - sz * 0.9, y - sz * 0.4, sz * 1.8, sz * 0.8))
            pygame.draw.rect(s, col, (x - sz * 0.5, y - sz * 0.2, sz, sz * 0.4))

    elif ty == 11:
        # MOTHERSHIP
        if not _try_enemy_sprite(s, "mothership.png", x, y, sz, target_h=int(sz * 4.5), flip=False):
            pygame.draw.ellipse(s, (100, 60, 110), (x - sz, y - sz * 0.7, sz * 2, sz * 1.4))
            pygame.draw.ellipse(s, col, (x - sz * 0.6, y - sz * 0.4, sz * 1.2, sz * 0.8))
            pygame.draw.circle(s, (255, 230, 255), (int(x), int(y)), 4)
        # эскорт-мини-корабли (рисуются отдельно от спрайта)
        for e in f.get("esc", []):
            if not e["alive"]:
                continue
            ang = e["ang"] + t * (2.5 if f.get("esc_st") == 0 else 0)
            ex = x + math.cos(ang) * e["r"]
            ey = y + math.sin(ang) * e["r"]
            pygame.draw.polygon(s, (255, 200, 240),
                                [(ex, ey - 4), (ex + 3, ey + 3), (ex - 3, ey + 3)])

    elif ty == 12:
        # HYBRID
        if not _try_enemy_sprite(s, "hybrid.png", x, y, sz, target_h=int(sz * 4.5), flip=False):
            pygame.draw.polygon(s, (100, 30, 30), [(x - sz, y + sz * 0.5), (x, y + sz),
                                                    (x + sz, y + sz * 0.5), (x, y - sz)])
            pygame.draw.polygon(s, col, [(x - sz * 0.6, y), (x, y + sz * 0.5),
                                          (x + sz * 0.6, y), (x, y - sz * 0.6)])

    if f.get("elite") and ty < 11:
        pygame.draw.circle(s, GOLD, (int(x), int(y)), int(sz + 3), 1)

    if f["shield"] > 0:
        a = int(76 + 115 * (f["shield"] / f["msh"]))
        srf = pygame.Surface(((f["sz"] + 9) * 2,) * 2, pygame.SRCALPHA)
        pygame.draw.circle(srf, (94, 170, 235, a), (f["sz"] + 9, f["sz"] + 9), f["sz"] + 7, 2)
        s.blit(srf, (x - f["sz"] - 9, y - f["sz"] - 9))


# ----------------------------------------------------------------------------
# Боссы — 5 уникальных форм
# ----------------------------------------------------------------------------
BOSS_NAMES = ["SENTINEL", "VANGUARD", "RAVAGER", "HARBINGER", "ZONE LORD"]
# +30% ко всем боссам; первый ещё +100% сверху
BOSS_HP = [1040, 2080, 5200, 15600, 52000]


def make_boss(W, wave, diff_mult):
    num = wave // 5
    btype = num - 1
    hp = BOSS_HP[btype] * diff_mult
    boss_speed_mult = 1 + (num - 1) * 0.25
    cores = [110, 120, 130, 145, 160]
    parts = build_boss_parts(btype, num, diff_mult)
    return {
        "type": btype, "num": num, "diff": boss_speed_mult,
        "x": W / 2, "y": -190, "vx": 36 + num * 4, "rot": 0,
        "coreR": cores[btype], "hp": hp, "mhp": hp,
        "shield": hp * 0.3, "msh": hp * 0.3, "enter": 1,
        "phase": 0, "pt": 2.0, "cf": 0, "ch": 0, "hitf": 0,
        "parts": parts, "ams": 2, "beaming": 0,
        "atks": boss_atks(btype),
        "ang": 0,
    }


def boss_atks(btype):
    if btype == 0:
        return ["laser3", "fan", "laser3", "fan"]
    if btype == 1:
        return ["laser3", "miss", "fan", "beam"]
    if btype == 2:
        return ["laser3", "miss", "fan", "chain", "beam"]
    if btype == 3:
        return ["miss", "laser3", "fan", "chain", "beam"]
    return ["chain", "miss", "fan", "spawn", "beam", "laser3", "spawn"]  # ZONE LORD спавнит корабли


def build_boss_parts(btype, num, diff_mult):
    parts = []
    ph = 50 * (1.3 ** (num - 1)) * diff_mult
    if btype == 0:
        for ax, ay in [(-70, 30), (70, 30), (-40, 60), (40, 60), (0, 70)]:
            parts.append({"dx": ax, "dy": ay, "r": 12, "k": "g", "hp": ph, "mhp": ph})
    elif btype == 1:
        for i in range(6):
            a = i / 6 * 6.28
            parts.append({"dx": math.cos(a) * 80, "dy": math.sin(a) * 80,
                          "r": 12, "k": "c", "hp": ph, "mhp": ph})
    elif btype == 2:
        for i in range(6):
            a = i / 6 * 6.28
            parts.append({"dx": math.cos(a) * 70, "dy": math.sin(a) * 70,
                          "r": 11, "k": "e", "hp": ph, "mhp": ph})
    elif btype == 3:
        for ax, ay in [(-90, 0), (90, 0), (0, -80), (0, 80),
                       (-50, -50), (50, -50), (-50, 50), (50, 50)]:
            parts.append({"dx": ax, "dy": ay, "r": 11, "k": "g", "hp": ph, "mhp": ph})
    else:
        for i in range(12):
            a = i / 12 * 6.28
            r = 100 + (i % 2) * 12
            parts.append({"dx": math.cos(a) * r, "dy": math.sin(a) * r,
                          "r": 12, "k": "g", "hp": ph * 1.3, "mhp": ph * 1.3})
    return parts


def part_pos(b, g):
    a = b.get("ang", 0)
    ca, sa = math.cos(a), math.sin(a)
    return b["x"] + g["dx"] * ca - g["dy"] * sa, b["y"] + g["dx"] * sa + g["dy"] * ca


_BOSS_SPRITE_CACHE = {}
_ENEMY_SPRITE_CACHE = {}


def _try_enemy_sprite(s, filename, x, y, sz, target_h, flip=True):
    """Загрузка спрайта врага. Если flip=True — переворачиваем по Y (враги летят вниз,
    а спрайты обычно нарисованы носом вверх). Возвращает True если спрайт нарисован."""
    import os
    import sys as _sys
    key = (filename, target_h, flip)
    sp = _ENEMY_SPRITE_CACHE.get(key, "?")
    if sp == "?":
        base_dir = getattr(_sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base_dir, "assets", filename)
        if not os.path.exists(path):
            _ENEMY_SPRITE_CACHE[key] = None
        else:
            try:
                raw = pygame.image.load(path).convert_alpha()
                iw, ih = raw.get_size()
                scale = target_h / ih
                scaled = pygame.transform.smoothscale(raw, (int(iw * scale), int(ih * scale)))
                if flip:
                    sp = pygame.transform.flip(scaled, False, True)
                else:
                    sp = scaled
                _ENEMY_SPRITE_CACHE[key] = sp
            except Exception:
                _ENEMY_SPRITE_CACHE[key] = None
        sp = _ENEMY_SPRITE_CACHE[key]
    if sp is None:
        return False
    sw, sh = sp.get_size()
    s.blit(sp, (int(x) - sw // 2, int(y) - sh // 2))
    return True


def _try_boss_sprite(s, b, x, y, filename, target_w, t):
    """Пытается нарисовать босса с PNG-спрайта. Возвращает True при успехе."""
    import os
    import sys as _sys
    key = (filename, target_w)
    sp = _BOSS_SPRITE_CACHE.get(key, "?")
    if sp == "?":
        base_dir = getattr(_sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base_dir, "assets", filename)
        if not os.path.exists(path):
            _BOSS_SPRITE_CACHE[key] = None
        else:
            try:
                raw = pygame.image.load(path).convert_alpha()
                iw, ih = raw.get_size()
                scale = target_w / iw
                sp = pygame.transform.smoothscale(raw, (int(iw * scale), int(ih * scale)))
                _BOSS_SPRITE_CACHE[key] = sp
            except Exception:
                _BOSS_SPRITE_CACHE[key] = None
        sp = _BOSS_SPRITE_CACHE[key]
    if sp is None:
        return False
    sw, sh = sp.get_size()
    # лёгкое покачивание
    dy = int(math.sin(t * 1.2) * 4)
    s.blit(sp, (x - sw // 2, y - sh // 2 + dy))
    # помечаем, что босс отрисован из спрайта (для main.py — знать про экранный флэш)
    b["_sprite"] = True
    return True


def draw_boss(s, b, px, py, t):
    btype = b["type"]
    x, y = int(b["x"]), int(b["y"])
    pal = [
        {"a": (58, 42, 82), "b": (122, 90, 168), "c": (36, 26, 54), "cc": (255, 150, 60)},
        {"a": (35, 64, 78), "b": (74, 143, 181), "c": (22, 38, 46), "cc": (120, 210, 255)},
        {"a": (82, 38, 31), "b": (181, 104, 58), "c": (50, 22, 18), "cc": (255, 140, 70)},
        {"a": (52, 28, 60), "b": (160, 88, 200), "c": (34, 16, 38), "cc": (220, 140, 255)},
        {"a": (90, 30, 30), "b": (220, 80, 60), "c": (50, 16, 12), "cc": (255, 230, 100)},
    ][btype]

    # сбросить флаг перед отрисовкой
    b["_sprite"] = False

    if btype == 0:
        if not _try_boss_sprite(s, b, x, y, "boss1.png", 300, t):
            _draw_ravager(s, b, x, y, pal, t)
    elif btype == 1:
        if not _try_boss_sprite(s, b, x, y, "boss2.png", 322, t):
            _draw_tempest(s, b, x, y, pal, t)
    elif btype == 2:
        if not _try_boss_sprite(s, b, x, y, "boss3.png", 360, t):
            _draw_resonator(s, b, x, y, pal, t)
    elif btype == 3:
        if not _try_boss_sprite(s, b, x, y, "boss4.png", 400, t):
            _draw_harbinger(s, b, x, y, pal, t)
    else:
        if not _try_boss_sprite(s, b, x, y, "boss5.png", 440, t):
            _draw_zonelord(s, b, x, y, pal, t)

    # если босс отрисован из PNG-спрайта — не рисуем поверх ни щитового кольца,
    # ни «шаров»-турелей: они не совпадают с формой спрайта и портят картинку.
    if b.get("_sprite"):
        return

    if b["shield"] > 0:
        a = int(38 + 90 * (b["shield"] / b["msh"]))
        rr = 130
        srf = pygame.Surface((rr * 2, rr * 2), pygame.SRCALPHA)
        pygame.draw.circle(srf, (94, 170, 235, a), (rr, rr), rr - 4, 4)
        s.blit(srf, (x - rr, y - rr))

    for g in b["parts"]:
        gx, gy = part_pos(b, g)
        gx, gy = int(gx), int(gy)
        if g["hp"] <= 0:
            pygame.draw.circle(s, (36, 28, 46), (gx, gy), 5)
            continue
        ang = math.atan2(py - gy, px - gx)
        pygame.draw.line(s, (30, 26, 38), (gx, gy),
                         (int(gx + math.cos(ang) * 13), int(gy + math.sin(ang) * 13)), 5)
        bcol = {"g": (74, 59, 94), "c": (38, 86, 110), "e": (106, 42, 42)}[g["k"]]
        pygame.draw.circle(s, bcol, (gx, gy), 8)
        pygame.draw.circle(s, pal["b"], (gx, gy), 8, 2)
        if g["k"] == "c" and b["ch"] > 0:
            pygame.draw.circle(s, (143, 208, 255), (gx, gy), 4)
        if g["k"] == "e":
            pygame.draw.circle(s, (255, 150, 80), (gx, gy), 3)


def _draw_ravager(s, b, x, y, pal, t):
    Rc = b["coreR"]
    hull = [(x, y + Rc + 30), (x + Rc + 30, y + 20), (x + Rc + 20, y - Rc),
            (x + 30, y - Rc - 20), (x - 30, y - Rc - 20),
            (x - Rc - 20, y - Rc), (x - Rc - 30, y + 20)]
    pygame.draw.polygon(s, pal["a"], hull)
    pygame.draw.polygon(s, pal["b"], hull, 2)
    for sg in (-1, 1):
        pygame.draw.polygon(s, pal["c"],
                            [(x + sg * 12, y - Rc - 20), (x + sg * 22, y - Rc - 40),
                             (x + sg * 6, y - Rc - 18)])
    _draw_core(s, x, y, Rc * 0.5, pal, b["cf"])


def _draw_tempest(s, b, x, y, pal, t):
    Rc = b["coreR"]
    pygame.draw.circle(s, pal["a"], (x, y), Rc + 30)
    pygame.draw.circle(s, (0, 0, 0), (x, y), Rc + 10)
    pygame.draw.circle(s, pal["b"], (x, y), Rc + 30, 3)
    for i in range(6):
        a = i / 6 * 6.28 + t * 0.4
        x2, y2 = x + math.cos(a) * (Rc + 28), y + math.sin(a) * (Rc + 28)
        pygame.draw.line(s, pal["b"], (x, y), (int(x2), int(y2)), 3)
    _draw_core(s, x, y, Rc, pal, b["cf"])


def _draw_resonator(s, b, x, y, pal, t):
    Rc = b["coreR"]
    pts = []
    for i in range(6):
        a = i / 6 * 6.28 + math.pi / 6
        pts.append((x + math.cos(a) * (Rc + 25), y + math.sin(a) * (Rc + 25)))
    pygame.draw.polygon(s, pal["a"], pts)
    pygame.draw.polygon(s, pal["b"], pts, 3)
    pts2 = []
    for i in range(6):
        a = i / 6 * 6.28 + math.pi / 6
        pts2.append((x + math.cos(a) * (Rc - 5), y + math.sin(a) * (Rc - 5)))
    pygame.draw.polygon(s, pal["c"], pts2)
    _draw_core(s, x, y, Rc * 0.5, pal, b["cf"])


def _draw_harbinger(s, b, x, y, pal, t):
    Rc = b["coreR"]
    pygame.draw.circle(s, pal["a"], (x, y), Rc)
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        wing = [(x + dx * Rc * 0.4 - dy * 20, y + dy * Rc * 0.4 + dx * 20),
                (x + dx * (Rc + 60), y + dy * (Rc + 60)),
                (x + dx * Rc * 0.4 + dy * 20, y + dy * Rc * 0.4 - dx * 20)]
        pygame.draw.polygon(s, pal["a"], wing)
        pygame.draw.polygon(s, pal["b"], wing, 2)
    pygame.draw.circle(s, pal["b"], (x, y), Rc, 3)
    _draw_core(s, x, y, Rc * 0.6, pal, b["cf"])


def _draw_zonelord(s, b, x, y, pal, t):
    Rc = b["coreR"]
    pygame.draw.circle(s, pal["a"], (x, y), Rc + 50)
    pygame.draw.circle(s, pal["c"], (x, y), Rc + 50, 4)
    for i in range(12):
        a = i / 12 * 6.28 + t * 0.2
        px = x + math.cos(a) * (Rc + 30)
        py = y + math.sin(a) * (Rc + 30)
        pygame.draw.circle(s, pal["b"], (int(px), int(py)), 8)
    pygame.draw.circle(s, pal["a"], (x, y), Rc + 5)
    pygame.draw.circle(s, pal["b"], (x, y), Rc + 5, 2)
    _draw_core(s, x, y, Rc * 0.7, pal, b["cf"])


def _draw_core(s, x, y, r, pal, cf):
    r = int(r)
    if r <= 0:
        return
    pygame.draw.circle(s, (26, 13, 13), (x, y), r)
    glow = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
    cc = pal["cc"]
    for i in range(r, 0, -2):
        al = int(220 * (i / r) * (0.7 + cf * 0.3))
        pygame.draw.circle(glow, (cc[0], cc[1], cc[2], al), (r, r), i)
    s.blit(glow, (x - r, y - r))
    pygame.draw.circle(s, AMBER, (x, y), r, 2)


# обратная совместимость
gun_pos = part_pos
