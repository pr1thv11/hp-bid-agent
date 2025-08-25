# browser_runner.py  (simplified)
import os, base64, json, sys, asyncio
from openai import OpenAI
from playwright.async_api import async_playwright

WIDTH, HEIGHT = 1280, 800
client = OpenAI()

async def main(task_json):
    task = json.loads(task_json)
    prompt   = task["prompt"]
    max_turn = task.get("max_turns", 15)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True,
                                          args=["--disable-extensions","--disable-file-system"])
        page = await browser.new_page(viewport={"width": WIDTH,"height": HEIGHT})
        await page.goto("about:blank")

        def snap():
            return base64.b64encode(page.screenshot(full_page=False)).decode()

        # ---- first model call
        resp = client.responses.create(
            model="computer-use-preview",
            tools=[{"type":"computer_use_preview",
                    "display_width":WIDTH,"display_height":HEIGHT,
                    "environment":"browser"}],
            input=[{"type":"message","role":"user","content":prompt},
                   {"type":"input_image","image_url":f"data:image/png;base64,{snap()}"}],
            truncation="auto"
        )

        for _ in range(max_turn):
            calls = [item for item in resp.output if item["type"]=="computer_call"]
            if not calls:
                break

            call = calls[0]
            act  = call["action"]

            # ---- execute action -------------------------------------------------
            t   = act["type"]
            if t=="click":
                await page.mouse.click(act["x"],act["y"],button=act.get("button","left"))
            elif t=="type":
                await page.keyboard.type(act["text"])
            elif t=="keypress":
                for k in act["keys"]: await page.keyboard.press(k)
            elif t=="scroll":
                await page.mouse.move(act["x"],act["y"])
                await page.evaluate(f"window.scrollBy({act['scrollX']},{act['scrollY']})")
            elif t=="wait":
                await page.wait_for_timeout(2000)
            # --------------------------------------------------------------------

            # follow-up
            resp = client.responses.create(
                model="computer-use-preview",
                previous_response_id=resp.id,
                tools=[{"type":"computer_use_preview",
                        "display_width":WIDTH,"display_height":HEIGHT,
                        "environment":"browser"}],
                input=[{"type":"computer_call_output",
                        "call_id":call["call_id"],
                        "output":{"type":"computer_screenshot",
                                  "image_url":f"data:image/png;base64,{snap()}"},
                        "current_url":page.url}],
                truncation="auto")

        await browser.close()
        print(json.dumps({"final_output":resp.output},ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
