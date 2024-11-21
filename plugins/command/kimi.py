#  Copyright (c) 2024. Henry Yang
#
#  This program is licensed under the GNU General Public License v3.0.

import requests
import re
import yaml
from loguru import logger
from utils.database import BotDatabase
from utils.plugin_interface import PluginInterface
from wcferry import client
from wcferry_helper import XYBotWxMsg

class kimi(PluginInterface):
    def __init__(self):
        config_path = "plugins/command/kimi.yml"
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f.read())

        self.command_format_menu = config["command_format_menu"]
        self.kimi_version = config["kimi_version"]
        self.kimi_point_price = config["kimi_point_price"]
        self.kimi_max_token = config["kimi_max_token"]
        self.kimi_temperature = config["kimi_temperature"]

        main_config_path = "main_config.yml"
        with open(main_config_path, "r", encoding="utf-8") as f:
            main_config = yaml.safe_load(f.read())

        self.admins = main_config["admins"]

        # 从docker compose中获取api链接和密钥
        self.kimi_api_base = os.getenv("KIMI_API_BASE")  # Kimi api 链接
        self.kimi_api_key = os.getenv("KIMI_API_KEY")  # Kimi api 密钥

        sensitive_words_path = "sensitive_words.yml"
        with open(sensitive_words_path, "r", encoding="utf-8") as f:
            sensitive_words_config = yaml.safe_load(f.read())
        self.sensitive_words = sensitive_words_config["sensitive_words"]

        self.db = BotDatabase()

    async def run(self, bot: client.Wcf, recv: XYBotWxMsg):
        recv.content = re.split(" |\u2005", recv.content)
        user_wxid = recv.sender
        error_message = ""

        if self.db.get_points(user_wxid) < self.kimi_point_price and self.db.get_whitelist(user_wxid) != 1 and user_wxid not in self.admins:
            error_message = f"-----XYBot-----\n积分不足,需要{self.kimi_point_price}点⚠️"
        elif len(recv.content) < 2:
            error_message = f"-----XYBot-----\n参数错误!❌\n\n{self.command_format_menu}"

        kimi_request_message = " ".join(recv.content[1:])
        if not self.sensitive_word_check(kimi_request_message):
            error_message = "-----XYBot-----\n内容包含敏感词!⚠️"

        if not error_message:
            out_message = "-----XYBot-----\n已收到指令，处理中，请勿重复发送指令！👍"
            await self.send_friend_or_group(bot, recv, out_message)

            if self.db.get_whitelist(user_wxid) == 1 or user_wxid in self.admins:
                kimi_answer = await self.kimi(kimi_request_message)
                if kimi_answer[0]:
                    out_message = f"-----XYBot-----\n因为你在白名单内，所以没扣除积分！👍\nKimi回答：\n{kimi_answer[1]}\n\n⚙️Kimi版本：{self.kimi_version}"
                else:
                    out_message = f"-----XYBot-----\n出现错误！⚠️{kimi_answer[1]}"
                await self.send_friend_or_group(bot, recv, out_message)

            elif self.db.get_points(user_wxid) >= self.kimi_point_price:
                self.db.add_points(user_wxid, self.kimi_point_price * -1)
                kimi_answer = await self.kimi(kimi_request_message)
                if kimi_answer[0]:
                    out_message = f"-----XYBot-----\n已扣除{self.kimi_point_price}点积分，还剩{self.db.get_points(user_wxid)}点积分👍\nKimi回答：\n{kimi_answer[1]}\n\n⚙️Kimi版本：{self.kimi_version}"
                else:
                    self.db.add_points(user_wxid, self.kimi_point_price)
                    out_message = f"-----XYBot-----\n出现错误，已补回积分！⚠️{kimi_answer[1]}"
                await self.send_friend_or_group(bot, recv, out_message)
        else:
            await self.send_friend_or_group(bot, recv, error_message)

    async def kimi(self, kimi_request_message):
        headers = {
            "Authorization": f"Bearer {self.kimi_api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "prompt": kimi_request_message,
            "max_tokens": self.kimi_max_token,
            "temperature": self.kimi_temperature
        }
        try:
            response = requests.post(self.kimi_api_base, headers=headers, json=data)
            response.raise_for_status()
            kimi_completion = response.json()
            return True, kimi_completion.get("choices", [{}])[0].get("text", "")
        except Exception as error:
            return False, str(error)

    def sensitive_word_check(self, message):
        for word in self.sensitive_words:
            if word in message:
                return False
        return True

    async def send_friend_or_group(self, bot: client.Wcf, recv: XYBotWxMsg, out_message="null"):
        if recv.from_group():
            out_message = f"@{self.db.get_nickname(recv.sender)}\n{out_message}"
            logger.info(f'[发送@信息]{out_message}| [发送到] {recv.roomid}')
            bot.send_text(out_message, recv.roomid, recv.sender)
        else:
            logger.info(f'[发送信息]{out_message}| [发送到] {recv.roomid}')
            bot.send_text(out_message, recv.roomid)
