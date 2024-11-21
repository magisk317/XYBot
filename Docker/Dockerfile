FROM henryxiaoyang/wechat-box-3.9.10.27:latest

COPY Docker/root/ /

# 设置工作目录
WORKDIR /home/app

# 克隆 XYBot 仓库
RUN git clone https://github.com/magisk317/XYBot.git

# 切换到 XYBot 目录
WORKDIR /home/app/XYBot

# 升级 pip 并安装依赖
RUN pip3 install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple \
    && pip3 install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# init with GUI
RUN bash -c 'nohup /wx-entrypoint.sh 2>&1 &' && sleep 5 \
    && sudo cp -r /wechat-etc/* /etc/

ENTRYPOINT ["/wx-entrypoint.sh"]
