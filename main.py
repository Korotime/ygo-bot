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
from datetime import datetime

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
    text = f"🔎 Tổng cộng: **{total}** lá bài liên quan đến tộc **{name}**"
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



# ========== CARD SEARCH BY NAME ==========
async def search_card_by_name(ctx, name):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(API_URL, params={"fname": name}) as resp:
                            data = await resp.json()

                    if "data" not in data:
                        return await ctx.send("❌ Không tìm thấy lá bài nào với tên đó.")

                    results = data["data"]
                    if len(results) == 1:
                        return await send_card_info(ctx, results[0])

                    # Nếu có nhiều lá gần đúng
                    class CardSelectView(View):
                        def __init__(self, results):
                            super().__init__(timeout=30)
                            options = [
                                discord.SelectOption(label=card["name"], value=str(i))
                                for i, card in enumerate(results[:25])
                            ]
                            self.add_item(CardDropdown(options, results))

                    class CardDropdown(Select):
                        def __init__(self, options, results):
                            super().__init__(placeholder="🔍 Chọn lá bài để xem thông tin", options=options, min_values=1, max_values=1)
                            self.results = results

                        async def callback(self, interaction: discord.Interaction):
                            index = int(self.values[0])
                            await send_card_info(interaction, self.results[index])

                    await ctx.send("❓ Có phải bạn đang tìm một trong những lá sau?", view=CardSelectView(results))
class CardSelectView(View):
    def __init__(self, card_names):
        super().__init__(timeout=60)
        self.add_item(CardSelect(card_names))

class CardSelect(Select):
    def __init__(self, card_names):
        options = [
            discord.SelectOption(label=name, description="Nhấn để xem chi tiết")
            for name in card_names[:25]
        ]
        super().__init__(placeholder="🔍 Chọn lá bài để xem thông tin", options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_card = self.values[0]
        await interaction.response.defer()
        await send_card_detail(interaction, selected_card)

                # Gửi thông tin chi tiết của lá bài
async def send_card_info(target, card):
                    embed = discord.Embed(title=card["name"], description=card.get("desc", ""), color=0x1e90ff)
                    embed.add_field(name="Type", value=card.get("type", "Unknown"))
                    if "race" in card:
                        embed.add_field(name="Race", value=card["race"])
                    if "attribute" in card:
                        embed.add_field(name="Attribute", value=card["attribute"])
                    if "card_images" in card:
                        embed.set_thumbnail(url=card["card_images"][0]["image_url"])
                    await target.send(embed=embed)
async def send_card_detail(interaction, card_name):
    async with aiohttp.ClientSession() as session:
        async with session.get(API_URL, params={"name": card_name}) as resp:
            data = await resp.json()
            if "data" not in data:
                await interaction.followup.send("❌ Không tìm thấy thông tin lá bài.")
                return

            card = data["data"][0]
            embed = discord.Embed(title=card["name"], description=card["desc"], color=0x2ecc71)
            embed.set_thumbnail(url=card.get("card_images", [{}])[0].get("image_url", ""))
            embed.add_field(name="Type", value=card.get("type", ""))
            embed.add_field(name="Race", value=card.get("race", ""))
            embed.add_field(name="Attribute", value=card.get("attribute", "N/A"))
            embed.set_footer(text=f"ID: {card.get('id')}")
            await interaction.followup.send(embed=embed, view=VietHoaButtonView(card["name"]))
class VietHoaButton(discord.ui.Button):
                        def __init__(self, card_name):
                            super().__init__(label="Mô Tả Việt Hóa", style=discord.ButtonStyle.success, custom_id="btn_viet_hoa")
                            self.card_name = card_name

async def callback(self, interaction: discord.Interaction):
                            card_row = df_vn[df_vn["name"].str.lower() == self.card_name.lower()]
                            if card_row.empty:
                                await interaction.response.send_message("🛑 Lá bài này chưa được Việt hóa.", ephemeral=True)
                                return

                            desc = str(card_row.iloc[0]["desc"])
                            if "- Được dịch bởi Fanpage Yugioh Đấu Bài Ma Thuật -" not in desc.lower():
                                await interaction.response.send_message("❌ Lá này chưa có bản dịch chính thức.", ephemeral=True)
                            else:
                                await interaction.response.send_message(f"**Mô tả Việt hóa:**\n{desc}", ephemeral=True)
class VietHoaButtonView(discord.ui.View):
    def __init__(self, card_name):
        super().__init__(timeout=None)
        self.add_item(VietHoaButton(card_name))

async def search_card_by_name(ctx, name):
    async with aiohttp.ClientSession() as session:
        async with session.get(API_URL, params={"fname": name}) as resp:
            data = await resp.json()

            if "data" not in data:
                await ctx.send("❌ Không tìm thấy lá bài nào.")
                return

            matches = [c['name'] for c in data['data'] if name.lower() in c['name'].lower()]

            if len(matches) > 1:
                view = CardSelectView(matches)
                await ctx.send("❓ Có phải bạn đang tìm một trong những lá sau?", view=view)
                return

            if len(matches) == 1:
                await send_card_detail(ctx, matches[0])
            else:
                await ctx.send("❌ Không tìm thấy lá bài nào.")
                # Lệnh prefix
@bot.command(name="name")
async def name_prefix(ctx, *, name: str):
                    await search_card_by_name(ctx, name)

                # Slash command
@bot.tree.command(name="name", description="Tìm thông tin 1 lá bài theo tên")
@app_commands.describe(name="Tên lá bài cần tìm")
async def name_slash(interaction: discord.Interaction, name: str):
                    await search_card_by_name(interaction, name)


# ========== META, MIX, HELP, MIXDECK ==========

async def fetch_meta(region: str):
    if region not in ["tcg", "ocg"]:
        return "Region phải là 'tcg' hoặc 'ocg'.", []

    url = f"https://www.yugiohmeta.com/tier-list?region={region.upper()}"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return f"Không thể lấy dữ liệu từ yugiohmeta.com (HTTP {resp.status})", []

            html = await resp.text()

    soup = BeautifulSoup(html, "html.parser")

    labels = soup.select("div.label")
    percents = soup.select("div.bottom-sub-label")

    date_str = f"📊 **Meta {region.upper()}** - cập nhật: {datetime.now().strftime('%d/%m/%Y')}"
    decks = []

    for i in range(min(10, len(labels))):
        name = labels[i].text.strip()
        percent = percents[i].text.strip()
        decks.append(f"{name} - {percent}")

    return date_str, decks

@bot.command(name="metatcg")
async def metatcg(ctx):
    date, lst = await fetch_meta("tcg")
    if isinstance(lst, str):
        await ctx.send(lst)
        return

    msg = f"{date}\n\n"
    msg += "\n".join(f"`{i+1}.` {line}" for i, line in enumerate(lst))
    await ctx.send(msg)

@bot.command(name="metaocg")
async def meta_ocg(ctx):
    text = (
        "📦 **Top 10 Deck OCG - Cập nhật ngày 22/06/2025**\n\n"
        "1. **Vanquish Soul** – (103) 29.10%\n"
        "2. **Yummy** - (84) 23.73%\n"
        "3. **Maliss** – (37) 10.45%\n"
        "4. **Dragon Tail** – (28) 7.91%\n"
        "5. **Sky Striker** – (18) 5.08%\n"
        "6. **Lunalight** – (15) 4.24%\n"
        "7. **White Forest** – (10) 2.82%\n"
        "8. **Crystron** – (8) 2.26%\n"
        "9. **Ryzeal** – (8) 2.26%\n"
        "10. **Blue-Eyes** – (7) 1.98%\n"
    )
    await ctx.send(text)

@bot.tree.command(name="metaocg", description="Top 10 meta OCG")
async def metaocg_slash(interaction: discord.Interaction):
    await meta_ocg(await bot.get_context(interaction))

@bot.command(name="mix")
async def mix_cards(ctx, count: int = 15):
    count = max(1, min(count, 20))
    card_list = [
        "Ash Blossom & Joyous Spring", "Maxx \"C\"", "Called by the Grave", "Infinite Impermanence",
        "Effect Veiler", "Nibiru, the Primal Being", "Ghost Ogre & Snow Rabbit", "Droll & Lock Bird",
        "Dark Ruler No More", "Evenly Matched", "Forbidden Droplet", "Ghost Belle & Haunted Mansion",
        "Lightning Storm", "Raigeki", "Triple Tactics Talent", "Dimension Shifter", "Cosmic Cyclone",
        "Twin Twisters", "Crossout Designator", "Book of Moon"
    ]
    text = "🧠 **Các lá bài linh hoạt dùng được nhiều deck:**\n"
    text += "\n".join(f"• {c}" for c in card_list[:count])
    await ctx.send(text)

@bot.tree.command(name="mix", description="Gợi ý các lá bài linh hoạt")
@app_commands.describe(count="Số lượng bài cần gợi ý (tối đa 20)")
async def mix_slash(interaction: discord.Interaction, count: int = 15):
    await mix_cards(await bot.get_context(interaction), count)

@bot.command(name="metasp")
async def metasp_alias(ctx, count: int = 15):
    await mix_cards(ctx, count)

@bot.tree.command(name="metasp", description="Gợi ý các lá bài linh hoạt (tên khác)")
@app_commands.describe(count="Số lượng bài cần gợi ý (tối đa 20)")
async def metasp_slash(interaction: discord.Interaction, count: int = 15):
    await mix_cards(await bot.get_context(interaction), count)

@bot.command(name="ygohelp")
async def help_command(ctx):
    text = (
        "🤖 **Danh sách lệnh:**\n"
        ".ds <tên_tộc>: Tìm tất cả lá bài thuộc tộc bài\n"
        ".name <tên_lá_bài>: Xem tên và hình ảnh 1 lá bài cụ thể"
        ".metatcg: Top 10 tộc bài meta TCG hiện tại\n"
        ".metaocg: Top 10 tộc bài meta OCG hiện tại\n"
        ".mix [số]: Gợi ý các lá bài linh hoạt\n"
        ".mixdeck <tên_tộc>: Gợi ý tộc bài kết hợp\n"
        ".ping: Kiểm tra bot hoạt động"
    )
    await ctx.send(text)

@bot.tree.command(name="ygohelp", description="Hiển thị danh sách lệnh của bot")
async def help_slash(interaction: discord.Interaction):
    await help_command(await bot.get_context(interaction))

@bot.command(name="mixdeck")
async def mixdeck_prefix(ctx, *, name: str):
    await suggest_mixdeck(ctx, name)

@bot.tree.command(name="mixdeck", description="Gợi ý tộc bài kết hợp tốt với 1 tộc bài")
@app_commands.describe(name="Tên tộc bài")
async def mixdeck_slash(interaction: discord.Interaction, name: str):
    await suggest_mixdeck(interaction, name)

async def suggest_mixdeck(interaction_or_ctx, name):
    if isinstance(interaction_or_ctx, discord.Interaction):
        await interaction_or_ctx.response.send_message(f"⏳ Đang tìm các tộc bài kết hợp với **{name}**... (mất vài giây)")
        followup = interaction_or_ctx.followup
        send_func = followup.send
    else:
        await interaction_or_ctx.send(f"⏳ Đang tìm các tộc bài kết hợp với **{name}**... (mất vài giây)")
        send_func = interaction_or_ctx.send

    suggestions = await fetch_mixdeck_suggestions(name)
    if not suggestions:
        await send_func(f"❌ Không tìm thấy gợi ý nào từ web cho tộc **{name}**.")
        return
    text = f"🔗 **Các tộc bài thường phối hợp với {name} (tham khảo từ Yugipedia):**\n"
    for s in suggestions:
        text += f"• **{s}**\n"
    await send_func(text)

async def fetch_mixdeck_suggestions(archetype):
    query = archetype.replace(" ", "_")
    url = f"https://yugipedia.com/wiki/{query}_(archetype)"
    suggestions = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                header_candidates = soup.find_all("span", class_="mw-headline")
                target_header = None
                for header in header_candidates:
                    if any(kw in header.text for kw in ["Recommended support", "Related archetypes", "Combos", "Mix"]):
                        target_header = header
                        break
                if target_header:
                    for tag in target_header.parent.find_next_siblings():
                        if tag.name == "ul":
                            for li in tag.find_all("li"):
                                text = li.get_text(strip=True)
                                if text and text not in suggestions:
                                    suggestions.append(text)
                                if len(suggestions) >= 10:
                                    break
                            break
    except Exception:
        suggestions = []
    return suggestions

# ========== PING & READY ==========
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
