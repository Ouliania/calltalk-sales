#!/usr/bin/env bash
# ==============================================================================
# ЕДИНЫЙ СТАНДАРТНЫЙ СКРИПТ ТРАНСКРИБАЦИИ ВСТРЕЧ ДЛЯ CALL-TALK
# ==============================================================================
# Использование:
#   ./transcribe_meeting.sh "/путь/к/файлу/записи.webm" [директория_для_текста]
#
# Скрипт:
# 1. Извлекает легкое моно-аудио (16kHz, 64kbps MP3) через системный ffmpeg за 2-4 секунды.
# 2. Транскрибирует через предустановленный whisper CLI на CPU с моделью base (ru).
# 3. Сохраняет итоговый .txt файл в указанную папку (по умолчанию ./transcripts).
# ==============================================================================

set -e

INPUT_FILE="$1"
OUT_DIR="${2:-/Users/ulyana/CALL TALK/transcripts}"

if [ -z "$INPUT_FILE" ]; then
    echo "Ошибка: Укажите путь к аудио- или видеофайлу записи встречи."
    echo "Пример: ./transcribe_meeting.sh '/Users/ulyana/Downloads/Meeting.webm'"
    exit 1
fi

if [ ! -f "$INPUT_FILE" ]; then
    echo "Ошибка: Файл не найден: $INPUT_FILE"
    exit 1
fi

mkdir -p "$OUT_DIR"
mkdir -p "/Users/ulyana/CALL TALK/scratch"

FILENAME=$(basename "$INPUT_FILE")
BASENAME="${FILENAME%.*}"
AUDIO_TMP="/Users/ulyana/CALL TALK/scratch/${BASENAME}_audio.mp3"
RESULT_TXT="$OUT_DIR/${BASENAME}.txt"

echo "=== [1/2] Извлечение аудио из $FILENAME ==="
/opt/homebrew/bin/ffmpeg -y -i "$INPUT_FILE" -vn -ar 16000 -ac 1 -c:a libmp3lame -b:a 64k "$AUDIO_TMP" -loglevel error

echo "=== [2/2] Транскрибация через Whisper (CPU, model: base, lang: ru) ==="
/opt/homebrew/bin/whisper "$AUDIO_TMP" --model base --language ru --device cpu --output_dir "$OUT_DIR" --output_format txt

# Удаляем временное аудио
rm -f "$AUDIO_TMP"

echo "=== Готово! Результат сохранен в: $RESULT_TXT ==="
