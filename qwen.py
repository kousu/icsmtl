#!/usr/bin/env python3
#
# Tip: get a token from https://huggingface.co/settings/tokens and pass it by
# $  export HF_TOKEN=hf_....
#
# to get faster initial startup.

import os
from transformers import pipeline

# Use a pipeline as a high-level helper

pipe = pipeline("image-text-to-text",
                #model="Qwen/Qwen2-VL-7B-Instruct",
                model="Qwen/Qwen3.5-9B",
                model=""
                token=os.getenv('HF_TOKEN', None))

messages = [
    {
        "role": "user",
        "content": [
            {"type": "image", "url": "https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/p-blog/candy.JPG"},
#             {"type": "text", "text":
#                 """Today is 2026-03-10. Extract ALL events from this image.

# Return a JSON array. Each event object must have:
# - title: string (REQUIRED)
# - date: YYYY-MM-DD (use 2026 if year not shown)
# - end_date: YYYY-MM-DD or null (for multi-day events)
# - start_time: HH:MM (24h) or null
# - end_time: HH:MM (24h) or null
# - location: venue/address or null
# - description: key details using ORIGINAL wording from the image. Include performers, prices, URLs, special instructions. Keep the poster's voice.

# Rules:
# - Always return a JSON array, even for 1 event
# - Every event MUST have a title
# - Response must be ONLY valid JSON, no markdown fences, no explanation
#             """},
            {"type": "text", "text": "What animal is on the candy?"}
        ]
    },
]
pipe(text=messages)
