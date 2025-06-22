import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
from web import keep_alive  # Web server giữ Replit sống
from discord.ui import View, Select, select
import pandas as pd
import difflib
from bs4 import BeautifulSoup

try:
    df_vn = pd.read_excel("trans_vn_cards.xlsx", sheet_name="Raw")
    print("✅ File Excel đã được đọc thành công.")
    print(df_vn.head())  # In thử vài dòng đầu tiên
except Exception as e:
    print(f"❌ Lỗi khi đọc file Excel: {e}")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=".", intents=intents)
API_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"

# ========== DS COMMAND ==========
async def search_and_reply(interaction_or_ctx, name, use_embed=True):
    await interaction_or_ctx.send(f"🔍 Đang tìm bài thuộc tộc **{name}**...")

    all_cards = []  # Danh sách gộp

    # 1. Lấy từ API chính
    async with aiohttp.ClientSession() as session:
        async with session.get(API_URL, params={"archetype": name}) as resp:
            try:
                data = await resp.json()
                if resp.status == 200 and "data" in data:
                    all_cards.extend(data["data"])
                else:
                    # Gợi ý tên gần đúng nếu sai
                    async with session.get(API_URL) as all_resp:
                        all_data = await all_resp.json()
                        if "data" in all_data:
                            archetypes = sorted(set(card.get("archetype", "") for card in all_data["data"] if "archetype" in card))
                            close = difflib.get_close_matches(name, archetypes, n=1, cutoff=0.6)
                            if close:
                                fixed_name = close[0]
                                await interaction_or_ctx.send(f"↺ Không tìm thấy **{name}**, thử lại với **{fixed_name}**...")
                                return await search_and_reply(interaction_or_ctx, fixed_name)
                            else:
                                await interaction_or_ctx.send(f"❌ Không tìm thấy tộc bài nào tên **{name}**.")
                                return
            except Exception as e:
                await interaction_or_ctx.send(f"❌ Lỗi khi đọc dữ liệu API: {e}")
                return

    # 2. Thêm support từ mô tả (DSP-style)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL) as resp:
                all_data = await resp.json()
                for c in all_data["data"]:
                    desc = c.get("desc", "").lower()
                    arche = c.get("archetype", "").lower()
                    if name.lower() in desc and arche != name.lower():
                        all_cards.append(c)
    except Exception as e:
        print(f"[!] Lỗi khi tìm support mô tả: {e}")

    # 3. Thêm support từ wiki (nếu có)
    try:
        support_cards = await fetch_support_cards(name)
        for card_name in support_cards:
            all_cards.append({"name": card_name, "type": "Support (wiki)"})
    except Exception as e:
        print(f"[!] Lỗi khi lấy support wiki: {e}")

    # 4. Hiển thị gộp tất cả
    card_lines = [f"> {c['name']}" for c in all_cards]
    total = len(card_lines)

    text = f"🔎 Tổng cộng: **{total}** lá bài liên quan đến tộc **{name}**\n\n"
    text += "\n".join(card_lines)

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
                                await interaction.response.send_message(f"**Mô tả Việt hóa:**\n```{desc}```", ephemeral=True)
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

@bot.command(name="meta")
async def meta(ctx):
    text = "🔥 **Top 5 tộc bài meta hiện tại trong Master Duel:**\n"
    text += "\n".join([
        "1. Kashtira – Control + banish face-down; Xyz Rank 7 floodgate",
        "2. Labrynth – Disruption mạnh, kiểm soát bàn đấu",
        "3. Runick – Hỗ trợ Kashtira, extra disruption",
        "4. Spright – Combo Link tốc độ cao",
        "5. Purrely – Control engine giống Kashtira"
    ])
    await ctx.send(text)

@bot.tree.command(name="meta", description="Top 5 tộc bài meta hiện tại")
async def meta_slash(interaction: discord.Interaction):
    await meta(await bot.get_context(interaction))

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
        ".meta: Top 5 tộc bài meta hiện tại\n"
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
    text = f"🔗 **Các tộc bài thường phối hợp với `{name}` (tham khảo từ Yugipedia):**\n"
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
