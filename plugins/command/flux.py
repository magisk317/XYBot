#  Copyright (c) 2024. Henry Yang
#
#  This program is licensed under the GNU General Public License v3.0.
import os
import yaml
import re
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

class flux(PluginInterface):
    def __init__(self):
        config_path = "plugins/command/flux.yml"
        with open(config_path, "r", encoding="utf-8") as f:  # 读取设置
            config = yaml.safe_load(f.read())

        self.command_format_menu = config["command_format_menu"]  # 指令格式

        self.model = config["model"]  # 模型名称
        self.size = config["size"]  # 图片尺寸
        self.seed = config["seed"]  # 随机种子
        self.guidance = config["guidance"]  # 指导权重
        self.steps = config["steps"]  # 采样步骤

        main_config_path = "main_config.yml"
        with open(main_config_path, "r", encoding="utf-8") as f:  # 读取设置
            main_config = yaml.safe_load(f.read())

        self.admins = main_config["admins"]  # 获取管理员列表

        sensitive_words_path = "sensitive_words.yml"  # 加载敏感词yml
        with open(sensitive_words_path, "r", encoding="utf-8") as f:  # 读取设置
            sensitive_words_config = yaml.safe_load(f.read())
        self.sensitive_words = sensitive_words_config["sensitive_words"]  # 敏感词列表

        self.db = BotDatabase()

        # 从环境变量中获取API密钥
        self.api_key = os.getenv("FLUX_API_KEY")

    async def run(self, bot: client.Wcf, recv: XYBotWxMsg):
        recv.content = re.split(" |\u2005", recv.content)  # 拆分消息

        user_wxid = recv.sender  # 获取发送者wxid

        error_message = ""

        if self.db.get_points(user_wxid) < 1 and self.db.get_whitelist(
                user_wxid) != 1 and user_wxid not in self.admins:  # 积分不足 不在白名单 不是管理员
            error_message = f"-----XYBot-----\n积分不足,需要1点⚠️"
        elif len(recv.content) < 2:  # 指令格式正确
            error_message = f"-----XYBot-----\n参数错误!❌\n\n{self.command_format_menu}"

        request_message = " ".join(recv.content[1:])  # 用户问题
        if not self.sensitive_word_check(request_message):  # 敏感词检查
            error_message = "-----XYBot-----\n内容包含敏感词!⚠️"

        if not error_message:
            out_message = "-----XYBot-----\n已收到指令，处理中，请勿重复发送指令！👍"  # 发送已收到信息，防止用户反复发送命令
            await self.send_friend_or_group(bot, recv, out_message)

            if self.db.get_whitelist(user_wxid) == 1 or user_wxid in self.admins:  # 如果用户在白名单内/是管理员
                flux_result = await self.flux(request_message)
                if flux_result[0]:
                    out_message = f"-----XYBot-----\n因为你在白名单内，所以没扣除积分！👍\n图片生成成功，等待下载。"
                else:
                    out_message = f"-----XYBot-----\n出现错误！⚠️{flux_result}"
                await self.send_friend_or_group(bot, recv, out_message)

            elif self.db.get_points(user_wxid) >= 1:
                self.db.add_points(user_wxid, -1)  # 减掉积分
                flux_result = await self.flux(request_message)  # 从FLUX-schnell api 获取图片
                if flux_result[0]:
                    out_message = f"-----XYBot-----\n已扣除1点积分，还剩{self.db.get_points(user_wxid)}点积分👍\n图片生成成功，等待下载。"
                else:
                    self.db.add_points(user_wxid, 1)  # 补回积分
                    out_message = f"-----XYBot-----\n出现错误，已补回积分！⚠️{flux_result}"
                await self.send_friend_or_group(bot, recv, out_message)
        else:
            await self.send_friend_or_group(bot, recv, error_message)

    async def flux(self, request_message):
        rsp = ImageSynthesis.call(model=self.model,
                                  prompt=request_message,
                                  size=self.size,
                                  seed=self.seed,
                                  guidance=self.guidance,
                                  steps=self.steps,
                                  api_key=self.api_key)  # 添加API密钥
        if rsp.status_code == HTTPStatus.OK:
            for result in rsp.output.results:
                file_name = PurePosixPath(unquote(urlparse(result.url).path)).parts[-1]
                with open('./%s' % file_name, 'wb+') as f:
                    f.write(requests.get(result.url).content)
            return True, "图片生成成功，已保存为%s" % file_name
        else:
            return False, f"Failed, status_code: {rsp.status_code}, code: {rsp.code}, message: {rsp.message}"

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