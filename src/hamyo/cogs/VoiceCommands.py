import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from DataManager import DataManager
import pytz
from typing import List

class VoiceCommands(commands.GroupCog, group_name="보이스"):
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = DataManager()
        self.tz = pytz.timezone('Asia/Seoul')
        
    async def cog_load(self):
        print(f"✅ {self.__class__.__name__} loaded successfully!")

    async def log(self, message):
        try:
            logger = self.bot.get_cog('Logger')
            if logger:
                await logger.log(message)
        except Exception as e:
            print(f"❌ {self.__class__.__name__} 로그 전송 중 오류 발생: {e}")
            
    def calculate_points(self, seconds: int) -> int:
        """음성 채널 사용 시간을 점수로 변환 (1분당 2점, 초 단위 내림)"""
        minutes = seconds // 60
        return minutes * 2

    def format_duration(self, total_seconds: int) -> str:
        days, remainder = divmod(total_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{days}일 {hours}시간 {minutes}분 {seconds}초 ({self.calculate_points(total_seconds)}점)"
    
    async def get_expanded_tracked_channels(self) -> List[int]:
        tracked_ids = await self.data_manager.get_tracked_channels("voice")
        expanded_ids = set()

        for cid in tracked_ids:
            ch = self.bot.get_channel(cid)
            if isinstance(ch, discord.VoiceChannel):
                expanded_ids.add(ch.id)
            elif isinstance(ch, discord.CategoryChannel):
                for vc in ch.voice_channels:
                    expanded_ids.add(vc.id)
            else:
                expanded_ids.add(cid)

        return list(expanded_ids)

    @app_commands.command(name="확인", description="개인 누적 시간을 확인합니다.")
    @app_commands.describe(
        user="확인할 사용자를 선택합니다. (미입력 시 현재 사용자)",
        period="확인할 기간을 선택합니다. (일간/주간/월간/누적, 미입력 시 오늘)",
        base_date="기준일을 지정합니다. (YYYY-MM-DD 형식, 미입력 시 현재 날짜)"
    )
    @app_commands.choices(period=[
        app_commands.Choice(name="일간", value="일간"),
        app_commands.Choice(name="주간", value="주간"),
        app_commands.Choice(name="월간", value="월간"),
        app_commands.Choice(name="누적", value="누적")
    ])
    async def check_time(self, interaction: discord.Interaction, 
                        user: discord.Member = None, 
                        period: str = "일간",
                        base_date: str = None):
        try:
            user = user or interaction.user

            if base_date:
                try:
                    base_datetime = datetime.strptime(base_date, "%Y-%m-%d")
                    base_datetime = base_datetime.replace(tzinfo=self.tz)
                except ValueError:
                    await interaction.response.send_message("날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식으로 입력해주세요.", ephemeral=True)
                    return
            else:
                base_datetime = datetime.now(self.tz)

            tracked_channels = await self.get_expanded_tracked_channels()
            times, start_date, end_date = await self.data_manager.get_user_times(user.id, period, base_datetime, tracked_channels)

            if not times:
                await interaction.response.send_message(f"해당 기간에 기록된 음성 채팅 기록이 없습니다.", ephemeral=True)
                return

            await interaction.response.defer()

            total_seconds = sum(times.values())
            start_str = start_date.strftime("%Y-%m-%d") if start_date else "-"
            end_str = (end_date - timedelta(days=1)).strftime("%Y-%m-%d") if end_date else "-"

            category_details = {}

            for channel_id, seconds in times.items():
                channel = self.bot.get_channel(channel_id)

                if channel:
                    category = channel.category
                    category_id = category.id if category else None
                    category_name = category.name if category else "기타"
                    category_position = category.position if category else float('inf')
                    channel_name = channel.name
                    channel_position = channel.position
                else:
                    # 삭제된 채널 처리
                    original_category_id = await self.data_manager.get_deleted_channel_category(channel_id)
                    category = self.bot.get_channel(original_category_id) if original_category_id else None
                    category_id = original_category_id
                    category_name = category.name if category else "삭제된 카테고리"
                    category_position = category.position if category else float('inf')
                    channel_name = "삭제된 채널"
                    channel_position = float('inf')

                if category_id not in category_details:
                    category_details[category_id] = {
                        "name": category_name,
                        "position": category_position,
                        "channels": [],
                        "total": 0,
                        "deleted_total": 0
                    }

                if channel_name == "삭제된 채널":
                    category_details[category_id]["deleted_total"] += seconds
                else:
                    category_details[category_id]["channels"].append((channel_name, seconds, channel_position))

                category_details[category_id]["total"] += seconds

            sorted_categories = sorted(category_details.items(), key=lambda x: (x[1]["position"], x[1]["name"]))

            embed = discord.Embed(
                title="음성 기록 확인",
                description=f"{user.mention}님의 {period}({start_str} ~ {end_str}) 기록입니다.",
                colour=discord.Colour.from_rgb(253, 237, 134)
            )

            for _, cat in sorted_categories:
                cat_total = cat["total"]
                cat_title = f"**{cat['name']}**"
                field_value = ""

                for cname, sec, pos in sorted(cat["channels"], key=lambda x: x[2]):
                    field_value += f"{cname}: {self.format_duration(sec)}\n"

                if cat.get("deleted_total", 0) > 0:
                    field_value += f"삭제된 채널: {self.format_duration(cat['deleted_total'])}\n"

                field_value += f"\n**{cat['name']} 종합 시간**: {self.format_duration(cat_total)}"
                embed.add_field(name=cat_title, value=field_value, inline=False)

            embed.add_field(
                name="───────── ౨ৎ ─────────",
                value=f"**종합**: {self.format_duration(total_seconds)}",
                inline=False
            )

            await interaction.followup.send(embed=embed)
            await self.log(f"{interaction.user}({interaction.user.id})님께서 {user}({user.id})님의 {period} 기록을 조회했습니다.")

        except Exception as e:
            await self.log(f"음성 채팅 기록 확인 중 오류 발생: {e}")
            await interaction.response.send_message("기록 조회 중 오류가 발생했습니다.", ephemeral=True)
        
        
    @app_commands.command(name="순위", description="음성 채널 사용 시간 순위를 확인합니다.")
    @app_commands.describe(
        period="확인할 기간을 선택합니다. (일간/주간/월간/누적, 기본값: 일간)",
        page="확인할 페이지를 선택합니다. (기본값: 1)",
        base_date="기준일을 지정합니다. (YYYY-MM-DD 형식, 미입력시 현재 날짜)"
    )
    @app_commands.choices(period=[
        app_commands.Choice(name="일간", value="일간"),
        app_commands.Choice(name="주간", value="주간"),
        app_commands.Choice(name="월간", value="월간"),
        app_commands.Choice(name="누적", value="누적")
    ])
    async def check_ranking(self, interaction: discord.Interaction, 
                        period: str = "일간", 
                        page: int = 1,
                        base_date: str = None):
        
        try:
            # 기준일 파싱
            if base_date:
                try:
                    base_datetime = datetime.strptime(base_date, "%Y-%m-%d")
                    base_datetime = base_datetime.replace(tzinfo=self.tz)
                except ValueError:
                    await interaction.response.send_message("날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식으로 입력해주세요.", ephemeral=True)
                    return
            else:
                base_datetime = datetime.now(self.tz)
            
            # 페이지 유효성 검사
            if page < 1:
                await interaction.response.send_message("페이지 번호는 1 이상이어야 합니다.", ephemeral=True)
                return
            
            await interaction.response.defer() # 시간이 오래 걸릴 것을 대비해 defer 처리
            
            # 총 시간 데이터 조회
            tracked_channels = await self.get_expanded_tracked_channels()
            all_data, start_date, end_date = await self.data_manager.get_all_users_times(period, base_datetime, tracked_channels)

            user_totals = [(uid, sum(times.values())) for uid, times in all_data.items()]
            ranked = sorted(user_totals, key=lambda x: x[1], reverse=True)

            if not ranked:
                return await interaction.followup.send("해당 기간에 해당하는 기록이 없습니다.", ephemeral=True)

            items_per_page = 10
            start_index = (page - 1) * items_per_page
            end_index = start_index + items_per_page
            total_pages = (len(ranked) + items_per_page - 1) // items_per_page

            if page > total_pages:
                return await interaction.followup.send(f"요청한 페이지는 존재하지 않습니다. (1-{total_pages})", ephemeral=True)

            start_str = start_date.strftime("%Y-%m-%d") if start_date else "-"
            end_str = (end_date - timedelta(days=1)).strftime("%Y-%m-%d") if end_date else "-"
            
            # 임베드 생성
            embed = discord.Embed(
                title=f"음성 채널 순위",
                description=f"{period}({start_str} ~ {end_str}) 기준의 순위를 조회합니다.",
                colour=discord.Colour.from_rgb(253, 237, 134)
            )
            embed.set_footer(text=f"페이지: {page}/{total_pages} • 반영까지 최대 1분이 소요될 수 있습니다.")
            embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)

            # 현재 페이지의 순위 표시
            for i, (uid, seconds) in enumerate(ranked[start_index:end_index], start=start_index + 1):
                member = interaction.guild.get_member(uid)
                name = member.display_name if member else f"알 수 없음 ({uid})"
                embed.add_field(
                    name=f"{i}위 - {name}",
                    value=self.format_duration(seconds),
                    inline=False
                )
                
            # 호출자의 순위가 현재 페이지에 포함되어 있지 않은 경우 하단에 추가 표시
            caller_id = interaction.user.id
            if caller_id not in [uid for uid, _ in ranked[start_index:end_index]]:
                for i, (uid, seconds) in enumerate(ranked, start=1):
                    if uid == caller_id:
                        member = interaction.guild.get_member(uid)
                        name = member.display_name if member else f"알 수 없음 ({uid})"
                        embed.add_field(
                            name="───────── ౨ৎ ─────────",
                            value=f"{interaction.user.mention}님의 순위 - {i}위({self.format_duration(seconds)})",
                            inline=False
                        )
                        break


            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            await self.log(f"순위 확인 중 오류 발생: {e}")
            await interaction.response.send_message("순위 조회 중 오류가 발생했습니다.", ephemeral=True)
            

    @app_commands.command(name="역할순위", description="특정 역할 내에서 음성 채널 사용 시간 순위를 확인합니다.")
    @app_commands.describe(
        role="순위를 조회할 디스코드 역할",
        period="확인할 기간을 선택합니다. (일간/주간/월간/누적, 기본값: 일간)",
        page="확인할 페이지를 선택합니다. (기본값: 1)",
        base_date="기준일을 지정합니다. (YYYY-MM-DD 형식, 미입력시 현재 날짜)"
    )
    @app_commands.choices(period=[
        app_commands.Choice(name="일간", value="일간"),
        app_commands.Choice(name="주간", value="주간"),
        app_commands.Choice(name="월간", value="월간"),
        app_commands.Choice(name="누적", value="누적")
    ])
    async def check_role_ranking(self, interaction: discord.Interaction,
                                role: discord.Role,
                                period: str = "일간",
                                page: int = 1,
                                base_date: str = None):
            try:
                # 기준일 파싱
                if base_date:
                    try:
                        base_datetime = datetime.strptime(base_date, "%Y-%m-%d")
                        base_datetime = base_datetime.replace(tzinfo=self.tz)
                    except ValueError:
                        await interaction.response.send_message("날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식으로 입력해주세요.", ephemeral=True)
                        return
                else:
                    base_datetime = datetime.now(self.tz)

                if page < 1:
                    await interaction.response.send_message("페이지 번호는 1 이상이어야 합니다.")
                    return
                
                await interaction.response.defer()  # 시간이 오래 걸릴 것을 대비해 defer 처리
                
                # 총 시간 데이터 조회
                tracked_channels = await self.get_expanded_tracked_channels()
                all_data, start_date, end_date = await self.data_manager.get_all_users_times(period, base_datetime, tracked_channels)

                role_member_ids = {member.id for member in role.members}
                filtered = [(uid, sum(times.values())) for uid, times in all_data.items() if uid in role_member_ids]
                ranked = sorted(filtered, key=lambda x: x[1], reverse=True)

                if not ranked:
                    return await interaction.followup.send(f"{role.name} 역할의 기록이 없습니다.", ephemeral=True)

                items_per_page = 10
                start_index = (page - 1) * items_per_page
                end_index = start_index + items_per_page
                total_pages = (len(ranked) + items_per_page - 1) // items_per_page

                if page > total_pages:
                    return await interaction.followup.send(f"요청한 페이지는 존재하지 않습니다. (1-{total_pages})", ephemeral=True)

                start_str = start_date.strftime("%Y-%m-%d") if start_date else "-"
                end_str = (end_date - timedelta(days=1)).strftime("%Y-%m-%d") if end_date else "-"
                    
                # 임베드 생성
                embed = discord.Embed(
                    title=f"{role.name} 역할 음성 사용 시간 순위",
                    description=f"{period}({start_str} ~ {end_str}) 기준의 순위를 조회합니다.",
                    colour=role.colour
                )
                embed.set_footer(text=f"페이지: {page}/{total_pages} • 반영까지 최대 1분이 소요될 수 있습니다.")
                embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)

                # 현재 페이지의 순위 표시
                for i, (uid, seconds) in enumerate(ranked[start_index:end_index], start=start_index + 1):
                    member = interaction.guild.get_member(uid)
                    name = member.display_name if member else f"알 수 없음 ({uid})"
                    embed.add_field(
                        name=f"{i}위 - {name}",
                        value=self.format_duration(seconds),
                        inline=False
                    )
                    
                # 호출자의 순위가 현재 페이지에 포함되어 있지 않은 경우 하단에 추가 표시
                caller_id = interaction.user.id
                if caller_id not in [uid for uid, _ in ranked[start_index:end_index]]:
                    for i, (uid, seconds) in enumerate(ranked, start=1):
                        if uid == caller_id:
                            member = interaction.guild.get_member(uid)
                            name = member.display_name if member else f"알 수 없음 ({uid})"
                            embed.add_field(
                                name="───────── ౨ৎ ─────────",
                                value=f"{interaction.user.mention}님의 순위 - {i}위({self.format_duration(seconds)})",
                                inline=False
                            )
                            break

                await interaction.followup.send(embed=embed)

            except Exception as e:
                await self.log(f"순위 확인 중 오류 발생: {e}")
                await interaction.response.send_message("역할 순위 조회 중 오류가 발생했습니다.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceCommands(bot))