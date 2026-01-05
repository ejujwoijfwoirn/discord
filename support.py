import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import asyncio
import os
import io

# =========================================================
# ⚙️ إعدادات البوت
# =========================================================

TOKEN = os.getenv('support_bot_token')
SUPPORT_ROLE_ID = 1355125616407609425  
LOG_CHANNEL_ID = 1456728865366872209   

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# =========================================================
# 📝 نموذج سبب التذكرة (Modal)
# =========================================================

class TicketModal(Modal):
    def __init__(self):
        super().__init__(title="📝 فتح تذكرة دعم فني")

    reason = TextInput(
        label="ما هو سبب فتح التذكرة؟",
        style=discord.TextStyle.paragraph,
        placeholder="اشرح مشكلتك باختصار هنا...",
        required=True,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        # التحقق مرة أخرى لزيادة الأمان (في حال ضغط الزر مرتين بسرعة جداً)
        ticket_name = f"ticket-{interaction.user.name.lower()}"
        existing_channel = discord.utils.get(interaction.guild.text_channels, name=ticket_name)
        if existing_channel:
             await interaction.response.send_message(f"❌ لديك تذكرة مفتوحة بالفعل: {existing_channel.mention}", ephemeral=True)
             return

        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="🎫 Support Tickets")
        
        if not category:
            category = await guild.create_category("🎫 Support Tickets")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        support_role = guild.get_role(SUPPORT_ROLE_ID)
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        # تم التعديل هنا لإستخدام lower()
        channel = await guild.create_text_channel(name=ticket_name, category=category, overwrites=overwrites)

        embed = discord.Embed(
            title="🎫 تذكرة دعم فني جديدة",
            description=f"مرحباً {interaction.user.mention}\n\nتم استلام طلبك بنجاح.\nيرجى انتظار أحد أفراد الدعم الفني.\n\n**📄 سبب التذكرة:**\n```{self.reason.value}```",
            color=discord.Color.blue()
        )
        embed.set_footer(text="نظام الدعم الفني الذكي")
        
        await channel.send(f"{interaction.user.mention} | <@&{SUPPORT_ROLE_ID}>", embed=embed, view=TicketControls())
        await interaction.followup.send(f"✅ تم إنشاء تذكرتك بنجاح: {channel.mention}", ephemeral=True)

# =========================================================
# 🎮 لوحة التحكم داخل التذكرة (Controls)
# =========================================================

class TicketControls(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 إغلاق التذكرة", style=discord.ButtonStyle.red, custom_id="close_ticket", emoji="🔒")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⚠️ **هل أنت متأكد من إغلاق التذكرة؟**", view=ConfirmClose(), ephemeral=True)

    @discord.ui.button(label="🙋‍♂️ استلام التذكرة", style=discord.ButtonStyle.green, custom_id="claim_ticket", emoji="🙋‍♂️")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id == SUPPORT_ROLE_ID for role in interaction.user.roles) and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ هذا الزر للدعم الفني فقط.", ephemeral=True)

        embed = discord.Embed(description=f"✅ **تم استلام التذكرة بواسطة:** {interaction.user.mention}", color=discord.Color.green())
        await interaction.channel.send(embed=embed)
        
        button.disabled = True
        button.label = f"مستلمة: {interaction.user.display_name}"
        button.style = discord.ButtonStyle.secondary
        await interaction.message.edit(view=self)
        await interaction.response.defer()

class ConfirmClose(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="نعم، اغلق واحفظ السجل", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        channel = interaction.channel
        
        messages = [message async for message in channel.history(limit=500, oldest_first=True)]
        transcript_text = f"Ticket Transcript for {channel.name}\nClosed by: {interaction.user.name}\n\n"
        
        for msg in messages:
            transcript_text += f"[{msg.created_at.strftime('%Y-%m-%d %H:%M')}] {msg.author.name}: {msg.content}\n"

        transcript_file = discord.File(io.BytesIO(transcript_text.encode("utf-8")), filename=f"{channel.name}.txt")

        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(title="🔒 تذكرة مغلقة", description=f"تم إغلاق التذكرة: `{channel.name}`\nبواسطة: {interaction.user.mention}", color=discord.Color.red())
            await log_channel.send(embed=log_embed, file=transcript_file)
        
        await channel.send("✅ **جاري إغلاق التذكرة وحفظ السجل...**")
        await asyncio.sleep(3)
        await channel.delete()

# =========================================================
# 🖥️ زر فتح التذكرة الرئيسي (Launcher)
# =========================================================

class TicketLauncher(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📩 فتح تذكرة دعم", style=discord.ButtonStyle.blurple, custom_id="create_ticket_btn", emoji="📩")
    async def launch(self, interaction: discord.Interaction, button: discord.ui.Button):
        # --- بداية التعديل: التحقق من وجود تذكرة ---
        ticket_name = f"ticket-{interaction.user.name.lower()}"
        existing_channel = discord.utils.get(interaction.guild.text_channels, name=ticket_name)
        
        if existing_channel:
             await interaction.response.send_message(f"❌ **لديك تذكرة مفتوحة بالفعل:** {existing_channel.mention}", ephemeral=True)
             return
        # --- نهاية التعديل ---

        await interaction.response.send_modal(TicketModal())

# =========================================================
# 🚀 تشغيل البوت
# =========================================================

@bot.event
async def on_ready():
    print(f'✅ {bot.user} is Ready for Support!')
    bot.add_view(TicketLauncher())
    bot.add_view(TicketControls())

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_support(ctx):
    embed = discord.Embed(
        title="🛠️ مركز الدعم الفني",
        description="إذا واجهتك مشكلة أو لديك استفسار، لا تتردد في فتح تذكرة.\n\nاضغط على الزر أدناه للتواصل معنا 👇",
        color=discord.Color.from_rgb(44, 47, 51)
    )
    embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
    embed.set_image(url="https://media.discordapp.net/attachments/10000/10000/support_banner.png") 
    
    await ctx.send(embed=embed, view=TicketLauncher())

bot.run(TOKEN)