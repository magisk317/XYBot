FROM henryxiaoyang/wechat-box-3.9.10.27:latest

# clear /payloads
RUN sudo rm -rf /payloads

COPY Docker/root/ /

# 设置工作目录
WORKDIR /home/apps

# init with GUI
RUN bash -c 'nohup /entrypoint.sh 2>&1 &' && sleep 5 && /payloads.sh \
    && sudo cp -r /wechat-etc/* /etc/ \
    && sudo rm /tmp/.X0-lock
#settings

ENTRYPOINT ["/wx-entrypoint.sh"]