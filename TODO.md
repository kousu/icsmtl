## Bugs

- [x] mtlrave: if link in caption, include in ics; if not, use the telegram post link
- [x] mtlrave: trust the date from the TAG over the date from the OCR
- [ ] lowercase the titles/descriptions from ocr_flyer() (maybe only if they're entirely uppercase?)
- [ ] cultmtl: remove "The post ... first appeared on CultMTL"
- [ ] event de-duplicator
- [ ] consider embedding flyers into events via base64 URL encoding
- [ ] meetup: "The YD Hootenany" isn't being scraped
- [ ] preserve rich text in X-ALT-DESC;FMTTYPE=text/html field
- [ ] Call OCR directly instead of bouncing through @omarieclaire's site
  - it is currently a call to Claude.ai's API; [here is the code](https://www.val.town/x/omarieclaire/image-to-cal/code/main.ts#L516)
    - call Gemini or ChatGPT's free version? Or bounce through OpenRouter.ai?
    - https://openrouter.ai/nvidia/llama-nemotron-embed-vl-1b-v2:free ?
  - replace Claude with a call to a local model (via ollama?)
    - https://huggingface.co/models?pipeline_tag=image-to-text&sort=trending (many of these can be `ollama run`'d directly, or run via llama.cpp, e.g `ollama run hf.co/noctrex/LightOnOCR-2-1B-GGUF:Q4_K_M`)
    - https://huggingface.co/noctrex/PaddleOCR-VL-1.5-GGUF?local-app=ollama
    - https://huggingface.co/xtuner/llava-llama-3-8b-v1_1-gguf?local-app=ollama
    - https://huggingface.co/noctrex/LightOnOCR-2-1B-GGUF?local-app=ollama
    - https://huggingface.co/llava-hf/llava-1.5-7b-hf
    - https://huggingface.co/Qwen/Qwen2-VL-7B-Instruct / https://huggingface.co/Qwen/Qwen3.5-9B
      - https://medium.com/@shivashishbhardwaj/using-qwen-vl-for-vision-language-tasks-a-practical-guide-ba19b6e86d7e
    - other ideas, honestly probably not as accurate:
    - https://huggingface.co/spaces/bp7274/Flyer_Extractor/tree/main
    - https://huggingface.co/spaces/bp7274/Flyer_Extractor/blob/main/app.py
    - https://huggingface.co/spaces/MrAltYT/FlyerDetection/blob/main/app.py
    - https://huggingface.co/spaces/tlogandesigns/image-text-compliance/blob/main/app.py

## Sources

- [ ] https://www.effervescence-citoyenne.xyz/calendrier/
- [ ] https://ra.co/events/ca/montreal
- [ ] https://montreal.askapunk.net/
  - available direct at https://montreal.askapunk.net/feed/ics
- [ ] https://montreal.ca/evenements
- [x] https://www.meetup.com/yellowdoor/events/calendar
  - available direct at https://yellowdoor.org/feed/eo-events/
