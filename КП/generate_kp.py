#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CALL-TALK КП Генератор
Автоматическая сборка 9-слайдового коммерческого предложения в HTML в фирменном стиле Call-Talk
(Тарифы на 4 и 2 месяца, расчет от маржи, без графического знака рубля)
"""

import os
import sys
import json

def generate(config_path=None):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(base_dir, 'CALL-TALK_КП_Шаблон.html')
    default_config_path = os.path.join(base_dir, 'client_example.json')

    if not os.path.exists(template_path):
        print(f"Ошибка: Шаблон не найден по пути {template_path}")
        return

    data = {}
    if os.path.exists(default_config_path):
        with open(default_config_path, 'r', encoding='utf-8') as f:
            data.update(json.load(f))

    if config_path and os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            data.update(json.load(f))
        print(f"Загружен конфиг из: {config_path}")
    else:
        print("Используются данные по умолчанию из client_example.json")

    with open(template_path, 'r', encoding='utf-8') as f:
        html = f.read()

    for key, val in data.items():
        html = html.replace(f"{{{{{key}}}}}", str(val))

    clean_name = data.get("CLIENT_NAME", "Client").replace(" ", "_").replace('"', "").replace("/", "_")
    output_html = os.path.join(base_dir, f"CALL-TALK_КП_{clean_name}.html")

    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✓ Успешно создан HTML-файл КП (9 слайдов): {output_html}")
    print("ℹ️ Внимание: PDF создается только после утверждения HTML-версии пользователем.")

if __name__ == '__main__':
    cfg = sys.argv[1] if len(sys.argv) > 1 else None
    generate(cfg)
