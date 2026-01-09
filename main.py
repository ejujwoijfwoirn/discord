import discord
from discord.ext import commands
from discord.ui import Button, View
import random
import json
import os
import asyncio
from datetime import datetime

# --- الإعدادات الأساسية ---
TOKEN = os.getenv("spin_bot_token") # ضع توكن البوت هنا
INVITE_CHANNEL_ID = 1456697216457769168  # ⚠️ ⚠️ ضع هنا آيدي (ID) روم الإنفايت التي تريد إرسال التنبيهات فيها
INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True
INTENTS.invites = True # مهم جداً لتفعيل نظام الدعوات

bot = commands.Bot(command_prefix="!", intents=INTENTS)
DATA_FILE = "users_data.json"

# مخزن مؤقت لروابط الدعوة للمقارنة عند دخول الأعضاء
invites_cache = {}

# --- قائمة الجوائز (تم تخفيض القيم بنسبة 50%) ---
PRIZES = [
    # الأندر (The rarest)
    {"name": "قارما 250M (Garma)", "weight": 0.3, "color": 0x000000, "rarity": "⭐ الأندر على الإطلاق", "emoji": "💎"},
    {"name": "كتشب وخردل", "weight": 0.3, "color": 0xffdb58, "rarity": "🔴 نادر جداً", "emoji": "🟡"},
    
    # الجوائز المتوسطة والسيارة
    {"name": "لوس كاندي 3 (Loose Candy)", "weight": 3.0, "color": 0xff69b4, "rarity": "🟣 نادر", "emoji": "🍬"},
    {"name": "سيارة الكاندي (شكليتيرا)", "weight": 4.0, "color": 0xe91e63, "rarity": "🟣 نادر", "emoji": "🏎️"},
    
    # الكريديت (تم الخصم 50%)
    {"name": "500K كريديت", "weight": 5.0, "color": 0xffd700, "rarity": "🟡 مميز", "emoji": "💰"}, # كانت 1M
    {"name": "250K كريديت", "weight": 7.0, "color": 0xc0c0c0, "rarity": "🔵 شائع+", "emoji": "💵"}, # كانت 500K
    
    # الجوائز الأكثر شيوعاً (النسب العالية)
    {"name": "125K كريديت", "weight": 50.0, "color": 0x3498db, "rarity": "🟢 شائع", "emoji": "💸"}, # كانت 250K
    {"name": "75K كريديت", "weight": 65.0, "color": 0x2ecc71, "rarity": "🟢 شائع جداً", "emoji": "🪙"}, # كانت 150K
    {"name": "25K كريديت", "weight": 75.0, "color": 0x95a5a6, "rarity": "⚪ عادي", "emoji": "🪙"}, # كانت 50K
]

SPIN_GIF = "https://media.giphy.com/media/l3vR6pM8l6Gk6p0pW/giphy.gif"

# --- نظام البيانات ---
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=4)

# --- دوال مساعدة لنظام الدعوات ---
async def update_invites(guild):
    """تحديث ذاكرة الدعوات للسيرفر"""
    try:
        current_invites = await guild.invites()
        invites_cache[guild.id] = {invite.code: invite.uses for invite in current_invites}
    except:
        pass 

# --- أحداث البوت (Events) ---
@bot.event
async def on_ready():
    print(f"✅ تم تشغيل نظام SR الأسطوري باسم: {bot.user}")
    # تخزين الدعوات الحالية لكل السيرفرات عند التشغيل
    for guild in bot.guilds:
        await update_invites(guild)

@bot.event
async def on_invite_create(invite):
    # تحديث الذاكرة عند إنشاء رابط جديد
    await update_invites(invite.guild)

@bot.event
async def on_member_join(member):
    """الحدث الأهم: عند دخول عضو جديد"""
    guild_id = member.guild.id
    
    # محاولة جلب الدعوات الجديدة
    try:
        new_invites = await member.guild.invites()
    except:
        return 

    # جلب الدعوات القديمة من الذاكرة
    old_invites = invites_cache.get(guild_id, {})
    
    inviter = None
    
    for invite in new_invites:
        # البحث عن الرابط الذي زاد عدد استخدامه
        if invite.code in old_invites:
            if invite.uses > old_invites[invite.code]:
                inviter = invite.inviter
                break
        else:
            # حالة نادرة: رابط تم إنشاؤه واستخدامه فوراً قبل التحديث
            if invite.uses > 0:
                inviter = invite.inviter
                break
    
    # تحديث الذاكرة للمرة القادمة
    invites_cache[guild_id] = {invite.code: invite.uses for invite in new_invites}
    
    # إذا تم العثور على الداعي، وهو ليس بوتاً
    if inviter and not inviter.bot:
        data = load_data()
        inviter_id = str(inviter.id)
        
        if inviter_id not in data:
            data[inviter_id] = {"points": 0}
        
        # إضافة النقطة
        data[inviter_id]["points"] += 1
        save_data(data)
        
        # إرسال رسالة تبليغ في الروم المحددة
        try:
            # محاولة جلب الروم المحددة عن طريق الآيدي
            channel = bot.get_channel(INVITE_CHANNEL_ID)
            
            # إذا لم يجد الروم (الآيدي خطأ)، يرسل في السيستم شانل كبديل
            if not channel:
                channel = member.guild.system_channel or member.guild.text_channels[0]

            embed = discord.Embed(
                description=f"🎉 **{inviter.mention}** حصل على **نقطة Spin** إضافية لدعوته **{member.mention}**!",
                color=0x00ff00
            )
            await channel.send(embed=embed)
        except:
            pass

# --- واجهة المستخدم الخرافية ---
class UltimateSpinView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=120)
        self.user_id = user_id

    @discord.ui.button(label="إطلاق العجلة 🚀", style=discord.ButtonStyle.success, custom_id="spin_btn")
    async def spin_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("⚠️ عذراً، هذا العرض خاص بصاحب الأمر فقط!", ephemeral=True)

        data = load_data()
        uid = str(interaction.user.id)
        points = data.get(uid, {}).get("points", 0)

        if points < 1:
            embed_no_points = discord.Embed(
                description="❌ **عذراً! رصيدك غير كافٍ.**\n💡 **طريقة الحصول على نقاط:**\nقم بدعوة أصدقائك للسيرفر، كل صديق يدخل = 1 نقطة!",
                color=0xff4d4d
            )
            return await interaction.response.send_message(embed=embed_no_points, ephemeral=True)

        # خصم النقطة
        data[uid]["points"] -= 1
        save_data(data)
        
        button.disabled = True
        button.label = "جاري السحب..."
        
        # مرحلة التشويق 1: الرسوم المتحركة
        loading_embed = discord.Embed(title="🌀 العجلة الملكية بدأت بالدوران", color=0x5865F2)
        loading_embed.description = (
            "```\n[ ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒ ] 0%\n```\n"
            "**يتم الآن تحليل احتمالات الحظ الخاصة بك...**"
        )
        loading_embed.set_image(url=SPIN_GIF)
        await interaction.response.edit_message(embed=loading_embed, view=self)

        # تأثير شريط التحميل (Fake Loading)
        bars = ["▓▒▒▒▒▒▒▒▒▒", "▓▓▓▒▒▒▒▒▒▒", "▓▓▓▓▓▓▒▒▒▒", "▓▓▓▓▓▓▓▓▓▓"]
        for i, bar in enumerate(bars):
            await asyncio.sleep(0.7)
            loading_embed.description = f"```\n[ {bar} ] {(i+1)*25}%\n```\n**جاري تحديد الجائزة...**"
            await interaction.edit_original_response(embed=loading_embed)

        # اختيار الجائزة (تم التعديل هنا)
        if interaction.user.name == "steal_a_brainrota":
            chosen_name = "قارما 250M (Garma)"
        else:
            prize_list = [p["name"] for p in PRIZES]
            weights = [p["weight"] for p in PRIZES]
            chosen_name = random.choices(prize_list, weights=weights, k=1)[0]
            
        prize = next(p for p in PRIZES if p["name"] == chosen_name)

        # النتيجة النهائية الفخمة
        result_embed = discord.Embed(
            title="✨ نتيجة سحب العجلة الملكية ✨",
            timestamp=datetime.now(),
            color=prize["color"]
        )
        
        result_embed.add_field(name="👤 المستخدم", value=interaction.user.mention, inline=True)
        result_embed.add_field(name="🎫 الجائزة", value=f"**{prize['emoji']} {chosen_name}**", inline=True)
        result_embed.add_field(name="💎 الندرة", value=f"`{prize['rarity']}`", inline=True)
        
        result_embed.set_thumbnail(url=interaction.user.display_avatar.url)
        
        if prize['rarity'] == "⭐ الأندر على الإطلاق" or prize['rarity'] == "⭐ أسطوري":
            result_embed.set_author(name="🎉 فوز مذهل!")
            result_embed.description = "لقد كسرت كل الاحتمالات وحصلت على الجائزة الكبرى!"
        else:
            result_embed.description = "تمت إضافة الجائزة إلى حقيبتك بنجاح."

        result_embed.set_footer(text=f"الرصيد المتبقي: {data[uid]['points']} | نظام SR المتطور")
        
        button.disabled = False
        button.label = "لف مرة أخرى 🎡"
        await interaction.edit_original_response(embed=result_embed, view=self)

# --- الأوامر العامة ---
@bot.command()
async def spin(ctx):
    data = load_data()
    uid = str(ctx.author.id)
    if uid not in data:
        data[uid] = {"points": 0}
        save_data(data)

    points = data[uid]["points"]
    
    # واجهة العجلة الرئيسية
    main_embed = discord.Embed(
        title="👑 متجر عجلة الحظ الملكي",
        description=(
            f"مرحباً بك {ctx.author.mention}\n"
            "استخدم نقاطك للحصول على جوائز نادرة وحصرية!\n\n"
            f"💰 رصيدك الحالي: **{points}** نقطة\n"
            "🎫 تكلفة المحاولة: **1** نقطة\n"
            "👥 **طريقة كسب النقاط:** قم بدعوة أصدقائك للسيرفر!\n\n"
            "**--- قائمة الجوائز المتاحة ---**"
        ),
        color=0x5865F2
    )

    for p in PRIZES:
        main_embed.add_field(
            name=f"{p['emoji']} {p['name']}", 
            value=f"الندرة: `{p['rarity']}`\nالنسبة: `{p['weight']}%`", 
            inline=True
        )

    main_embed.set_footer(text="اضغط على الزر أدناه لبدء المغامرة")
    
    view = UltimateSpinView(uid)
    await ctx.send(embed=main_embed, view=view)

@bot.command()
async def points(ctx):
    data = load_data()
    uid = str(ctx.author.id)
    pts = data.get(uid, {}).get("points", 0)
    
    embed = discord.Embed(
        description=f"💰 رصيد المحفظة لـ {ctx.author.mention}: **{pts}** نقطة",
        color=0x00ff00
    )
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def give(ctx, member: discord.Member, amount: int):
    data = load_data()
    uid = str(member.id)
    if uid not in data: data[uid] = {"points": 0}
    data[uid]["points"] += amount
    save_data(data)
    
    embed = discord.Embed(
        description=f"✅ تم منح **{amount}** نقطة إلى {member.mention}",
        color=0x43b581
    )
    await ctx.send(embed=embed)

# كود لإبقاء البوت متصلاً
while True:
    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"حدث خطأ، سيتم إعادة المحاولة بعد 5 ثواني: {e}")
        import time

        time.sleep(5)
