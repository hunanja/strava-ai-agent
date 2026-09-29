import asyncio
import json
import sys

import anthropic
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

MODEL = "claude-sonnet-5-5"
MAX_STEPS = 8  # pysäytysehto, ettei agentti kierrä loputtomiin

SYSTEM = (
    "Olet urheiluanalyytikko, joka auttaa juoksijaa ja pyöräilijää ymmärtämään "
    "treenidataansa. Hae aina data työkaluilla ennen kuin teet väitteitä "
    "treeneistä. Jos dataa ei ole tai se ei riitä johtopäätökseen, sano se "
    "suoraan äläkä arvaa. Vastaa suomeksi ja tiiviisti."
)

llm = anthropic.AsyncAnthropic()


async def main():
    params = StdioServerParameters(command=sys.executable, args=["strava_server.py"])

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1. Hae työkalut palvelimelta ja käännä Anthropicin muotoon
            listed = await session.list_tools()
            tools = [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "input_schema": t.inputSchema,
                }
                for t in listed.tools
            ]
            print("Työkalut:", [t["name"] for t in tools])

            messages = []
            while True:
                question = input("\nKysy (tyhjä lopettaa): ").strip()
                if not question:
                    break
                messages.append({"role": "user", "content": question})

                # 2. Agenttisilmukka
                for step in range(MAX_STEPS):
                    resp = await llm.messages.create(
                        model=MODEL,
                        max_tokens=1500,
                        system=SYSTEM,
                        tools=tools,
                        messages=messages,
                    )
                    messages.append({"role": "assistant", "content": resp.content})

                    if resp.stop_reason != "tool_use":
                        break

                    results = []
                    for block in resp.content:
                        if block.type != "tool_use":
                            continue
                        print(f"  → {block.name}({json.dumps(block.input)})")
                        result = await session.call_tool(block.name, block.input)
                        text = "\n".join(
                            c.text for c in result.content if c.type == "text"
                        )
                        results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": text,
                            "is_error": bool(result.isError),
                        })
                    messages.append({"role": "user", "content": results})
                else:
                    print("Pysäytetty: askelraja täyttyi.")

                answer = "".join(b.text for b in resp.content if b.type == "text")
                print("\n" + answer)


asyncio.run(main())