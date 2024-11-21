FROM henryxiaoyang/wechat-box-3.9.10.27:latest

# clear /payloads
RUN sudo rm -rf /payloads

COPY Docker/root/ /

# 设置工作目录
WORKDIR /home/app

# init with GUI
RUN bash -c 'nohup /wx-entrypoint.sh 2>&1 &' && sleep 5 && /payloads.sh

#settings

ENTRYPOINT ["/wx-entrypoint.sh"]
