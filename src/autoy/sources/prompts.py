SHORTS_SCRIPT_RULES = {
    "ru": """

Дополнительные требования (не меняют формат ответа — по-прежнему только JSON):
- ЭТО СЦЕНАРИЙ ДЛЯ YOUTUBE SHORTS НА 30 СЕКУНД. Поле "text" — строго 60-75 слов, не более 480 символов. Это жёсткий лимит: лучше выбросить деталь, чем превысить.
- Структура "text" (соблюдать строго):
  Предложение 1 (ХУК, 0-2 сек) — самый шокирующий или неожиданный факт. Без разгона, без "стало известно", без "по данным источников", без названия ведомства в начале. Обращайся к зрителю. Плохо: "Швейцария присоединилась к 20-му пакету санкций ЕС". Хорошо: "Швейцария только что перестала быть нейтральной."
  Предложения 2-5 (СУТЬ) — одна мысль на предложение, максимум 12 слов каждое, активный залог, конкретные цифры и имена. Никаких вводных конструкций.
  Предпоследнее предложение (ВОПРОС) — короткий провокационный вопрос зрителю: "Кто здесь прав?", "Чем это закончится?", "Это победа или капитуляция?".
  Последнее предложение (ЗАЦЕПКА) — одна фраза, из-за которой хочется пересмотреть или остаться: "И это только первый шаг." / "Подписывайся — дальше будет жёстче."
- ЗАПРЕЩЕННЫЕ ОБОРОТЫ: "Кроме того", "Более того", "Также стоит отметить", "Важно отметить", "играет ключевую роль", "В заключение", "В этом видео", "по сообщениям СМИ".
- "title" — максимум 8 слов, это не заголовок новостной ленты, а крючок. Меняй формат каждый раз, не повторяй одно и то же начало. Форматы: "Это меняет всё: ...", "Никто не ожидал: ...", "[Страна] сделала то, чего боялись", "Что скрывают за ...", "[Число] часов до ...", "Почему [X] вдруг ...".
- Заголовок не должен начинаться со слов: "Россия", "Украина", "США" — начинай с действия или интриги, а не с субъекта.
- Не сокращай смысл до бессмыслицы: факты должны остаться проверяемыми и точными.""",
    "en": """

Additional requirements (the response format is unchanged — still JSON only):
- THIS IS A 30-SECOND YOUTUBE SHORTS SCRIPT. The "text" field must be 60-75 words and no more than 480 characters. Hard limit: drop a detail rather than exceed it.
- "text" structure (follow strictly):
  Sentence 1 (HOOK, 0-2 sec) — the single most shocking or unexpected fact. No wind-up, no "according to reports", no agency name first. Speak to the viewer.
  Sentences 2-5 (SUBSTANCE) — one idea per sentence, max 12 words each, active voice, concrete numbers and names. No connective filler.
  Second-to-last sentence (QUESTION) — a short provocative question: "Who is right here?", "How does this end?", "A win or a surrender?".
  Last sentence (LOOP) — one line that makes the viewer stay or rewatch: "And this is only the first step." / "Follow — the next one is bigger."
- BANNED PHRASES: "Additionally", "Furthermore", "Moreover", "It is important to note", "plays a crucial role", "In conclusion", "In this video", "according to reports".
- "title" — max 8 words, a hook, not a newswire headline. Rotate the format every time. Formats: "This Changes Everything: ...", "Nobody Expected This: ...", "[Country] Just Did the Unthinkable", "What They Hid About ...", "[N] Hours Until ...", "Why [X] Suddenly ...".
- Do not start the title with "Russia", "Ukraine", "US" — start with the action or the intrigue.
- Do not sacrifice accuracy: every fact must stay verifiable.""",
}


def shorts_rules(lang: str) -> str:
    return SHORTS_SCRIPT_RULES.get(lang, SHORTS_SCRIPT_RULES["en"])
