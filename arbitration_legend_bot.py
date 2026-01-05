import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import asyncio
import os
import json
import datetime

# =========================================================
# ⚙️ إعدادات بوت الوساطة - Arbitration Legend
# =========================================================

TOKEN = os.getenv('middleman_bot_token')  # تأكد من التوكن
MIDDLEMAN_ROLE_ID = 1456396363418828901
LOG_CHANNEL_ID = 1456728865366872209

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=['!', '-', '/'], intents=intents)

active_tickets = {}
ticket_claims = {}
DB_FILE = "mediator_ratings.json"

# =========================================================
# 💾 دوال حفظ واسترجاع التقييمات
# =========================================================

def load_ratings():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_new_rating(mediator_id, stars_count):
    data = load_ratings()
    mid = str(mediator_id)
    if mid not in data:
        data[mid] = []
    data[mid].append(stars_count)
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# =========================================================
# 📝 نموذج كتابة التعليق (Modal) - مظهر احترافي
# =========================================================

class RatingModal(Modal):
    def __init__(self, mediator, stars_count, stars_display, reporter):
        super().__init__(title="✍️ تفاصيل تجربتك")
        self.mediator = mediator
        self.stars_count = stars_count
        self.stars_display = stars_display
        self.reporter = reporter

        self.comment = TextInput(
            label="كيف كانت خدمة الوسيط؟",
            placeholder="اكتب ملاحظاتك هنا... (اختياري)",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )
        self.add_item(self.comment)

    async def on_submit(self, interaction: discord.Interaction):
        # حفظ التقييم في قاعدة البيانات
        save_new_rating(self.mediator.id, self.stars_count)
        
        user_comment = self.comment.value if self.comment.value else "لا يوجد تعليق إضافي"
        
        # إرسال رسالة شكر للمستخدم
        thank_embed = discord.Embed(
            title="✅ تم استلام تقييمك",
            description="شكراً لك! رأيك يساعدنا على تحسين خدماتنا.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=thank_embed, ephemeral=True)

        # إرسال السجل (Log)
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="🌟 تقييم خدمة وساطة",
                color=discord.Color.gold(),
                timestamp=datetime.datetime.now()
            )
            log_embed.set_thumbnail(url=self.mediator.avatar.url if self.mediator.avatar else self.mediator.default_avatar.url)
            log_embed.set_author(name=self.reporter.display_name, icon_url=self.reporter.avatar.url if self.reporter.avatar else self.reporter.default_avatar.url)
            
            log_embed.add_field(name="👮‍♂️ الوسيط", value=self.mediator.mention, inline=True)
            log_embed.add_field(name="👤 العميل", value=self.reporter.mention, inline=True)
            log_embed.add_field(name="⭐ التقييم", value=f"{self.stars_display} **({self.stars_count}/5)**", inline=False)
            log_embed.add_field(name="📝 التعليق", value=f"```{user_comment}```", inline=False)
            log_embed.set_footer(text=f"Mediator ID: {self.mediator.id}")
            
            await log_channel.send(embed=log_embed)

# =========================================================
# 🎮 أوامر التحكم (إضافة - طرد - تغيير اسم - إنهاء)
# =========================================================

def is_ticket(ctx):
    return ctx.channel.category and "Tickets" in ctx.channel.category.name

@bot.command(aliases=['اضافة', 'adduser'])
async def add(ctx, member: discord.Member):
    if is_ticket(ctx):
        await ctx.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
        embed = discord.Embed(description=f"✅ **تم إضافة {member.mention} إلى التذكرة.**", color=discord.Color.green())
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ هذا الأمر يعمل فقط داخل التذاكر.")

@bot.command(aliases=['طرد', 'removeuser', 'kick'])
async def remove(ctx, member: discord.Member):
    if is_ticket(ctx):
        await ctx.channel.set_permissions(member, overwrite=None)
        embed = discord.Embed(description=f"⛔ **تم إخراج {member.mention} من التذكرة.**", color=discord.Color.red())
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ هذا الأمر يعمل فقط داخل التذاكر.")

@bot.command(aliases=['تسمية', 'rename'])
async def name(ctx, *, new_name: str):
    if is_ticket(ctx):
        old_name = ctx.channel.name
        formatted_name = new_name.replace(" ", "-")
        await ctx.channel.edit(name=f"⚖️-{formatted_name}")
        embed = discord.Embed(description=f"✏️ **تم تغيير الاسم إلى `{formatted_name}`**", color=discord.Color.blue())
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ هذا الأمر يعمل فقط داخل التذاكر.")

# === 🔥 أمر إنهاء التذكرة الجديد 🔥 ===
@bot.command(aliases=['انهاء', 'اغلاق', 'close'])
async def close_ticket(ctx):
    if not is_ticket(ctx):
        return await ctx.send("❌ هذا الأمر يعمل فقط داخل التذاكر.")

    # التحقق من الصلاحيات (فقط الوسيط المستلم أو الإدارة أو صاحب الرول)
    role = ctx.guild.get_role(MIDDLEMAN_ROLE_ID)
    is_admin = ctx.author.guild_permissions.administrator
    has_role = role in ctx.author.roles if role else False
    claimer_id = ticket_claims.get(ctx.channel.id)
    is_claimer = claimer_id == ctx.author.id

    if not (has_role or is_admin or is_claimer):
        return await ctx.send("❌ فقط الوسيط المسؤول أو الإدارة يمكنهم إغلاق التذكرة.")

    # عرض خيارات الإغلاق
    close_embed = discord.Embed(
        title="🔒 تأكيد إنهاء العملية",
        description="هل تمت عملية الوساطة بنجاح وتريد أرشفتها؟",
        color=discord.Color.dark_grey()
    )
    await ctx.send(embed=close_embed, view=CloseOptionView())

# =========================================================
# 🎟️ نظام الوساطة (Views)
# =========================================================

class CloseOptionView(View):
    def __init__(self): 
        super().__init__(timeout=None)
    
    @discord.ui.button(label="✅ نعم، تمت بنجاح", style=discord.ButtonStyle.green, custom_id="c_success")
    async def confirm_close(self, i: discord.Interaction, b: discord.ui.Button):
        await i.response.defer()
        
        mediator_id = ticket_claims.get(i.channel.id)
        mediator = i.guild.get_member(mediator_id) if mediator_id else None

        # إرسال التقييم للأطراف (ما عدا البوتات والوسيط)
        if mediator:
            members_to_rate = [x for x in i.channel.members if not x.bot and x.id != mediator_id]
            
            for p in members_to_rate:
                try:
                    rating_embed = discord.Embed(
                        title="🌟 تقييم مستوى الخدمة",
                        description=f"عزيزي {p.name}،\nشكراً لاستخدامك خدماتنا.\n\nكيف كانت تجربتك مع الوسيط {mediator.mention}؟\nيرجى اختيار التقييم المناسب بالأسفل.",
                        color=discord.Color.from_rgb(47, 49, 54) # لون داكن فخم
                    )
                    rating_embed.set_thumbnail(url=i.guild.icon.url if i.guild.icon else None)
                    rating_embed.set_footer(text="Arbitration Legend System")
                    
                    await p.send(embed=rating_embed, view=EnhancedRatingView(mediator, p))
                except Exception as e:
                    print(f"Error sending DM to {p}: {e}")
        
        # رسالة الحذف
        completion_embed = discord.Embed(
            description="📂 **سيتم أرشفة وحذف التذكرة خلال 5 ثواني...**",
            color=discord.Color.greyple()
        )
        await i.channel.send(embed=completion_embed)
        
        await asyncio.sleep(5)
        
        # تنظيف البيانات
        if i.channel.id in ticket_claims: del ticket_claims[i.channel.id]
        for user_id, channel_id in list(active_tickets.items()):
            if channel_id == i.channel.id:
                del active_tickets[user_id]
                break
                
        await i.channel.delete()
    
    @discord.ui.button(label="❌ إلغاء الإغلاق", style=discord.ButtonStyle.grey, custom_id="c_cancel")
    async def cancel_close(self, i, b):
        await i.message.delete()
        await i.response.send_message("تم إلغاء عملية الإغلاق.", ephemeral=True)

class TicketView(View):
    def __init__(self): 
        super().__init__(timeout=None)
    
    @discord.ui.button(label="فتح تذكرة وساطة", style=discord.ButtonStyle.blurple, custom_id="req_ticket", emoji="⚖️")
    async def create_ticket(self, i, b):
        if i.user.id in active_tickets and bot.get_channel(active_tickets[i.user.id]): 
            return await i.response.send_message("❌ لديك تذكرة مفتوحة بالفعل!", ephemeral=True)
        
        g = i.guild
        cat = discord.utils.get(g.categories, name="⚖️ Tickets") or await g.create_category("⚖️ Tickets")
        
        overwrites = {
            g.default_role: discord.PermissionOverwrite(read_messages=False), 
            i.user: discord.PermissionOverwrite(read_messages=True), 
            g.me: discord.PermissionOverwrite(read_messages=True)
        }
        
        middleman_role = g.get_role(MIDDLEMAN_ROLE_ID)
        if middleman_role: 
            overwrites[middleman_role] = discord.PermissionOverwrite(read_messages=True)
        
        ch = await g.create_text_channel(f"⚖️-{i.user.name}", category=cat, overwrites=overwrites)
        active_tickets[i.user.id] = ch.id
        
        welcome_embed = discord.Embed(
            title="⚖️ منطقة الوساطة الآمنة",
            description=f"مرحباً {i.user.mention} 👋\n\nأنت الآن في تذكرة خاصة. يرجى انتظار استلام التذكرة من قبل أحد الوسطاء المعتمدين.\n\n**🛠️ أوامر التحكم:**\n`!add @user` : إضافة طرف آخر\n`!remove @user` : إزالة طرف\n`!name <new_name>` : تغيير اسم الروم\n`!close` : إنهاء التذكرة",
            color=discord.Color.from_rgb(88, 101, 242)
        )
        welcome_embed.set_thumbnail(url=i.user.avatar.url if i.user.avatar else i.user.default_avatar.url)
        welcome_embed.set_footer(text="نضمن لك حقك بآمان 🔒")
        
        await ch.send(f"{i.user.mention} | <@&{MIDDLEMAN_ROLE_ID}>", embed=welcome_embed, view=ControlView())
        await i.response.send_message(f"✅ تم إنشاء التذكرة: {ch.mention}", ephemeral=True)

class ControlView(View):
    def __init__(self): 
        super().__init__(timeout=None)
    
    # تمت إزالة زر الإغلاق من هنا بناءً على طلبك ليصبح أمراً كتابياً فقط
    
    @discord.ui.button(label="🙋‍♂️ استلام التذكرة", style=discord.ButtonStyle.primary, custom_id="claim_tkt")
    async def claim_ticket(self, i: discord.Interaction, b: discord.ui.Button):
        if i.channel.id in ticket_claims:
             return await i.response.send_message("❌ التذكرة مستلمة بالفعل!", ephemeral=True)

        role = i.guild.get_role(MIDDLEMAN_ROLE_ID)
        is_admin = i.user.guild_permissions.administrator
        has_role = role in i.user.roles if role else False

        if not (has_role or is_admin):
            return await i.response.send_message("❌ هذا الزر مخصص للوسطاء فقط.", ephemeral=True)

        ticket_claims[i.channel.id] = i.user.id
        
        b.disabled = True
        b.label = f"الوسيط: {i.user.display_name}"
        b.style = discord.ButtonStyle.success
        
        await i.message.edit(view=self)
        
        claim_embed = discord.Embed(
            description=f"✅ **تم استلام التذكرة بواسطة:** {i.user.mention}\nيرجى طرح تفاصيل الاتفاق الآن.",
            color=discord.Color.gold()
        )
        await i.channel.send(embed=claim_embed)

class EnhancedRatingView(View):
    def __init__(self, mediator, reporter):
        super().__init__(timeout=None)
        self.mediator = mediator
        self.reporter = reporter

    async def open_rating_modal(self, interaction, stars, star_count):
        # هنا نقوم بفتح الـ Modal بدلاً من الانتظار في الشات
        modal = RatingModal(self.mediator, star_count, stars, self.reporter)
        await interaction.response.send_modal(modal)
        
        # تعطيل الأزرار بعد الضغط لمنع التكرار
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

    @discord.ui.button(label="ممتاز (5/5)", style=discord.ButtonStyle.success, emoji="🤩")
    async def rate_5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_rating_modal(interaction, "⭐⭐⭐⭐⭐", 5)

    @discord.ui.button(label="جيد جداً (4/5)", style=discord.ButtonStyle.primary, emoji="😊")
    async def rate_4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_rating_modal(interaction, "⭐⭐⭐⭐", 4)

    @discord.ui.button(label="جيد (3/5)", style=discord.ButtonStyle.secondary, emoji="😐")
    async def rate_3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_rating_modal(interaction, "⭐⭐⭐", 3)

    @discord.ui.button(label="سيء (1/5)", style=discord.ButtonStyle.danger, emoji="😡")
    async def rate_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_rating_modal(interaction, "⭐", 1)

# =========================================================
# 📊 كوماند الإحصائيات (Stats Command)
# =========================================================

@bot.command(aliases=['myratings', 'تقييمي', 'تقييماتي'])
async def stats(ctx, member: discord.Member = None):
    target = member or ctx.author
    data = load_ratings()
    mid = str(target.id)
    
    if mid not in data or not data[mid]:
        return await ctx.send(f"❌ **{target.display_name}** ليس لديه أي تقييمات مسجلة.")
    
    ratings_list = data[mid]
    total_ratings = len(ratings_list)
    average_rating = sum(ratings_list) / total_ratings
    
    count_5 = ratings_list.count(5)
    count_4 = ratings_list.count(4)
    count_3 = ratings_list.count(3)
    count_2 = ratings_list.count(2)
    count_1 = ratings_list.count(1)
    
    def make_bar(count, total):
        percent = (count / total) * 10
        return "▰" * int(percent) + "▱" * (10 - int(percent))

    embed = discord.Embed(
        title=f"📊 ملف الوسيط: {target.display_name}",
        color=discord.Color.from_rgb(255, 215, 0) # Gold
    )
    embed.set_thumbnail(url=target.avatar.url if target.avatar else target.default_avatar.url)
    
    embed.add_field(name="⭐ التقييم العام", value=f"**{average_rating:.2f} / 5.00**", inline=False)
    embed.add_field(name="📦 إجمالي العمليات", value=f"**{total_ratings}**", inline=False)
    
    details = (
        f"`5⭐` {make_bar(count_5, total_ratings)} ({count_5})\n"
        f"`4⭐` {make_bar(count_4, total_ratings)} ({count_4})\n"
        f"`3⭐` {make_bar(count_3, total_ratings)} ({count_3})\n"
        f"`2⭐` {make_bar(count_2, total_ratings)} ({count_2})\n"
        f"`1⭐` {make_bar(count_1, total_ratings)} ({count_1})"
    )
    embed.add_field(name="📈 تحليل الأداء", value=details, inline=False)
    
    await ctx.send(embed=embed)

@bot.event
async def on_ready():
    print(f'✅ {bot.user} - Arbitration Legend (Pro Version) Online!')
    bot.add_view(TicketView())
    bot.add_view(ControlView())
    bot.add_view(CloseOptionView())

@bot.command()
async def setup(ctx):
    if ctx.author.guild_permissions.administrator:
        setup_embed = discord.Embed(
            title="💎 نظام الوساطة المعتمد",
            description="لطلب وسيط لضمان حقك في التعاملات المالية أو التبادلات، اضغط على الزر أدناه.\n\n> **ملاحظة:** فتح التذاكر للجادين فقط.",
            color=discord.Color.from_rgb(44, 47, 51)
        )
        setup_embed.set_image(url="https://media.discordapp.net/attachments/10000/10000/banner.png") # يمكنك وضع رابط بانر هنا
        await ctx.send(embed=setup_embed, view=TicketView())

bot.run(TOKEN)
