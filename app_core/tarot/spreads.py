from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class SpreadPosition:
    index: int
    name_ru: str
    name_en: str
    prompt_hint_ru: str


@dataclass(frozen=True)
class SpreadDefinition:
    slug: str
    title_ru: str
    title_en: str
    description_ru: str
    knowledge_path: str
    positions: List[SpreadPosition]


SPREADS: List[SpreadDefinition] = [
    SpreadDefinition(
        slug="one_card",
        title_ru="Одна карта",
        title_en="One Card",
        description_ru="Быстрая рефлексия: главный смысл момента в одном символическом ключе.",
        knowledge_path="knowledge_base/tarot/spreads/one_card.md",
        positions=[
            SpreadPosition(
                index=0,
                name_ru="Центральный смысл",
                name_en="Central message",
                prompt_hint_ru="Сформулируй главный смысл карты и что именно стоит заметить по вопросу.",
            )
        ],
    ),
    SpreadDefinition(
        slug="three_card_past_present_future",
        title_ru="Три карты: прошлое — настоящее — будущее",
        title_en="Three Card: Past, Present, Future",
        description_ru="Связь раннего влияния с текущей реальностью и возможным следующим направлением (без фатальности).",
        knowledge_path="knowledge_base/tarot/spreads/three_card_past_present_future.md",
        positions=[
            SpreadPosition(
                index=0,
                name_ru="Прошлое",
                name_en="Past",
                prompt_hint_ru="Что из прошлого продолжает влиять на текущую ситуацию/настрой?",
            ),
            SpreadPosition(
                index=1,
                name_ru="Настоящее",
                name_en="Present",
                prompt_hint_ru="Что сейчас является «якорем» вопроса — активное состояние или напряжение?",
            ),
            SpreadPosition(
                index=2,
                name_ru="Будущее",
                name_en="Future",
                prompt_hint_ru="Какая динамика может развиваться дальше, если текущий паттерн сохранится?",
            ),
        ],
    ),
    SpreadDefinition(
        slug="three_card_situation_obstacle_outcome",
        title_ru="Три карты: ситуация — препятствие — исход",
        title_en="Three Card: Situation, Obstacle, Outcome",
        description_ru="Прояснение текущего контекста, основного барьера и того, куда ведёт траектория при ваших условиях.",
        knowledge_path="knowledge_base/tarot/spreads/three_card_situation_obstacle_outcome.md",
        positions=[
            SpreadPosition(
                index=0,
                name_ru="Ситуация",
                name_en="Situation",
                prompt_hint_ru="Зафиксируй контекст и ключевое условие вопроса.",
            ),
            SpreadPosition(
                index=1,
                name_ru="Препятствие",
                name_en="Obstacle",
                prompt_hint_ru="Назови главный барьер, который искажает или тормозит поток.",
            ),
            SpreadPosition(
                index=2,
                name_ru="Итог",
                name_en="Outcome",
                prompt_hint_ru="Какой возможный следующий шаг/направление складывается сейчас — без гарантированности.",
            ),
        ],
    ),
    SpreadDefinition(
        slug="three_card_relationships",
        title_ru="Три карты: я — другой — динамика",
        title_en="Three Card: Relationships",
        description_ru="Понимание роли каждой стороны и активного паттерна между ними — с фокусом на то, что вы можете влиять.",
        knowledge_path="knowledge_base/tarot/spreads/three_card_relationships.md",
        positions=[
            SpreadPosition(
                index=0,
                name_ru="Я",
                name_en="Self",
                prompt_hint_ru="Какой у тебя вклад/позиция/потребности в этом взаимодействии?",
            ),
            SpreadPosition(
                index=1,
                name_ru="Другой человек",
                name_en="Other person",
                prompt_hint_ru="Как выглядит видимая позиция/сторона другого в этой динамике?",
            ),
            SpreadPosition(
                index=2,
                name_ru="Динамика",
                name_en="Dynamic",
                prompt_hint_ru="Что сейчас «держит» контакт и где проявляется активный паттерн?",
            ),
        ],
    ),
    SpreadDefinition(
        slug="three_card_choice",
        title_ru="Три карты: выбор — вариант A/B — скрытый фактор",
        title_en="Three Card: Choice",
        description_ru="Практичный взгляд на два направления и на то, что влияет на оба варианта сразу.",
        knowledge_path="knowledge_base/tarot/spreads/three_card_choice.md",
        positions=[
            SpreadPosition(
                index=0,
                name_ru="Вариант A",
                name_en="Option A",
                prompt_hint_ru="Какая вероятная линия развития, польза и риски у первого варианта?",
            ),
            SpreadPosition(
                index=1,
                name_ru="Вариант B",
                name_en="Option B",
                prompt_hint_ru="Какая вероятная линия развития, польза и риски у второго варианта?",
            ),
            SpreadPosition(
                index=2,
                name_ru="Скрытый фактор",
                name_en="Hidden factor",
                prompt_hint_ru="Что может быть причиной общей динамики для обоих вариантов?",
            ),
        ],
    ),
    SpreadDefinition(
        slug="five_card_deep_reading",
        title_ru="Пять карт: углублённое чтение",
        title_en="Five Card: Deep Reading",
        description_ru="Слои вопроса: влияние, настоящее, скрытый фактор, совет и возможное направление.",
        knowledge_path="knowledge_base/tarot/spreads/five_card_deep_reading.md",
        positions=[
            SpreadPosition(
                index=0,
                name_ru="Прошлое влияние",
                name_en="Past influence",
                prompt_hint_ru="Что из прошлого/фоновой динамики формирует текущий фон?",
            ),
            SpreadPosition(
                index=1,
                name_ru="Текущее состояние",
                name_en="Present state",
                prompt_hint_ru="Как проявляется текущее состояние и что с ним связано?",
            ),
            SpreadPosition(
                index=2,
                name_ru="Скрытое влияние",
                name_en="Hidden influence",
                prompt_hint_ru="Что недооценено/не сразу видно и усложняет картину?",
            ),
            SpreadPosition(
                index=3,
                name_ru="Совет",
                name_en="Advice",
                prompt_hint_ru="Какой мягкий практический сдвиг/настройка поможет?",
            ),
            SpreadPosition(
                index=4,
                name_ru="Возможный результат",
                name_en="Possible result",
                prompt_hint_ru="Какое направление может сложиться, если совет учтён (без окончательности).",
            ),
        ],
    ),
    SpreadDefinition(
        slug="celtic_cross",
        title_ru="Кельтский крест",
        title_en="Celtic Cross",
        description_ru="Глубокое структурированное чтение: напряжение, корень, внутренний/внешний контекст и возможное направление.",
        knowledge_path="knowledge_base/tarot/spreads/celtic_cross.md",
        positions=[
            SpreadPosition(0, "Покрытие / ситуация", "Cover / present situation", "Что сейчас ближе всего к ядру вопроса?"),
            SpreadPosition(1, "Перекрестье / вызов", "Cross / challenge", "Какая главная преграда или напряжение влияет на картину?"),
            SpreadPosition(2, "Корень", "Below / root", "Какой глубинный мотив/основа здесь просматривается?"),
            SpreadPosition(3, "Недавнее прошлое", "Behind / recent past", "Что недавно сдвигало динамику и уходит из фокуса?"),
            SpreadPosition(4, "Возможность / вершина", "Crown / possibility", "Какое лучшее доступное направление раскрывается сознательно?"),
            SpreadPosition(5, "Ближайшее будущее", "Ahead / near future", "Что может проявиться в ближайшей последовательности событий?"),
            SpreadPosition(6, "Внутренняя позиция", "Self", "Как ты настроен(а) изнутри и что это говорит о твоей роли?"),
            SpreadPosition(7, "Окружение", "Environment", "Как внешние факторы/отношения влияют на динамику?"),
            SpreadPosition(8, "Надежды и страхи", "Hopes and fears", "Что ты хочешь удержать и чего боишься потерять?"),
            SpreadPosition(9, "Возможный исход", "Possible outcome", "Какое направление выглядит наиболее вероятным при текущих условиях?"),
        ],
    ),
    SpreadDefinition(
        slug="twelve_months",
        title_ru="Двенадцать месяцев",
        title_en="Twelve Months",
        description_ru="Отражение тем в циклах времени: что выходит на передний план по месяцам.",
        knowledge_path="knowledge_base/tarot/spreads/twelve_months.md",
        positions=[
            SpreadPosition(0, "Текущий месяц", "Current month", "Главная тема ближайшего месяца — что заметить?"),
            SpreadPosition(1, "Следующий месяц", "Next month", "Какая тема начинает проявляться дальше?"),
            SpreadPosition(2, "Месяц 3", "Month 3", "Как развивается линия?"),
            SpreadPosition(3, "Месяц 4", "Month 4", "Где появляется новая окраска/задача?"),
            SpreadPosition(4, "Месяц 5", "Month 5", "Что требует внимания?"),
            SpreadPosition(5, "Месяц 6", "Month 6", "Где происходит внутренняя настройка?"),
            SpreadPosition(6, "Месяц 7", "Month 7", "Как меняется ритм?"),
            SpreadPosition(7, "Месяц 8", "Month 8", "Что усиливается или уходит?"),
            SpreadPosition(8, "Месяц 9", "Month 9", "Какая точка проверки?"),
            SpreadPosition(9, "Месяц 10", "Month 10", "Что созревает в результате?"),
            SpreadPosition(10, "Месяц 11", "Month 11", "Как подводится база к завершению года?"),
            SpreadPosition(11, "Месяц 12", "Month 12", "Какой общий итог/тема цикла по завершению?"),
        ],
    ),
    SpreadDefinition(
        slug="horoscope_spread",
        title_ru="Гороскопный расклад",
        title_en="Horoscope Spread",
        description_ru="Широкая карта областей жизни: где что доминирует и как это сочетается в общей картине.",
        knowledge_path="knowledge_base/tarot/spreads/horoscope_spread.md",
        positions=[
            SpreadPosition(0, "Я и жизненность", "Self and vitality", "Как проявляется твой внутренний тон и присутствие?"),
            SpreadPosition(1, "Ресурсы и ценности", "Resources and values", "Что поддерживает и что для тебя важно?"),
            SpreadPosition(2, "Коммуникация и обучение", "Communication and learning", "Какие сообщения/обучение заметны?"),
            SpreadPosition(3, "Дом и корни", "Home and roots", "Что говорит о фундаменте и безопасности?"),
            SpreadPosition(4, "Творчество и удовольствие", "Creativity and pleasure", "Где хочется творить/радоваться?"),
            SpreadPosition(5, "Работа и рутины", "Work and routines", "Что в твоих повседневных обязанностях требует внимания?"),
            SpreadPosition(6, "Партнёрства", "Partnerships", "Какие связи/контракты формируют поле?"),
            SpreadPosition(7, "Общие ресурсы и трансформация", "Shared resources and transformation", "Где идут изменения через общие ресурсы?"),
            SpreadPosition(8, "Вера и расширение", "Beliefs and expansion", "Как расширяется взгляд/перспектива?"),
            SpreadPosition(9, "Карьера и публичная роль", "Career and public role", "Какой вектор проявляется в направлении статуса/дела?"),
            SpreadPosition(10, "Друзья и надежды", "Friends and hopes", "Кого ты выбираешь вокруг и что поддерживает надежду?"),
            SpreadPosition(11, "Внутренняя жизнь и скрытое", "Inner life and hidden matters", "Какие тонкие процессы/темы внутри созревают?"),
        ],
    ),
]

SPREAD_BY_SLUG: Dict[str, SpreadDefinition] = {s.slug: s for s in SPREADS}


def list_spreads() -> List[SpreadDefinition]:
    return list(SPREADS)


def get_spread(spread_slug: str) -> SpreadDefinition:
    key = (spread_slug or "").strip()
    if key not in SPREAD_BY_SLUG:
        known = ", ".join(sorted(SPREAD_BY_SLUG.keys()))
        raise ValueError(f"Unknown spread slug: {spread_slug}. Known: {known}")
    return SPREAD_BY_SLUG[key]

