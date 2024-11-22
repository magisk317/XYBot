#  Copyright (c) 2024. Henry Yang
#
#  This program is licensed under the GNU General Public License v3.0.
#
#  This program是基于GNU通用公共许可证v3.0授权的。

import base64
import os
import re
import time
import yaml
import requests
from loguru import logger
from wcferry import client
from aiohttp import ClientSession
from utils.database import BotDatabase
from utils.plugin_interface import PluginInterface
from wcferry_helper import XYBotWxMsg
from dashscope import ImageSynthesis
from http import HTTPStatus
from urllib.parse import urlparse, unquote
from pathlib import PurePosixPath
import asyncio

class flux(PluginInterface):
    def __init__(self):
        config_path = "plugins/command/flux.yml"
        with open(config_path, "r", encoding="utf-8") as f:  # 读取设置
            config = yaml.safe_load(f.read())

        self.price = config["price"]  # 每次使用的积分

        self.model = config["model"]  # 模型名称
        self.size = config["size"]  # 图片尺寸
        self.seed = config["seed"]  # 随机种子
        self.guidance = config["guidance"]  # 指导权重

        self.command_format_menu = config["command_format_menu"]  # 帮助菜单

        main_config_path = "main_config.yml"
        with open(main_config_path, "r", encoding="utf-8") as f:  # 读取设置
            main_config = yaml.safe_load(f.read())

        self.admins = main_config["admins"]  # 管理员列表

        sensitive_words_path = "sensitive_words.yml"  # 加载敏感词yml
        with open(sensitive_words_path, "r", encoding="utf-8") as f:  # 读取设置
            sensitive_words_config = yaml.safe_load(f.read())
        self.sensitive_words = sensitive_words_config["sensitive_words"]  # 敏感词列表

        self.db = BotDatabase()

        # 从环境变量中获取API密钥和基础URL
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        self.api_base = os.getenv("FLUX_API_BASE")
        # 设置dashscope客户端的API密钥和基础URL
        ImageSynthesis.api_key = self.api_key
        ImageSynthesis.api_base = self.api_base


    async def run(self, bot: client.Wcf, recv: XYBotWxMsg):
        recv.content = re.split(" |\u2005", recv.content)  # 拆分消息

        user_wxid = recv.sender  # 获取发送者wxid
        user_request_prompt = " ".join(recv.content[1:])  # 用户请求提示

        error = ""
        if len(recv.content) < 2:  # 指令格式正确
            error = f"-----XYBot-----\n参数错误！🙅\n\n{self.command_format_menu}"
        # 检查积分是否足够，管理员与白名单不需要检查
        elif user_wxid not in self.admins and self.db.get_whitelist(user_wxid) == 0 and self.db.get_points(
                user_wxid) < self.price:
            error = f"-----XYBot-----\n积分不足！😭需要 {self.price} 点积分！"
        elif not self.sensitive_word_check(user_request_prompt):  # 敏感词检查
            error = "-----XYBot-----\n内容包含敏感词!⚠️"
        elif not user_request_prompt.strip():
            error = f"-----XYBot-----\n请输入描述！🤔\n\n{self.command_format_menu}"

        if error:  # 如果没满足生成图片的条件，向用户发送为什么
            await self.send_friend_or_group(bot, recv, error)
            return

        await self.send_friend_or_group(bot, recv, "-----XYBot-----\n正在生成图片，请稍等...🤔")

        image_path = await self.generate_image(user_request_prompt)

        if isinstance(image_path, Exception):  # 如果出现错误，向用户发送错误信息
            await self.send_friend_or_group(bot, recv, f"-----XYBot-----\n出现错误，未扣除积分！⚠️\n{image_path}")
            return

        if user_wxid not in self.admins and self.db.get_whitelist(user_wxid) == 0:  # 如果用户不是管理员或者白名单，扣积分
            self.db.add_points(user_wxid, -self.price)
            await self.send_friend_or_group(bot, recv, f"-----XYBot-----\n🎉图片生成完毕，已扣除 {self.price} 点积分！🙏")

        bot.send_image(image_path, recv.roomid)
        logger.info(f'[发送图片]{image_path}| [发送到] {recv.roomid}')

    async def generate_image(self, prompt):  # 返回生成的图片的绝对路径，报错的话返回错误
        loop = asyncio.get_event_loop()
        rsp = await loop.run_in_executor(None, lambda: ImageSynthesis.call(
            model=self.model,
            prompt=prompt,
            size=self.size,
            seed=self.seed,
            guidance=self.guidance
        ))
        if rsp.status_code == HTTPStatus.OK:
            logger.debug(f"Response JSON: {rsp.output}")
            logger.debug(f"Usage: {rsp.usage}")

            for result in rsp.output.results:
                file_name = PurePosixPath(unquote(urlparse(result.url).path)).parts[-1]
                save_path = os.path.abspath(f"resources/cache/{file_name}")
                with open(save_path, "wb") as f:
                    f.write(requests.get(result.url).content)
                return save_path
        else:
            logger.error(f"Failed, status_code: {rsp.status_code}, code: {rsp.code}, message: {rsp.message}")
            return Exception(f"HTTP Error: {rsp.status_code}, {rsp.code}, {rsp.message}")

    async def send_friend_or_group(self, bot: client.Wcf, recv: XYBotWxMsg, out_message: str):
        if recv.from_group():  # 判断是群还是私聊
            out_message = f"@{self.db.get_nickname(recv.sender)}\n{out_message}"
            logger.info(f'[发送@信息]{out_message}| [发送到] {recv.roomid}')
            bot.send_text(out_message, recv.roomid, recv.sender)  # 发送@信息
        else:
            logger.info(f'[发送信息]{out_message}| [发送到] {recv.roomid}')
            bot.send_text(out_message, recv.roomid)  # 发送信息

    def sensitive_word_check(self, message):  # 检查敏感词
        for word in self.sensitive_words:
            if word in message:
                return False
        return True
