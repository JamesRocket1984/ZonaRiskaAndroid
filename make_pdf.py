#!/usr/bin/env python3
"""Генератор PDF-бестиария кораблей «Зона Риска»."""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, Image, PageBreak)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ASSETS = os.path.join(os.path.dirname(__file__), "assets")

# Регистрируем шрифт с кириллицей
FONT = "Helvetica"
FONT_B = "Helvetica-Bold"
for cand in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
    if os.path.exists(cand):
        name = "DejaVu" if "Bold" not in cand else "DejaVuB"
        pdfmetrics.registerFont(TTFont(name, cand))
        if "Bold" not in cand:
            FONT = "DejaVu"
        else:
            FONT_B = "DejaVuB"

ATK = {
    "l": "Лазер (одиночный луч)",
    "lh": "Тяжёлый лазер — клин из 3 лучей",
    "m": "Самонаводящаяся ракета",
    "ram": "Таран (летит на игрока)",
    "lm": "Лазер + ракета одновременно",
    "lm2": "Залп 3 лазеров + ракета",
    "p": "Плазменный шар (самонаводящийся)",
    "z": "Цепная молния (электро-дуга)",
    "u": "Звуковая волна (кольцо с просветами)",
    "f": "Веер из 5 лазеров",
    "om": "Сброс мин",
    "esc": "Выпускает корабли-эскорт",
}

# (type, min_wave, hp, speed, sz, reward, hp/w, rw/w, atk)
SHIPS = [
    (0, 1, 18, 78, 14, 3, 6, 1, "l", "SCOUT", "Разведчик",
     "Лёгкий быстрый истребитель. Основа вражеского флота. Слабая броня, но берёт числом."),
    (3, 2, 14, 115, 11, 4, 4, 2, "ram", "RAIDER", "Налётчик",
     "Самый быстрый корабль. Не стреляет — таранит. Хрупкий, но опасен на скорости. "
     "Из корабля-матки и финального босса вылетает уже как стрелок ядовитыми шарами."),
    (2, 4, 130, 32, 26, 22, 26, 5, "m", "CRUISER", "Крейсер",
     "Тяжёлый бронированный корабль. Пускает самонаводящиеся ракеты. Медленный, живучий."),
    (4, 6, 60, 28, 24, 30, 22, 6, "lm", "WARDEN", "Страж",
     "Комбо-боец: лазер и ракета одновременно. Оснащён энергощитом (70% брони). "
     "Первый по-настоящему опасный противник."),
    (5, 6, 22, 60, 13, 7, 5, 2, "ram", "KAMIKAZE", "Камикадзе",
     "Застывает, целится — и бросается на игрока рывком. Иногда прячется в астероидах."),
    (6, 9, 50, 40, 18, 12, 14, 4, "p", "PLASMER", "Плазмер",
     "Стреляет медленными самонаводящимися плазменными шарами. Сложно увернуться."),
    (1, 11, 100, 48, 18, 8, 16, 3, "lh", "GUNNER", "Канонир",
     "Тяжёлое орудие — клин из трёх лазеров. На экране не больше двух одновременно."),
    (7, 14, 70, 36, 20, 16, 16, 4, "z", "STORMER", "Штормовик",
     "Бьёт цепной молнией, которая тянется за ним. Урон только на самом конце разряда."),
    (8, 16, 90, 30, 22, 20, 18, 5, "u", "ECHOER", "Ревун",
     "Излучает звуковые кольца с 4 просветами. Уклоняйся сквозь разрывы. "
     "Затухающее кольцо (последние 25%) уже безвредно."),
    (9, 16, 80, 40, 20, 18, 16, 4, "f", "SCATTERER", "Рассеиватель",
     "Накрывает веером из 5 лазеров. Стреляет раз в 7 секунд. На экране только один."),
    (10, 18, 120, 32, 22, 22, 20, 5, "om", "MINER", "Минёр",
     "Расставляет мины. Мина через 2-3 сек взрывается, разбрасывая красную шрапнель."),
    (11, 21, 220, 24, 30, 40, 30, 8, "esc", "MOTHERSHIP", "Матка",
     "Огромный носитель под щитом. Сам не стреляет. Каждые 5 секунд выпускает 2 налётчика-стрелка. "
     "Самый медленный корабль в игре."),
    (12, 23, 140, 38, 24, 28, 24, 6, "lm2", "HYBRID", "Гибрид",
     "Вершина эволюции флота: залп из 3 лазеров и ракета разом. Появляется у финального рубежа."),
]

# боссы: (sprite, name, ru, hp, sector, desc)
BOSSES = [
    ("boss1.png", "SENTINEL", "Страж Врат", 1040, 5,
     "Первый рубеж. Тройной лазер и веер. Проверка на прочность."),
    ("boss2.png", "VANGUARD", "Авангард", 2080, 10,
     "Добавляет ракетные залпы и импульсный луч. Держи дистанцию."),
    ("boss3.png", "RAVAGER", "Опустошитель", 5200, 15,
     "Цепные молнии, веер, ракеты. Хаотичная смена атак."),
    ("boss4.png", "HARBINGER", "Вестник", 15600, 20,
     "Крепость с восемью турелями. Всё сразу и без пауз."),
    ("boss5.png", "ZONE LORD", "Владыка Зоны", 52000, 25,
     "Финал. Выпускает по 5 налётчиков-стрелков, чередуя с молниями, ракетами и веером."),
]

SPRITE = {0: "scout.png", 1: "gunner.png", 2: "cruiser.png", 3: "raider.png",
          4: "warden.png", 5: "kamikaze.png", 6: "plasmer.png", 7: "stormer.png",
          8: "echoer.png", 9: "scatterer.png", 10: "miner.png", 11: "mothership.png",
          12: "hybrid.png"}

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Title"], fontName=FONT_B, fontSize=26,
                    textColor=colors.HexColor("#7ee0c0"), alignment=TA_CENTER, spaceAfter=6)
SUB = ParagraphStyle("SUB", parent=styles["Normal"], fontName=FONT, fontSize=11,
                     textColor=colors.HexColor("#8899bb"), alignment=TA_CENTER, spaceAfter=16)
NAME = ParagraphStyle("NAME", parent=styles["Normal"], fontName=FONT_B, fontSize=15,
                      textColor=colors.HexColor("#c0d0f0"))
RU = ParagraphStyle("RU", parent=styles["Normal"], fontName=FONT, fontSize=10,
                    textColor=colors.HexColor("#8899bb"), spaceAfter=4)
DESC = ParagraphStyle("DESC", parent=styles["Normal"], fontName=FONT, fontSize=9.5,
                      textColor=colors.HexColor("#334"), leading=13)
SEC = ParagraphStyle("SEC", parent=styles["Heading1"], fontName=FONT_B, fontSize=17,
                     textColor=colors.HexColor("#5a7"), spaceBefore=10, spaceAfter=8)
CELL = ParagraphStyle("CELL", parent=styles["Normal"], fontName=FONT, fontSize=9,
                      textColor=colors.HexColor("#223"))


def img_cell(fname, box=90):
    p = os.path.join(ASSETS, fname)
    if not os.path.exists(p):
        return Paragraph("—", CELL)
    from PIL import Image as PILImage
    iw, ih = PILImage.open(p).size
    scale = min(box / iw, box / ih)
    return Image(p, width=iw * scale, height=ih * scale)


def build():
    doc = SimpleDocTemplate(os.path.join(os.path.dirname(__file__), "..", "ZonaRiska_Bestiary.pdf"),
                            pagesize=A4, topMargin=18 * mm, bottomMargin=15 * mm,
                            leftMargin=15 * mm, rightMargin=15 * mm)
    story = []
    story.append(Paragraph("ЗОНА РИСКА", H1))
    story.append(Paragraph("Бестиарий флота ксеносов · порядок появления в бою", SUB))

    story.append(Paragraph("РЯДОВЫЕ КОРАБЛИ", SEC))
    for (ty, mw, hp, sp, sz, rw, hpw, rww, atk, name, ru, desc) in SHIPS:
        lvl = (mw - 1) // 5 + 1
        info = [
            [Paragraph(f"<b>{name}</b>", NAME)],
            [Paragraph(ru, RU)],
            [Paragraph(
                f"<b>Появление:</b> сектор {mw} (уровень {lvl})&nbsp;&nbsp;"
                f"<b>Прочность:</b> {hp} (+{hpw}/сектор)<br/>"
                f"<b>Скорость:</b> {sp}&nbsp;&nbsp;<b>Награда:</b> {rw} кр (+{rww}/сектор)<br/>"
                f"<b>Атака:</b> {ATK.get(atk, atk)}", CELL)],
            [Paragraph(desc, DESC)],
        ]
        inner = Table(info, colWidths=[120 * mm])
        inner.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 1),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        row = Table([[img_cell(SPRITE[ty], 88), inner]], colWidths=[45 * mm, 125 * mm])
        row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#ccd")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f6fb")),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(row)
        story.append(Spacer(1, 6))

    story.append(PageBreak())
    story.append(Paragraph("БОССЫ", SEC))
    for (spr, name, ru, hp, sec, desc) in BOSSES:
        info = [
            [Paragraph(f"<b>{name}</b>", NAME)],
            [Paragraph(ru, RU)],
            [Paragraph(f"<b>Рубеж:</b> сектор {sec}&nbsp;&nbsp;<b>Прочность:</b> {hp}", CELL)],
            [Paragraph(desc, DESC)],
        ]
        inner = Table(info, colWidths=[110 * mm])
        inner.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 1),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        row = Table([[img_cell(spr, 110), inner]], colWidths=[55 * mm, 115 * mm])
        row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#caa")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#faf4f6")),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.append(row)
        story.append(Spacer(1, 8))

    doc.build(story)
    print("PDF готов")


if __name__ == "__main__":
    build()
