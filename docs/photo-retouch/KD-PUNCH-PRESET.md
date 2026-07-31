# KD Punch — пресет ретуши хот-дог / сосиски

Цель: убрать «каталожную тусклость», добавить contrast + цветной punch без оранжевого мыла.  
Референс энергии: Impossible sausage hero / Chomps pack — **не** Getty stock.

До/после на ваших кадрах: [`before-after/`](before-after/)  
Moodboard: [`moodboard.html`](moodboard.html)

---

## 1. Lightroom Classic / Lightroom (Develop)

Создайте пресет **`KD Punch Hotdog v1`** с этими значениями (стартовая точка; ± по кадру).

### Basic
| Параметр | Значение |
|---|---|
| Temp | +3 … +8 (тепло, не +20) |
| Tint | 0 … +3 (чуть magenta, если серый фон) |
| Exposure | +0.10 … +0.25 |
| Contrast | +18 … +25 |
| Highlights | −10 … −20 |
| Shadows | +5 … +15 |
| Whites | +8 … +15 |
| Blacks | −8 … −15 |
| Texture | +15 … +25 |
| Clarity | +8 … +15 |
| Dehaze | 0 … +5 |
| Vibrance | +12 … +18 |
| Saturation | +4 … +8 |

### Presence tip
Сначала Vibrance, потом чуть Saturation. Не наоборот.

### Tone Curve
- Point curve: лёгкий **S** (тени −5, света +5 по ощущению)
- Или Parametric: Lights +10, Darks −5

### HSL / Color — Mixer (главный «модный» рычаг)
| Канал | Hue | Sat | Lum |
|---|---|---|---|
| Red | 0 … −5 | **+20 … +30** | −5 … 0 |
| Orange | −5 … 0 | **+10 … +18** | +5 … +10 (булка) |
| Yellow | 0 … +5 | **+15 … +25** | 0 … +5 (горчица/лук) |
| Green | −5 … 0 | **+18 … +28** | −5 … 0 (огурцы) |
| Aqua/Blue/Purple/Magenta | 0 | 0 | 0 |

### Color Grading (опционально)
- Midtones: Hue ~35–40, Saturation 5–8 (тёплый mid)
- Shadows: Hue ~220, Saturation 3–5 (лёгкий холод в тени = «дорого»)
- Blending 50, Balance 0

### Detail
- Sharpening: Amount 45–55, Radius 1.0, Detail 35, Masking 40–60 (Alt/Option тянуть Masking)
- Noise: только если нужно (Color 10–15)

### Calibration (секретный punch)
| | |
|---|---|
| Red Primary Saturation | +8 … +12 |
| Green Primary Saturation | +4 … +8 |
| Blue Primary Saturation | −2 … 0 |
| Shadows Tint | +2 |

### Фон
1. Кисть / Select Subject → Invert → фон  
2. Exposure +0.15…+0.35, Whites +20, Saturation −20  
3. Или заменить фон на **#FFFFFF** / brand burgundy `#3A1412` в Photoshop после пресета

Сохранить: Develop → Create Preset → группа `Kazan Delicacies` → имя `KD Punch Hotdog v1`.

---

## 2. Capture One

| Инструмент | Значение |
|---|---|
| White Balance | Kelvin +150…300 от авто |
| Exposure | +0.1…0.2 |
| Contrast | +12…18 |
| Brightness | +3…6 |
| Saturation | +6…10 |
| Clarity | +8…12 |
| Structure | +6…10 |
| Levels | RGB чёрная точка чуть вправо, белая чуть влево |
| Color Balance Mid | warm +3…5 |
| Color Editor → Red/Orange/Yellow/Green | Sat +10…20 точечно |
| High Dynamic Range | Highlights −10, Shadows +10 |

Сохранить как Style: `KD Punch Hotdog v1`.

---

## 3. Что пресет НЕ чинит (нужна пересъёмка)

- Полностью плоский softbox без блика на кетчупе  
- Серый «грязный» infinity вместо белого/цветного блока  
- Сухая колбаса без жира/сока  
- Идеально-стерильный зигзаг соуса без жизни  

Мини-бриф на 1 день съёмки — в [`SHOOT-BRIEF.md`](SHOOT-BRIEF.md).

---

## 4. Чеклист «модность» перед экспортом

- [ ] Есть **блик** на соусе или колбасе  
- [ ] Тень читается (не «парит в тумане»)  
- [ ] Кетчуп красный, не кирпичный; горчица жёлтая, не охра  
- [ ] Фон белый чистый **или** один brand-color, не серый  
- [ ] Crop смелее: меньше воздуха, diagonal или macro  
- [ ] Нет оранжевого «Instagram soap» по всей картинке  

---

## 5. Batch на диск

Черновой preview-пайплайн (Python, restrained):

```bash
python3 -m venv /tmp/kd-photo-venv
/tmp/kd-photo-venv/bin/pip install Pillow
# скрипт-логика — как в сессии; эталон результата лежит в before-after/
```

Для продакшена: **Lightroom-пресет выше**, не скрипт.
