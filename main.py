import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
from web import keep_alive  # Web server giữ Replit sống
from discord.ui import View, Select
import pandas as pd
import difflib
from bs4 import BeautifulSoup

# Đọc file Excel dịch
try:
    df_vn = pd.read_excel("trans_vn_cards.xlsx", sheet_name="Raw")
    print("✅ File Excel đã được đọc thành công.")
    print(df_vn.head())
except Exception as e:
    print(f"❌ Lỗi khi đọc file Excel: {e}")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=".", intents=intents)
API_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"

@bot.command(name="ds")
async def ds_prefix(ctx, *, name: str):
    await search_and_reply(ctx, name)

@bot.tree.command(name="ds", description="Tìm bài theo tộc bài (gồm các lá support)")
@app_commands.describe(name="Tên tộc bài muốn tìm")
async def ds_slash(interaction: discord.Interaction, name: str):
    await search_and_reply(interaction, name)

async def search_and_reply(interaction_or_ctx, name):
    await interaction_or_ctx.send(f"🔍 Đang tìm bài liên quan đến tộc **{name}**...")

    cards = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL, params={"archetype": name}) as resp:
                data = await resp.json()
                if resp.status == 200 and "data" in data:
                    cards.extend(data["data"])
                else:
                    async with session.get(API_URL) as all_resp:
                        all_data = await all_resp.json()
                        if "data" in all_data:
                            archetypes = sorted(set(c.get("archetype", "") for c in all_data["data"] if "archetype" in c))
                            close = difflib.get_close_matches(name, archetypes, n=1, cutoff=0.6)
                            if close:
                                fixed_name = close[0]
                                await interaction_or_ctx.send(f"↺ Không tìm thấy **{name}**, thử lại với **{fixed_name}**...")
                                return await search_and_reply(interaction_or_ctx, fixed_name)
                            else:
                                await interaction_or_ctx.send(f"❌ Không tìm thấy tộc bài nào tên **{name}**.")
                                return
    except Exception as e:
        await interaction_or_ctx.send(f"❌ Lỗi khi đọc dữ liệu: {e}")
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL) as resp:
                all_data = await resp.json()
                for c in all_data["data"]:
                    if c in cards:
                        continue
                    desc = c.get("desc", "").lower()
                    arche = c.get("archetype", "").lower() if c.get("archetype") else ""
                    if name.lower() in desc and arche != name.lower():
                        cards.append(c)
    except Exception as e:
        print(f"[!] Lỗi khi tìm mô tả: {e}")

    monsters_main, monsters_extra, spells, traps = [], [], [], []

    for c in cards:
        ctype = c.get("type", "")
        card_name = f"> {c['name']}"
        if "Monster" in ctype:
            if any(x in ctype for x in ["Fusion", "Synchro", "Xyz", "Link"]):
                monsters_extra.append(card_name)
            else:
                monsters_main.append(card_name)
        elif "Spell" in ctype:
            spells.append(card_name)
        elif "Trap" in ctype:
            traps.append(card_name)

    total = len(cards)
    text = f"🔎 Tổng cộng: **{total}** lá bài liên quan đến tộc **{name}**
"
    if monsters_main:
        text += "\n-------\n🟧 **Quái Thú Chính:**\n" + "\n".join(monsters_main)
    if monsters_extra:
        text += "\n-------\n🟪 **Quái Thú Extra Deck:**\n" + "\n".join(monsters_extra)
    if spells:
        text += "\n-------\n🟦 **Phép:**\n" + "\n".join(spells)
    if traps:
        text += "\n-------\n🟥 **Bẫy:**\n" + "\n".join(traps)

    if len(text) > 2000:
        chunks = [text[i:i+1900] for i in range(0, len(text), 1900)]
        for chunk in chunks:
            await interaction_or_ctx.send(chunk)
    else:
        await interaction_or_ctx.send(text)

@bot.command()
async def ping(ctx):
    await ctx.send("Tao nè!")

@bot.event
async def on_ready():
    print(f'✅ Bot đang hoạt động dưới tên {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f'✅ Slash commands synced: {len(synced)}')
    except Exception as e:
        print(f'❌ Lỗi sync slash command: {e}')

keep_alive()
TOKEN = os.environ['TOKEN']
bot.run(TOKEN)
