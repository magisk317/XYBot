#  Copyright (c) 2024. Henry Yang
#
#  This program is licensed under the GNU General Public License v3.0.

import re
import yaml
from loguru import logger
from wcferry import client
from aiohttp import ClientSession
from utils.database import BotDatabase
from utils.plugin_interface import PluginInterface
from wcferry_helper import XYBotWxMsg

class big_model(PluginInterface):
    def __init__(self):
        config_path = "plugins/command/big_model.yml"
        with open(config_path, "r", encoding="utf-8") as f:  # 读取设置
            config = yaml.safe_load(f.read())

        self.command_format_menu = config["command_format_menu"]  # 指令格式

        self.model_version = config["model_version"]  # 大模型版本
        self.point_price = config["point_price"]  # 使用价格（单次）
        self.max_token = config["max_token"]  # 最大token
        self.temperature = config["temperature"]  # 温度

        main_config_path = "main_config.yml"
        with open(main_config_path, "r", encoding="utf-8") as f:  # 读取设置
            main_config = yaml.safe_load(f.read())

        self.admins = main_config["admins"]  # 获取管理员列表

        self.api_base = main_config["bigModelApi"]  # 智谱大模型api链接
        self.api_key = main_config["bigModelApiKey"]  # 智谱大模型api密钥

        sensitive_words_path = "sensitive_words.yml"  # 加载敏感词yml
        with open(sensitive_words_path, "r", encoding="utf-8") as f:  # 读取设置
            sensitive_words_config = yaml.safe_load(f.read())
        self.sensitive_words = sensitive_words_config["sensitive_words"]  # 敏感词列表

        self.db = BotDatabase()

    async def run(self, bot: client.Wcf, recv: XYBotWxMsg):
        recv.content = re.split(" |\u2005", recv.content)  # 拆分消息

        user_wxid = recv.sender  # 获取发送者wxid

        error_message = ""

        if self.db.get_points(user_wxid) < self.point_price and self.db.get_whitelist(
                user_wxid) != 1 and user_wxid not in self.admins:  # 积分不足 不在白名单 不是管理员
            error_message = f"-----XYBot-----\n积分不足,需要{self.point_price}点⚠️"
        elif len(recv.content) < 2:  # 指令格式正确
            error_message = f"-----XYBot-----\n参数错误!❌\n\n{self.command_format_menu}"

        request_message = " ".join(recv.content[1:])  # 用户问题
        if not self.sensitive_word_check(request_message):  # 敏感词检查
            error_message = "-----XYBot-----\n内容包含敏感词!⚠️"

        if not error_message:
            out_message = "-----XYBot-----\n已收到指令，处理中，请勿重复发送指令！👍"  # 发送已收到信息，防止用户反复发送命令
            await self.send_friend_or_group(bot, recv, out_message)

            if self.db.get_whitelist(user_wxid) == 1 or user_wxid in self.admins:  # 如果用户在白名单内/是管理员
                big_model_answer = await self.big_model(request_message)
                if big_model_answer[0]:
                    out_message = f"-----XYBot-----\n因为你在白名单内，所以没扣除积分！👍\n智谱大模型回答：\n{big_model_answer[1]}\n\n⚙️大模型版本：{self.model_version}"
                else:
                    out_message = f"-----XYBot-----\n出现错误！⚠️{big_model_answer}"
                await self.send_friend_or_group(bot, recv, out_message)

            elif self.db.get_points(user_wxid) >= self.point_price:
                self.db.add_points(user_wxid, self.point_price * -1)  # 减掉积分
                big_model_answer = await self.big_model(request_message)  # 从智谱大模型 api 获取回答
                if big_model_answer[0]:
                    out_message = f"-----XYBot-----\n已扣除{self.point_price}点积分，还剩{self.db.get_points(user_wxid)}点积分👍\n智谱大模型回答：\n{big_model_answer[1]}\n\n⚙️大模型版本：{self.model_version}"  # 创建信息
                else:
                    self.db.add_points(user_wxid, self.point_price)  # 补回积分
                    out_message = f"-----XYBot-----\n出现错误，已补回积分！⚠️{big_model_answer}"
                await self.send_friend_or_group(bot, recv, out_message)
        else:
            await self.send_friend_or_group(bot, recv, error_message)

    async def big_model(self, request_message):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        data = {
            "messages": [
                {"role": "user", "content": request_message}
            ],
            "model": self.model_version,
            "temperature": self.temperature,
            "max_tokens": self.max_token
        }
        async with ClientSession() as session:
            try:
                async with session.post(self.api_base, headers=headers, json=data) as response:
                    result = await response.json()
                    if response.status == 200:
                        return True, result['choices'][0]['message']['content']
                    else:
                        return False, f"HTTP Error: {response.status}, {result.get('error', {}).get('message', 'Unknown error')}"
            except Exception as e:
                return False, str(e)

    def sensitive_word_check(self, message):  # 检查敏感词
        for word in self.sensitive_words:
            if word in message:
                return False
        return True

    async def send_friend_or_group(self, bot: client.Wcf, recv: XYBotWxMsg, out_message="null"):
        if recv.from_group():  # 判断是群还是私聊
            out_message = f"@{self.db.get_nickname(recv.sender)}\n{out_message}"
            logger.info(f'[发送@信息]{out_message}| [发送到] {recv.roomid}')
            bot.send_text(out_message, recv.roomid, recv.sender)  # 发送@信息

        else:
            logger.info(f'[发送信息]{out_message}| [发送到] {recv.roomid}')
            bot.send_text(out_message, recv.roomid)  # 发送