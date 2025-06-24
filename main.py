import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
from discord.ui import View, Select
import pandas as pd
import difflib
from bs4 import BeautifulSoup
from datetime import datetime

df_vn = pd.read_excel("trans_vn_cards.xlsx")
print("DEBUG tên nhận:", self.card_name)
print("DEBUG danh sách df_vn:", df_vn['name'].str.lower().tolist())

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
            if isinstance(interaction, discord.Interaction):
                await interaction.followup.send(embed=embed, view=VietHoaButtonView(card["name"], df_vn))
            else:
                await interaction.send(embed=embed, view=VietHoaButtonView(card["name"]))
class VietHoaButton(discord.ui.Button):
    def __init__(self, card_name, df_vn):
        super().__init__(label="Mô Tả Việt Hóa", style=discord.ButtonStyle.success, custom_id="btn_viet_hoa")
        self.card_name = card_name
        self.df_vn = df_vn

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        card_row = self.df_vn[self.df_vn["name"].str.lower() == self.card_name.lower()]
        if card_row.empty:
            await interaction.followup.send("🔴 Lá bài này chưa được Việt hóa.", ephemeral=True)
            return

        desc = str(card_row.iloc[0]["desc"])
        if "- Được dịch bởi Fanpage Yugioh Đấu Bài Ma Thuật -" not in desc.lower():
            await interaction.followup.send("❌ Lá này chưa có bản dịch chính thức.", ephemeral=True)
        else:
            await interaction.followup.send(f"**Mô tả Việt hóa:**\n{desc}", ephemeral=True)

class VietHoaButtonView(discord.ui.View):
    def __init__(self, card_name, df_vn):
        super().__init__(timeout=None)
        self.add_item(VietHoaButton(card_name, df_vn))

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
    if region != "tcg":
        return "Chỉ hỗ trợ TCG ở chế độ tự động. OCG cần cập nhật tay."

    # Top 3 chép tay, lấy từ yugiohmeta.com hôm nay (23/06/2025)
    top3 = [
        "1. Maliss - (159) 27.89%",
        "2. Ryzeal Mitsurugi - (156) 27.37%",
        "3. Mitsurugi - (52) 9.12%"
    ]

    url = f"https://www.yugiohmeta.com/tier-list?region=TCG"
    headers = {"User-Agent": "Mozilla/5.0"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return f"Không thể lấy dữ liệu từ yugiohmeta.com (HTTP {resp.status})"
            html = await resp.text()

    soup = BeautifulSoup(html, "html.parser")
    labels = soup.select("div.label")[0:7]   # chỉ lấy 7 cái tiếp theo
    percents = soup.select("div.bottom-sub-label")[0:7]

    others = []
    for i in range(len(labels)):
        name = labels[i].text.strip()
        percent = percents[i].text.strip()
        others.append(f"{i+4}. {name} - {percent}")

    result = f"📊 **Meta TCG** - cập nhật: {datetime.now().strftime('%d/%m/%Y')}\n"
    result += "```" + "\n".join(top3 + others) + "\n```"
    return result

@bot.command(name="metatcg")
async def metatcg(ctx):
    result = await fetch_meta("tcg")
    await ctx.send(result)

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

@bot.command(name="mixtcg")
async def mix_tcg(ctx):
    text = (
        "🧠 **Các lá bài linh hoạt (TCG Meta – cập nhật ngày 23/06/2025):**\n"
        "• MULCHARMY FUWALOS — 90% | 2\n"
        "• ASH BLOSSOM & JOYOUS SPRING — 86% | 2\n"
        "• DROLL & LOCK BIRD — 85% | 2\n"
        "• CALLED BY THE GRAVE — 66% | 1\n"
        "• NIBIRU, THE PRIMAL BEING — 60% | 2\n"
        "• INFINITE IMPERMANENCE — 58% | 2\n"
        "• MULCHARMY PURULIA — 56% | 2\n"
        "• TRIPLE TACTICS TALENT — 46% | 1\n"
        "• DOMINUS IMPULSE — 40% | 2\n"
        "• BYSTIAL MAGNAMHUT — 37% | 1\n"
    )
    await ctx.send(text)
    
@bot.command(name="mixocg")
async def mix_ocg(ctx):
    text = (
        "🧠 **Các lá bài linh hoạt (OCG Meta – cập nhật ngày 23/06/2025):**\n"
        "• MAXX \"C\" — 98% | 2\n"
        "• ASH BLOSSOM & JOYOUS SPRING — 97% | 2\n"
        "• CALLED BY THE GRAVE — 65% | 1\n"
        "• MULCHARMY FUWALOS — 48% | 2\n"
        "• TRIPLE TACTICS TALENT — 47% | 1\n"
        "• CROSSOUT DESIGNATOR — 41% | 1\n"
        "• FORBIDDEN DROPLET — 40% | 2\n"
        "• K9 - #17 IZUNA — 33% | 2\n"
        "• K9 - #ØŰ LUPUS — 33% | 1\n"
        "• TRIPLE TACTICS THRUST — 31% | 1\n"
    )
    await ctx.send(text)

@bot.command(name="ygohelp")
async def help_command(ctx):
    text = (
        "🤖 **Danh sách lệnh:**\n"
        ".ds <tên_tộc>: Tìm tất cả lá bài thuộc tộc bài\n"
        ".name <tên_lá_bài>: Xem tên và hình ảnh 1 lá bài cụ thể"
        ".meta: Top 10 tộc bài meta TCG/OCG hiện tại\n"
        ".mix: Top 10 lá bài support TCG/OCG hiện tại\n"
        ".metasp [số]: Công dụng y như lệnh mix\n"
        ".ping: Kiểm tra bot hoạt động"
    )
    await ctx.send(text)

@bot.command(name="meta")
async def help_command(ctx):
    text = (
        "🤖 **Vui lòng nhập TCG hay OCG:**\n"
        ".metatcg: Top 10 tộc bài meta TCG hiện tại\n"
        ".metaocg: Top 10 tộc bài meta OCG hiện tại\n"
    )
    await ctx.send(text)

@bot.command(name="mix")
async def help_command(ctx):
    text = (
        "🤖 **Vui lòng nhập TCG hay OCG:**\n"
        ".mixtcg: Top 10 lá bài support TCG hiện tại\n"
        ".mixocg: Top 10 lá bài support OCG hiện tại\n"
    )
    await ctx.send(text)

@bot.tree.command(name="ygohelp", description="Hiển thị danh sách lệnh của bot")
async def help_slash(interaction: discord.Interaction):
    await help_command(await bot.get_context(interaction))

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
TOKEN = os.getenv("TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ TOKEN chưa được thiết lập trong biến môi trường.")
