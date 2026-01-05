import discord
from discord.ext import commands
from discord.ui import Button, View
import asyncio
import os
import json

# =========================================================
# ⚙️ إعدادات بوت الوساطة - Arbitration Legend
# =========================================================

TOKEN = os.getenv('middleman_bot_token')  # تأكد من التوكن
MIDDLEMAN_ROLE_ID = 1456396363418828901
LOG_CHANNEL_ID = 1456728865366872209

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
# تم إضافة علامة التعجب ! كبادئة للأوامر
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
# 🎮 أوامر التحكم (إضافة - طرد - تغيير اسم)
# =========================================================

# 1. أمر إضافة عضو
@bot.command(aliases=['اضافة', 'adduser'])
async def add(ctx, member: discord.Member):
    # التأكد أن الأمر يتم داخل تذكرة (يمكنك تعديل الشرط حسب رغبتك)
    if ctx.channel.category and "Tickets" in ctx.channel.category.name:
        await ctx.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
        embed = discord.Embed(description=f"✅ **تم إضافة {member.mention} إلى التذكرة بنجاح.**", color=discord.Color.green())
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ هذا الأمر يعمل فقط داخل التذاكر.")

# 2. أمر طرد عضو
@bot.command(aliases=['طرد', 'removeuser', 'kick'])
async def remove(ctx, member: discord.Member):
    if ctx.channel.category and "Tickets" in ctx.channel.category.name:
        # إزالة الصلاحيات (Overwrite = None) تعني العودة للإعدادات الافتراضية (لا يرى الروم)
        await ctx.channel.set_permissions(member, overwrite=None)
        embed = discord.Embed(description=f"⛔ **تم إخراج {member.mention} من التذكرة.**", color=discord.Color.red())
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ هذا الأمر يعمل فقط داخل التذاكر.")

# 3. أمر تغيير اسم التذكرة
@bot.command(aliases=['تسمية', 'rename'])
async def name(ctx, *, new_name: str):
    if ctx.channel.category and "Tickets" in ctx.channel.category.name:
        old_name = ctx.channel.name
        # استبدال المسافات بشرطات لأن ديسكورد لا يقبل مسافات في أسماء الرومات النصية
        formatted_name = new_name.replace(" ", "-")
        await ctx.channel.edit(name=f"⚖️-{formatted_name}")
        
        embed = discord.Embed(description=f"✏️ **تم تغيير اسم التذكرة من `{old_name}` إلى `{formatted_name}`**", color=discord.Color.blue())
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ هذا الأمر يعمل فقط داخل التذاكر.")

# =========================================================
# 🎟️ نظام الوساطة (Views)
# =========================================================

class CloseOptionView(View):
    def __init__(self): 
        super().__init__(timeout=None)
    
    @discord.ui.button(label="✅ تمت العملية", style=discord.ButtonStyle.green, custom_id="c_success")
    async def s(self, i: discord.Interaction, b: discord.ui.Button):
        await i.response.defer()
        
        mediator_id = ticket_claims.get(i.channel.id)
        mediator = i.guild.get_member(mediator_id) if mediator_id else None

        if not mediator:
            await i.channel.send("⚠️ تنبيه: لم يتم تسجيل وسيط لهذه التذكرة، لن يتم إرسال طلبات تقييم.")
        else:
            # استثناء البوتات والوسيط من التقييم
            members_to_rate = [x for x in i.channel.members if not x.bot and x.id != mediator_id]
            
            for p in members_to_rate:
                try:
                    rating_embed = discord.Embed(
                        title="⭐ تقييم الوسيط الأسطوري",
                        description=f"العملية تمت بنجاح! \nما رأيك في خدمات الوسيط {mediator.mention}؟\n\nاختر التقييم المناسب من الأزرار أدناه",
                        color=discord.Color.from_rgb(255, 215, 0)
                    )
                    rating_embed.set_thumbnail(url=mediator.avatar.url if mediator.avatar else mediator.default_avatar.url)
                    rating_embed.set_footer(text="تقييمك سيساعدنا في تحسين الخدمة")
                    
                    await p.send(embed=rating_embed, view=EnhancedRatingView(mediator, p))
                except Exception as e:
                    print(f"Error sending DM to {p}: {e}")
        
        completion_embed = discord.Embed(
            title="🎉 تمت العملية بنجاح",
            description="سيتم حذف التذكرة خلال 5 ثواني...",
            color=discord.Color.green()
        )
        if mediator:
            completion_embed.add_field(name="الوسيط", value=mediator.mention)

        await i.channel.send(embed=completion_embed)
        
        await asyncio.sleep(5)
        
        if i.channel.id in ticket_claims: del ticket_claims[i.channel.id]
        for user_id, channel_id in list(active_tickets.items()):
            if channel_id == i.channel.id:
                del active_tickets[user_id]
                break
                
        await i.channel.delete()
    
    @discord.ui.button(label="❌ إلغاء", style=discord.ButtonStyle.red, custom_id="c_fail")
    async def f(self, i, b):
        cancel_embed = discord.Embed(
            title="❌ تم إلغاء التذكرة",
            description="سيتم حذف التذكرة خلال 3 ثواني...",
            color=discord.Color.red()
        )
        await i.response.send_message(embed=cancel_embed)
        await asyncio.sleep(3)
        
        if i.channel.id in ticket_claims: del ticket_claims[i.channel.id]
        for user_id, channel_id in list(active_tickets.items()):
            if channel_id == i.channel.id:
                del active_tickets[user_id]
                break
                
        await i.channel.delete()

class TicketView(View):
    def __init__(self): 
        super().__init__(timeout=None)
    
    @discord.ui.button(label="⚖️ طلب وسيط", style=discord.ButtonStyle.blurple, custom_id="req_ticket", emoji="⚖️")
    async def c(self, i, b):
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
            title="⚖️ تذكرة وساطة جديدة",
            description=f"مرحباً {i.user.mention}!\n\nأنت الآن في قناة الوساطة.\nالرجاء انتظار أحد الوسطاء لاستلام التذكرة.\n\n**الأوامر المتاحة:**\n`!add @user` : لإضافة عضو\n`!remove @user` : لطرد عضو\n`!name <new_name>` : لتغيير اسم التذكرة",
            color=discord.Color.from_rgb(138, 43, 226)
        )
        welcome_embed.set_footer(text="نظام الأوامر", icon_url=i.user.avatar)
        
        # تم تعديل الفيو هنا لاستخدام ControlView المعدل (بدون زر إضافة)
        await ch.send(f"{i.user.mention} | <@&{MIDDLEMAN_ROLE_ID}>", embed=welcome_embed, view=ControlView())
        await i.response.send_message(f"✅ تم فتح تذكرتك: {ch.mention}", ephemeral=True)

class ControlView(View):
    def __init__(self): 
        super().__init__(timeout=None)
    
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
        b.label = f"مستلمة بواسطة: {i.user.display_name}"
        b.style = discord.ButtonStyle.secondary
        
        await i.message.edit(view=self)
        
        claim_embed = discord.Embed(
            description=f"✅ **تم استلام التذكرة بواسطة الوسيط:** {i.user.mention}\n\nيمكنك الآن استخدام الأوامر:\n`!add`, `!remove`, `!name`",
            color=discord.Color.gold()
        )
        await i.channel.send(embed=claim_embed)

    # تمت إزالة زر إضافة عضو من هنا لأنك تريدها كأمر كتابي

    @discord.ui.button(label="🔖 إنهاء التذكرة", style=discord.ButtonStyle.red, custom_id="cls_tkt")
    async def c(self, i, b):
        close_embed = discord.Embed(
            title="🔍 هل اكتملت المشكلة؟",
            description="اختر إذا تمت العملية أم لا",
            color=discord.Color.orange()
        )
        await i.response.send_message(embed=close_embed, view=CloseOptionView())

class EnhancedRatingView(View):
    def __init__(self, mediator, reporter):
        super().__init__(timeout=None)
        self.mediator = mediator
        self.reporter = reporter

    async def submit_rating(self, interaction, stars, star_count):
        save_new_rating(self.mediator.id, star_count)

        prompt_embed = discord.Embed(
            title="✍️ أضف تعليقك (اختياري)",
            description="اكتب تعليقك في الشات. لديك 60 ثانية\n(إذا لم تكتب شيء سيتم تسجيل التقييم بدون تعليق)",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=prompt_embed, ephemeral=True)

        def check(m):
            return m.author == self.reporter and isinstance(m.channel, discord.DMChannel)

        try:
            msg = await bot.wait_for('message', check=check, timeout=60)
            comment = msg.content
        except asyncio.TimeoutError:
            comment = "(لا يوجد تعليق)"

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="🌟 تقييم أسطوري جديد 🌟",
                color=discord.Color.from_rgb(255, 215, 0)
            )
            embed.set_thumbnail(url=self.mediator.avatar.url if self.mediator.avatar else self.mediator.default_avatar.url)
            
            stars_display = "⭐" * star_count + "☆" * (5 - star_count)
            
            embed.add_field(name="👤 الوسيط (المُقيَّم)", value=self.mediator.mention, inline=True)
            embed.add_field(name="👤 المُقيِّم", value=self.reporter.mention, inline=True)
            embed.add_field(name="⭐ التقييم", value=f"{stars_display}\n({star_count}/5)", inline=True)
            embed.add_field(name="💬 التعليق", value=f">>> {comment}", inline=False)
            embed.set_footer(text=f"تم التقييم في {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
            
            await log_channel.send(embed=embed)

        thanks_embed = discord.Embed(
            title="✅ شكراً على تقييمك!",
            description="تقييمك وصل وتم تسجيله بنجاح.",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=thanks_embed, ephemeral=True)
        
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

    @discord.ui.button(label="⭐⭐⭐⭐⭐ ممتاز جداً", style=discord.ButtonStyle.success)
    async def rate_5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.submit_rating(interaction, "⭐⭐⭐⭐⭐", 5)

    @discord.ui.button(label="⭐⭐⭐⭐ جيد جداً", style=discord.ButtonStyle.blurple)
    async def rate_4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.submit_rating(interaction, "⭐⭐⭐⭐", 4)

    @discord.ui.button(label="⭐⭐⭐ جيد", style=discord.ButtonStyle.blurple)
    async def rate_3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.submit_rating(interaction, "⭐⭐⭐", 3)

    @discord.ui.button(label="⭐⭐ مقبول", style=discord.ButtonStyle.gray)
    async def rate_2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.submit_rating(interaction, "⭐⭐", 2)

    @discord.ui.button(label="⭐ سيء", style=discord.ButtonStyle.danger)
    async def rate_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.submit_rating(interaction, "⭐", 1)

# =========================================================
# 📊 كوماند الإحصائيات (Stats Command)
# =========================================================

@bot.command(aliases=['myratings', 'تقييمي', 'تقييماتي'])
async def stats(ctx, member: discord.Member = None):
    target = member or ctx.author
    data = load_ratings()
    mid = str(target.id)
    
    if mid not in data or not data[mid]:
        return await ctx.send(f"❌ **{target.display_name}** ليس لديه أي تقييمات مسجلة حتى الآن.")
    
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
        return "🟦" * int(percent) + "⬜" * (10 - int(percent))

    embed = discord.Embed(
        title=f"📊 إحصائيات الوسيط: {target.display_name}",
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=target.avatar.url if target.avatar else target.default_avatar.url)
    
    embed.add_field(name="🌟 التقييم العام", value=f"**{average_rating:.2f} / 5.00**", inline=False)
    embed.add_field(name="📦 عدد العمليات", value=f"**{total_ratings} عملية**", inline=False)
    
    details = (
        f"5⭐: {make_bar(count_5, total_ratings)} ({count_5})\n"
        f"4⭐: {make_bar(count_4, total_ratings)} ({count_4})\n"
        f"3⭐: {make_bar(count_3, total_ratings)} ({count_3})\n"
        f"2⭐: {make_bar(count_2, total_ratings)} ({count_2})\n"
        f"1⭐: {make_bar(count_1, total_ratings)} ({count_1})"
    )
    embed.add_field(name="📈 تفاصيل التقييمات", value=details, inline=False)
    
    await ctx.send(embed=embed)

@bot.event
async def on_ready():
    print(f'✅ {bot.user} - Arbitration Legend متصل بنجاح!')
    bot.add_view(TicketView())
    bot.add_view(ControlView())
    bot.add_view(CloseOptionView())
    print("✅ جميع أنظمة الوساطة جاهزة")

@bot.command()
async def setup(ctx):
    if ctx.author.guild_permissions.administrator:
        setup_embed = discord.Embed(
            title="⚖️ نظام طلب الوسيط الأسطوري",
            description="اضغط على الزر أدناه لطلب وسيط موثوق لحل نزاعاتك",
            color=discord.Color.from_rgb(138, 43, 226)
        )
        setup_embed.set_footer(text="نحن هنا لمساعدتك 💫")
        await ctx.send(embed=setup_embed, view=TicketView())

bot.run(TOKEN)
